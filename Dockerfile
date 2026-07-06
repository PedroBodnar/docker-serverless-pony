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

# Point ComfyUI at the checkpoint + detector models on the attached network
# volume (mounted at /runpod-volume on serverless). ComfyUI auto-loads this file
# from its base dir. Nothing is downloaded or baked into the image.
COPY extra_model_paths.yaml /comfyui/extra_model_paths.yaml
