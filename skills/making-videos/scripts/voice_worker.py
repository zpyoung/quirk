#!/usr/bin/env python3
"""Kokoro narration and faster-whisper word alignment; runs only inside the skill's cache venv.

``voice.py`` is the stdlib launcher that picks the interpreter, environment and paths. Heavy
imports (kokoro_onnx, soundfile, numpy, faster_whisper) happen inside the commands so the pure
helpers stay importable without them. Each command prints one JSON object as its last stdout
line and exits 0; any failure raises, so the launcher sees a non-zero exit and the traceback.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Iterable

MODEL_FILE = "kokoro-v1.0.onnx"
VOICES_FILE = "voices-v1.0.bin"
LANGUAGE = "en-us"


def apply_patches(phonemes: str, pronunciations: dict) -> str:
    """Rewrite a phoneme string with the brand's ``{word: {"from", "to"}}`` patches.

    Patches act on phonemes, not spelling, because espeak's lexicon is what mispronounces a word.
    """
    for patch in pronunciations.values():
        phonemes = phonemes.replace(patch["from"], patch["to"])
    return phonemes


def words_path(wav: "str | Path") -> Path:
    """Where a clip's word timings live: the wav path with ``.words.json`` in place of ``.wav``."""
    return Path(wav).with_suffix(".words.json")


def words_from_segments(segments: Iterable) -> "list[dict]":
    """Flatten faster-whisper segments into ``[{text, start, end}]`` with times in seconds."""
    return [
        {"text": w.word.strip(), "start": round(w.start, 3), "end": round(w.end, 3)}
        for segment in segments
        for w in segment.words
    ]


def load_16k(path: str, ffmpeg: str = "ffmpeg"):
    """Decode ``path`` to mono 16 kHz float32 samples with ffmpeg.

    faster-whisper's own decoder needs a newer PyAV than resolves in the venv.
    """
    import numpy as np

    raw = subprocess.run(
        [ffmpeg, "-v", "error", "-i", path, "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
        check=True,
        capture_output=True,
    ).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0


def _cmd_say(args: argparse.Namespace) -> dict:
    import soundfile as sf
    from kokoro_onnx import Kokoro
    from kokoro_onnx.tokenizer import Tokenizer

    model_dir = Path(args.model_dir)
    model_path, voices_path = model_dir / MODEL_FILE, model_dir / VOICES_FILE
    for needed in (model_path, voices_path):
        if not needed.is_file():
            raise FileNotFoundError(
                f"Kokoro model file missing: {needed} (run doctor.py install --what tts --yes)"
            )
    lines = json.loads(Path(args.lines).read_text(encoding="utf-8"))
    pronunciations = json.loads(args.pronunciations)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    tokenizer = Tokenizer()
    model = Kokoro(str(model_path), str(voices_path))
    clips = []
    for line in lines:
        phonemes = apply_patches(tokenizer.phonemize(line["text"], LANGUAGE), pronunciations)
        samples, rate = model.create(phonemes, voice=args.voice, is_phonemes=True)
        wav = out_dir / f"{line['id']}.wav"
        sf.write(str(wav), samples, rate)
        clips.append({"id": line["id"], "wav": str(wav), "duration_s": round(len(samples) / rate, 3)})
        print(f"{line['id']}: {clips[-1]['duration_s']}s", file=sys.stderr)
    return {"clips": clips}


def _cmd_align(args: argparse.Namespace) -> dict:
    from faster_whisper import WhisperModel

    model = WhisperModel(args.model, device="cpu", compute_type="int8")
    words = []
    for wav in args.wavs:
        segments, _ = model.transcribe(
            load_16k(wav, args.ffmpeg), language="en", word_timestamps=True, beam_size=5
        )
        path = words_path(wav)
        timed = words_from_segments(segments)
        path.write_text(json.dumps(timed, indent=1), encoding="utf-8")
        words.append({"clip": Path(wav).stem, "path": str(path)})
        print(f"{Path(wav).name}: {len(timed)} words", file=sys.stderr)
    return {"words": words}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="voice_worker.py", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    say = sub.add_parser("say", help="synthesize each line to <out-dir>/<id>.wav")
    say.add_argument("--lines", required=True, help="lines JSON: [{id, text, start_s}]")
    say.add_argument("--voice", required=True)
    say.add_argument("--out-dir", required=True)
    say.add_argument("--model-dir", required=True)
    say.add_argument("--pronunciations", default="{}", help="JSON {word: {from, to}} phoneme patches")
    say.set_defaults(func=_cmd_say)

    align = sub.add_parser("align", help="write <wav stem>.words.json beside each wav")
    align.add_argument("--model", default="small.en")
    align.add_argument("--ffmpeg", default="ffmpeg")
    align.add_argument("--wavs", nargs="+", required=True)
    align.set_defaults(func=_cmd_align)
    return parser


def main(argv: "list[str] | None" = None) -> int:
    args = build_parser().parse_args(argv)
    result = args.func(args)
    sys.stdout.write(json.dumps(result) + "\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
