import contextlib
import io
import json

import review_memory as m

FP = "ab" * 32


def _record(repo, findings):
    return {"schemaVersion": 1, "updated_at": 1, "snapshot": {
        "identity": {"repo": repo, "target": "change", "number": "1"}, "started_at": 1,
        "file_hashes": {}, "findings": [
            {"fingerprint": FP[:-2] + "%02d" % i, "dimension": dim, "file": "a.py", "note": "",
             "disposition": disp, "seat": seat} for i, (dim, disp, seat) in enumerate(findings)]}}


def _write(state, name, value):
    path = state / "quirk" / "review-memory" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) if isinstance(value, dict) else value)


def _stats(argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = m.main(["stats"] + argv)
    return rc, json.loads(buf.getvalue())


def test_compute_stats_groups_both_seat_vocabularies_and_sorts_by_dismiss_rate():
    records = [_record("h/p", [("db", "ignore", "reviewer"), ("db", "fix", "author"),
                               ("comments", "ignore", "author"), ("comments", "ignore", "reviewer"),
                               ("correctness", "later", "reviewer"), ("correctness", "detail", "author"),
                               ("correctness", "none", "author")])]
    result = m.compute_stats(records)
    assert result["records"] == 1
    assert result["lenses"] == [
        {"id": "comments", "kept": 0, "dismissed": 2, "undecided": 0, "dismiss_rate": 1.0},
        {"id": "db", "kept": 1, "dismissed": 1, "undecided": 0, "dismiss_rate": 0.5},
        {"id": "correctness", "kept": 2, "dismissed": 0, "undecided": 1, "dismiss_rate": 0.0},
    ]


def test_stats_cli_filters_by_repo_and_skips_unreadable_records(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    monkeypatch.setattr(m, "_repo_identity", lambda repo: ("h/p", []))
    _write(tmp_path, "one.json", _record("h/p", [("db", "ignore", "reviewer")]))
    _write(tmp_path, "other.json", _record("h/q", [("db", "fix", "author")]))
    _write(tmp_path, "broken.json", "{not json")
    rc, result = _stats(["--repo", str(tmp_path)])
    assert rc == 0 and result["records"] == 1
    assert result["lenses"] == [{"id": "db", "kept": 0, "dismissed": 1, "undecided": 0, "dismiss_rate": 1.0}]
    assert any("broken.json" in w for w in result["warnings"])
    rc, result = _stats(["--all"])
    assert result["records"] == 2


def test_empty_ledger_reports_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "missing"))
    rc, result = _stats(["--all"])
    assert rc == 0 and result == {"lenses": [], "records": 0, "warnings": []}
