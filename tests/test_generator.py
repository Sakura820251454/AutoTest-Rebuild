# -*- coding: utf-8 -*-
"""
generator 工程生成回归测试

覆盖：模板模式批量生成（每个源文件一个工程）、模板名读取与回退、工程名/产物名
在 .project/.cproject/.cdtbuild/.cdtproject 中的替换、目标目录已存在时的跳过与重建、
模板/源目录缺失、必备文件缺失、手动模式的工程校验。
全部使用合成模板与临时目录，不调用 CCS。

一旦我被更新务必更新我的开头注释以及所属文件夹的 README.md
"""

import shutil
import unittest
from pathlib import Path
from xml.etree import ElementTree

from tests.helpers import TempTestCase, make_config
from src.generator import ProjectGenerator
from src.exceptions import GeneratorError, SourceFileError, TemplateNotFoundError


def project_xml(name):
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<projectDescription>\n'
        f'\t<name>{name}</name>\n'
        '\t<comment>regression template</comment>\n'
        '\t<projects>\n'
        f'\t\t<project>{name}</project>\n'
        '\t</projects>\n'
        '</projectDescription>\n'
    )


def cproject_xml(name):
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<cproject>\n'
        '\t<storageModule moduleId="cdtBuildSystem">\n'
        f'\t\t<project id="{name}.com.ti.ccstudio" artifactName="{name}">\n'
        f'\t\t\t<configuration artifactName="{name}" name="Debug">\n'
        f'\t\t\t\t<option id="linkerID.OUTPUT_FILE" value="{name}.out"/>\n'
        f'\t\t\t\t<option id="linkerID.MAP_FILE" value="{name}.map"/>\n'
        '\t\t\t</configuration>\n'
        '\t\t</project>\n'
        '\t</storageModule>\n'
        '</cproject>\n'
    )


def cdtbuild_xml(name):
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<cdtbuild>\n'
        f'\t<configuration artifactName="{name}" name="Debug">\n'
        f'\t\t<fileInfo output="{name}.out" map="{name}.map"/>\n'
        '\t</configuration>\n'
        '</cdtbuild>\n'
    )


def cdtproject_xml(name):
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<cdtproject>\n'
        f'\t<projectName={name}/>\n'
        '</cdtproject>\n'
    )


class GeneratorBase(TempTestCase):

    def _config(self, mode="template"):
        return make_config(self.tmp, generation_mode=mode)

    def _write_template(self, name="tmpl_proj", with_project=True, with_cproject=True,
                        with_cdtbuild=False, with_cdtproject=False):
        self.make_dir("templates")
        if with_project:
            self.write_text("templates/.project", project_xml(name))
        if with_cproject:
            self.write_text("templates/.cproject", cproject_xml(name))
        if with_cdtbuild:
            self.write_text("templates/.cdtbuild", cdtbuild_xml(name))
        if with_cdtproject:
            self.write_text("templates/.cdtproject", cdtproject_xml(name))
        return self.tmp / "templates"

    def _write_source(self, file_name, content):
        self.make_dir("source")
        self.write_text(Path("source") / file_name, content)
        return self.tmp / "source" / file_name


class TemplateGenerationTest(GeneratorBase):

    def test_template_name_is_read_from_project_file(self):
        self._write_template("tmpl_proj")
        self._write_source("a.c", "int a;\n")

        generator = ProjectGenerator(self._config())

        self.assertEqual(generator.template_name, "tmpl_proj")

    def test_template_name_falls_back_to_directory_name(self):
        self.make_dir("templates")

        generator = ProjectGenerator(self._config())

        self.assertEqual(generator.template_name, "templates")

    def test_generates_one_project_per_source_file(self):
        self._write_template()
        self._write_source("alpha.c", "/* alpha */\n")
        self._write_source("beta.s", "; beta\n")

        results = ProjectGenerator(self._config()).generate()

        self.assertEqual([r.project_name for r in results], ["alpha", "beta"])
        self.assertTrue(all(r.success for r in results))
        self.assertTrue((self.tmp / "workspace" / "alpha" / "alpha.c").is_file())
        self.assertTrue((self.tmp / "workspace" / "beta" / "beta.s").is_file())
        project_text = (self.tmp / "workspace" / "alpha" / ".project").read_text(encoding="utf-8")
        self.assertIn("<name>alpha</name>", project_text)

    def test_source_file_content_is_copied_verbatim(self):
        self._write_template()
        content = "int main(void) { return 42; }\n"
        self._write_source("main_case.c", content)

        ProjectGenerator(self._config()).generate()

        copied = self.tmp / "workspace" / "main_case" / "main_case.c"
        self.assertEqual(copied.read_text(encoding="utf-8"), content)

    def test_source_file_order_is_deterministic(self):
        self._write_template()
        for name in ["z.c", "a.asm", "m.s"]:
            self._write_source(name, "x\n")

        results = ProjectGenerator(self._config()).generate()

        self.assertEqual([r.project_name for r in results], ["a", "m", "z"])

    def test_all_project_reference_forms_are_replaced(self):
        self._write_template(with_cdtbuild=True, with_cdtproject=True)
        self._write_source("case_a.c", "int x;\n")

        results = ProjectGenerator(self._config()).generate()

        self.assertTrue(results[0].success)
        project_dir = self.tmp / "workspace" / "case_a"
        texts = {
            name: (project_dir / name).read_text(encoding="utf-8")
            for name in [".project", ".cproject", ".cdtbuild", ".cdtproject"]
        }
        for name, text in texts.items():
            self.assertNotIn("tmpl_proj", text, name)
        self.assertIn("<name>case_a</name>", texts[".project"])
        self.assertIn("<project>case_a</project>", texts[".project"])
        self.assertIn('artifactName="case_a"', texts[".cproject"])
        self.assertIn('"case_a.out"', texts[".cproject"])
        self.assertIn('"case_a.map"', texts[".cproject"])
        self.assertIn("case_a.com.ti", texts[".cproject"])
        self.assertIn('artifactName="case_a"', texts[".cdtbuild"])
        self.assertIn('"case_a.map"', texts[".cdtbuild"])
        self.assertIn("projectName=case_a", texts[".cdtproject"])

    def test_template_name_with_regex_metacharacters_is_replaced_literally(self):
        self._write_template("tmpl.proj+v1")
        self._write_source("x.c", "int x;\n")

        ProjectGenerator(self._config()).generate()

        project_text = (self.tmp / "workspace" / "x" / ".project").read_text(encoding="utf-8")
        self.assertIn("<name>x</name>", project_text)
        self.assertNotIn("tmpl.proj+v1", project_text)

    def test_project_name_with_space_and_chinese_is_used_verbatim(self):
        self._write_template()
        self._write_source("测试 case.c", "int x;\n")

        results = ProjectGenerator(self._config()).generate()

        self.assertTrue(results[0].success)
        project_dir = self.tmp / "workspace" / "测试 case"
        self.assertTrue((project_dir / "测试 case.c").is_file())
        project_text = (project_dir / ".project").read_text(encoding="utf-8")
        self.assertIn("<name>测试 case</name>", project_text)


class ProjectNameEscapingTest(GeneratorBase):
    """工程名含 XML 特殊字符时仍要产出合法 XML"""

    def _copy_template(self, dest_name):
        template = self._write_template(with_cdtbuild=True)
        project_dir = self.tmp / "copied" / dest_name
        project_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(str(template), str(project_dir))
        return project_dir

    def test_source_file_with_ampersand_generates_parsable_project(self):
        self._write_template()
        self._write_source("a&b.c", "int x;\n")

        results = ProjectGenerator(self._config()).generate()

        self.assertTrue(results[0].success)
        project_dir = results[0].project_dir
        self.assertTrue((project_dir / "a&b.c").is_file())
        project_text = (project_dir / ".project").read_text(encoding="utf-8")
        self.assertIn("<name>a&amp;b</name>", project_text)
        ElementTree.parse(str(project_dir / ".project"))

    def test_special_characters_are_escaped_and_xml_parses(self):
        cases = [
            ("<x>", "&lt;x&gt;"),
            ('a"b', "a&quot;b"),
            ("a'b", "a'b"),
            ("a&b", "a&amp;b"),
        ]
        for index, (name, escaped) in enumerate(cases):
            with self.subTest(name=name):
                project_dir = self._copy_template(f"p{index}")

                ProjectGenerator(self._config())._replace_project_name(project_dir, name)

                project_text = (project_dir / ".project").read_text(encoding="utf-8")
                self.assertIn(f"<name>{escaped}</name>", project_text)
                self.assertNotIn("tmpl_proj", project_text)
                ElementTree.parse(str(project_dir / ".project"))
                ElementTree.parse(str(project_dir / ".cproject"))
                cproject_text = (project_dir / ".cproject").read_text(encoding="utf-8")
                self.assertIn(f'artifactName="{escaped}"', cproject_text)

    def test_existing_entities_are_not_double_escaped(self):
        self._write_template()
        self.write_text("templates/.project",
                        project_xml("tmpl_proj").replace("regression template", "R&amp;D"))
        self._write_source("case_a.c", "int x;\n")

        ProjectGenerator(self._config()).generate()

        project_text = (self.tmp / "workspace" / "case_a" / ".project").read_text(encoding="utf-8")
        self.assertIn("R&amp;D", project_text)
        self.assertNotIn("R&amp;amp;D", project_text)

    def test_broken_template_project_is_reported_as_failure(self):
        self._write_template()
        self.write_text("templates/.project",
                        '<projectDescription>\n\t<name>tmpl_proj</name>\n</projectDescription\n')
        self._write_source("case_a.c", "int x;\n")

        results = ProjectGenerator(self._config()).generate()

        self.assertFalse(results[0].success)
        self.assertIn("XML", results[0].error)


class ExistingTargetTest(GeneratorBase):

    def test_existing_project_is_skipped_when_clean_false(self):
        self._write_template()
        self._write_source("case_a.c", "int x;\n")
        target = self.make_dir("workspace", "case_a")
        marker = target / "marker.txt"
        marker.write_text("keep", encoding="utf-8")

        results = ProjectGenerator(self._config()).generate(clean=False)

        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].success)
        self.assertIn("跳过", results[0].error)
        self.assertTrue(marker.is_file())
        self.assertFalse((target / "case_a.c").exists())

    def test_existing_project_is_recreated_when_clean_true(self):
        self._write_template()
        self._write_source("case_a.c", "int x;\n")
        target = self.make_dir("workspace", "case_a")
        marker = target / "marker.txt"
        marker.write_text("stale", encoding="utf-8")

        results = ProjectGenerator(self._config()).generate(clean=True)

        self.assertTrue(results[0].success)
        self.assertFalse(marker.exists())
        self.assertTrue((target / "case_a.c").is_file())


class PreconditionsTest(GeneratorBase):

    def test_missing_template_dir_raises(self):
        self.make_dir("source")

        with self.assertRaises(TemplateNotFoundError):
            ProjectGenerator(self._config()).generate()

    def test_missing_source_dir_raises(self):
        self._write_template()

        with self.assertRaises(SourceFileError):
            ProjectGenerator(self._config()).generate()

    def test_missing_cproject_raises(self):
        self._write_template(with_cproject=False)
        self.make_dir("source")

        with self.assertRaises(GeneratorError) as ctx:
            ProjectGenerator(self._config()).generate()

        self.assertEqual(ctx.exception.error_code, 2004)
        self.assertIn(".cproject", str(ctx.exception))

    def test_no_source_files_returns_empty_list(self):
        self._write_template()
        self.make_dir("source")

        results = ProjectGenerator(self._config()).generate()

        self.assertEqual(results, [])
        self.assertTrue((self.tmp / "workspace").is_dir())


class ManualModeTest(GeneratorBase):

    def test_valid_and_invalid_projects_are_flagged(self):
        self.make_dir("workspace", "good")
        self.write_text("workspace/good/.project", project_xml("good"))
        self.write_text("workspace/good/.cproject", cproject_xml("good"))
        self.make_dir("workspace", "bad")
        self.write_text("workspace/bad/.project", project_xml("bad"))

        results = ProjectGenerator(self._config("manual")).generate()

        by_name = {r.project_name: r for r in results}
        self.assertEqual(sorted(by_name), ["bad", "good"])
        self.assertTrue(by_name["good"].success)
        self.assertIsNone(by_name["good"].source_file)
        self.assertFalse(by_name["bad"].success)
        self.assertEqual(by_name["bad"].error, "工程验证失败")

    def test_empty_generate_dir_raises(self):
        self.make_dir("workspace")

        with self.assertRaises(GeneratorError) as ctx:
            ProjectGenerator(self._config("manual")).generate()

        self.assertEqual(ctx.exception.error_code, 2005)

    def test_missing_generate_dir_raises(self):
        with self.assertRaises(SourceFileError):
            ProjectGenerator(self._config("manual")).generate()


if __name__ == "__main__":
    unittest.main()
