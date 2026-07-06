#!/usr/bin/env python3
"""Build-time guard: fail the image build LOUDLY if the required custom nodes
did not actually install.

The deployed image once shipped without ComfyUI-Impact-Pack even though the
Dockerfile ran `comfy-node-install comfyui-impact-pack comfyui-impact-subpack`
— `comfy-node-install` can fail silently, and the broken image only surfaced at
job time as `Node 'FaceDetailer' not found`. This script turns that into a build
failure instead: it scans the installed custom-node sources for the class names
the `t2i-v05-hires` workflow needs and exits non-zero if any are missing.

Two checks, both cheap (no ComfyUI/GPU needed):
  1. Source presence — grep the .py sources for the class definitions, proving
     `comfy-node-install` actually copied the node code.
  2. Runtime deps import — `import cv2`, `ultralytics`, etc. Source presence is
     NOT enough: `comfy-node-install` once copied the source but skipped the
     Python deps, so both packs failed to import at runtime with
     "No module named 'cv2'" and FaceDetailer reported "not found". Importing the
     critical deps here turns that into a build failure instead.
"""
import importlib
import os
import sys

CUSTOM_NODES = "/comfyui/custom_nodes"

# class_type -> pack it comes from (for the error message).
REQUIRED = {
    "FaceDetailer": "ComfyUI-Impact-Pack",
    "UltralyticsDetectorProvider": "ComfyUI-Impact-Subpack",
}

# Runtime deps whose absence makes the packs fail to import (module -> pip name).
# These are the module-level imports at the top of the pack __init__ that broke
# before; if any is missing the build must fail, not the render job.
REQUIRED_IMPORTS = {
    "cv2": "opencv-python-headless",
    "ultralytics": "ultralytics",
    "skimage": "scikit-image",
    "segment_anything": "segment-anything",
}


def sources():
    for root, _dirs, files in os.walk(CUSTOM_NODES):
        for f in files:
            if f.endswith(".py"):
                yield os.path.join(root, f)


def main() -> int:
    if not os.path.isdir(CUSTOM_NODES):
        print(f"FATAL: {CUSTOM_NODES} does not exist", file=sys.stderr)
        return 1

    text_by_file = {}
    for path in sources():
        try:
            text_by_file[path] = open(path, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue

    missing = []
    for cls, pack in REQUIRED.items():
        # Match a class definition or NODE_CLASS_MAPPINGS registration.
        needle_class = f"class {cls}"
        needle_map = f'"{cls}"'
        hits = [p for p, t in text_by_file.items() if needle_class in t or needle_map in t]
        status = "OK" if hits else "MISSING"
        print(f"  [{status}] {cls} ({pack}) -> {len(hits)} source file(s)")
        if not hits:
            missing.append((cls, pack))

    if missing:
        print("\nFATAL: required custom node SOURCE not installed:", file=sys.stderr)
        for cls, pack in missing:
            print(f"  - {cls} (from {pack})", file=sys.stderr)
        print(
            "\nThe `comfy-node-install` step did not actually install these. "
            "Fix the install before shipping — a missing node fails every job at "
            "runtime with \"Node '<name>' not found\".",
            file=sys.stderr,
        )
        # List what IS present, to aid debugging.
        try:
            present = sorted(os.listdir(CUSTOM_NODES))
            print(f"\ncustom_nodes/ contains: {present}", file=sys.stderr)
        except OSError:
            pass
        return 1

    # Source present is not enough — the packs also need their Python deps to
    # import, or ComfyUI silently drops the nodes at startup ("not found").
    missing_deps = []
    for mod, pip_name in REQUIRED_IMPORTS.items():
        try:
            importlib.import_module(mod)
            print(f"  [OK] import {mod} ({pip_name})")
        except Exception as exc:  # ImportError, and anything a dep raises on import
            print(f"  [MISSING] import {mod} ({pip_name}) -> {type(exc).__name__}: {exc}")
            missing_deps.append((mod, pip_name))

    if missing_deps:
        print("\nFATAL: required runtime dependencies do not import:", file=sys.stderr)
        for mod, pip_name in missing_deps:
            print(f"  - {mod}  (pip install {pip_name})", file=sys.stderr)
        print(
            "\nThe node source is present but these deps are missing, so both "
            "Impact packs fail to import at runtime and FaceDetailer reports "
            "\"not found\". Install the packs' requirements in the image.",
            file=sys.stderr,
        )
        return 1

    print("\nAll required custom nodes present and their runtime deps import.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
