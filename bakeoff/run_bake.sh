#!/bin/bash
# Bake-off pod entry. Env: DROP, JOB, REPO (raw base URL incl. commit, folder bakeoff/), optional HF_TOKEN
mkdir -p /w; exec >> /w/log.txt 2>&1; set -x
UP(){ curl -s -m 900 -X POST -H "Content-Type: application/octet-stream" --data-binary @"$1" "$DROP?job=$JOB&name=$2"; echo; }
( n=0; while true; do sleep 120; n=$((n+1)); cp /w/log.txt /w/hb.txt; UP /w/hb.txt "log_hb$(printf %02d $n).txt" >/dev/null 2>&1; done ) &
[ -f /w/DONE ] && sleep infinity
export DEBIAN_FRONTEND=noninteractive HF_HUB_ENABLE_HF_TRANSFER=1
{ set +x; } 2>/dev/null
[ -z "$HF_TOKEN" ] && unset HF_TOKEN
case "$HF_TOKEN" in *RUNPOD_SECRET*) unset HF_TOKEN;; esac
[ -n "$HF_TOKEN" ] && echo "HF_TOKEN present (len ${#HF_TOKEN})" || echo "HF_TOKEN missing"; set -x
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader; df -h /w | tail -1; free -g | head -2
apt-get update -qq && apt-get install -y -qq ffmpeg git > /dev/null
pip install -q --break-system-packages pillow numpy huggingface_hub hf_transfer imageio imageio-ffmpeg 2>&1 | tail -1
pip install -q --break-system-packages "git+https://github.com/huggingface/diffusers" transformers accelerate sentencepiece bitsandbytes 2>&1 | tail -2
curl -sfL "$REPO/bake.py" -o /w/bake.py; curl -sfL "$REPO/../blender/Inter-Bold.otf" -o /w/Inter-Bold.otf
if [ "$ONLY" != "ltx" ]; then git clone -q --depth 1 https://github.com/comfyanonymous/ComfyUI /w/ComfyUI
cd /w/ComfyUI && grep -v -E '^(torch|torchvision|torchaudio)([<>=].*)?$' requirements.txt > /w/req2.txt && pip install -q --break-system-packages -r /w/req2.txt 2>&1 | tail -2; fi
python3 -c "import torch;print('torch',torch.__version__,torch.cuda.is_available())"
cd /w && python3 /w/bake.py
UP /w/log.txt bake_log.txt; touch /w/DONE; sleep infinity
