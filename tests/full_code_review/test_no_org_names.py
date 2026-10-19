import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ROOTS = (REPO / "skills" / "full-code-review", REPO / "tests" / "full_code_review",
         REPO / "tests" / "fixtures" / "full-code-review")

# assembled from fragments so this file's own source never matches; the org and plugin
# names match as substrings (catching prefixed variants), the short plugin name only as a word
_NAMES = ["re" + "charge", "sak" + "ura", "source" + "bot"]
PATTERN = re.compile("|".join(_NAMES) + r"|\bk" + r"ai\b", re.IGNORECASE)


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


def test_pattern_catches_prefixed_and_bare_names():
    for sample in ("re" "charge_token", "re" "chargeapps.com", "sak" "ura:review", "k" "ai:review",
                   "the k" "ai plugin", "source" "bot-researcher"):
        assert PATTERN.search(sample), sample
    assert not PATTERN.search("kaizen and kaiju")
