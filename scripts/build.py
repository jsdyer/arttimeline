#!/usr/bin/env python3
"""Build a browser tool using Python's standard library; no network required."""
from html import escape
import json
from pathlib import Path
import re
import shutil
import tempfile
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def metadata(root=ROOT):
    tool = json.loads((root / "tool.json").read_text(encoding="utf-8"))
    required = {"id", "title", "description", "category", "tags", "icon", "url", "source", "hosting", "access", "data_info"}
    if not isinstance(tool, dict) or set(tool) != required:
        raise ValueError("tool.json has missing or unknown fields")
    for key in required - {"tags", "data_info"}:
        if not isinstance(tool[key], str) or not tool[key].strip():
            raise ValueError(f"tool.json: {key} must be a nonempty string")
    if not SLUG.fullmatch(tool["id"]) or tool["url"] != f'/{tool["id"]}/' or tool["hosting"] != "project":
        raise ValueError("Use a lowercase tool ID, matching /id/ URL and project hosting")
    if not isinstance(tool["tags"], list) or not all(isinstance(t, str) and t.strip() for t in tool["tags"]):
        raise ValueError("tags must be an array of nonempty strings")
    if tool["access"] != "browser":
        raise ValueError("This starter produces an immediately usable browser tool; use access: browser")
    info = tool["data_info"]
    if (not isinstance(info, dict) or info.get("mode") not in ("snapshot", "live", "local", "reference", "mixed")
            or not isinstance(info.get("detail"), str) or not info["detail"].strip()):
        raise ValueError("Describe the tool's inputs for its homepage card in data_info")
    guide = (root / "README.md").read_text(encoding="utf-8")
    begin, end = "<!-- coolcode:guide -->", "<!-- /coolcode:guide -->"
    if guide.count(begin) != 1 or guide.count(end) != 1 or not guide.partition(begin)[2].partition(end)[0].strip() or guide.index(begin) > guide.index(end):
        raise ValueError("Include a practical README note between the coolcode:guide markers")
    source = urlsplit(tool["source"])
    if source.scheme != "https" or not source.hostname or source.username is not None or any(c.isspace() for c in tool["source"]) or "\\" in tool["source"]:
        raise ValueError("source must be an HTTPS URL without credentials or whitespace")
    return tool


def validate_collection(root=ROOT):
    config = json.loads((root / "web/config.json").read_text())
    if not isinstance(config.get("presets"), list) or not all(isinstance(x, str) and x.strip() for x in config["presets"]):
        raise ValueError("presets must be a list of search strings")
    if type(config.get("pageSize")) is not int or not 1 <= config["pageSize"] <= 100:
        raise ValueError("pageSize must be between 1 and 100")
    for field in ("metObjectIds", "aicObjectIds"):
        ids = config.get("baseline", {}).get(field)
        if not isinstance(ids, list) or not all(type(i) is int and i > 0 for i in ids) or len(set(ids)) != len(ids):
            raise ValueError("Baseline artwork IDs must be positive and unique per provider")
    capture = json.loads((root / "web/data/collection.json").read_text())
    records = capture.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("Opening collection must contain records")
    keys = set()
    for record in records:
        if record.get("provider") not in ("met", "aic") or type(record.get("id")) is not int or record["id"] <= 0:
            raise ValueError("Invalid museum artwork identity")
        if record.get("key") != f"{record['provider']}:{record['id']}" or record["key"] in keys:
            raise ValueError("Duplicate or invalid museum artwork key")
        keys.add(record["key"])
        for field in ("title", "artist", "date", "source", "api", "retrievedAt"):
            if not isinstance(record.get(field), str) or not record[field]:
                raise ValueError(f"Missing artwork {field}")
        for field in ("start", "end"):
            if record.get(field) is not None and type(record[field]) is not int:
                raise ValueError("Date bounds must be integer years or null")
        for field in ("source", "api", "retrievedFrom"):
            value = record.get(field)
            if value and (urlsplit(value).scheme != "https" or urlsplit(value).username):
                raise ValueError("Museum evidence URLs must be HTTPS")
        if record.get("image"):
            host = urlsplit(record["image"]).hostname
            if record.get("publicDomain") is not True or host not in ("images.metmuseum.org", "www.artic.edu") or urlsplit(record["image"]).scheme != "https":
                raise ValueError("Images require explicit public-domain status and a museum host")
    return capture


def build(root=ROOT):
    tool = metadata(root)
    validate_collection(root)
    output = root / "dist"
    if output.is_symlink():
        raise ValueError("dist must not be a symlink")
    web = root / "web"
    if web.is_symlink() or any(p.is_symlink() for p in web.rglob("*")):
        raise ValueError("web/ must not contain symlinks")
    with tempfile.TemporaryDirectory(prefix="coolcode-tool-") as temporary:
        stage = Path(temporary) / "site"
        shutil.copytree(web, stage)
        index = stage / "index.html"
        page = index.read_text(encoding="utf-8")
        for token, key in {"TITLE": "title", "DESCRIPTION": "description", "TOOL_ID": "id", "SOURCE_URL": "source"}.items():
            placeholder = "{{" + token + "}}"
            if placeholder not in page:
                raise ValueError(f"Missing template placeholder: {placeholder}")
            page = page.replace(placeholder, escape(tool[key], quote=True))
        slug = tool["id"]
        on_coolcode = (
            slug != "coolcode-tool-template"
            and tool["source"].rstrip("/") == f"https://github.com/jsdyer/{slug}"
        )
        reporting = {
            "{{VISIT_COUNTER}}": '<script defer src="/assets/tool-metrics.js" referrerpolicy="no-referrer"></script>',
            "{{ISSUE_LINK}}": f'<a href="https://coolcode.ca/report/?tool={slug}" referrerpolicy="no-referrer">Report an issue</a>',
        }
        for placeholder, markup in reporting.items():
            if placeholder not in page:
                raise ValueError(f"Missing template placeholder: {placeholder}")
            page = page.replace(placeholder, markup if on_coolcode else "")
        if re.search(r"\{\{[A-Z_]+\}\}", page):
            raise ValueError("Unresolved template placeholder in web/index.html")
        index.write_text(page, encoding="utf-8")
        (stage / ".nojekyll").touch()
        if output.exists():
            shutil.rmtree(output)
        shutil.copytree(stage, output)
    print(f'Built dist/ for {tool["id"]}')


if __name__ == "__main__":
    try:
        build()
    except (OSError, ValueError) as exc:
        raise SystemExit(f"Build failed: {exc}")
