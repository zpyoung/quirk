#!/usr/bin/env python3
"""In-Blender guard for the making-videos skill: inspects the scene, then renders the frame range.

Runs inside Blender after the author's scene-building script, as the second ``--python`` argument,
so the author's script never has to import it:
``blender -b FILE --python-exit-code 1 --python PY --python bl_guard.py -- --out DIR --frames A-B [--alpha]``.
It refuses to render when the scene is Blender's startup scene or when text faces away from the camera,
sets the output path in Python (never ``-o``/``-a``, whose order silently matters), renders
``DIR/f_####.png`` and writes ``DIR/guard.json``:
``{default_scene, view_transform, text_objects, mirrored_frames, edge_on_frames, frames_rendered}``.
The classification helpers take plain data so they load and test without ``bpy``.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Sequence, Tuple

try:
    import bpy  # type: ignore[import-not-found]
except ImportError:
    bpy = None

EDGE_ON_LIMIT = 0.2
BACK_FACE_TOLERANCE = 1e-6
STARTUP_MESH = "Cube"


def parse_frames(spec: str) -> Tuple[int, int]:
    """Parse ``A-B`` into an inclusive ``(first, last)`` pair; raises ``ValueError`` when malformed."""
    try:
        first_s, last_s = spec.split("-")
        first, last = int(first_s), int(last_s)
    except ValueError:
        raise ValueError(f"--frames must look like 10-240, got {spec!r}") from None
    if first < 0 or last < first:
        raise ValueError(f"--frames needs 0 <= A <= B, got {spec!r}")
    return first, last


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parse the arguments after Blender's ``--``, ignoring flags that belong to the author's script."""
    parser = argparse.ArgumentParser(prog="bl_guard.py", add_help=False)
    parser.add_argument("--out", required=True)
    parser.add_argument("--frames", required=True)
    parser.add_argument("--alpha", action="store_true")
    args, _ = parser.parse_known_args(list(argv))
    return args


def world_normal(rows: Sequence[Sequence[float]]) -> Tuple[float, float, float]:
    """The unit world-space direction of an object's local +Z from its 3x3 world matrix rows.

    Text objects face +Z, so this is the direction their readable side points.
    """
    vec = (float(rows[0][2]), float(rows[1][2]), float(rows[2][2]))
    length = math.sqrt(sum(c * c for c in vec))
    if length == 0.0:
        return (0.0, 0.0, 0.0)
    return (vec[0] / length, vec[1] / length, vec[2] / length)


def classify_facing(
    normal: Sequence[float], obj_pos: Sequence[float], cam_pos: Sequence[float]
) -> Tuple[bool, bool]:
    """Return ``(mirrored, edge_on)`` for a text object's +Z ``normal`` against the camera.

    The dot of the normal with the unit vector from object to camera is negative (beyond float noise) when the
    camera sees the back of the text (mirrored) and within ``EDGE_ON_LIMIT`` of zero when it is edge-on.
    An object sitting on the camera counts as edge-on.
    """
    to_cam = [c - o for c, o in zip(cam_pos, obj_pos)]
    length = math.sqrt(sum(c * c for c in to_cam))
    if length == 0.0:
        return (False, True)
    dot = sum(n * c / length for n, c in zip(normal, to_cam))
    return (dot < -BACK_FACE_TOLERANCE, abs(dot) < EDGE_ON_LIMIT)


def is_default_scene(objects: Sequence[dict]) -> bool:
    """True when the scene is Blender's startup scene or has nothing to render.

    ``objects`` is a list of ``{"name": str, "type": str}``. That is the lone mesh ``Cube`` with the
    default ``Camera`` and ``Light``, or no objects besides cameras and lights.
    """
    content = [o for o in objects if o["type"] not in ("CAMERA", "LIGHT")]
    if not content:
        return True
    if len(content) != 1 or content[0]["type"] != "MESH" or content[0]["name"] != STARTUP_MESH:
        return False
    return all(o["name"] in ("Camera", "Light") for o in objects if o["type"] in ("CAMERA", "LIGHT"))


def _write_guard(out: Path, guard: dict) -> None:
    (out / "guard.json").write_text(json.dumps(guard), encoding="utf-8")


def _inspect_text(scene, first: int, last: int) -> Tuple[list, list, list]:
    texts = [o for o in scene.objects if o.type == "FONT" and not o.hide_render]
    mirrored, edge_on = [], []
    if texts and scene.camera is None:
        raise RuntimeError("scene has no active camera")
    for frame in range(first, last + 1):
        if not texts:
            break
        scene.frame_set(frame)
        cam_pos = tuple(scene.camera.matrix_world.translation)
        for obj in texts:
            world = obj.matrix_world
            normal = world_normal([tuple(row)[:3] for row in world.to_3x3()])
            is_mirrored, is_edge = classify_facing(normal, tuple(world.translation), cam_pos)
            if is_mirrored and frame not in mirrored:
                mirrored.append(frame)
            if is_edge and frame not in edge_on:
                edge_on.append(frame)
    return [o.name for o in texts], mirrored, edge_on


def main(argv: Sequence[str]) -> int:
    """Inspect the open scene, write ``guard.json`` and render unless a check failed."""
    args = parse_args(argv)
    first, last = parse_frames(args.frames)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene

    default = is_default_scene([{"name": o.name, "type": o.type} for o in scene.objects])
    text_objects, mirrored, edge_on = _inspect_text(scene, first, last)
    guard = {
        "default_scene": default,
        "view_transform": scene.view_settings.view_transform,
        "text_objects": text_objects,
        "mirrored_frames": mirrored,
        "edge_on_frames": edge_on,
        "frames_rendered": 0,
    }
    _write_guard(out, guard)
    if default or mirrored:
        print(f"bl_guard: refusing to render: {json.dumps(guard)}", file=sys.stderr)
        return 0

    render = scene.render
    render.filepath = str(out / "f_####")
    render.use_file_extension = True
    render.image_settings.file_format = "PNG"
    render.image_settings.color_mode = "RGBA" if args.alpha else "RGB"
    render.film_transparent = bool(args.alpha)
    scene.frame_start, scene.frame_end, scene.frame_step = first, last, 1
    bpy.ops.render.render(animation=True)

    guard["frames_rendered"] = last - first + 1
    _write_guard(out, guard)
    return 0


if __name__ == "__main__":
    if bpy is None:
        print("bl_guard.py runs inside Blender; use blender_render.py", file=sys.stderr)
        raise SystemExit(1)
    main(sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])
