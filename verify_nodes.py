#!/usr/bin/env python3
"""Build-time guard: fail the image build LOUDLY if the required custom nodes
did not actually install.

The deployed image once shipped without ComfyUI-Impact-Pack even though the
Dockerfile ran `comfy-node-install comfyui-impact-pack comfyui-impact-subpack`
— `comfy-node-install` can fail silently, and the broken image only surfaced at
job time as `Node 'FaceDetailer' not found`. This script turns that into a build
failure instead: it scans the installed custom-node sources for the class names
the `t2i-v05-hires` workflow needs and exits non-zero if any are missing.

Cheap on purpose: it greps the .py sources for the class definitions rather than
importing ComfyUI (which would need torch + a GPU). Presence of the source is
what `comfy-node-install` must guarantee; ComfyUI loads it at runtime.
"""
import os
import sys

CUSTOM_NODES = "/comfyui/custom_nodes"

# class_type -> pack it comes from (for the error message).
REQUIRED = {
    "FaceDetailer": "ComfyUI-Impact-Pack",
    "UltralyticsDetectorProvider": "ComfyUI-Impact-Subpack",
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
        print("\nFATAL: required custom nodes not installed:", file=sys.stderr)
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

    print("\nAll required custom nodes present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
