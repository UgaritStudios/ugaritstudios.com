#!/bin/bash
J=blender1
mkdir -p /w/f; exec > /w/log.txt 2>&1; set -x
UP(){ curl -s -m 600 -X POST --data-binary @"$1" "$DROP?job=$J&name=$2"; echo; }
( n=0; while true; do sleep 90; n=$((n+1)); cp /w/log.txt /w/hb.txt; UP /w/hb.txt "log_hb$(printf %02d $n).txt" >/dev/null 2>&1; done ) &
if [ -f /w/DONE ]; then sleep infinity; fi
T00=$(date +%s)
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq && apt-get install -y -qq ffmpeg xz-utils libxrender1 libxi6 libxkbcommon0 libsm6 libgl1 libxxf86vm1 libxfixes3 libegl1 >/dev/null
URL=$(python3 - <<'PY'
import re,urllib.request
def get(u): return urllib.request.urlopen(u,timeout=60).read().decode()
idx=get("https://download.blender.org/release/")
vers=sorted({(int(a),int(b)) for a,b in re.findall(r'Blender(\d+)\.(\d+)/',idx)})
for a,b in reversed(vers):
    d=f"https://download.blender.org/release/Blender{a}.{b}/"
    files=re.findall(r'blender-(\d+\.\d+\.\d+)-linux-x64\.tar\.xz"',get(d))
    if files:
        v=sorted(files,key=lambda s:[int(x) for x in s.split('.')])[-1]
        print(f"{d}blender-{v}-linux-x64.tar.xz"); break
PY
)
[ -z "$URL" ] && URL="https://download.blender.org/release/Blender4.5/blender-4.5.3-linux-x64.tar.xz"
echo "BLENDER_URL=$URL"
curl -sL "$URL" | tar -xJ -C /w
B=$(ls -d /w/blender-*/blender | head -1); $B --version | head -1
pip install -q --break-system-packages global-land-mask pillow numpy 2>/dev/null || pip install -q global-land-mask pillow numpy
python3 - <<'PY'
from global_land_mask import globe; import numpy as np; from PIL import Image
water=globe._mask[::5, ::5]; land=~water
img=np.zeros(water.shape+(3,),np.uint8); img[:]=(18,48,92); img[land]=(214,166,70)
Image.fromarray(img).resize((8192,4096),Image.LANCZOS).save('/w/earth_albedo.png')
PY
curl -sL "https://raw.githubusercontent.com/UgaritStudios/ugaritstudios.com/render-jobs/blender/globe_flyover.py" -o /w/globe_flyover.py; wc -c /w/globe_flyover.py
T0=$(date +%s); echo "setup_seconds=$((T0-T00))"
nvidia-smi --query-gpu=name,memory.total --format=csv
$B -b -P /w/globe_flyover.py -- --out /w/f/frame_ --frames 1-120 --samples 64 --res 1920x1080 --device GPU --tex /w/earth_albedo.png 2>&1 | grep -vE "^Fra:|Sample|Path Tracing" | tail -40
T1=$(date +%s); echo "render_seconds=$((T1-T0)) frames=$(ls /w/f | wc -l)"
ffmpeg -y -loglevel error -framerate 24 -i /w/f/frame_%04d.png -c:v libx264 -pix_fmt yuv420p -crf 18 -preset medium /w/globe_flyover_1080p.mp4
ls -la /w/globe_flyover_1080p.mp4
UP /w/globe_flyover_1080p.mp4 globe_flyover_1080p.mp4
UP /w/f/frame_0120.png frame_0120.png
echo "total_seconds=$(( $(date +%s)-T00 ))"
UP /w/log.txt blender_log.txt
touch /w/DONE
sleep infinity
