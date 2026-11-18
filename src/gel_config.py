# -*- coding: utf-8 -*-
"""
GEL 文件注入与生效信息

@input Config.paths.ccxml / Config.paths.gel_file / Config.paths.ccs_dss
@output prepare_session_ccxml()、cleanup_session_ccxml()、describe_effective_gel()
@pos 测试执行与硬件检测共用的 GEL 准备层：仅在 tools.gel_file 非空时复制 ccxml、
     在 <device><cpu> 下写入 GEL File 属性并交给 DSS；空值完全不介入

一旦我被更新务必更新我的开头注释以及所属文件夹的 README.md
"""

import hashlib
import os
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, Union

from .exceptions import GelConfigError
from .runtime_paths import to_posix

GEL_PROPERTY_ID = "GEL File"

_GEL_MISSING_SUGGESTION = (
    "请在配置的 tools.gel_file 中填写本机实际存在的 GEL 文件路径，"
    "或清空该项以使用设备默认 GEL"
)
_CPU_MISSING_SUGGESTION = (
    "请先在 CCS 的 Target Configuration 中为该设备指定 GEL 并保存"
    "（CCS 会在 ccxml 中生成 <device><cpu> 节点）后重试；"
    "或将 tools.gel_file 留空以使用设备默认 GEL"
)


def prepare_session_ccxml(ccxml: Union[str, Path], gel_file: Optional[Union[str, Path]]) -> Optional[Path]:
    """
    按配置生成用于本次 DSS 会话的 ccxml

    - gel_file 为空：返回 None（调用方继续用原 ccxml，行为与之前完全一致）
    - gel_file 非空：复制一份临时 ccxml，在 <device><cpu> 下写入 GEL File 属性

    临时文件由调用方通过 cleanup_session_ccxml() 清理；原 ccxml 不会被修改。
    """
    if not gel_file:
        return None

    gel_path = Path(gel_file)
    if not gel_path.is_file():
        raise GelConfigError(
            "指定的 GEL 文件不存在",
            str(gel_path),
            _GEL_MISSING_SUGGESTION,
        )

    ccxml_path = Path(ccxml)
    if not ccxml_path.is_file():
        raise GelConfigError(
            "CCXML 文件不存在，无法注入 GEL",
            str(ccxml_path),
            "请检查配置中的 ccxml 路径，或清空 tools.gel_file 后重试",
        )

    try:
        tree = ET.parse(str(ccxml_path))
    except ET.ParseError as exc:
        raise GelConfigError(
            f"CCXML 文件格式无法解析（{exc}）",
            str(ccxml_path),
            "请用 CCS 重新保存该 ccxml 后重试",
        )

    cpu_node = _find_first_cpu(tree.getroot())
    if cpu_node is None:
        raise GelConfigError(
            "CCXML 中找不到可注入 GEL 的 <device><cpu> 节点",
            str(ccxml_path),
            _CPU_MISSING_SUGGESTION,
        )

    _set_gel_property(cpu_node, to_posix(gel_path.resolve()))
    return _write_temp_ccxml(tree, ccxml_path)


def cleanup_session_ccxml(temp_ccxml: Optional[Union[str, Path]]) -> None:
    """删除临时 ccxml；None 或已删除时静默跳过"""
    if not temp_ccxml:
        return
    try:
        os.unlink(str(temp_ccxml))
    except OSError:
        pass


def describe_effective_gel(
    ccxml: Union[str, Path],
    gel_file: Optional[Union[str, Path]],
    ccs_dss: Optional[Union[str, Path]] = None,
) -> str:
    """
    生成一行"实际生效的 GEL"描述：路径 + 来源（配置时附 SHA256）

    默认来源需要查 ccxml / targetdb，查不到时只说明"设备默认"，不影响运行。
    """
    if gel_file:
        gel_path = Path(gel_file)
        digest = _sha256(gel_path)
        if digest:
            return f"GEL 生效: {to_posix(gel_path)}（来源: 配置，SHA256: {digest}）"
        return f"GEL 生效: {to_posix(gel_path)}（来源: 配置）"

    declared = _gel_from_ccxml(ccxml)
    if declared is not None:
        return f"GEL 生效: {to_posix(declared)}（来源: ccxml 指定）"

    default = _gel_from_targetdb(ccxml, ccs_dss)
    if default is not None:
        return f"GEL 生效: {to_posix(default)}（来源: 设备默认）"

    return "GEL 生效: 设备默认（未能解析出具体文件，不影响运行）"


def _find_first_cpu(root: ET.Element) -> Optional[ET.Element]:
    """返回第一个满足 <device><cpu> 的 cpu 节点"""
    for device in root.iter("device"):
        cpu = device.find("cpu")
        if cpu is not None:
            return cpu
    return None


def _set_gel_property(cpu_node: ET.Element, gel_value: str) -> None:
    """写入/覆盖 cpu 下的 GEL File 属性"""
    for prop in cpu_node.findall("property"):
        if prop.get("id") == GEL_PROPERTY_ID:
            prop.set("Type", "filepathfield")
            prop.set("Value", gel_value)
            return

    prop = ET.SubElement(cpu_node, "property")
    prop.set("Type", "filepathfield")
    prop.set("Value", gel_value)
    prop.set("id", GEL_PROPERTY_ID)


def _write_temp_ccxml(tree: ET.ElementTree, ccxml_path: Path) -> Path:
    """
    在原 ccxml 同目录写临时副本

    同目录可保证 ccxml 内的相对引用按原位置解析；文件名以点开头，便于识别。
    """
    try:
        fd, tmp_name = tempfile.mkstemp(
            dir=str(ccxml_path.parent),
            prefix=f".{ccxml_path.stem}.gel-",
            suffix=".ccxml",
        )
        os.close(fd)
    except OSError as exc:
        raise GelConfigError(
            f"无法在 ccxml 所在目录创建临时副本（{exc}）",
            str(ccxml_path.parent),
            "请确认该目录可写，或把 ccxml 放到有写权限的目录后重试",
        )

    try:
        payload = (b'<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
                   + ET.tostring(tree.getroot(), encoding="utf-8"))
        with open(tmp_name, "wb") as f:
            f.write(payload)
    except Exception:
        cleanup_session_ccxml(tmp_name)
        raise

    return Path(tmp_name)


def _sha256(path: Path) -> Optional[str]:
    try:
        digest = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _resolve_value(value: Optional[str], base: Path) -> Optional[Path]:
    """把 ccxml/targetdb 里的路径值解析成绝对路径；空值返回 None"""
    text = (value or "").strip()
    if not text:
        return None
    path = Path(text)
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def _gel_from_ccxml(ccxml: Union[str, Path]) -> Optional[Path]:
    """读取 ccxml 中已显式声明的 GEL File 属性"""
    ccxml_path = Path(ccxml)
    try:
        root = ET.parse(str(ccxml_path)).getroot()
    except (OSError, ET.ParseError):
        return None

    for device in root.iter("device"):
        for cpu in device.findall("cpu"):
            for prop in cpu.findall("property"):
                if prop.get("id") == GEL_PROPERTY_ID:
                    return _resolve_value(prop.get("Value"), ccxml_path.parent)
    return None


def _gel_from_targetdb(ccxml: Union[str, Path],
                       ccs_dss: Optional[Union[str, Path]]) -> Optional[Path]:
    """
    按 ccxml 引用的 targetdb 设备文件查设备默认 GEL

    查不到（ccs_dss 缺失、设备 xml 不存在、结构不符）时返回 None，不影响运行。
    """
    if not ccs_dss:
        return None

    try:
        ccs_base = Path(ccs_dss).resolve().parent.parent.parent
        targetdb = ccs_base / "common" / "targetdb"
        if not targetdb.is_dir():
            return None

        ccxml_root = ET.parse(str(Path(ccxml))).getroot()
        for instance in ccxml_root.iter("instance"):
            xml_name = instance.get("xml") or ""
            xml_path = instance.get("xmlpath") or ""
            if not xml_name or not xml_path.startswith("devices"):
                continue

            device_xml = targetdb / xml_path / xml_name
            if not device_xml.is_file():
                continue

            device_root = ET.parse(str(device_xml)).getroot()
            for cpu in device_root.iter("cpu"):
                for prop in cpu.findall("property"):
                    if prop.get("id") == GEL_PROPERTY_ID:
                        return _resolve_value(prop.get("Value"), targetdb)
    except (OSError, ET.ParseError):
        return None

    return None
