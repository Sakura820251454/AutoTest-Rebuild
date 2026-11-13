# -*- coding: utf-8 -*-
"""
executor 与 FLASH 加密集成回归测试

覆盖：批量结束后按用例/子目录加密 FLASH.dat、每个用例的加密状态写入 encrypt_status、
缺失 FLASH.dat 的失败记录、RAM 用例跳过、同一子目录去重只加密一次。
"""

import unittest
from unittest import mock

from tests.helpers import TempTestCase, make_case, make_config, write_flash_dat
from src.executor import TestExecutor


FLASH_SEGMENTS = [{"name": "FLASH", "addr": "0x80000", "len": "0x80000",
                   "width": 15, "page": 0}]
RAM_SEGMENTS = [{"name": "M0", "addr": "0x0000", "len": "0x200",
                 "width": 15, "page": 0}]


class EncryptFlashIntegrationTest(TempTestCase):

    def _executor(self, verify=False):
        cfg = make_config(self.tmp, generation_mode="manual",
                          test={"encrypt_flash_dat": True, "flash_encrypt_verify": verify})
        return TestExecutor(cfg)

    def test_encrypts_flash_case_and_records_success(self):
        executor = self._executor()
        dat_dir = self.make_dir("results", "case_flash")
        write_flash_dat(dat_dir / "memory" / "FLASH.dat")
        case = make_case(self.tmp, name="case_flash", dat_dir=dat_dir,
                         segments=FLASH_SEGMENTS)

        executor._encrypt_flash_dats([case])

        self.assertEqual(executor.encrypt_failures, [])
        self.assertEqual(executor.encrypt_status["case_flash"]["result"], "success")
        for i in range(4):
            self.assertTrue((dat_dir / "memory" / f"FLASH{i}.dat").is_file())

    def test_flash_segment_without_dat_is_reported(self):
        executor = self._executor()
        dat_dir = self.make_dir("results", "case_broken")
        case = make_case(self.tmp, name="case_broken", dat_dir=dat_dir,
                         segments=FLASH_SEGMENTS)

        executor._encrypt_flash_dats([case])

        self.assertEqual(executor.encrypt_status["case_broken"]["result"], "failed")
        self.assertTrue(executor.encrypt_status["case_broken"]["text"].startswith("失败"))
        self.assertEqual(len(executor.encrypt_failures), 1)
        self.assertIn("FLASH.dat 不存在", executor.encrypt_failures[0])

    def test_ram_case_is_skipped(self):
        executor = self._executor()
        dat_dir = self.make_dir("results", "case_ram")
        case = make_case(self.tmp, name="case_ram", dat_dir=dat_dir,
                         segments=RAM_SEGMENTS)

        executor._encrypt_flash_dats([case])

        self.assertEqual(executor.encrypt_status["case_ram"]["result"], "skip")
        self.assertIn("不适用", executor.encrypt_status["case_ram"]["text"])
        self.assertEqual(executor.encrypt_failures, [])

    def test_same_subdir_is_encrypted_once(self):
        executor = self._executor()
        dat_dir = self.make_dir("results", "case_dup")
        write_flash_dat(dat_dir / "memory" / "FLASH.dat")
        case = make_case(self.tmp, name="case_dup", dat_dir=dat_dir, segments=FLASH_SEGMENTS,
                         export_points=[
                             {"when": "after_run", "enabled": True, "subdir": "memory"},
                             {"when": "before_run", "enabled": True, "subdir": "memory"},
                         ])

        with mock.patch("src.executor.encrypt_flash_dat_file",
                        return_value=(True, "ok")) as fake:
            executor._encrypt_flash_dats([case])

        self.assertEqual(fake.call_count, 1)
        self.assertEqual(executor.encrypt_status["case_dup"]["result"], "success")

    def test_distinct_subdirs_are_encrypted_separately(self):
        executor = self._executor()
        dat_dir = self.make_dir("results", "case_multi")
        write_flash_dat(dat_dir / "memory" / "FLASH.dat")
        write_flash_dat(dat_dir / "pre" / "FLASH.dat")
        case = make_case(self.tmp, name="case_multi", dat_dir=dat_dir, segments=FLASH_SEGMENTS,
                         export_points=[
                             {"when": "after_run", "enabled": True, "subdir": "memory"},
                             {"when": "before_run", "enabled": True, "subdir": "pre"},
                         ])

        with mock.patch("src.executor.encrypt_flash_dat_file",
                        return_value=(True, "ok")) as fake:
            executor._encrypt_flash_dats([case])

        self.assertEqual(fake.call_count, 2)


if __name__ == "__main__":
    unittest.main()
