"""Builder library for the writing-html-artifacts skill.

The CLIs under ``scripts/`` stay thin and import these modules, so tests can drive the
logic directly. Everything here is standard library only and makes no network calls.
"""
from __future__ import annotations

from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2]

__all__ = ["SKILL_DIR", "checks", "fsutil", "header", "manifest", "resolve", "tokens", "vendor"]
