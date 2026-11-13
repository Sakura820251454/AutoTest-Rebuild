# -*- coding: utf-8 -*-
"""
配置路径异常回归测试

覆盖：results_dir 无法访问（权限拒绝）时，Config.load 应抛可读的 ConfigPathError，
而不是把原生 PermissionError 直接抛给界面。
"""

import unittest
from pathlib import Path
from unittest import mock

from tests.helpers import TempTestCase, make_config_dict
from src.config import Config
from src.exceptions import ConfigPathError


class ConfigPathErrorTest(TempTestCase):

    def test_permission_denied_results_dir_raises_config_path_error(self):
        config_path = self.write_json("config.json", make_config_dict(self.tmp))
        target = str(self.tmp / "results")
        original_resolve = Path.resolve

        def fake_resolve(self, *args, **kwargs):
            if str(self) == target:
                raise PermissionError(13, "拒绝访问")
            return original_resolve(self, *args, **kwargs)

        with mock.patch.object(Path, "resolve", fake_resolve):
            with self.assertRaises(ConfigPathError) as ctx:
                Config.load(config_path)

        self.assertEqual(1003, ctx.exception.error_code)
        self.assertIn("权限拒绝", str(ctx.exception))
        self.assertIn("results", str(ctx.exception).lower())

    def test_other_os_error_is_wrapped(self):
        config_path = self.write_json("config.json", make_config_dict(self.tmp))
        target = str(self.tmp / "results")
        original_resolve = Path.resolve

        def fake_resolve(self, *args, **kwargs):
            if str(self) == target:
                raise OSError(123, "设备未就绪")
            return original_resolve(self, *args, **kwargs)

        with mock.patch.object(Path, "resolve", fake_resolve):
            with self.assertRaises(ConfigPathError) as ctx:
                Config.load(config_path)

        self.assertEqual(1003, ctx.exception.error_code)
        self.assertIn("设备未就绪", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
