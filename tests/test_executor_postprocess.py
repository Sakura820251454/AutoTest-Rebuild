# -*- coding: utf-8 -*-
"""
executor 后处理回归测试（不依赖 DSS / 硬件）

覆盖：_post_process_dat_files 剥 CCS 文件头（旧/新格式、幂等、误伤保护），
_copy_case_projects 的中间文件过滤与幂等重建。
"""

import unittest

from tests.helpers import TempTestCase, make_case, make_config
from src.executor import TestExecutor


class PostProcessDatTest(TempTestCase):

    def setUp(self):
        super().setUp()
        self.cfg = make_config(self.tmp, generation_mode="manual")
        self.executor = TestExecutor(self.cfg)

    def _memory_file(self, case_name, content, subdir="memory"):
        dat_dir = self.make_dir("results", case_name, subdir)
        path = dat_dir / "FLASH.dat"
        path.write_text(content, encoding="utf-8")
        return path

    def test_strips_legacy_header(self):
        path = self._memory_file("c1", "1651 1 80000000 0 10\n0011223344556677\n")
        case = make_case(self.tmp, name="c1")

        self.executor._post_process_dat_files([case])

        self.assertEqual(path.read_text(encoding="utf-8"), "0011223344556677\n")

    def test_strips_new_format_header(self):
        path = self._memory_file("c1", "1651 9 88675cac 0 c278 c00000000\n0011223344556677\n")
        case = make_case(self.tmp, name="c1")

        self.executor._post_process_dat_files([case])

        self.assertEqual(path.read_text(encoding="utf-8"), "0011223344556677\n")

    def test_second_run_is_noop(self):
        path = self._memory_file("c1", "1651 1 80000000 0 10\n0011223344556677\n")
        case = make_case(self.tmp, name="c1")

        self.executor._post_process_dat_files([case])
        self.executor._post_process_dat_files([case])

        self.assertEqual(path.read_text(encoding="utf-8"), "0011223344556677\n")

    def test_plain_data_is_not_touched(self):
        content = "0011223344556677\n8899AABBCCDDEEFF\n"
        path = self._memory_file("c1", content)
        case = make_case(self.tmp, name="c1")

        self.executor._post_process_dat_files([case])

        self.assertEqual(path.read_text(encoding="utf-8"), content)

    def test_empty_file_is_not_touched(self):
        path = self._memory_file("c1", "")
        case = make_case(self.tmp, name="c1")

        self.executor._post_process_dat_files([case])

        self.assertEqual(path.read_text(encoding="utf-8"), "")

    def test_only_configured_subdir_is_processed(self):
        kept = self._memory_file("c1", "1651 1 80000000 0 10\nDATA\n", subdir="other")
        case = make_case(self.tmp, name="c1", export_points=[
            {"when": "after_run", "enabled": True, "subdir": "memory"}
        ])
        self._memory_file("c1", "1651 1 80000000 0 10\nDATA\n", subdir="memory")

        self.executor._post_process_dat_files([case])

        self.assertTrue(kept.read_text(encoding="utf-8").startswith("1651"))

    def test_header_with_extra_token_is_kept(self):
        content = "1651 1 80000000 0 10 tail extra\n0011223344556677\n"
        path = self._memory_file("c1", content)
        case = make_case(self.tmp, name="c1")

        self.executor._post_process_dat_files([case])

        self.assertEqual(path.read_text(encoding="utf-8"), content)


class CopyCaseProjectTest(TempTestCase):

    def setUp(self):
        super().setUp()
        self.cfg = make_config(self.tmp, generation_mode="manual")
        self.executor = TestExecutor(self.cfg)

        self.project = self.make_dir("workspace", "case1")
        (self.project / ".project").write_text("<project/>", encoding="utf-8")
        (self.project / ".cproject").write_text("<cproject/>", encoding="utf-8")
        (self.project / "main.c").write_text("int main(void){return 0;}", encoding="utf-8")
        include = self.make_dir("workspace", "case1", "include")
        (include / "app.h").write_text("#pragma once", encoding="utf-8")
        self.make_dir("workspace", "case1", "Debug")
        (self.project / "Debug" / "case1.out").write_bytes(b"\x01")
        (self.project / "Debug" / "case1.map").write_text("map", encoding="utf-8")
        (self.project / "Debug" / "case1.obj").write_bytes(b"\x02")
        sub = self.make_dir("workspace", "case1", "Debug", "sub")
        (sub / "case1.d").write_text("dep", encoding="utf-8")
        settings = self.make_dir("workspace", "case1", ".settings")
        (settings / "org.eclipse.core.resources.prefs").write_text("x", encoding="utf-8")
        (settings / "language.settings.xml").write_text("<x/>", encoding="utf-8")
        metadata = self.make_dir("workspace", "case1", ".metadata")
        (metadata / "junk.txt").write_text("x", encoding="utf-8")
        (self.project / "notes.txt").write_text("note", encoding="utf-8")

    def _case(self):
        out = self.project / "Debug" / "case1.out"
        return make_case(self.tmp, name="case1", out=out,
                         dat_dir=self.tmp / "results" / "case1")

    def test_copies_sources_and_filters_intermediates(self):
        case = self._case()
        self.executor._copy_case_projects([case])

        dest = self.tmp / "results" / "case1" / "project"
        copied = {p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file()}
        self.assertEqual(copied, {
            ".project",
            ".cproject",
            "main.c",
            "include/app.h",
            "Debug/case1.out",
            "Debug/case1.map",
            ".settings/language.settings.xml",
            "notes.txt",
        })

    def test_second_copy_removes_stale_files(self):
        case = self._case()
        self.executor._copy_case_projects([case])

        dest = self.tmp / "results" / "case1" / "project"
        stale = dest / "stale.tmp"
        stale.write_text("old", encoding="utf-8")

        self.executor._copy_case_projects([case])

        self.assertFalse(stale.exists())
        self.assertTrue((dest / "main.c").is_file())

    def test_missing_project_root_returns_false_without_side_effects(self):
        dat_dir = self.make_dir("results", "orphan")
        case = make_case(self.tmp, name="orphan",
                         out=self.tmp / "nowhere" / "Debug" / "orphan.out",
                         dat_dir=dat_dir)

        ok = self.executor._copy_case_project(case)

        self.assertFalse(ok)
        self.assertFalse((dat_dir / "project").exists())

    def test_disabled_copy_project_does_nothing(self):
        cfg = make_config(self.tmp, generation_mode="manual", test={"copy_project": False})
        executor = TestExecutor(cfg)
        case = self._case()

        executor._copy_case_projects([case])

        self.assertFalse((self.tmp / "results" / "case1" / "project").exists())


if __name__ == "__main__":
    unittest.main()
