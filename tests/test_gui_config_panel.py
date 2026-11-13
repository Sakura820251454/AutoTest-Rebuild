# -*- coding: utf-8 -*-
"""
配置面板 GUI 回归测试（Qt offscreen，不弹窗）

覆盖：生成模式切换时模板/源文件两行的可见性、加密开关与回读校验联动、
字段加载/回读往返（含结果目录、隐藏兼容字段）、Flash 三态。
"""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt                      # noqa: E402
from PyQt5.QtWidgets import QApplication          # noqa: E402

from tests.helpers import TempTestCase, make_config   # noqa: E402
from gui.widgets.config_panel import ConfigPanel      # noqa: E402


class ConfigPanelTest(TempTestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        super().setUp()
        self.panel = ConfigPanel()
        self.addCleanup(self.panel.deleteLater)

    def test_default_is_template_mode_and_rows_visible(self):
        self.assertFalse(any(w.isHidden() for w in self.panel.template_mode_widgets))

    def test_switching_to_manual_hides_template_rows(self):
        self.panel.generation_mode_combo.setCurrentText("manual")
        self.assertTrue(all(w.isHidden() for w in self.panel.template_mode_widgets))

        self.panel.generation_mode_combo.setCurrentText("template")
        self.assertFalse(any(w.isHidden() for w in self.panel.template_mode_widgets))

    def test_load_manual_config_hides_template_rows(self):
        cfg = make_config(self.tmp, generation_mode="manual")
        self.panel.load_config(cfg)
        self.assertTrue(all(w.isHidden() for w in self.panel.template_mode_widgets))

    def test_load_template_config_shows_template_rows(self):
        cfg = make_config(self.tmp, generation_mode="template")
        self.panel.load_config(cfg)
        self.assertFalse(any(w.isHidden() for w in self.panel.template_mode_widgets))

    def test_fields_roundtrip_through_panel(self):
        cfg = make_config(
            self.tmp,
            generation_mode="manual",
            test={
                "device": "F28379D",
                "cpu": "C28xx_CPU1",
                "test_timeout": 30000,
                "test_batch_size": 5,
                "auto_resume": False,
                "max_retries": 3,
                "retry_delay": 20,
                "encrypt_flash_dat": True,
                "flash_encrypt_verify": True,
                "copy_project": False,
            },
        )
        self.panel.load_config(cfg)
        data = self.panel.get_config_dict()

        self.assertEqual(data["generate_dir"], str(cfg.paths.generate_dir))
        self.assertEqual(data["results_dir"], str(cfg.paths.results_dir))
        self.assertEqual(data["device"], "F28379D")
        self.assertEqual(data["cpu"], "C28xx_CPU1")
        self.assertEqual(data["timeout"], 30000)
        self.assertEqual(data["test_batch_size"], 5)
        self.assertFalse(data["auto_resume"])
        self.assertEqual(data["max_retries"], 3)
        self.assertEqual(data["retry_delay"], 20)
        self.assertTrue(data["encrypt_flash_dat"])
        self.assertTrue(data["flash_encrypt_verify"])
        self.assertFalse(data["copy_project"])
        self.assertEqual(data["generation"]["generation_mode"], "manual")

    def test_hidden_legacy_fields_are_preserved(self):
        cfg = make_config(self.tmp)
        self.panel.load_config(cfg)
        data = self.panel.get_config_dict()
        self.assertEqual(data["ccs_workspace"], str(cfg.paths.ccs_workspace))
        self.assertEqual(data["result_dir"], str(cfg.paths.result_dir))

    def test_encryption_off_disables_verify_checkbox(self):
        cfg = make_config(self.tmp, test={"encrypt_flash_dat": False,
                                          "flash_encrypt_verify": True})
        self.panel.load_config(cfg)

        self.assertFalse(self.panel.encrypt_flash_checkbox.isChecked())
        self.assertFalse(self.panel.flash_verify_checkbox.isEnabled())

        self.panel.encrypt_flash_checkbox.setChecked(True)
        self.assertTrue(self.panel.flash_verify_checkbox.isEnabled())
        self.assertTrue(self.panel.flash_verify_checkbox.isChecked())

    def test_encryption_on_enables_verify_checkbox(self):
        cfg = make_config(self.tmp, test={"encrypt_flash_dat": True,
                                          "flash_encrypt_verify": False})
        self.panel.load_config(cfg)
        self.assertTrue(self.panel.encrypt_flash_checkbox.isChecked())
        self.assertTrue(self.panel.flash_verify_checkbox.isEnabled())
        self.assertFalse(self.panel.flash_verify_checkbox.isChecked())

    def test_results_dir_edit_is_reflected_in_exported_dict(self):
        cfg = make_config(self.tmp)
        self.panel.load_config(cfg)
        new_dir = str(self.tmp / "other_results")

        self.panel.results_dir_selector.set_path(new_dir)

        self.assertEqual(self.panel.get_config_dict()["results_dir"], new_dir)

    def test_is_flash_tristate_roundtrip(self):
        cfg_auto = make_config(self.tmp)
        self.panel.load_config(cfg_auto)
        self.assertNotIn("is_flash", self.panel.get_config_dict())
        self.assertEqual(self.panel.is_flash_checkbox.checkState(), Qt.PartiallyChecked)

        cfg_flash = make_config(self.tmp, raw_extra={"cases": [
            {"name": "c1", "out": "c1.out", "dat_dir": "d1", "is_flash": True}
        ]})
        self.panel.load_config(cfg_flash)
        self.assertIs(self.panel.get_config_dict()["is_flash"], True)

        cfg_ram = make_config(self.tmp, raw_extra={"cases": [
            {"name": "c1", "out": "c1.out", "dat_dir": "d1", "is_flash": False}
        ]})
        self.panel.load_config(cfg_ram)
        self.assertIs(self.panel.get_config_dict()["is_flash"], False)


if __name__ == "__main__":
    unittest.main()
