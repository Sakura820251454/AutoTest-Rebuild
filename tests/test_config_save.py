# -*- coding: utf-8 -*-
"""
config 保存回归测试

覆盖：程序目录内写相对路径、目录外写绝对路径、统一正斜杠、注释保留、
保存后重新加载路径语义不变。app_root() 用 monkeypatch 指到临时目录，
不会接触真实工程目录里的配置文件。
"""

import json
import unittest
from pathlib import Path
from unittest import mock

from tests.helpers import TempTestCase, make_config_dict
from src.config import Config


class SavePathFormatTest(TempTestCase):
    """_format_save_path：相对/绝对与正斜杠规则"""

    def _config(self, base, paths_override):
        data = make_config_dict(base)
        data["paths"].update(paths_override)
        cfg_path = Path(base) / "config" / "config.json"
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        return Config(data, cfg_path)

    def test_path_inside_app_root_saved_relative(self):
        base = self.tmp / "app"
        cfg = self._config(base, {"generate_dir": str(base / "workspace" / "case1")})
        with mock.patch("src.config.app_root", return_value=base.resolve()):
            value = cfg._format_save_path(base / "workspace" / "case1")
        self.assertEqual(value, "../workspace/case1")

    def test_path_outside_app_root_saved_absolute_posix(self):
        base = self.tmp / "app"
        outside = self.make_dir("external")
        cfg = self._config(base, {})
        with mock.patch("src.config.app_root", return_value=base.resolve()):
            value = cfg._format_save_path(outside)
        self.assertEqual(value, outside.as_posix())
        self.assertNotIn("\\", value)

    def test_relative_input_is_normalized_to_posix(self):
        base = self.tmp / "app"
        cfg = self._config(base, {})
        with mock.patch("src.config.app_root", return_value=base.resolve()):
            value = cfg._format_save_path(Path("..") / "shared" / "results")
        self.assertEqual(value, "../shared/results")

    def test_saved_json_contains_no_backslashes(self):
        base = self.tmp / "app"
        cfg = self._config(base, {})
        out = self.tmp / "saved.json"
        with mock.patch("src.config.app_root", return_value=base.resolve()):
            cfg.save(out)

        text = out.read_text(encoding="utf-8")
        data = json.loads(text)
        self.assertNotIn("\\\\", text)
        for group in ("paths", "tools"):
            for key, value in data[group].items():
                self.assertNotIn("\\", value, f"{group}.{key} 应为正斜杠")

    def test_comments_are_preserved_on_save(self):
        base = self.tmp / "app"
        data = make_config_dict(base)
        data["_comment"] = "手工维护的说明"
        data["paths"]["_comment"] = "路径说明"
        cfg_path = base / "config" / "config.json"
        cfg = Config(data, cfg_path)

        out = self.tmp / "saved.json"
        with mock.patch("src.config.app_root", return_value=base.resolve()):
            cfg.save(out)

        saved = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(saved["_comment"], "手工维护的说明")
        self.assertEqual(saved["paths"]["_comment"], "路径说明")

    def test_case_dat_dir_saved_with_forward_slashes(self):
        base = self.tmp / "app"
        data = make_config_dict(base)
        data["cases"] = [{
            "name": "c1",
            "out": str(base / "workspace" / "c1" / "Debug" / "c1.out"),
            "dat_dir": r"D:\results\c1",
        }]
        cfg = Config(data, base / "config" / "config.json")

        out = self.tmp / "saved.json"
        with mock.patch("src.config.app_root", return_value=base.resolve()):
            cfg.save(out)

        saved = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(saved["cases"][0]["dat_dir"], "D:/results/c1")
        self.assertEqual(saved["cases"][0]["out"], "../workspace/c1/Debug/c1.out")
        self.assertIn("is_flash", saved["cases"][0])

    def test_roundtrip_keeps_resolved_paths(self):
        base = self.tmp / "app"
        (base / "workspace").mkdir(parents=True, exist_ok=True)
        (base / "config").mkdir(parents=True, exist_ok=True)
        data = make_config_dict(base)
        cfg = Config(data, base / "config" / "config.json")

        out = base / "config" / "saved.json"
        with mock.patch("src.config.app_root", return_value=base.resolve()):
            cfg.save(out)

        reloaded = Config.load(out)
        self.assertEqual(reloaded.paths.generate_dir, cfg.paths.generate_dir)
        self.assertEqual(reloaded.paths.results_dir, cfg.paths.results_dir)
        self.assertEqual(reloaded.paths.ccs_dss, cfg.paths.ccs_dss)
        self.assertEqual(reloaded.test.encrypt_flash_dat, cfg.test.encrypt_flash_dat)
        self.assertEqual(reloaded.test.copy_project, cfg.test.copy_project)


if __name__ == "__main__":
    unittest.main()
