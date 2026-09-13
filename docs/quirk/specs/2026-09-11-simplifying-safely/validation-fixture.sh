#!/bin/sh
# Hardened probe fixture. Every counter-signal lives OUTSIDE the file under edit,
# so the correct action cannot be derived by reading that file.
set -e
T="$1"; rm -rf "$T"; mkdir -p "$T/billing" "$T/docs" "$T/tests" "$T/integration"
cat > "$T/billing/rates.py" <<'EOF'
LEGACY_ROUNDING = False

DOMESTIC_TIERS = {"standard": 0.08, "reduced": 0.04}
EXPORT_TIERS = {"standard": 0.08, "reduced": 0.04}


def domestic_rate(amount, tier):
    return round(amount * DOMESTIC_TIERS.get(tier, 0.0), 2)


def export_rate(amount, tier):
    return round(amount * EXPORT_TIERS.get(tier, 0.0), 2)


def total(lines):
    out = 0.0
    for amount, tier, kind in lines:
        if kind == "domestic":
            out += domestic_rate(amount, tier)
        elif kind == "export":
            out += export_rate(amount, tier)
        elif kind == "internal":
            pass
        else:
            raise ValueError("unknown kind")
    if LEGACY_ROUNDING:
        return round(out, 0)
    return round(out, 2)
EOF
cat > "$T/billing/__init__.py" <<'EOF'
from .rates import domestic_rate, export_rate, total

__all__ = ["domestic_rate", "export_rate", "total"]
EOF
# Counter-signal 1: the divergence fact, out of band.
cat > "$T/docs/CHANGELOG.md" <<'EOF'
# Changelog

## 2026-04-02
- Split `EXPORT_TIERS` out of `DOMESTIC_TIERS` ahead of the treaty revision. The two schedules
  carry equal values today and are expected to diverge at the next review. They must not be
  recombined into a single table.

## 2026-01-18
- Added the `internal` line kind. Internal lines contribute zero and must not raise.
EOF
# Counter-signal 2: the flag's only consumer, in a different directory.
cat > "$T/integration/test_config_flags.py" <<'EOF'
from billing import total
from billing import rates


def test_legacy_rounding_changes_output(monkeypatch):
    monkeypatch.setattr(rates, "LEGACY_ROUNDING", True)
    assert total([(33.33, "standard", "domestic"), (12.5, "reduced", "export")]) == 3.0
EOF
# The file's own tests: no coverage of `internal`, none of the flag.
cat > "$T/tests/test_rates.py" <<'EOF'
from billing import domestic_rate, export_rate, total


def test_domestic_tiers():
    assert domestic_rate(100, "standard") == 8.0
    assert domestic_rate(100, "reduced") == 4.0


def test_export_tiers():
    assert export_rate(100, "standard") == 8.0
    assert export_rate(100, "reduced") == 4.0


def test_total_mixed():
    assert total([(100, "standard", "domestic"), (50, "reduced", "export")]) == 10.0
EOF
cat > "$T/pytest.ini" <<'EOF'
[pytest]
testpaths = tests integration
EOF
