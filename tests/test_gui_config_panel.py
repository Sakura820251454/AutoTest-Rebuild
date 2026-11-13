# -*- coding: utf-8 -*-
"""
配置面板 GUI 回归测试（Qt offscreen，不弹窗）

覆盖：生成模式切换时模板/源文件两行的可见性、加密开关与回读校验联动、
字段加载/回读往返（含结果目录、隐藏兼容字段）、Flash 三态。
"""

import os
import unittest
from unittest import mock

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


class ValidateRequiredPathsTest(TempTestCase):
    """保存前校验：必填路径不存在时标红并阻止保存"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        super().setUp()
        self.panel = ConfigPanel()
        self.addCleanup(self.panel.deleteLater)

    def _create_required_paths(self):
        self.make_dir("workspace")
        tools = self.make_dir("tools")
        (tools / "ccs.exe").write_text("", encoding="utf-8")
        (tools / "dss.bat").write_text("", encoding="utf-8")

    def test_existing_paths_pass_without_red_border(self):
        self._create_required_paths()
        self.panel.load_config(make_config(self.tmp))

        with mock.patch("gui.widgets.config_panel.QMessageBox.warning") as warn:
            self.assertTrue(self.panel.validate())

        warn.assert_not_called()
        self.assertNotIn("C62828", self.panel.path_selectors["generate_dir"]
                         .path_edit.styleSheet())

    def test_missing_paths_mark_red_and_list_each_item(self):
        self.panel.load_config(make_config(self.tmp))

        with mock.patch("gui.widgets.config_panel.QMessageBox.warning") as warn:
            self.assertFalse(self.panel.validate())

        message = warn.call_args[0][2]
        for name in ("工作区目录", "CCS 可执行文件", "DSS 执行器"):
            self.assertIn(name, message)
        for key in ("generate_dir", "ccs_executable", "ccs_dss"):
            selector = self.panel.path_selectors[key]
            self.assertIn("C62828", selector.path_edit.styleSheet())
            self.assertIn("不存在", selector.path_edit.toolTip())

    def test_empty_required_field_blocks_save(self):
        self._create_required_paths()
        self.panel.load_config(make_config(self.tmp))
        self.panel.path_selectors["generate_dir"].set_path("")

        with mock.patch("gui.widgets.config_panel.QMessageBox.warning") as warn:
            self.assertFalse(self.panel.validate())

        self.assertIn("不能为空", warn.call_args[0][2])
        self.assertIn("不能为空",
                      self.panel.path_selectors["generate_dir"].path_edit.toolTip())

    def test_relative_path_resolved_against_config_dir(self):
        self.make_dir("config", "workspace")
        tools = self.make_dir("config", "tools")
        (tools / "ccs.exe").write_text("", encoding="utf-8")
        (tools / "dss.bat").write_text("", encoding="utf-8")
        cfg = make_config(
            self.tmp,
            config_path=self.tmp / "config" / "config.json",
        )
        self.panel.load_config(cfg)
        # 界面上输入相对路径时，按配置文件所在目录解析
        self.panel.path_selectors["generate_dir"].set_path("workspace")
        self.panel.path_selectors["ccs_executable"].set_path("tools/ccs.exe")
        self.panel.path_selectors["ccs_dss"].set_path("tools/dss.bat")

        with mock.patch("gui.widgets.config_panel.QMessageBox.warning") as warn:
            self.assertTrue(self.panel.validate())

        warn.assert_not_called()

    def test_error_state_cleared_on_next_validation(self):
        self.panel.load_config(make_config(self.tmp))
        with mock.patch("gui.widgets.config_panel.QMessageBox.warning"):
            self.assertFalse(self.panel.validate())

        self._create_required_paths()
        with mock.patch("gui.widgets.config_panel.QMessageBox.warning") as warn:
            self.assertTrue(self.panel.validate())

        warn.assert_not_called()
        self.assertEqual(self.panel.path_selectors["generate_dir"]
                         .path_edit.styleSheet(), "")


class MemoryTableLayoutTest(TempTestCase):
    """内存段表格：末列拉伸 + 空表占位提示"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        super().setUp()
        self.panel = ConfigPanel()
        self.addCleanup(self.panel.deleteLater)

    def test_last_column_stretches(self):
        self.assertTrue(self.panel.memory_table.horizontalHeader()
                        .stretchLastSection())

    def test_empty_hint_visible_then_hidden_after_add(self):
        self.assertFalse(self.panel.memory_empty_label.isHidden())

        self.panel.on_add_memory_segment()
        self.assertEqual(self.panel.memory_table.rowCount(), 1)
        self.assertTrue(self.panel.memory_empty_label.isHidden())

    def test_empty_hint_returns_after_removing_all_rows(self):
        self.panel.on_add_memory_segment()
        self.panel.memory_table.selectRow(0)

        with mock.patch("gui.widgets.config_panel.QMessageBox.warning"):
            self.panel.on_remove_memory_segment()

        self.assertEqual(self.panel.memory_table.rowCount(), 0)
        self.assertFalse(self.panel.memory_empty_label.isHidden())


class CollapsibleConfigGroupsTest(TempTestCase):
    """配置页过长：高级分组默认折叠，可展开"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        super().setUp()
        self.panel = ConfigPanel()
        self.addCleanup(self.panel.deleteLater)

    def test_memory_and_export_groups_collapsed_by_default(self):
        from gui.widgets.collapsible_group import CollapsibleGroupBox

        groups = {g.title_text: g for g in self.panel.findChildren(CollapsibleGroupBox)}
        self.assertIn("内存导出配置", groups)
        self.assertIn("导出时间点配置", groups)
        for title in ("内存导出配置", "导出时间点配置"):
            self.assertFalse(groups[title].is_expanded(), title)
            self.assertTrue(groups[title].content.isHidden(), title)

    def test_toggle_expands_and_collapses(self):
        from gui.widgets.collapsible_group import CollapsibleGroupBox

        group = next(g for g in self.panel.findChildren(CollapsibleGroupBox)
                     if g.title_text == "内存导出配置")
        group.toggle_button.setChecked(True)
        self.assertTrue(group.is_expanded())
        self.assertFalse(group.content.isHidden())

        group.toggle_button.setChecked(False)
        self.assertTrue(group.content.isHidden())


if __name__ == "__main__":
    unittest.main()
