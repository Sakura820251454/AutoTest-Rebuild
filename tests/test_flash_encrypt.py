# -*- coding: utf-8 -*-
"""
FLASH 段 dat 加密封装回归测试

覆盖：进程内加载根目录 encrypt_flash_dat.py、FLASH0~3.dat 产出校验、
回读校验模式、输入文件不被改写、加密结果可解密还原、缺失文件/行数错误/脚本缺失的失败分支。
"""

import unittest
from unittest import mock

from tests.helpers import TempTestCase, flash_words, write_flash_dat
from src import flash_encrypt


class EncryptFlashDatTest(TempTestCase):

    def _prepare(self):
        dat = write_flash_dat(self.tmp / "memory" / "FLASH.dat")
        return dat

    def test_produces_four_instances_and_keeps_input(self):
        dat = self._prepare()
        before = dat.read_bytes()

        ok, detail = flash_encrypt.encrypt_flash_dat_file(dat, timeout=120)

        self.assertTrue(ok, detail)
        self.assertEqual(dat.read_bytes(), before, "原始 FLASH.dat 不应被改写")
        for i in range(4):
            out = dat.with_name(f"FLASH{i}.dat")
            self.assertTrue(out.is_file(), f"缺少 {out.name}")
            self.assertEqual(len(out.read_text(encoding="ascii").splitlines()), 16384)

    def test_verify_mode_roundtrip(self):
        dat = self._prepare()

        ok, detail = flash_encrypt.encrypt_flash_dat_file(dat, timeout=120, verify=True)
        self.assertTrue(ok, detail)

        module = flash_encrypt._load_script(flash_encrypt.script_path())
        origin, _ = module.read_rows(str(dat), 65536)
        instances = []
        for i in range(4):
            rows, _ = module.read_rows(str(dat.with_name(f"FLASH{i}.dat")), 16384)
            instances.append([module.dec_word(v, a, i) for a, v in enumerate(rows)])
        self.assertEqual(module.interleave(instances), origin)

    def test_missing_input_returns_false(self):
        ok, detail = flash_encrypt.encrypt_flash_dat_file(self.tmp / "nope" / "FLASH.dat")
        self.assertFalse(ok)
        self.assertIn("不存在", detail)

    def test_wrong_row_count_returns_false(self):
        dat = write_flash_dat(self.tmp / "memory" / "FLASH.dat", flash_words(10))

        ok, detail = flash_encrypt.encrypt_flash_dat_file(dat, timeout=120)

        self.assertFalse(ok)
        self.assertIn("exit 1", detail)
        self.assertFalse((dat.parent / "FLASH0.dat").exists())

    def test_missing_script_returns_false(self):
        dat = write_flash_dat(self.tmp / "memory" / "FLASH.dat", flash_words(8))
        with mock.patch.object(flash_encrypt, "script_path",
                               return_value=self.tmp / "missing_script.py"):
            ok, detail = flash_encrypt.encrypt_flash_dat_file(dat)
        self.assertFalse(ok)
        self.assertIn("未找到加密脚本", detail)


if __name__ == "__main__":
    unittest.main()
