"""Tests for the making-videos skill's studio bookkeeping script."""
from __future__ import annotations

import datetime
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "making-videos" / "scripts"
STUDIO_PY = SCRIPTS / "studio.py"
TODAY = datetime.date.today().isoformat()


@pytest.fixture()
def env(tmp_path: Path) -> dict:
    return {
        "PATH": "/usr/bin:/bin",
        "HOME": str(tmp_path / "home"),
        "QUIRK_STUDIO": str(tmp_path / "studio"),
        "QUIRK_VIDEO_CACHE": str(tmp_path / "cache"),
    }


def run_studio(*args: object, env: dict) -> tuple[int, dict]:
    proc = subprocess.run(
        [sys.executable, str(STUDIO_PY), *map(str, args)],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    out = proc.stdout.strip()
    assert out, f"no stdout (rc={proc.returncode}): {proc.stderr}"
    return proc.returncode, json.loads(out)


def write_json(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload) if not isinstance(payload, str) else payload)
    return path


def new_project(env: dict, tmp_path: Path, slug: str = "demo", brief: object = None):
    extra: list = []
    if brief is not None:
        extra = ["--brief-json", write_json(tmp_path / f"{slug}-brief.json", brief)]
    return run_studio("project", "new", "--slug", slug, "--product", "acme", *extra, env=env)


def test_init_creates_studio_dirs(env, tmp_path):
    code, out = run_studio("init", env=env)
    assert code == 0
    studio = tmp_path / "studio"
    assert out["studio"] == str(studio)
    assert (studio / "videos").is_dir()
    assert (studio / "brands").is_dir()
    assert out["created"]
    code, again = run_studio("init", env=env)
    assert code == 0
    assert again["created"] == []


def test_project_new_creates_dated_folder_and_default_brief(env, tmp_path):
    code, out = new_project(env, tmp_path)
    assert code == 0
    project = Path(out["project"])
    assert project == tmp_path / "studio" / "videos" / f"{TODAY}-demo"
    assert project.is_dir()
    brief = json.loads(Path(out["brief"]).read_text())
    assert Path(out["brief"]) == project / "brief.json"
    assert brief["slug"] == "demo"
    assert brief["product"] == "acme"
    assert brief["aspects"] == ["16:9"]
    assert brief["cloud_allow"] == []
    assert brief["music"]["source"] == "none"
    assert brief["created"] == TODAY
    assert isinstance(brief["narration"], bool)


@pytest.mark.parametrize("length_s, narration", [(15, False), (20, False), (21, True), (90, True)])
def test_narration_default_follows_length(env, tmp_path, length_s, narration):
    code, out = new_project(env, tmp_path, brief={"title": "T", "length_s": length_s})
    assert code == 0
    brief = json.loads(Path(out["brief"]).read_text())
    assert brief["length_s"] == length_s
    assert brief["narration"] is narration
    assert brief["title"] == "T"


def test_brief_json_overrides_defaults(env, tmp_path):
    code, out = new_project(
        env,
        tmp_path,
        brief={
            "length_s": 60,
            "aspects": ["9:16"],
            "narration": False,
            "cloud_allow": ["pexels"],
            "music": {"source": "file", "path": "a.mp3"},
        },
    )
    assert code == 0
    brief = json.loads(Path(out["brief"]).read_text())
    assert brief["aspects"] == ["9:16"]
    assert brief["narration"] is False
    assert brief["cloud_allow"] == ["pexels"]
    assert brief["music"] == {"source": "file", "path": "a.mp3"}


def test_length_over_cap_fails_naming_cap(env, tmp_path):
    code, out = new_project(env, tmp_path, brief={"length_s": 200})
    assert code == 1
    assert "180" in out["error"]
    assert not list((tmp_path / "studio" / "videos").glob("*"))


def test_length_at_cap_is_allowed(env, tmp_path):
    code, _ = new_project(env, tmp_path, brief={"length_s": 180})
    assert code == 0


@pytest.mark.parametrize("slug", ["Bad Slug", "UPPER", "a_b", "../x", ""])
def test_bad_slug_fails(env, tmp_path, slug):
    code, out = new_project(env, tmp_path, slug=slug)
    assert code in (1, 2)
    assert "error" in out


def test_duplicate_project_fails(env, tmp_path):
    assert new_project(env, tmp_path)[0] == 0
    code, out = new_project(env, tmp_path)
    assert code == 1
    assert "exists" in out["error"]


def test_unknown_cloud_provider_fails_naming_it(env, tmp_path):
    code, out = new_project(env, tmp_path, brief={"length_s": 30, "cloud_allow": ["pexels", "bogus"]})
    assert code == 1
    assert "bogus" in out["error"]


def test_invalid_brief_json_fails(env, tmp_path):
    code, out = new_project(env, tmp_path, brief="{not json")
    assert code == 1
    assert "error" in out


def test_version_new_numbers_sequentially(env, tmp_path):
    project = Path(new_project(env, tmp_path)[1]["project"])
    code, v1 = run_studio("version", "new", "--project", project, env=env)
    assert code == 0
    assert v1["version"] == "v1"
    assert Path(v1["path"]) == project / "v1"
    assert list((project / "v1").iterdir()) == []
    code, v2 = run_studio("version", "new", "--project", project, env=env)
    assert code == 0
    assert v2["version"] == "v2"


def test_version_new_never_reuses_a_number(env, tmp_path):
    project = Path(new_project(env, tmp_path)[1]["project"])
    run_studio("version", "new", "--project", project, env=env)
    (project / "v3").mkdir()
    code, out = run_studio("version", "new", "--project", project, env=env)
    assert code == 0
    assert out["version"] == "v4"


def test_version_new_on_missing_project_fails(env, tmp_path):
    code, out = run_studio("version", "new", "--project", tmp_path / "nope", env=env)
    assert code == 1
    assert "error" in out
    assert not (tmp_path / "nope").exists()


BRAND = {
    "product": "acme",
    "colors": {"primary": "#112233"},
    "fonts": {"heading": {"family": "Inter", "files": []}},
    "voice": {"engine": "kokoro", "id": "af_heart"},
}


def test_brand_show_missing_returns_null(env, tmp_path):
    code, out = run_studio("brand", "show", "--product", "acme", env=env)
    assert code == 0
    assert out["brand"] is None
    assert out["path"] == str(tmp_path / "studio" / "brands" / "acme" / "brand.json")


def test_brand_save_unconfirmed_then_confirmed(env, tmp_path):
    src = write_json(tmp_path / "brand.json", {**BRAND, "confirmed": True})
    code, out = run_studio("brand", "save", "--product", "acme", "--file", src, env=env)
    assert code == 0
    assert out["confirmed"] is False
    saved = json.loads(Path(out["path"]).read_text())
    assert saved["confirmed"] is False
    code, shown = run_studio("brand", "show", "--product", "acme", env=env)
    assert shown["brand"]["colors"] == BRAND["colors"]
    assert shown["brand"]["confirmed"] is False

    code, out = run_studio("brand", "save", "--product", "acme", "--file", src, "--confirm", env=env)
    assert code == 0
    assert out["confirmed"] is True
    assert json.loads(Path(out["path"]).read_text())["confirmed"] is True


def test_brand_save_invalid_json_fails(env, tmp_path):
    src = write_json(tmp_path / "brand.json", "{oops")
    code, out = run_studio("brand", "save", "--product", "acme", "--file", src, env=env)
    assert code == 1
    assert "error" in out


@pytest.mark.parametrize("missing", ["product", "colors", "fonts", "voice"])
def test_brand_save_missing_key_fails(env, tmp_path, missing):
    brand = {k: v for k, v in BRAND.items() if k != missing}
    src = write_json(tmp_path / "brand.json", brand)
    code, out = run_studio("brand", "save", "--product", "acme", "--file", src, env=env)
    assert code == 1
    assert missing in out["error"]


def test_brand_save_missing_file_fails(env, tmp_path):
    code, out = run_studio("brand", "save", "--product", "acme", "--file", tmp_path / "none.json", env=env)
    assert code == 1
    assert "error" in out


def test_usage_error_is_one_json_object_exit_2(env):
    code, out = run_studio("project", "new", env=env)
    assert code == 2
    assert "error" in out


def test_common_constants():
    sys.path.insert(0, str(SCRIPTS))
    try:
        import _mv_common as _common
    finally:
        sys.path.remove(str(SCRIPTS))
    assert _common.HYPERFRAMES_VERSION == "0.8.185"
    assert _common.PLAYWRIGHT_VERSION.count(".") == 2
    assert set(_common.PROVIDER_KEY_ENV) == {"elevenlabs", "openai", "pexels", "pixabay", "freesound"}
    assert set(_common.SCRUB_ENV) == {"GEMINI_API_KEY", "GOOGLE_API_KEY", *_common.PROVIDER_KEY_ENV.values()}


def _common():
    sys.path.insert(0, str(SCRIPTS))
    try:
        import _mv_common as _common
    finally:
        sys.path.remove(str(SCRIPTS))
    return _common


def test_common_load_brief_and_log_call(env, tmp_path):
    common = _common()
    project = Path(new_project(env, tmp_path)[1]["project"])
    assert common.load_brief(project)["slug"] == "demo"
    with pytest.raises(FileNotFoundError):
        common.load_brief(tmp_path / "nope")
    common.log_call(project, {"a": 1})
    common.log_call(project, {"a": 2})
    lines = (project / "calls.jsonl").read_text().splitlines()
    assert [json.loads(line)["a"] for line in lines] == [1, 2]
    with pytest.raises(FileNotFoundError):
        common.log_call(tmp_path / "nope", {})
    assert not (tmp_path / "nope").exists()


def test_common_paths_honor_env(monkeypatch, tmp_path):
    common = _common()
    monkeypatch.setenv("QUIRK_STUDIO", str(tmp_path / "s"))
    monkeypatch.setenv("QUIRK_VIDEO_CACHE", str(tmp_path / "c"))
    assert common.studio_root() == tmp_path / "s"
    assert common.project_dir("x") == tmp_path / "s" / "videos" / "x"
    assert common.venv_python() == tmp_path / "c" / "venv" / "bin" / "python"
    monkeypatch.delenv("QUIRK_STUDIO")
    assert common.studio_root().name == "Studio"
