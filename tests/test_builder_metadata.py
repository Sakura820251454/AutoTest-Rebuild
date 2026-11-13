# -*- coding: utf-8 -*-
"""
构建器 .metadata 处理回归测试

覆盖：build_all 只在初始化构建前清理一次 .metadata，初始化构建后必须保留，
否则首个正式构建会触发 CCS 的 Clean-only build（需要 make.exe）而必然失败。
不调用真实 CCS，仅用桩验证目录生命周期。
"""

import unittest

from tests.helpers import TempTestCase, make_config
from src.builder import ProjectBuilder, BuildResult


class MetadataLifecycleTest(TempTestCase):

    def setUp(self):
        super().setUp()
        self.workspace = self.make_dir("workspace")
        # 旧元数据：应在初始化构建前被清掉
        self.make_dir("workspace", ".metadata")
        self.write_text("workspace/.metadata/old_marker", "stale")
        # 一个有效工程（只为让 find_projects 有结果）
        self.make_dir("workspace", "proj1")
        self.write_text("workspace/proj1/.project", "<projectDescription/>")
        # CCS 可执行文件存在性校验
        self.make_dir("tools")
        self.write_text("tools/ccs.exe", "")

        self.cfg = make_config(self.tmp)
        self.builder = ProjectBuilder(self.cfg)

        self.init_saw_stale = None
        self.formal_saw_metadata = None
        self.formal_saw_init_marker = None

    def _fake_init_build(self, project_path):
        meta = self.workspace / ".metadata"
        self.init_saw_stale = (meta / "old_marker").exists()
        # 模拟 CCS 初始化构建后创建新的 .metadata
        meta.mkdir(exist_ok=True)
        (meta / "init_marker").write_text("init", encoding="utf-8")

    def _fake_build_projects(self, projects):
        meta = self.workspace / ".metadata"
        self.formal_saw_metadata = meta.is_dir()
        self.formal_saw_init_marker = (meta / "init_marker").exists()
        return [BuildResult(project_name=p.name, out_file=None, success=True) for p in projects]

    def test_metadata_is_kept_after_init_build(self):
        self.builder._run_init_build = self._fake_init_build
        self.builder._build_projects = self._fake_build_projects

        results = self.builder.build_all()

        self.assertFalse(self.init_saw_stale, "初始化构建前应清理旧 .metadata")
        self.assertTrue(self.formal_saw_metadata, "初始化构建后必须保留 .metadata")
        self.assertTrue(self.formal_saw_init_marker, "初始化构建写入的 .metadata 不能被二次删除")
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].success)

    def test_metadata_is_not_deleted_twice(self):
        """回归保护：源码里不应再出现初始化构建后的第二次 rmtree"""
        import inspect
        from src import builder as builder_module

        src = inspect.getsource(builder_module.ProjectBuilder.build_all)
        self.assertEqual(src.count("rmtree(metadata_dir"), 1)


if __name__ == "__main__":
    unittest.main()
