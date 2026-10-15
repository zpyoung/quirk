import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ROOTS = (REPO / "skills" / "full-code-review", REPO / "tests" / "full_code_review")

# assembled from fragments so this file's own source never matches
_NAMES = ["re" + "charge", "re" + "chargeapps", "sak" + "ura", "source" + "bot"]
PATTERN = re.compile(r"\b(%s)\b|\bk" r"ai:" % "|".join(_NAMES), re.IGNORECASE)


def test_no_org_or_origin_plugin_names_ship_with_the_skill():
    hits = []
    for root in ROOTS:
        for path in sorted(root.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for number, line in enumerate(text.splitlines(), 1):
                if PATTERN.search(line):
                    hits.append("%s:%d: %s" % (path.relative_to(REPO), number, line.strip()[:120]))
    assert hits == []
