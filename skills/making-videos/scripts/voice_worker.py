#!/usr/bin/env python3
"""Kokoro narration and faster-whisper word alignment; runs only inside the skill's cache venv.

``voice.py`` is the stdlib launcher that picks the interpreter, environment and paths. Heavy
imports (kokoro_onnx, soundfile, numpy, faster_whisper) happen inside the commands so the pure
helpers stay importable without them. Each command prints one JSON object as its last stdout
line and exits 0. A missing executable prints ``{error, missing}`` and exits 3; any other failure
raises, so the launcher sees a non-zero exit and the traceback.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterable

MODEL_FILE = "kokoro-v1.0.onnx"
VOICES_FILE = "voices-v1.0.bin"
LANGUAGE = "en-us"

TARGET_LUFS = -16.0
TRUE_PEAK_CEILING_DBTP = -1.5
LOUDNORM_PEAK_DBTP = -2.0
LOUDNORM_LRA = 11
# the limiter keeps peak-to-loudness under the 14.5 LU that a linear gain to -16 LUFS at -1.5 dBTP allows
LEVELING_CHAIN = (
    "acompressor=threshold=-24dB:ratio=3:attack=5:release=100:makeup=4,"
    "alimiter=limit=-14dB:attack=2:release=40:level=0"
)
FFMPEG_TIMEOUT_S = 600
EXIT_MISSING_TOOL = 3
CLIP_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
MEASURED_KEYS = ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")


class MissingTool(Exception):
    """A required executable is not installed; ``main`` reports it as exit 3 with ``missing`` set."""

    def __init__(self, tool: str, message: str):
        super().__init__(message)
        self.tool = tool


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


def parse_loudnorm(stderr: str) -> dict:
    """The JSON block that ``loudnorm=print_format=json`` prints at the end of ffmpeg's stderr."""
    blocks = re.findall(r"\{[^{}]*\}", stderr)
    if not blocks:
        raise RuntimeError(f"ffmpeg printed no loudnorm measurement: {stderr.strip()[-400:]}")
    return json.loads(blocks[-1])


def _finite(value: object) -> "float | None":
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _measurable(measured: dict) -> bool:
    """Whether a loudnorm measurement can be fed back as ``measured_*``; it cannot for clips under
    the 400 ms gating window or for silence, which measure as ``-inf``."""
    return all(_finite(measured.get(key)) is not None for key in MEASURED_KEYS)


def _run_ffmpeg(ffmpeg: str, argv: "list[str]", src: Path) -> str:
    try:
        proc = subprocess.run([ffmpeg, *argv], capture_output=True, text=True, timeout=FFMPEG_TIMEOUT_S)
    except FileNotFoundError:
        raise MissingTool("ffmpeg", f"ffmpeg not found: {ffmpeg}") from None
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed on {src.name} (exit {proc.returncode}): {proc.stderr.strip()[-400:]}")
    return proc.stderr


def _loudnorm(ffmpeg: str, src: Path, prefilter: str, measured: "dict | None", dst: "Path | None", rate: int) -> dict:
    """One ffmpeg pass: measure ``src`` through ``prefilter`` + loudnorm, writing ``dst`` when given."""
    options = f"I={TARGET_LUFS}:TP={LOUDNORM_PEAK_DBTP}:LRA={LOUDNORM_LRA}"
    if measured:
        options += (
            f":measured_I={measured['input_i']}:measured_TP={measured['input_tp']}"
            f":measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}"
            f":offset={measured['target_offset']}:linear=true"
        )
    argv = ["-hide_banner", "-nostats", "-y", "-i", str(src), "-af", f"{prefilter}loudnorm={options}:print_format=json"]
    argv += ["-ar", str(rate), "-ac", "1", "-c:a", "pcm_s16le", str(dst)] if dst else ["-f", "null", "-"]
    return parse_loudnorm(_run_ffmpeg(ffmpeg, argv, src))


def _level_only(ffmpeg: str, src: Path, dst: Path, rate: int) -> None:
    argv = ["-hide_banner", "-nostats", "-y", "-i", str(src), "-af", LEVELING_CHAIN]
    _run_ffmpeg(ffmpeg, argv + ["-ar", str(rate), "-ac", "1", "-c:a", "pcm_s16le", str(dst)], src)


def normalize_clip(ffmpeg: str, raw: Path, out: Path, rate: int) -> dict:
    """Write ``out`` as ``raw`` compressed and loudness-normalized to -16 LUFS, and measure the result.

    Two loudnorm passes (measure, then apply the measurement as a linear gain) so the clip keeps its
    dynamics; ffmpeg falls back to dynamic mode on its own when a linear gain would break the peak
    ceiling, and ``normalization`` reports which one ran. A clip loudnorm cannot measure (shorter
    than 400 ms, or silent) gets only the compressor and limiter, with ``normalization`` set to
    ``skipped_short`` and a ``reason``. Returns ``{lufs, true_peak_dbtp, normalization}`` measured on
    ``out``, where a level that is not finite is ``None``. Intermediates live in a private temporary
    directory beside ``out``, never under a name a clip id could take.
    """
    first = _loudnorm(ffmpeg, raw, LEVELING_CHAIN + ",", None, None, rate)
    with tempfile.TemporaryDirectory(prefix=".normalize-", dir=out.parent) as scratch:
        tmp = Path(scratch) / "leveled.wav"
        if _measurable(first):
            kind = _loudnorm(ffmpeg, raw, LEVELING_CHAIN + ",", first, tmp, rate).get("normalization_type", "unknown")
            extra: dict = {}
        else:
            _level_only(ffmpeg, raw, tmp, rate)
            kind = "skipped_short"
            extra = {"reason": "loudnorm cannot measure a clip under 400 ms or a silent one; only compressed and limited"}
        final = _loudnorm(ffmpeg, tmp, "", None, None, rate)
        os.replace(tmp, out)
    return {
        "lufs": _rounded(final["input_i"]),
        "true_peak_dbtp": _rounded(final["input_tp"]),
        "normalization": kind,
        **extra,
    }


def _rounded(value: object) -> "float | None":
    number = _finite(value)
    return None if number is None else round(number, 1)


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
    if shutil.which(args.ffmpeg) is None:
        raise MissingTool("ffmpeg", f"ffmpeg not found: {args.ffmpeg}")
    lines = json.loads(Path(args.lines).read_text(encoding="utf-8"))
    for line in lines:
        if not CLIP_ID_RE.match(line["id"]) or line["id"].endswith(".raw"):
            raise ValueError(f"invalid clip id {line['id']!r}")
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
        raw = out_dir / f"{line['id']}.raw.wav"
        sf.write(str(raw), samples, rate)
        levels = normalize_clip(args.ffmpeg, raw, wav, rate)
        clips.append(
            {
                "id": line["id"],
                "wav": str(wav),
                "raw": str(raw),
                "duration_s": round(len(samples) / rate, 3),
                **levels,
            }
        )
        print(
            f"{line['id']}: {clips[-1]['duration_s']}s {levels['lufs']} LUFS {levels['true_peak_dbtp']} dBTP {levels['normalization']}",
            file=sys.stderr,
        )
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
    say.add_argument("--ffmpeg", default="ffmpeg", help="ffmpeg used to level and normalize each clip")
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
    try:
        result = args.func(args)
    except MissingTool as exc:
        sys.stdout.write(json.dumps({"error": str(exc), "missing": exc.tool}) + "\n")
        sys.stdout.flush()
        return EXIT_MISSING_TOOL
    sys.stdout.write(json.dumps(result) + "\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
