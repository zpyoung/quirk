import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "skills" / "full-code-review" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _restore_prepare_diff_seams():
    # tests stub prepare_diff module functions in place; restore them so no stub leaks
    import prepare_diff
    saved = {name: getattr(prepare_diff, name) for name in ("commit_authors",)}
    yield
    for name, value in saved.items():
        setattr(prepare_diff, name, value)
