import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree


SKILL = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL / "scripts"


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name) / "book"
        self.project.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, text):
        path = self.project / name
        path.write_text(text, encoding="utf-8")
        return path

    def plan(self, **extra):
        value = {
            "version": 2, "novelName": "test-book", "displayTitle": "Test Book",
            "author": "Tester", "language": "zh", "totalChapters": 1,
            "minWordsPerChapter": 2, "maxWordsPerChapter": 4,
            "status": "in_progress", "chapters": [],
        }
        value.update(extra)
        self.write("04-generation-plan.json", json.dumps(value, ensure_ascii=False))
        return value

    def chapter(self, n=1, body="甲乙", pov="A"):
        self.write("chapter-%02d.md" % n, "# 第 %02d 章：测试\n\n*(POV: %s)*\n\n%s\n" % (n, pov, body))

    def notes(self, n=1, meta=True):
        prefix = "```meta\nchapter: %d\npov: A\nday: D+0\n```\n\n" % n if meta else "# notes\n\n"
        self.write("chapter-%02d-notes.md" % n, prefix + "- action\n")

    def controls(self):
        self.write("00-outline.md", "- [x] 第 01 章：测试 — action\n")
        self.write("01-characters.md", "# Characters\n- Ch.01 演进：action\n")
        self.write("02-timeline.md", "| 章节 | 时间节点 | 时长 | 关键事件 | 结尾状态 |\n|---|---|---|---|---|\n| 第01章 | D+0 | 1h | action | safe |\n")
        self.write("03-global-notes.md", "| 配角姓名 | 上次出场章节 | 出场形式 | 活跃度 |\n|---|---|---|---|\n| B | 第 01 章 | 在场 | 🟢 |\n")

    def invoke(self, script, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPTS / script), *map(str, args)],
            text=True, capture_output=True, check=False,
        )

    def test_wordcount_bilingual_lower_and_upper_bounds(self):
        self.plan(language="zh", minWordsPerChapter=2, maxWordsPerChapter=3)
        self.chapter(body="甲")
        self.assertEqual(self.invoke("check_chapter_wordcount.py", self.project / "chapter-01.md").returncode, 1)
        self.chapter(body="甲乙丙")
        self.assertEqual(self.invoke("check_chapter_wordcount.py", self.project / "chapter-01.md").returncode, 0)
        self.chapter(body="甲乙丙丁戊")
        result = self.invoke("check_chapter_wordcount.py", self.project / "chapter-01.md", "--json")
        self.assertEqual(result.returncode, 1)
        self.assertTrue(json.loads(result.stdout)[0]["over_max"])

        self.plan(language="en", minWordsPerChapter=2, maxWordsPerChapter=3)
        self.chapter(body="one")
        self.assertEqual(self.invoke("check_chapter_wordcount.py", self.project / "chapter-01.md").returncode, 1)
        self.chapter(body="one two three")
        self.assertEqual(self.invoke("check_chapter_wordcount.py", self.project / "chapter-01.md").returncode, 0)
        self.chapter(body="one two three four")
        result = self.invoke("check_chapter_wordcount.py", self.project / "chapter-01.md", "--json")
        self.assertEqual(result.returncode, 1)
        self.assertTrue(json.loads(result.stdout)[0]["over_max"])

    def test_missing_meta_never_becomes_completed(self):
        self.plan(chapters=[{"chapterNumber": 1, "status": "draft", "wordCount": 0}])
        self.chapter()
        self.notes(meta=False)
        self.controls()
        result = self.invoke("sync_check.py", self.project, "--fix")
        self.assertNotEqual(result.returncode, 0)
        saved = json.loads((self.project / "04-generation-plan.json").read_text())
        self.assertNotEqual(saved["chapters"][0]["status"], "completed")

    def test_completed_plan_without_body_cannot_complete_book(self):
        self.plan(status="in_progress", chapters=[{"chapterNumber": 1, "status": "completed", "wordCount": 2}])
        self.notes()
        self.controls()
        self.invoke("sync_check.py", self.project, "--fix")
        saved = json.loads((self.project / "04-generation-plan.json").read_text())
        self.assertNotEqual(saved.get("status"), "completed")

    def test_rewriting_fix_preserves_rewriting_state(self):
        self.plan(chapters=[{"chapterNumber": 1, "status": "rewriting", "wordCount": 2, "retryCount": 1}])
        self.chapter()
        self.notes()
        self.controls()
        self.invoke("sync_check.py", self.project, "--fix")
        saved = json.loads((self.project / "04-generation-plan.json").read_text())
        self.assertEqual(saved["chapters"][0]["status"], "rewriting")
        self.assertNotEqual(saved.get("status"), "completed")

    def test_valid_project_fix_completes_only_after_clean_sync(self):
        self.plan(chapters=[{"chapterNumber": 1, "status": "draft", "wordCount": 0}])
        self.chapter()
        self.notes()
        self.controls()
        fixed = self.invoke("sync_check.py", self.project, "--fix")
        self.assertIn(fixed.returncode, (0, 1))
        clean = self.invoke("sync_check.py", self.project)
        self.assertEqual(clean.returncode, 0, clean.stdout + clean.stderr)
        saved = json.loads((self.project / "04-generation-plan.json").read_text())
        self.assertEqual(saved["chapters"][0]["status"], "completed")
        self.assertEqual(saved.get("status"), "completed")

    def test_finalize_rewrite_requires_valid_notes(self):
        self.plan(chapters=[{"chapterNumber": 1, "status": "rewriting", "wordCount": 2, "retryCount": 1}])
        self.chapter()
        self.notes()
        self.controls()
        result = self.invoke("sync_check.py", self.project, "--finalize-rewrite", "--chapter", 1, "--fix")
        self.assertIn(result.returncode, (0, 1))
        clean = self.invoke("sync_check.py", self.project)
        self.assertEqual(clean.returncode, 0, clean.stdout + clean.stderr)
        saved = json.loads((self.project / "04-generation-plan.json").read_text())
        self.assertEqual(saved["chapters"][0]["status"], "completed")

        self.plan(chapters=[{"chapterNumber": 1, "status": "rewriting", "wordCount": 2, "retryCount": 1}])
        self.notes(meta=False)
        self.controls()
        self.invoke("sync_check.py", self.project, "--finalize-rewrite", "--chapter", 1, "--fix")
        saved = json.loads((self.project / "04-generation-plan.json").read_text())
        self.assertEqual(saved["chapters"][0]["status"], "rewriting")

    def test_duplicate_chapter_numbers_reject_without_plan_write(self):
        self.plan(chapters=[
            {"chapterNumber": 1, "status": "planned"},
            {"chapterNumber": 1, "status": "planned"},
        ])
        before = (self.project / "04-generation-plan.json").read_bytes()
        result = self.invoke("sync_check.py", self.project, "--fix")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.project / "04-generation-plan.json").read_bytes(), before)

    def test_duplicate_body_filenames_reject_without_plan_write(self):
        self.plan(chapters=[{"chapterNumber": 1, "status": "planned"}])
        self.write("chapter-1.md", "# 第 1 章：重复\n\n*(POV: A)*\n\n甲乙\n")
        self.write("chapter-01.md", "# 第 01 章：重复\n\n*(POV: A)*\n\n甲乙\n")
        before = (self.project / "04-generation-plan.json").read_bytes()
        result = self.invoke("sync_check.py", self.project, "--fix")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.project / "04-generation-plan.json").read_bytes(), before)

    def test_partial_fix_cannot_complete_unchecked_broken_next_chapter(self):
        self.plan(totalChapters=2, chapters=[
            {"chapterNumber": 1, "status": "draft", "wordCount": 0},
            {"chapterNumber": 2, "status": "completed", "wordCount": 999},
        ])
        self.chapter(1)
        self.notes(1)
        self.write("chapter-02.md", "broken chapter\n")
        self.notes(2, meta=False)
        self.controls()
        self.invoke("sync_check.py", self.project, "--chapter", 1, "--fix")
        saved = json.loads((self.project / "04-generation-plan.json").read_text())
        self.assertNotEqual(saved.get("status"), "completed")

    def test_preflight_next_chapter_is_brief_and_notes_only(self):
        self.plan(totalChapters=2, chapters=[{"chapterNumber": 2, "pov": "A", "status": "planned"}])
        self.chapter(1, body="正文机密：不可带入")
        self.notes(1)
        self.write("00-outline.md", "## Briefs\n### 第 02 章：下一步\n- **POV**：A\n- **必须发生**：打开门\n")
        self.write("01-characters.md", "# Characters\n")
        self.write("02-timeline.md", "# Timeline\n")
        self.write("03-global-notes.md", "## 既成事实\n- 已知\n")
        result = self.invoke("preflight.py", self.project, 2, "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        packet = json.loads(result.stdout)
        self.assertIn("下一步", packet["brief"])
        self.assertIn("action", packet["prevNotes"])
        self.assertNotIn("正文机密", json.dumps(packet, ensure_ascii=False))

    def test_builtin_book_excludes_notes_and_has_valid_xml(self):
        self.plan(totalChapters=2, chapters=[
            {"chapterNumber": 1, "epubPath": "old-01.epub"},
            {"chapterNumber": 2, "epubPath": "old-02.epub"},
        ])
        self.chapter(1, body="甲乙")
        self.chapter(2, body="丙丁")
        self.notes(1)
        self.notes(2)
        output = self.project / "book.epub"
        result = self.invoke("export_epub.py", self.project, "--book", "--engine", "builtin", "--output", output)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        with zipfile.ZipFile(output) as archive:
            names = archive.namelist()
            self.assertFalse(any("notes" in name for name in names))
            self.assertIn("OEBPS/chapter-01.xhtml", names)
            for name in names:
                if name.endswith((".xml", ".xhtml", ".opf", ".ncx")):
                    ElementTree.fromstring(archive.read(name))
        saved = json.loads((self.project / "04-generation-plan.json").read_text())
        self.assertEqual(saved.get("bookEpubPath"), str(output))
        self.assertEqual([c["epubPath"] for c in saved["chapters"]], ["old-01.epub", "old-02.epub"])

        batch = self.project / "batch"
        result = self.invoke("export_epub.py", self.project, "--engine", "builtin", "--out", batch)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(sorted(p.name for p in batch.glob("*.epub")), ["chapter-01.epub", "chapter-02.epub"])


if __name__ == "__main__":
    unittest.main()
