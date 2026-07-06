# worker-pony-theme — thin ComfyUI serverless image for `/theme-experiment`

Build artifact for **ETAPA #03 pre-flight** provisioning (Phase 2 of
`plans/theme-experiment.md`). RunPod builds this image **from GitHub** (no local
Docker) and runs it as a scale-to-zero serverless endpoint that renders the
Pony-Realism `t2i-v05-hires` workflow on demand.

## What it is

A thin layer on top of the official RunPod ComfyUI worker:

- `FROM runpod/worker-comfyui:5.8.6-base` — ComfyUI + the `/run|/status` handler.
- Installs `comfyui-impact-pack` + `comfyui-impact-subpack` (FaceDetailer +
  UltralyticsDetectorProvider) — the only nodes the workflow needs beyond core.
- Installs those packs' Python deps explicitly (`cv2`, `ultralytics`, …) from
  their `requirements.txt`, minus the heavy `sam2` git dep. `comfy-node-install`
  copies the node source but silently skips these, and without them the packs
  fail to import at runtime with `No module named 'cv2'`.
- Runs `verify_nodes.py` at build time — asserts those two node sources landed
  **and** their runtime deps import, and **fails the build** otherwise (below).
- Copies `extra_model_paths.yaml` so ComfyUI reads the checkpoint + YOLO
  detectors from the attached **PONY/ZIMAGE** network volume at runtime.

**No models are baked into the image.** They stay on the network volume.

> **The three files at this dir must sit at the build repo's ROOT** (`Dockerfile`,
> `extra_model_paths.yaml`, `verify_nodes.py`) — RunPod builds from the GitHub
> repo root, not from this content repo.

### Why the build-time guard exists

`comfy-node-install` can exit 0 without a working install — twice now. First it
shipped without the Impact Pack source at all. Then, after that was fixed, it
shipped the source but **not the Python deps** (it aborts on the pack's `sam2`
git requirement yet exits 0), so both packs failed to import at runtime with
`No module named 'cv2'` and every render job still hit
`Node 'FaceDetailer' not found. The custom node may not be installed.`
`verify_nodes.py` now checks **both** layers: it greps the installed
`custom_nodes/` sources for `FaceDetailer` and `UltralyticsDetectorProvider`,
**and** imports the critical runtime deps (`cv2`, `ultralytics`, …), exiting
non-zero if anything is missing — so a broken install fails the RunPod build
instead of shipping.

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
   - **GPU:** `RTX 4090` / `RTX 5090` / `RTX A6000` (all 24–48 GB, all present in
     EU-RO-1). **Not RTX PRO 4500** — the Blackwell PRO 4500 is *pod-only* and is
     rejected by the serverless GPU enum. The A5000/RTX 3090 the endpoint was
     first created with do **not** exist in EU-RO-1 and left workers unschedulable.
   - **Workers:** min `0` (scale to zero), max `3`  ·  **FlashBoot:** on
4. Deploy, wait for the build, copy the **Endpoint ID**.

Then record the handshake in `.secrets/runpod.json`
(`{api_key, endpoint_id, network_volume_id, region}`) so `/theme-experiment` can
find the endpoint.
