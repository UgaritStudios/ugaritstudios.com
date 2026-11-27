#!/bin/bash
# Render Blender templates on a Runpod GPU. Env: DROP (render receiver URL), JOB (job tag), SPECS (space-separated spec files in this repo dir), REPO (raw base URL incl. commit)
mkdir -p /w/out; exec > /w/log.txt 2>&1; set -x
UP(){ curl -s -m 900 -X POST -H "Content-Type: application/octet-stream" --data-binary @"$1" "$DROP?job=$JOB&name=$2"; echo; }
( n=0; while true; do sleep 90; n=$((n+1)); cp /w/log.txt /w/hb.txt; UP /w/hb.txt "log_hb$(printf %02d $n).txt" >/dev/null 2>&1; done ) &
[ -f /w/DONE ] && sleep infinity
T00=$(date +%s); export DEBIAN_FRONTEND=noninteractive
apt-get update -qq && apt-get install -y -qq ffmpeg xz-utils libxrender1 libxi6 libxkbcommon0 libsm6 libgl1 libxxf86vm1 libxfixes3 libegl1 >/dev/null
URL=$(python3 - <<'PY'
import re,urllib.request
g=lambda u: urllib.request.urlopen(u,timeout=60).read().decode()
vs=sorted({(int(a),int(b)) for a,b in re.findall(r'Blender(\d+)\.(\d+)/',g("https://download.blender.org/release/"))})
for a,b in reversed(vs):
    d=f"https://download.blender.org/release/Blender{a}.{b}/"; fs=re.findall(r'blender-(\d+\.\d+\.\d+)-linux-x64\.tar\.xz"',g(d))
    if fs: print(d+"blender-"+sorted(fs,key=lambda s:[int(x) for x in s.split('.')])[-1]+"-linux-x64.tar.xz"); break
PY
)
[ -z "$URL" ] && URL="https://download.blender.org/release/Blender4.5/blender-4.5.3-linux-x64.tar.xz"
curl -sL "$URL" | tar -xJ -C /w; B=$(ls -d /w/blender-*/blender | head -1); $B --version | head -1
pip install -q --break-system-packages pillow 2>/dev/null || pip install -q pillow
cd /w && for f in globe_pins.py bars3d.py overlay.py overlay_bars.py make_globe_texture.py Inter-Bold.otf Inter-Regular.otf $SPECS; do curl -sfL "$REPO/$f" -o "/w/$f" || echo "MISSING $f"; done
curl -sL https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_admin_0_countries.geojson -o /w/countries.geojson
echo "setup_seconds=$(( $(date +%s)-T00 ))"; nvidia-smi --query-gpu=name --format=csv,noheader
for SPEC in $SPECS; do
  NAME=$(python3 -c "import json;print(json.load(open('/w/$SPEC'))['job_name'])"); TPL=$(python3 -c "import json;print(json.load(open('/w/$SPEC'))['template'])")
  F=/w/f_$NAME; O=/w/o_$NAME; mkdir -p $F $O; T0=$(date +%s)
  if [ "$TPL" = "globe_pins" ]; then
    python3 /w/make_globe_texture.py /w/$SPEC /w/countries.geojson /w/tex_$NAME.png 8192
    $B -b -P /w/globe_pins.py -- --spec /w/$SPEC --tex /w/tex_$NAME.png --out $F/frame_ --track $F/track.json --device GPU --samples 48 2>&1 | grep --line-buffered -E "Saved:|Error|GPU_|NO_GPU|DONE"
    python3 /w/overlay.py /w/$SPEC $F/track.json $F $O /w/Inter-Bold.otf /w/Inter-Regular.otf
  elif [ "$TPL" = "bars3d" ]; then
    $B -b -P /w/bars3d.py -- --spec /w/$SPEC --out $F/frame_ --track $F/track.json --device GPU --samples 48 2>&1 | grep --line-buffered -E "Saved:|Error|GPU_|NO_GPU|DONE"
    python3 /w/overlay_bars.py /w/$SPEC $F/track.json $F $O /w/Inter-Bold.otf /w/Inter-Regular.otf
  fi
  echo "render_seconds_$NAME=$(( $(date +%s)-T0 ))"
  ffmpeg -y -loglevel error -framerate 24 -i $O/frame_%04d.png -c:v libx264 -pix_fmt yuv420p -crf 18 /w/out/$NAME.mp4 && UP /w/out/$NAME.mp4 $NAME.mp4
done
echo "total_seconds=$(( $(date +%s)-T00 ))"; UP /w/log.txt run_log.txt; touch /w/DONE; sleep infinity
