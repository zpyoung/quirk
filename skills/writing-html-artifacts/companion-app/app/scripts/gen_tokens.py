"""Print the house --q-* tokens as CSS, the same call htmlkit/app.py makes for src/quirk-tokens.css."""
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(SKILL_DIR / "scripts"))

from htmlkit.tokens import merge_tokens, token_layers, tokens_css  # noqa: E402

sys.stdout.write(tokens_css(merge_tokens(token_layers(SKILL_DIR, None, None, None))))
