# worker-pony-theme — thin ComfyUI serverless image for `/theme-experiment`

Build artifact for **ETAPA #03 pre-flight** provisioning (Phase 2 of
`plans/theme-experiment.md`). RunPod builds this image **from GitHub** (no local
Docker) and runs it as a scale-to-zero serverless endpoint that renders the
Pony-Realism `t2i-v05-hires` workflow on demand.

## What it is

A 3-line thin layer on top of the official RunPod ComfyUI worker:

- `FROM runpod/worker-comfyui:5.8.6-base` — ComfyUI + the `/run|/status` handler.
- Installs `comfyui-impact-pack` + `comfyui-impact-subpack` (FaceDetailer +
  UltralyticsDetectorProvider) — the only nodes the workflow needs beyond core.
- Copies `extra_model_paths.yaml` so ComfyUI reads the checkpoint + YOLO
  detectors from the attached **PONY/ZIMAGE** network volume at runtime.

**No models are baked into the image.** They stay on the network volume.

## Why a custom image at all (ADR-0002 deviation)

ADR-0002 assumed a models-only volume + stock image (zero Docker). In reality the
PONY/ZIMAGE volume is a full self-contained *runpod-slim* ComfyUI install, and
`worker-comfyui` **cannot load custom nodes from a network volume** — they must
live in the image. So this thin image is the *only* viable path, not a fallback.

## Deploy (RunPod console — GitHub build)

GitHub-built serverless endpoints are **console-only** (no API/CLI). One time:

1. RunPod → Settings → Connections → **GitHub** → authorize this repo.
2. Serverless → **New Endpoint** → *Import Git Repository* → pick this repo.
   - Branch: `main`  ·  Dockerfile path: `Dockerfile` (repo root).
3. Configure:
   - **Network volume:** `PONY/ZIMAGE` (`22gwsnr9pl`)
   - **Region / datacenter:** `EU-RO-1` (the volume is region-locked)
   - **GPU:** RTX PRO 4500 (Blackwell)
   - **Workers:** min `0` (scale to zero), max `3`  ·  **FlashBoot:** on
4. Deploy, wait for the build, copy the **Endpoint ID**.

Then record the handshake in `.secrets/runpod.json`
(`{api_key, endpoint_id, network_volume_id, region}`) so `/theme-experiment` can
find the endpoint.
