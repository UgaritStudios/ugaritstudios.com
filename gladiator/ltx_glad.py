"""LTX-2.5 image-to-video for the BoomDoom gladiator verdict (bake-off vs Wan 2.2). Env: REPO, SHOTS, DROP, JOB, HF_TOKEN, LTX_SECONDS."""
import os, sys, json, subprocess, urllib.request
sys.path.insert(0, "/w")
import bake, ltx_comfy as L
cfg = json.load(urllib.request.urlopen(os.environ["REPO"] + "/" + os.environ["SHOTS"]))
os.makedirs("/w/img", exist_ok=True); shots = []
for s in cfg["shots"]:
    raw = f"/w/img/{s['id']}_raw"; p = f"/w/img/{s['id']}.jpg"
    urllib.request.urlretrieve(s["image_url"], raw)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-vf", "scale=1280:720", "-q:v", "2", p], check=True)
    shots.append({"id": s["id"], "image": p, "prompt": s["prompt"]})
bake.log("ltx shots", [s["id"] for s in shots])
L.PHOTO_SHOTS = shots; L.TEXT_SHOTS = []; bake.fetch_photos = lambda: None
L.NEG = "low quality, blurry, distorted, deformed hands, extra fingers, extra limbs, morphing, flicker, text, watermark"
L.main()
