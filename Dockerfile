# Thin worker-comfyui image for the /theme-experiment pre-flight (ETAPA #03).
#
# Base = official RunPod ComfyUI serverless worker (ComfyUI + the /run|/status
# job handler baked in). We add ONLY the two custom-node packs the Pony-Realism
# workflow needs: Impact Pack (FaceDetailer) and Impact Subpack
# (UltralyticsDetectorProvider). Models are NEVER baked here — they are served
# at runtime from the PONY/ZIMAGE network volume via extra_model_paths.yaml.
#
# Why this exists (deviates from ADR-0002's "zero-Docker stock image" path):
# the PONY/ZIMAGE volume is a full self-contained runpod-slim ComfyUI install,
# not a models-only volume. worker-comfyui cannot load custom nodes from a
# network volume (they must be in the image), so the thin-image path is the
# ONLY viable one here — not a fallback. See plans/theme-experiment.md Phase 2.
FROM runpod/worker-comfyui:5.8.6-base

# Impact Pack (FaceDetailer) + Impact Subpack (UltralyticsDetectorProvider).
# comfy-node-install resolves a version compatible with the bundled ComfyUI and
# surfaces install errors (comfy-cli hides them).
RUN comfy-node-install comfyui-impact-pack comfyui-impact-subpack

# comfy-node-install copies the node SOURCE but can silently skip the Python
# deps: it aborts on Impact Pack's `git+.../sam2` requirement yet still exits 0,
# so cv2 / ultralytics / etc. never install and BOTH packs fail to import at
# runtime with "No module named 'cv2'" (FaceDetailer then reports "not found").
# Install each pack's own requirements explicitly, dropping only the heavy,
# build-fragile sam2 git dependency — the t2i-v05-hires graph uses the YOLO bbox
# FaceDetailer path, not SAM. Reading the packs' requirements.txt keeps this in
# sync with whatever comfy-node-install pinned.
RUN grep -vhE '^[[:space:]]*git\+' \
      /comfyui/custom_nodes/comfyui-impact-pack/requirements.txt \
      /comfyui/custom_nodes/comfyui-impact-subpack/requirements.txt \
    | pip install --no-cache-dir -r /dev/stdin

# Guard: `comfy-node-install` can exit 0 without a working install — an earlier
# build shipped the node SOURCE but not its deps, so the packs failed to import
# at runtime ("No module named 'cv2'") and "Node 'FaceDetailer' not found" hit
# every job. verify_nodes.py asserts BOTH the node sources are present AND their
# runtime deps import, so a broken install fails THIS build, not every render.
COPY verify_nodes.py /tmp/verify_nodes.py
RUN python /tmp/verify_nodes.py

# Point ComfyUI at the checkpoint + detector models on the attached network
# volume (mounted at /runpod-volume on serverless). ComfyUI auto-loads this file
# from its base dir. Nothing is downloaded or baked into the image.
COPY extra_model_paths.yaml /comfyui/extra_model_paths.yaml
