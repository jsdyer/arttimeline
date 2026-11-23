import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from build import ROOT, build, metadata, validate_collection


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        shutil.copytree(ROOT / "web", self.root / "web")
        shutil.copyfile(ROOT / "tool.json", self.root / "tool.json")
        shutil.copyfile(ROOT / "README.md", self.root / "README.md")

    def edit(self, **changes):
        tool = json.loads((self.root / "tool.json").read_text())
        tool.update(changes)
        (self.root / "tool.json").write_text(json.dumps(tool))

    def test_build_is_scoped_to_web_and_escapes_metadata(self):
        (self.root / "private.txt").write_text("must not publish")
        self.edit(title='<img src=x onerror="bad()">')
        build(self.root)
        page = (self.root / "dist/index.html").read_text()
        self.assertIn('&lt;img', page)
        self.assertNotIn('<img', page)
        self.assertNotIn('{{', page)
        self.assertIn('href="./style.css"', page)
        self.assertFalse((self.root / "dist/private.txt").exists())
        self.assertTrue((self.root / "dist/.nojekyll").exists())

    def test_reporting_is_scoped_to_initialized_coolcode_tools(self):
        for owner, slug, enabled in [
            ("jsdyer", "coolcode-tool-template", False),
            ("another-owner", "my-tool", False),
            ("jsdyer", "my-tool", True),
        ]:
            with self.subTest(owner=owner, slug=slug):
                self.edit(id=slug, url=f"/{slug}/", source=f"https://github.com/{owner}/{slug}")
                build(self.root)
                page = (self.root / "dist/index.html").read_text()
                self.assertEqual('/assets/tool-metrics.js' in page, enabled)
                self.assertEqual(f'https://coolcode.ca/report/?tool={slug}' in page, enabled)
                self.assertNotIn("{{", page)

    def test_opening_collection_can_expand_without_a_fixed_count(self):
        path = self.root / "web/data/collection.json"
        data = json.loads(path.read_text())
        previous = len(data["records"])
        item = dict(data["records"][0])
        item.update(id=999999, key="met:999999")
        data["records"].append(item)
        path.write_text(json.dumps(data))
        self.assertEqual(len(validate_collection(self.root)["records"]), previous + 1)

    def test_image_without_public_domain_permission_is_rejected(self):
        path = self.root / "web/data/collection.json"
        data = json.loads(path.read_text())
        record = next(r for r in data["records"] if r["image"])
        record["publicDomain"] = False
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "public-domain"):
            build(self.root)

    def test_invalid_paging_and_duplicate_identity_are_rejected(self):
        path = self.root / "web/config.json"
        config = json.loads(path.read_text())
        config["pageSize"] = 0
        path.write_text(json.dumps(config))
        with self.assertRaisesRegex(ValueError, "pageSize"):
            validate_collection(self.root)
        config["pageSize"] = 12
        path.write_text(json.dumps(config))
        path = self.root / "web/data/collection.json"
        data = json.loads(path.read_text())
        data["records"].append(data["records"][0])
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            validate_collection(self.root)

    def test_url_matches_tool_id(self):
        self.edit(url="/different/")
        with self.assertRaises(ValueError): metadata(self.root)

    def test_requires_a_source_sentence_and_a_guide_note(self):
        (self.root / "README.md").write_text("# A tool")
        with self.assertRaisesRegex(ValueError, "README note"):
            metadata(self.root)
        self.edit(data_info={"mode": "local", "detail": ""})
        with self.assertRaisesRegex(ValueError, "homepage card"):
            metadata(self.root)

    def test_browser_access_is_explicit(self):
        self.edit(access="install")
        with self.assertRaisesRegex(ValueError, "immediately usable"):
            metadata(self.root)

    def test_failed_build_keeps_existing_output(self):
        build(self.root)
        existing = (self.root / "dist/index.html").read_bytes()
        self.edit(source="javascript:bad()")
        with self.assertRaises(ValueError): build(self.root)
        self.assertEqual((self.root / "dist/index.html").read_bytes(), existing)


if __name__ == "__main__": unittest.main()
