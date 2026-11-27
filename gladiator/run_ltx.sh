#!/bin/bash
# LTX-2.5 gladiator pod. Env: DROP, JOB, REPO (raw base incl. commit, folder gladiator/), BAKE (raw base of bakeoff/), SHOTS, HF_TOKEN, LTX_SECONDS
mkdir -p /w; exec >> /w/log.txt 2>&1; set -x
UP(){ curl -s -m 900 -X POST -H "Content-Type: application/octet-stream" --data-binary @"$1" "$DROP?job=$JOB&name=$2"; echo; }
( n=0; while true; do sleep 120; n=$((n+1)); cp /w/log.txt /w/hb.txt; UP /w/hb.txt "log_hb$(printf %02d $n).txt" >/dev/null 2>&1; done ) &
[ -f /w/DONE ] && sleep infinity
export DEBIAN_FRONTEND=noninteractive HF_HUB_ENABLE_HF_TRANSFER=1 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
{ set +x; } 2>/dev/null
case "$HF_TOKEN" in *RUNPOD_SECRET*|"") unset HF_TOKEN; echo "HF_TOKEN missing";; *) echo "HF_TOKEN present";; esac; set -x
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
apt-get update -qq && apt-get install -y -qq ffmpeg git > /dev/null
pip install -q --break-system-packages pillow numpy huggingface_hub hf_transfer imageio imageio-ffmpeg 2>&1 | tail -1
curl -sfL "$BAKE/bake.py" -o /w/bake.py; curl -sfL "$BAKE/ltx_comfy.py" -o /w/ltx_comfy.py; curl -sfL "$REPO/ltx_glad.py" -o /w/ltx_glad.py
git clone -q --depth 1 https://github.com/comfyanonymous/ComfyUI /w/ComfyUI
cd /w/ComfyUI && grep -v -E '^(torch|torchvision|torchaudio)([<>=].*)?$' requirements.txt > /w/req2.txt && pip install -q --break-system-packages -r /w/req2.txt 2>&1 | tail -2
pip install -q --break-system-packages --upgrade torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130 2>&1 | tail -2
cd /w && python3 /w/ltx_glad.py
UP /w/log.txt ltx_log.txt; touch /w/DONE; sleep infinity
