import contextlib
import io
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "skills", "full-code-review", "scripts"))
import add_guidance as m  # noqa: E402


def test_normalize(tmp_path):
    assert m.normalize_repo_key("https://h/g/p.git") == "g--p"


def test_scaffold_and_append(tmp_path):
    d = str(Path(tmp_path) / "g")
    p1, created1 = m.add_note(d, "grp--proj", "first note")
    assert created1 is True
    p2, created2 = m.add_note(d, "grp--proj", "second note")
    assert created2 is False and p1 == p2
    text = Path(p1).read_text()
    assert text.count("# Review guidance:") == 1
    assert "first note" in text and "second note" in text


def test_main_with_repo_key(tmp_path):
    d = str(Path(tmp_path) / "g")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = m.main(["--note", "hi", "--sakura-guidance-dir", d, "--repo-key", "a--b"])
    assert rc == 0
    out = json.loads(buf.getvalue())
    assert out["repo_key"] == "a--b" and out["created"] is True
    assert Path(out["file"]).is_file()


def test_main_no_key_errors(tmp_path):
    d = str(Path(tmp_path) / "g")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        # git-root points at an empty dir with no origin -> unresolvable
        rc = m.main(["--note", "hi", "--sakura-guidance-dir", d, "--git-root", str(tmp_path)])
    assert rc == 2
    assert "error" in json.loads(buf.getvalue())


if __name__ == "__main__":
    import tempfile
    import traceback
    fails = 0
    for name in sorted(n for n in dict(globals()) if n.startswith("test_")):
        fn = globals()[name]
        if not callable(fn):
            continue
        with tempfile.TemporaryDirectory() as td:
            try:
                fn(Path(td))
                print("PASS", name)
            except Exception:
                fails += 1
                print("FAIL", name)
                traceback.print_exc()
    print("DONE fails=%d" % fails)
    sys.exit(1 if fails else 0)
