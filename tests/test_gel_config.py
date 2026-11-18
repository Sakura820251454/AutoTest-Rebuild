# -*- coding: utf-8 -*-
"""
GEL 配置与 ccxml 注入回归测试

覆盖：tools.gel_file 配置往返（空/有值、相对/绝对）、空值零介入、
注入内容与临时文件清理、文件缺失中文报错、隐藏字段保值；
以及离线 DSS openSession 查询已登记 GEL，确认注入后的 ccxml 被 CCS 接受。

注意：DSS 验收用例依赖本机 CCS（默认 C:\ti\ccs1210），未安装时自动跳过。
"""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import xml.etree.ElementTree as ET

from tests.helpers import TempTestCase, make_config
from src.config import Config
from src.exceptions import GelConfigError
from src.gel_config import (
    cleanup_session_ccxml,
    describe_effective_gel,
    prepare_session_ccxml,
)

CCS_ROOT = Path(r"C:\ti\ccs1210\ccs")
DSS_JAVA = CCS_ROOT / "eclipse" / "jre" / "bin" / "java.exe"
DSS_JAR_DIR = CCS_ROOT / "ccs_base" / "DebugServer" / "packages" / "ti" / "dss" / "java"

_CCXML_WITH_DEVICE = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<configurations XML_version="1.2" id="configurations_0">
    <configuration XML_version="1.2" id="Texas Instruments XDS100v2 USB Debug Probe_0">
        <instance XML_version="1.2" desc="Texas Instruments XDS100v2 USB Debug Probe_0" href="connections/TIXDS100v2_Connection.xml" id="Texas Instruments XDS100v2 USB Debug Probe_0" xml="TIXDS100v2_Connection.xml" xmlpath="connections"/>
        <connection XML_version="1.2" id="Texas Instruments XDS100v2 USB Debug Probe_0">
            <instance XML_version="1.2" href="drivers/tixds100v2c28x.xml" id="drivers" xml="tixds100v2c28x.xml" xmlpath="drivers"/>
            <platform XML_version="1.2" id="platform_0">
                <instance XML_version="1.2" desc="TMS320F28335_0" href="devices/f28335.xml" id="TMS320F28335_0" xml="f28335.xml" xmlpath="devices"/>
                <device HW_revision="1" XML_version="1.2" description="TMS320F28335" id="TMS320F28335_0" partnum="TMS320F28335">
                    <cpu HW_revision="1.0" XML_version="1.2" description="CPU" deviceSim="false" id="C2800" isa="TMS320C28XX">
                        <property Type="filepathfield" Value="D:/old/custom.gel" id="GEL File"/>
                    </cpu>
                </device>
            </platform>
        </connection>
    </configuration>
</configurations>
"""


class GelConfigRoundTripTest(TempTestCase):
    """配置字段解析与保存往返"""

    def test_missing_field_means_no_gel(self):
        source = self.write_json("config/config.json", {"paths": {}})
        cfg = Config.load(source)
        self.assertIsNone(cfg.paths.gel_file)

    def test_relative_gel_resolved_against_config_dir(self):
        source = self.write_json("config/config.json", {
            "paths": {}, "tools": {"gel_file": "../gels/custom.gel"},
        })
        cfg = Config.load(source)
        self.assertEqual(cfg.paths.gel_file, (source.parent / "../gels/custom.gel").resolve())

    def test_absolute_gel_is_preserved(self):
        gel = self.tmp / "external" / "custom.gel"
        source = self.write_json("config/config.json", {
            "paths": {}, "tools": {"gel_file": str(gel)},
        })
        cfg = Config.load(source)
        self.assertEqual(cfg.paths.gel_file, gel.resolve())

    def test_save_relative_inside_app_root_and_reload(self):
        base = self.tmp / "app"
        gel = base / "gels" / "custom.gel"
        gel.parent.mkdir(parents=True, exist_ok=True)
        gel.write_text('menuitem "x";\n', encoding="utf-8")

        cfg_path = base / "config" / "config.json"
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg = Config({"paths": {}, "tools": {"gel_file": str(gel)}}, cfg_path)

        out = base / "config" / "saved.json"
        with mock.patch("src.config.app_root", return_value=base.resolve()):
            cfg.save(out)

        saved = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(saved["tools"]["gel_file"], "../gels/custom.gel")
        self.assertNotIn("\\", saved["tools"]["gel_file"])
        self.assertEqual(Config.load(out).paths.gel_file, gel.resolve())

    def test_save_absolute_outside_app_root(self):
        base = self.tmp / "app"
        other = self.make_dir("elsewhere")
        gel = other / "custom.gel"
        gel.write_text('menuitem "x";\n', encoding="utf-8")

        cfg = Config({"paths": {}, "tools": {"gel_file": str(gel)}},
                     base / "config" / "config.json")
        out = self.tmp / "saved.json"
        with mock.patch("src.config.app_root", return_value=base.resolve()):
            cfg.save(out)

        saved = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(saved["tools"]["gel_file"], gel.as_posix())

    def test_save_empty_field_writes_empty_string(self):
        cfg = Config({"paths": {}, "tools": {}}, self.tmp / "config" / "config.json")
        out = self.tmp / "saved.json"
        with mock.patch("src.config.app_root", return_value=self.tmp.resolve()):
            cfg.save(out)
        saved = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(saved["tools"]["gel_file"], "")


class GelPrepareTest(TempTestCase):
    """运行时准备：空值零介入、注入内容、清理、报错"""

    def _ccxml_with_device(self) -> Path:
        return self.write_text("target.ccxml", _CCXML_WITH_DEVICE)

    def _gel(self, name="custom.gel") -> Path:
        return self.write_text(name, 'menuitem "Probe";\n')

    def test_empty_gel_returns_none_without_touching_ccxml(self):
        ccxml = self._ccxml_with_device()
        before = ccxml.read_bytes()
        self.assertIsNone(prepare_session_ccxml(ccxml, None))
        self.assertIsNone(prepare_session_ccxml(ccxml, ""))
        self.assertEqual(ccxml.read_bytes(), before)
        self.assertEqual(list(ccxml.parent.glob("*.ccxml")), [ccxml])

    def test_injects_gel_property_and_keeps_original(self):
        ccxml = self._ccxml_with_device()
        gel = self._gel()
        before = ccxml.read_bytes()

        temp = prepare_session_ccxml(ccxml, gel)
        self.addCleanup(cleanup_session_ccxml, temp)
        self.assertIsNotNone(temp)
        self.assertNotEqual(temp, ccxml)
        self.assertEqual(ccxml.read_bytes(), before)

        cpu = ET.parse(str(temp)).getroot().find(".//device/cpu")
        prop = [p for p in cpu.findall("property") if p.get("id") == "GEL File"][0]
        self.assertEqual(prop.get("Type"), "filepathfield")
        self.assertEqual(prop.get("Value"), gel.resolve().as_posix())

    def test_temp_file_is_cleaned_up(self):
        ccxml = self._ccxml_with_device()
        temp = prepare_session_ccxml(ccxml, self._gel())
        self.assertTrue(temp.exists())
        cleanup_session_ccxml(temp)
        self.assertFalse(temp.exists())

    def test_missing_gel_raises_chinese_error(self):
        ccxml = self._ccxml_with_device()
        missing = self.tmp / "nope.gel"
        with self.assertRaises(GelConfigError) as ctx:
            prepare_session_ccxml(ccxml, missing)
        text = str(ctx.exception)
        self.assertIn("原因：", text)
        self.assertIn("路径：", text)
        self.assertIn("建议：", text)
        self.assertIn("GEL 文件不存在", text)
        self.assertIn(str(missing), text)

    def test_ccxml_without_device_cpu_raises(self):
        ccxml = self.write_text("plain.ccxml", (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<configurations><configuration><connection>'
            '<platform><instance xml="f28335.xml" xmlpath="devices"/></platform>'
            '</connection></configuration></configurations>\n'))
        with self.assertRaises(GelConfigError) as ctx:
            prepare_session_ccxml(ccxml, self._gel())
        text = str(ctx.exception)
        self.assertIn("<device><cpu>", text)
        self.assertIn("建议：", text)

    def test_describe_reports_configured_source_with_hash(self):
        gel = self._gel()
        line = describe_effective_gel(self._ccxml_with_device(), gel)
        self.assertIn("来源: 配置", line)
        self.assertIn("SHA256:", line)
        self.assertIn(gel.resolve().as_posix(), line)

    def test_describe_reports_empty_source(self):
        line = describe_effective_gel(self._ccxml_with_device(), None)
        self.assertIn("来源: ccxml 指定", line)


@unittest.skipUnless(
    DSS_JAVA.exists() and DSS_JAR_DIR.is_dir(),
    "本机未安装 CCS 12.10，跳过离线 DSS GEL 验收",
)
class GelDssAcceptanceTest(TempTestCase):
    """离线 openSession + 查询已登记 GEL，确认注入后的 ccxml 被 CCS 接受"""

    _JS = r'''
importPackage(Packages.com.ti.debug.engine.scripting);
importPackage(Packages.com.ti.ccstudio.scripting.environment);
importPackage(Packages.java.lang);

var CCXML = "%%CCXML%%";

function findDeclared(obj, name) {
    var c = obj.getClass();
    while (c !== null) {
        var ms = c.getDeclaredMethods();
        for (var i = 0; i < ms.length; i++) {
            if (String(ms[i].getName()) === name) {
                ms[i].setAccessible(true);
                return ms[i];
            }
        }
        c = c.getSuperclass();
    }
    return null;
}

var env = ScriptingEnvironment.instance();
var server = env.getServer("DebugServer.1");
var session = null;
try {
    server.setConfig(CCXML);
    session = server.openSession("Texas Instruments XDS100v2 USB Debug Probe_0", "C28xx");
    print("OPENED OK");
    var task = findDeclared(session, "getDspTask").invoke(session, null);
    var gelFiles = findDeclared(task, "getGelFiles").invoke(task, null);
    print("GEL COUNT=" + gelFiles.getCount());
    for (var i = 0; i < gelFiles.getCount(); i++) {
        var gf = gelFiles.getItem(i);
        print("GEL[" + i + "] name=" + gf.getName() + " parserError=" + gf.containsParserError());
    }
} catch (e) {
    print("PROBE ERROR: " + e);
} finally {
    if (session) { try { session.terminate(); } catch (e) {} }
    try { server.stop(); } catch (e) {}
}
print("PROBE DONE");
'''

    def test_injected_ccxml_registers_gel_in_ccs(self):
        dvt_dirs = sorted((CCS_ROOT / "ccs_base").glob("dvt_*"))
        if not dvt_dirs:
            self.skipTest("未找到 DSS scripting 运行库")
        classpath = "{};{}".format(
            str(DSS_JAR_DIR / "*"),
            str(dvt_dirs[0] / "scripting" / "*"),
        )

        ccxml = self.write_text("target.ccxml", _CCXML_WITH_DEVICE)
        gel = self.write_text("probe.gel", 'menuitem "Probe";\n')
        temp_ccxml = prepare_session_ccxml(ccxml, gel)
        self.addCleanup(cleanup_session_ccxml, temp_ccxml)

        script = self.write_text(
            "probe.js", self._JS.replace("%%CCXML%%", temp_ccxml.as_posix()))
        result = subprocess.run(
            [str(DSS_JAVA), "-cp", classpath,
             "org.mozilla.javascript.tools.shell.Main", str(script)],
            capture_output=True, timeout=180,
        )
        output = result.stdout.decode("utf-8", errors="replace")
        errors = result.stderr.decode("utf-8", errors="replace")

        self.assertIn("OPENED OK", output, output + errors)
        self.assertIn("GEL COUNT=1", output, output + errors)
        self.assertIn("name=" + gel.resolve().as_posix(), output.replace("\\", "/"),
                      output + errors)
        self.assertIn("parserError=false", output, output + errors)


if __name__ == "__main__":
    unittest.main()
