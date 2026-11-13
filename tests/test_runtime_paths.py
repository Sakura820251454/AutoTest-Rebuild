# -*- coding: utf-8 -*-
"""
runtime_paths 回归测试

覆盖：分隔符转换、路径去重键、源码模式与冻结模式下的程序目录/资源目录语义。
全部通过 monkeypatch 模拟 frozen 状态，不依赖真实 pyinstaller 产物。
"""

import unittest
from pathlib import Path
from unittest import mock

from tests.helpers import TempTestCase
from src import runtime_paths


class ToPosixAndKeyTest(TempTestCase):
    """纯函数：to_posix / path_key"""

    def test_to_posix_converts_backslashes(self):
        self.assertEqual(runtime_paths.to_posix(r"C:\a\b\c.dat"), "C:/a/b/c.dat")

    def test_to_posix_accepts_path_object(self):
        self.assertEqual(runtime_paths.to_posix(Path("a") / "b.dat"), "a/b.dat")

    def test_path_key_ignores_separator_and_case(self):
        self.assertEqual(
            runtime_paths.path_key(r"C:\Work\Case\FLASH.dat"),
            runtime_paths.path_key("c:/work/case/flash.dat"),
        )

    def test_path_key_keeps_distinct_paths_distinct(self):
        self.assertNotEqual(
            runtime_paths.path_key(r"C:\work\a"),
            runtime_paths.path_key(r"C:\work\b"),
        )


class SourceModeTest(TempTestCase):
    """源码模式（sys.frozen 不存在）"""

    def test_is_frozen_false_in_source_mode(self):
        with mock.patch.object(runtime_paths.sys, "frozen", False, create=True):
            self.assertFalse(runtime_paths.is_frozen())

    def test_app_root_is_project_root(self):
        with mock.patch.object(runtime_paths.sys, "frozen", False, create=True):
            expected = Path(runtime_paths.__file__).resolve().parents[1]
            self.assertEqual(runtime_paths.app_root(), expected)

    def test_bundle_root_equals_app_root(self):
        with mock.patch.object(runtime_paths.sys, "frozen", False, create=True):
            self.assertEqual(runtime_paths.bundle_root(), runtime_paths.app_root())

    def test_app_path_resolves_relative_to_app_root(self):
        with mock.patch.object(runtime_paths.sys, "frozen", False, create=True):
            expected = (runtime_paths.app_root() / "logs" / "x.log").resolve()
            self.assertEqual(runtime_paths.app_path("logs/x.log"), expected)

    def test_resource_path_prefers_app_root(self):
        with mock.patch.object(runtime_paths.sys, "frozen", False, create=True):
            target = runtime_paths.app_root() / "templates" / "dss_test.js.tmpl"
            self.assertTrue(target.is_file(), "项目内置模板应存在")
            self.assertEqual(runtime_paths.resource_path("templates/dss_test.js.tmpl"), target)


class FrozenModeTest(TempTestCase):
    """冻结模式：cmp 程序目录=exe 所在目录，资源目录=sys._MEIPASS"""

    def _patch_frozen(self, meipass=None):
        exe = self.make_dir("dist") / "AutoTest.exe"
        exe.write_text("", encoding="utf-8")
        patches = [
            mock.patch.object(runtime_paths, "is_frozen", return_value=True),
            mock.patch.object(runtime_paths.sys, "executable", str(exe)),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        if meipass is None:
            # 真实冻结环境一定有 _MEIPASS，这里模拟"属性不存在"而不是置 None
            existed = hasattr(runtime_paths.sys, "_MEIPASS")
            original = getattr(runtime_paths.sys, "_MEIPASS", None)
            if existed:
                del runtime_paths.sys._MEIPASS

                def _restore():
                    runtime_paths.sys._MEIPASS = original
                self.addCleanup(_restore)
        else:
            p = mock.patch.object(runtime_paths.sys, "_MEIPASS", str(meipass), create=True)
            p.start()
            self.addCleanup(p.stop)
        return exe

    def test_app_root_is_exe_dir(self):
        exe = self._patch_frozen(meipass=self.make_dir("bundle"))
        self.assertEqual(runtime_paths.app_root(), exe.resolve().parent)

    def test_bundle_root_is_meipass(self):
        bundle = self.make_dir("bundle")
        self._patch_frozen(meipass=bundle)
        self.assertEqual(runtime_paths.bundle_root(), bundle)

    def test_bundle_root_falls_back_to_app_root_without_meipass(self):
        self._patch_frozen(meipass=None)
        self.assertEqual(runtime_paths.bundle_root(), runtime_paths.app_root())

    def test_resource_path_falls_back_to_bundle(self):
        bundle = self.make_dir("bundle")
        asset = bundle / "templates" / "dss_test.js.tmpl"
        asset.parent.mkdir(parents=True, exist_ok=True)
        asset.write_text("x", encoding="utf-8")
        self._patch_frozen(meipass=bundle)
        self.assertEqual(runtime_paths.resource_path("templates/dss_test.js.tmpl"), asset)

    def test_resource_path_returns_app_candidate_when_missing(self):
        self._patch_frozen(meipass=self.make_dir("bundle"))
        missing = runtime_paths.resource_path("no/such/file.bin")
        self.assertEqual(missing, runtime_paths.app_root() / "no" / "such" / "file.bin")

    def test_app_path_uses_exe_dir_not_cwd(self):
        exe = self._patch_frozen(meipass=self.make_dir("bundle"))
        self.assertEqual(runtime_paths.app_path("results"), (exe.parent / "results").resolve())


if __name__ == "__main__":
    unittest.main()
