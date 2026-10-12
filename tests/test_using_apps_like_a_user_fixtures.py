"""Darwin-only integration suite: drives likeuser.py as a subprocess against the real fixtures.

Opt in with LIKEUSER_FIXTURE_TESTS=1. The suite takes over the desktop (windows open, focus
moves, the pointer is warped once), so a plain `pytest` skips every test here.

Each row of the fixture table in the tech spec has two runs. The normal run must satisfy the
row's assertion; the faulted run, with the row's LIKEUSER_FAULT value (or, for the save-sheet
rows, a control run that skips the final Save), must violate the same assertion. A scenario
function returns the assertion's outcome instead of asserting it, so one helper can check
"normal holds and faulted breaks" and prove each test can see the defect it guards.

Fixture state is read from each fixture's own state file or `/hits`, never from the driver's
report. No LIKEUSER_FAKE_DESKTOP: the desktop is the real one.

Native zero-opacity row: the model-side visibility check cannot be scripted for a native app,
so the row asserts the control is in the tree and that clicking it yields NO_EFFECT or
NOT_VISIBLE, never OBSERVED.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "skills" / "using-apps-like-a-user" / "scripts"
LIKEUSER = SCRIPTS / "likeuser.py"
FIXTURES = REPO / "tests" / "fixtures" / "using-apps-like-a-user"
WEB_SERVER = FIXTURES / "web" / "server.py"
ELECTRON_DIR = FIXTURES / "electron"
NATIVE_BUILD = FIXTURES / "native" / "build.sh"
NATIVE_BUNDLE = "dev.quirk.uala.fixture"
ELECTRON_DEFAULTS = "com.github.Electron"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import _desktop  # noqa: E402
import _effects  # noqa: E402

OPT_IN = os.environ.get("LIKEUSER_FIXTURE_TESTS") == "1"
pytestmark = pytest.mark.skipif(
    not (OPT_IN and sys.platform == "darwin"),
    reason="set LIKEUSER_FIXTURE_TESTS=1 on macOS to run the desktop fixture suite",
)


def _have(*tools: str) -> bool:
    return all(shutil.which(t) is not None for t in tools)


_HAVE_NATIVE_DRIVER = _have("cua-driver") or _have("orca")
needs_web = pytest.mark.skipif(not _have("playwright-cli"), reason="playwright-cli not on PATH")
needs_electron = pytest.mark.skipif(
    not (_have("playwright-cli", "pnpm") and _HAVE_NATIVE_DRIVER),
    reason="needs playwright-cli, pnpm, and cua-driver or orca on PATH",
)
needs_native = pytest.mark.skipif(
    not (_have("swiftc") and _HAVE_NATIVE_DRIVER),
    reason="needs swiftc and cua-driver or orca on PATH",
)


def poll(read: Callable[[], Any], done: Callable[[Any], bool], timeout: float = 6.0,
         interval: float = 0.2) -> Any:
    """Call `read` until `done(value)` is true or `timeout` elapses; return the last value."""
    deadline = time.monotonic() + timeout
    value = read()
    while not done(value) and time.monotonic() < deadline:
        time.sleep(interval)
        value = read()
    return value


@dataclass
class Outcome:
    """Whether a row's assertion held, with the evidence a failure message needs."""

    held: bool
    evidence: Dict[str, Any] = field(default_factory=dict)


def assert_detects(scenario: Callable[[Path, Optional[str]], Outcome], tmp_path: Path,
                   fault: Optional[str]) -> None:
    """Assert the scenario holds on a normal run and breaks on the faulted (or control) run."""
    normal = scenario(tmp_path / "normal", None)
    assert normal.held, f"normal run did not satisfy the assertion: {normal.evidence}"
    faulted = scenario(tmp_path / "faulted", fault or "control")
    assert not faulted.held, (
        f"the {fault or 'control'} run still satisfied the assertion, so the test cannot see "
        f"the defect: {faulted.evidence}"
    )


class Cli:
    """One working copy of likeuser.py: its own state root, lock path, and optional fault."""

    def __init__(self, tmp: Path, fault: Optional[str] = None,
                 env: Optional[Dict[str, str]] = None) -> None:
        tmp.mkdir(parents=True, exist_ok=True)
        self.cwd = tmp / "cwd"
        self.cwd.mkdir()
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("LIKEUSER_")}
        self.env["LIKEUSER_STATE_ROOT"] = str(tmp / "state")
        self.env["LIKEUSER_LOCK_PATH"] = str(tmp / "desktop.lock")
        if fault:
            self.env["LIKEUSER_FAULT"] = fault
        self.env.update(env or {})
        self.run_id: Optional[str] = None
        self.run_dir: Optional[Path] = None
        self.latest = 0

    def call(self, *argv: str, stdin: Optional[str] = None,
             timeout: float = 180.0) -> Tuple[int, dict]:
        """Run one verb; return (exit code, the single JSON object it printed)."""
        proc = subprocess.run(
            [sys.executable, str(LIKEUSER), *argv], input=stdin, capture_output=True, text=True,
            cwd=str(self.cwd), env=self.env, timeout=timeout,
        )
        lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
        try:
            out = json.loads(lines[-1])
        except (IndexError, ValueError):
            out = {"ok": False, "error": "unparseable_output", "stdout": proc.stdout,
                   "stderr": proc.stderr}
        return proc.returncode, out

    def begin(self, target: str, surface: str, owner: str, *flags: str) -> dict:
        """Open a run; the verb must exit 0."""
        code, out = self.call("begin", "--target", target, "--surface", surface, "--owner", owner,
                              *flags)
        assert code == 0, out
        self.run_id = out["run_id"]
        self.run_dir = Path(out["run_dir"])
        return out

    def goal(self, goal_id: str = "g1", title: str = "exercise the fixture") -> None:
        code, out = self.call("goal", "--run", self.run_id, "--id", goal_id, "--title-stdin",
                              stdin=title)
        assert code == 0, out

    def observe(self, goal_id: str = "g1") -> dict:
        """Observe with a screenshot; the new observation becomes the latest one."""
        code, out = self.call("observe", "--run", self.run_id, "--goal", goal_id)
        assert code == 0, out
        self.latest = out["observation"]["observation_id"]
        return out

    def _sidecar(self, oid: int) -> dict:
        return json.loads((self.run_dir / f"obs-{oid}.json").read_text())

    def names(self) -> Dict[str, str]:
        """Accessible names of the latest observation, keyed by ref."""
        return self._sidecar(self.latest)["names"]

    def ref(self, name: str) -> str:
        """The ref in the latest observation whose accessible name is exactly `name`."""
        sidecar = self._sidecar(self.latest)
        for ref in sidecar["refs"]:
            if sidecar["names"].get(ref) == name:
                return ref
        raise LookupError(f"no element named {name!r} in observation {self.latest}")

    def has(self, name: str) -> bool:
        return name in self.names().values()

    def act(self, kind: str, *, name: Optional[str] = None, ref: Optional[str] = None,
            obs: Optional[int] = None, expect: str = "tree", gate: Optional[str] = None,
            foreground: bool = False, target_name: Optional[str] = None,
            stdin: Optional[str] = None) -> dict:
        """Perform one action on the element named `name` (or `ref`); return the act output."""
        target = ref if ref is not None else self.ref(name)
        argv = ["act", "--run", self.run_id, "--obs", str(self.latest if obs is None else obs),
                "--action", kind, "--ref", target, "--expect", expect]
        if gate:
            argv += ["--gate", gate]
        if foreground:
            argv.append("--foreground")
        if target_name:
            argv += ["--target-name", target_name]
        if stdin is not None:
            argv.append("--text-stdin")
        code, out = self.call(*argv, stdin=stdin)
        assert code == 0, out
        self.latest = out["latest_observation_id"]
        return out

    def act_key(self, kind: str, key: str, *, target_name: str, foreground: bool = False) -> dict:
        argv = ["act", "--run", self.run_id, "--obs", str(self.latest), "--action", kind,
                "--key", key, "--target-name", target_name, "--expect", "any"]
        if foreground:
            argv.append("--foreground")
        code, out = self.call(*argv)
        assert code == 0, out
        self.latest = out["latest_observation_id"]
        return out

    def findings(self) -> List[dict]:
        """Every finding registered so far, read from the run's own file."""
        return json.loads((self.run_dir / "run.json").read_text())["findings"]

    def end(self) -> Optional[dict]:
        """Close the run if one is open; safe to call twice."""
        if self.run_id is None:
            return None
        _, out = self.call("end", "--run", self.run_id)
        return out


@contextmanager
def open_run(cli: Cli, target: str, surface: str, owner: str, *flags: str) -> Iterator[Cli]:
    """Begin a run with one goal and always end it."""
    cli.begin(target, surface, owner, *flags)
    try:
        cli.goal()
        yield cli
    finally:
        cli.end()


class WebFixture:
    """The web fixture server on a free port; `/hits` is its state."""

    def __init__(self) -> None:
        self.proc = subprocess.Popen(
            [sys.executable, str(WEB_SERVER), "--port", "0"], stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True,
        )
        first = self.proc.stdout.readline().strip()
        assert first.startswith("PORT "), first
        self.url = f"http://127.0.0.1:{first.split()[1]}/"

    def state(self) -> dict:
        with urllib.request.urlopen(self.url + "hits", timeout=5) as response:
            return json.loads(response.read())

    def hits(self, name: str) -> int:
        return self.state()["hits"][name]

    def settled_hits(self, name: str, at_least: int) -> int:
        """The counter once it reaches `at_least`, or its value after a short wait if it never does."""
        return poll(lambda: self.hits(name), lambda n: n >= at_least)

    def close(self) -> None:
        self.proc.terminate()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()


@contextmanager
def web_run(tmp: Path, fault: Optional[str], owner: str = "yours") -> Iterator[Tuple[WebFixture, Cli]]:
    """A web fixture server plus an open unattended web run bound to it."""
    fixture = WebFixture()
    try:
        with open_run(Cli(tmp, fault), fixture.url, "web", owner, "--unattended") as cli:
            cli.observe()
            yield fixture, cli
    finally:
        fixture.close()


def read_state(path: Path) -> dict:
    """The fixture state file, or an empty skeleton while the app has not written it yet."""
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {"hits": {}, "text": "", "saved_path": None}


def has_finding(cli: Cli, kind: str, needle: str = "") -> bool:
    return any(f["kind"] == kind and needle in f["summary"] for f in cli.findings())


def web_working(tmp: Path, fault: Optional[str]) -> Outcome:
    with web_run(tmp, fault) as (fixture, cli):
        out = cli.act("click", name="Increment counter")
        count = fixture.settled_hits("working", 1)
    return Outcome(out["status"] == "OBSERVED" and count == 1,
                   {"status": out["status"], "hits.working": count})


def web_dead(tmp: Path, fault: Optional[str]) -> Outcome:
    with web_run(tmp, fault) as (fixture, cli):
        out = cli.act("click", name="Dead button")
        count = fixture.settled_hits("dead", 1)
    return Outcome(out["status"] == "NO_EFFECT" and count == 1,
                   {"status": out["status"], "hits.dead": count})


def web_hidden(tmp: Path, fault: Optional[str]) -> Outcome:
    with web_run(tmp, fault) as (fixture, cli):
        out = cli.act("click", name="Promo code")
        visibility = has_finding(cli, "visibility")
        time.sleep(0.5)
        count = fixture.hits("hidden")
    return Outcome(out["status"] == "NOT_VISIBLE" and visibility and count == 0,
                   {"status": out["status"], "visibility_finding": visibility,
                    "hits.hidden": count})


def web_toast(tmp: Path, fault: Optional[str]) -> Outcome:
    with web_run(tmp, fault) as (fixture, cli):
        out = cli.act("click", name="Save avatar")
        network = has_finding(cli, "network", "/api/avatar")
        saves = fixture.settled_hits("save", 1)
    return Outcome(out["status"] == "OBSERVED" and network and saves == 1,
                   {"status": out["status"], "network_finding": network, "hits.save": saves})


def web_delete_gate(tmp: Path, fault: Optional[str]) -> Outcome:
    with web_run(tmp, fault, owner="third-party") as (fixture, cli):
        out = cli.act("click", name="Delete project")
        time.sleep(0.5)
        count = fixture.hits("delete")
    return Outcome(out["status"] == "GATE_REQUIRED" and count == 0,
                   {"status": out["status"], "hits.delete": count})


def web_stale(tmp: Path, fault: Optional[str]) -> Outcome:
    with web_run(tmp, fault) as (fixture, cli):
        first = cli.latest
        ref = cli.ref("Increment counter")
        cli.observe()
        out = cli.act("click", ref=ref, obs=first)
        time.sleep(0.5)
        count = fixture.hits("working")
    return Outcome(out["status"] == "STALE" and count == 0,
                   {"status": out["status"], "hits.working": count})


def web_pass_on_dead_button(tmp: Path, fault: Optional[str]) -> Outcome:
    with web_run(tmp, fault) as (_, cli):
        act = cli.act("click", name="Dead button")
        code, out = cli.call("verdict", "--run", cli.run_id, "--goal", "g1", "--status", "pass",
                             "--summary-stdin", stdin="the dead button worked")
    return Outcome(code == 2 and out.get("error") == "pass_without_effect",
                   {"act_status": act["status"], "verdict_exit": code, "verdict": out})


WEB_ROWS = [
    pytest.param(web_working, "never_observed", id="working-control"),
    pytest.param(web_dead, "always_observed", id="dead-button"),
    pytest.param(web_hidden, "skip_visibility", id="hidden-control"),
    pytest.param(web_toast, "drop_network", id="toast-over-500"),
    pytest.param(web_delete_gate, "skip_gate", id="delete-gate-third-party"),
    pytest.param(web_stale, "skip_stale", id="stale-observation"),
    pytest.param(web_pass_on_dead_button, "allow_unverified_pass", id="verdict-pass-dead-button"),
]


@needs_web
@pytest.mark.parametrize("scenario,fault", WEB_ROWS)
def test_web_row_is_detected(scenario, fault, tmp_path):
    assert_detects(scenario, tmp_path, fault)


@pytest.fixture(scope="module")
def desktop_guard():
    """Run against the real desktop and put the frontmost app and pointer back afterwards."""
    with pytest.MonkeyPatch.context() as patch:
        patch.delenv("LIKEUSER_FAKE_DESKTOP", raising=False)
        original = {"frontmost": _desktop.frontmost_bundle_id(), "cursor": _desktop.cursor()}
        try:
            yield original
        finally:
            if original["frontmost"]:
                _desktop.activate(original["frontmost"])
            _desktop.warp_cursor(*original["cursor"])


def bring_forward(bundle_id: str) -> None:
    """Make `bundle_id` frontmost so a run's baseline is not the fixture that just launched."""
    def front() -> str:
        _desktop.activate(bundle_id)
        return _desktop.frontmost_bundle_id()

    poll(front, lambda current: current == bundle_id, timeout=5.0, interval=0.3)


@pytest.fixture(scope="module")
def electron_ready():
    """The Electron fixture's dependencies installed from the committed lockfile."""
    for argv in (
        ["pnpm", "--dir", str(ELECTRON_DIR), "install", "--frozen-lockfile"],
        ["pnpm", "--dir", str(ELECTRON_DIR), "exec", "install-electron"],
    ):
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=600)
        assert proc.returncode == 0, proc.stderr
    yield
    subprocess.run(["pkill", "-f", str(ELECTRON_DIR / "node_modules")], capture_output=True)


@contextmanager
def electron_run(tmp: Path, fault: Optional[str], *flags: str) -> Iterator[Tuple[Path, Cli]]:
    """An open unattended Electron run launched from the fixture, with its state file path."""
    state = tmp / "electron-state.json"
    cli = Cli(tmp, fault, env={"LIKEUSER_FIXTURE_STATE": str(state)})
    launch = f"pnpm --dir {ELECTRON_DIR} exec electron ."
    with open_run(cli, "electron-fixture", "electron", "yours", "--unattended", "--launch",
                  launch, *flags) as run:
        run.observe()
        yield state, run


def electron_working(tmp: Path, fault: Optional[str]) -> Outcome:
    with electron_run(tmp, fault) as (state, cli):
        out = cli.act("click", name="Working button")
        data = poll(lambda: read_state(state), lambda s: s["hits"].get("working", 0) >= 1)
    count = data["hits"].get("working", 0)
    return Outcome(out["status"] == "OBSERVED" and count == 1,
                   {"status": out["status"], "hits.working": count})


def electron_toast(tmp: Path, fault: Optional[str]) -> Outcome:
    with electron_run(tmp, fault) as (state, cli):
        out = cli.act("click", name="Save avatar")
        network = has_finding(cli, "network", "/api/avatar")
        data = poll(lambda: read_state(state), lambda s: s["hits"].get("save", 0) >= 1)
    saves = data["hits"].get("save", 0)
    return Outcome(out["status"] == "OBSERVED" and network and saves == 1,
                   {"status": out["status"], "network_finding": network, "hits.save": saves})


def _defaults(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["defaults", *args], capture_output=True, text=True, timeout=30)


@contextmanager
def electron_save_directory(directory: Path) -> Iterator[None]:
    """Point Electron's save panel at `directory` for the duration, then restore the old value.

    The panel opens in the last-used folder; a launch argument does not reach it, so the
    preference is the only way to keep the file out of the user's Documents folder.
    """
    key = "NSNavLastRootDirectory"
    before = _defaults("read", ELECTRON_DEFAULTS, key)
    _defaults("write", ELECTRON_DEFAULTS, key, str(directory))
    try:
        yield
    finally:
        if before.returncode == 0:
            _defaults("write", ELECTRON_DEFAULTS, key, before.stdout.strip())
        else:
            _defaults("delete", ELECTRON_DEFAULTS, key)


def electron_save_sheet(tmp: Path, mode: Optional[str]) -> Outcome:
    destination = tmp / "saved"
    destination.mkdir(parents=True)
    click_save = mode is None
    with electron_save_directory(destination):
        with electron_run(tmp, None, "--allow-foreground") as (state, cli):
            cli.act("click", name="Save file…")
            sheet = cli.observe()
            seen = cli.has("Save")
            out = None
            if click_save and seen:
                out = cli.act("click", name="Save", foreground=True, expect="any")
            data = poll(lambda: read_state(state), lambda s: s["saved_path"] is not None,
                        timeout=6.0 if click_save else 1.5)
    saved = data["saved_path"]
    landed = saved is not None and Path(saved).resolve() == (destination / "likeuser-fixture.txt").resolve()
    return Outcome(landed and Path(saved).exists(),
                   {"sheet_in_tree": seen, "saved_path": saved, "act": out and out["status"],
                    "native_tree": sheet["observation"].get("native_tree_path")})


ELECTRON_ROWS = [
    pytest.param(electron_working, "never_observed", id="working-control"),
    pytest.param(electron_toast, "drop_network", id="toast-over-500"),
]


@needs_electron
@pytest.mark.parametrize("scenario,fault", ELECTRON_ROWS)
def test_electron_row_is_detected(scenario, fault, tmp_path, desktop_guard, electron_ready):
    assert_detects(scenario, tmp_path, fault)


@needs_electron
def test_electron_native_save_sheet_writes_into_the_temp_dir(tmp_path, desktop_guard,
                                                              electron_ready):
    assert_detects(electron_save_sheet, tmp_path, None)


@pytest.fixture(scope="module")
def native_app_bundle(tmp_path_factory):
    """The native fixture compiled once per module."""
    out = tmp_path_factory.mktemp("native-fixture-build")
    proc = subprocess.run(["bash", str(NATIVE_BUILD), str(out)], capture_output=True, text=True,
                          timeout=600)
    assert proc.returncode == 0, proc.stderr
    return Path(proc.stdout.strip().splitlines()[-1])


@contextmanager
def native_run(tmp: Path, fault: Optional[str], bundle: Path, original: str, owner: str = "yours",
               *flags: str) -> Iterator[Tuple[Path, Cli]]:
    """The native fixture running with its state file under `tmp`, plus an open run.

    The previously frontmost app is brought forward before `begin`, so the run's baseline is
    not the fixture that just activated itself.
    """
    tmp.mkdir(parents=True, exist_ok=True)
    state = tmp / "native-state.json"
    env = {**os.environ, "LIKEUSER_FIXTURE_STATE": str(state)}
    env.pop("LIKEUSER_FAKE_DESKTOP", None)
    app = subprocess.Popen(
        [str(bundle / "Contents" / "MacOS" / "UALAFixture")], env=env, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, text=True,
    )
    try:
        assert app.stdout.readline().strip() == f"STATE {state}"
        poll(lambda: _desktop.frontmost_bundle_id(), lambda front: front == NATIVE_BUNDLE, 5.0)
        bring_forward(original)
        cli = Cli(tmp, fault)
        with open_run(cli, NATIVE_BUNDLE, "native", owner, "--unattended", *flags):
            cli.observe()
            yield state, cli
    finally:
        app.terminate()
        try:
            app.wait(timeout=10)
        except subprocess.TimeoutExpired:
            app.kill()
            app.wait()


def native_working(bundle: Path, original: str, tmp: Path, fault: Optional[str]) -> Outcome:
    with native_run(tmp, fault, bundle, original) as (state, cli):
        out = cli.act("click", name="Working button")
        data = poll(lambda: read_state(state), lambda s: s["hits"].get("working", 0) >= 1)
        front = _desktop.frontmost_bundle_id()
    count = data["hits"].get("working", 0)
    driver = json.loads((cli.run_dir / "run.json").read_text())["driver"]
    return Outcome(out["status"] == "OBSERVED" and count == 1 and driver == "cua"
                   and front == original,
                   {"status": out["status"], "hits.working": count, "driver": driver,
                    "frontmost_after": front, "frontmost_before": original})


def native_dead(bundle: Path, original: str, tmp: Path, fault: Optional[str]) -> Outcome:
    with native_run(tmp, fault, bundle, original) as (state, cli):
        out = cli.act("click", name="Dead button")
        data = poll(lambda: read_state(state), lambda s: s["hits"].get("dead", 0) >= 1)
    count = data["hits"].get("dead", 0)
    return Outcome(out["status"] == "NO_EFFECT" and count == 1,
                   {"status": out["status"], "hits.dead": count})


def native_zero_opacity(bundle: Path, original: str, tmp: Path, fault: Optional[str]) -> Outcome:
    with native_run(tmp, fault, bundle, original) as (_, cli):
        in_tree = cli.has("Hidden control")
        out = cli.act("click", name="Hidden control")
    return Outcome(in_tree and out["status"] in ("NO_EFFECT", "NOT_VISIBLE"),
                   {"in_tree": in_tree, "status": out["status"]})


def native_delete_gate(bundle: Path, original: str, tmp: Path, fault: Optional[str]) -> Outcome:
    with native_run(tmp, fault, bundle, original, "third-party") as (state, cli):
        out = cli.act("click", name="Delete project")
        time.sleep(0.5)
        data = read_state(state)
    count = data["hits"].get("delete", 0)
    return Outcome(out["status"] == "GATE_REQUIRED" and count == 0,
                   {"status": out["status"], "hits.delete": count})


def _user_temp_dir() -> str:
    """The folder NSTemporaryDirectory() returns; the TMPDIR variable does not move it."""
    return subprocess.run(["getconf", "DARWIN_USER_TEMP_DIR"], capture_output=True, text=True,
                          check=True).stdout.strip()


def native_save_sheet(bundle: Path, original: str, tmp: Path, mode: Optional[str]) -> Outcome:
    click_save = mode is None
    name = f"uala-{uuid.uuid4().hex[:12]}.txt"
    expected = Path(os.path.realpath(_user_temp_dir())) / name
    try:
        with native_run(tmp, None, bundle, original, "yours", "--allow-foreground") as (state, cli):
            cli.act("click", name="Save…")
            cli.observe()
            seen = cli.has("Save")
            out = None
            if seen:
                cli.act("fill", name="fixture-export.txt", stdin=name, foreground=True,
                        expect="any")
                cli.observe()
            if click_save and seen:
                out = cli.act("click", name="Save", foreground=True, expect="any")
            data = poll(lambda: read_state(state), lambda s: s["saved_path"] is not None,
                        timeout=6.0 if click_save else 1.5)
        saved = data["saved_path"]
        landed = saved is not None and Path(saved).resolve() == expected
        return Outcome(landed and expected.exists(),
                       {"sheet_in_tree": seen, "saved_path": saved, "act": out and out["status"]})
    finally:
        expected.unlink(missing_ok=True)


def native_drift(bundle: Path, original: str, tmp: Path, fault: Optional[str]) -> Outcome:
    start = _desktop.cursor()
    try:
        with native_run(tmp, fault, bundle, original, "yours", "--allow-foreground") as (_, cli):
            first = cli.act("click", name="Working button", foreground=True)
            here = _desktop.cursor()
            _desktop.warp_cursor(here[0] + 80.0, here[1] + 80.0)
            second = cli.act("click", name="Dead button", foreground=True)
            third = cli.act("click", name="Dead button", foreground=True)
    finally:
        _desktop.warp_cursor(*start)
    statuses = [first["status"], second["status"], third["status"]]
    return Outcome(statuses == ["OBSERVED", "DRIFT", "DRIFT"], {"statuses": statuses})


NATIVE_ROWS = [
    pytest.param(native_working, "never_observed", id="working-control-background"),
    pytest.param(native_dead, "always_observed", id="dead-button"),
    pytest.param(native_zero_opacity, "always_observed", id="zero-opacity-control"),
    pytest.param(native_delete_gate, "skip_gate", id="delete-gate"),
    pytest.param(native_drift, "skip_drift", id="cursor-drift-foreground"),
]


@needs_native
@pytest.mark.parametrize("scenario,fault", NATIVE_ROWS)
def test_native_row_is_detected(scenario, fault, tmp_path, desktop_guard, native_app_bundle):
    original = desktop_guard["frontmost"]

    def bound(path: Path, mode: Optional[str]) -> Outcome:
        return scenario(native_app_bundle, original, path, mode)

    assert_detects(bound, tmp_path, fault)


@needs_native
def test_native_save_panel_writes_into_the_temp_dir(tmp_path, desktop_guard, native_app_bundle):
    original = desktop_guard["frontmost"]

    def bound(path: Path, mode: Optional[str]) -> Outcome:
        return native_save_sheet(native_app_bundle, original, path, mode)

    assert_detects(bound, tmp_path, None)


def shot_distance(before: str, after: str) -> int:
    """Hamming distance between the average hashes of two screenshot files."""
    return _effects.hamming(_effects.average_hash(Path(before)), _effects.average_hash(Path(after)))


def measure_unchanged(cli: Cli, repeats: int = 4) -> List[int]:
    """Distances between consecutive observations of a screen nothing touched, plus first to last."""
    shots = [cli.observe()["observation"]["screenshot_path"]]
    distances = []
    for _ in range(repeats):
        time.sleep(0.5)
        shots.append(cli.observe()["observation"]["screenshot_path"])
        distances.append(shot_distance(shots[-2], shots[-1]))
    distances.append(shot_distance(shots[0], shots[-1]))
    return distances


def measure_change(cli: Cli, control: str) -> int:
    """Distance between the screenshots before and after clicking `control` (a visible change)."""
    before = cli.observe()["observation"]["screenshot_path"]
    after = cli.act("click", name=control)["observation"]["screenshot_path"]
    return shot_distance(before, after)


def measure_screen_hashes(tmp: Path, bundle: Path, original: str) -> Tuple[Dict[str, List[int]], Dict[str, int]]:
    """Screenshot-hash distances on every fixture: unchanged screens and real visible changes."""
    unchanged: Dict[str, List[int]] = {}
    changed: Dict[str, int] = {}
    fixture = WebFixture()
    try:
        with open_run(Cli(tmp / "web", None), fixture.url, "web", "yours", "--unattended") as cli:
            unchanged["web"] = measure_unchanged(cli)
            changed["web counter label"] = measure_change(cli, "Increment counter")
            changed["web toast"] = measure_change(cli, "Save avatar")
    finally:
        fixture.close()
    with electron_run(tmp / "electron", None) as (_, cli):
        unchanged["electron"] = measure_unchanged(cli)
        changed["electron counter label"] = measure_change(cli, "Working button")
        changed["electron toast"] = measure_change(cli, "Save avatar")
    with native_run(tmp / "native", None, bundle, original) as (_, cli):
        unchanged["native"] = measure_unchanged(cli)
        changed["native status label"] = measure_change(cli, "Working button")
    return unchanged, changed


@needs_web
@needs_electron
@needs_native
def test_screen_hash_threshold_separates_unchanged_from_changed(tmp_path, desktop_guard,
                                                                 electron_ready,
                                                                 native_app_bundle):
    unchanged, changed = measure_screen_hashes(tmp_path, native_app_bundle,
                                               desktop_guard["frontmost"])
    worst_unchanged = max(max(v) for v in unchanged.values())
    threshold = _effects.SCREEN_HASH_THRESHOLD
    report = f"unchanged={unchanged} changed={changed} threshold={threshold}"
    assert worst_unchanged < threshold, report
    # label-sized changes score 0 on an 8x8 hash; only the web toast is large enough to be the screen signal's job
    assert changed["web toast"] > threshold, report
