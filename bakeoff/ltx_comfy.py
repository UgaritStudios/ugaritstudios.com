"""LTX-2.5 via ComfyUI using Lightricks' official int8 weights (fits a 48 GB GPU).
Rebuilds the official ComfyUI templates video_ltx2_5_t2v / _i2v (two-stage: half-res 8-step distilled pass,
x2 latent upscale, 3-step refine) as an API prompt. Same 6 shots and seeds as the Wan bake-off.
Env: DROP, JOB, HF_TOKEN (gated repo), optional LTX_SECONDS (default 5).
"""
import os, sys, json, time, shutil, subprocess, traceback, urllib.error
sys.path.insert(0, "/w")
import bake
from bake import log, up, comfy_api, W, OUT, COMFY, PHOTO_SHOTS, TEXT_SHOTS

SECS = int(os.environ.get("LTX_SECONDS", "5")); FPS = 24
WIDTH, HEIGHT = 1280, 720
FILES = [  # (repo, path in repo, ComfyUI models subfolder)
    ("Lightricks/LTX-2.5", "diffusion_models/ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors", "diffusion_models"),
    ("Lightricks/LTX-2.5", "text_encoders/gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors", "text_encoders"),
    ("Lightricks/LTX-2.5", "vae/ltx-2.5-video-vae-bf16.safetensors", "vae"),
    ("Lightricks/LTX-2.5", "vae/ltx-2.5-audio-vae-bf16.safetensors", "vae"),
    ("Lightricks/LTX-2.5", "latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors", "latent_upscale_models"),
]
NEG = "pc game, console game, video game, cartoon, childish, ugly, text, watermark"

def download():
    from huggingface_hub import hf_hub_download
    for repo, path, sub in FILES:
        t0 = time.time(); d = f"{COMFY}/models/{sub}"; os.makedirs(d, exist_ok=True)
        p = hf_hub_download(repo, path, local_dir=f"{W}/hf")
        dst = f"{d}/{os.path.basename(path)}"
        if not os.path.exists(dst): os.symlink(p, dst)
        log("dl", os.path.basename(path), f"{os.path.getsize(p)/1e9:.1f}GB", f"{time.time()-t0:.0f}s")

INFO = {}
def widget_names(cls):
    """Widget input names in UI order, plus which ones carry an extra control_after_generate value."""
    spec = INFO[cls]["input"]; names = []
    for sect in ("required", "optional"):
        for name, s in spec.get(sect, {}).items():
            t = s[0]; opts = s[1] if len(s) > 1 and isinstance(s[1], dict) else {}
            if isinstance(t, list) or t in ("INT", "FLOAT", "STRING", "BOOLEAN", "COMBO"):
                names.append((name, bool(opts.get("control_after_generate"))))
    return names

class G:
    def __init__(self): self.p = {}; self.n = 0
    def add(self, cls, links=None, named=None, pos=None):
        if cls not in INFO: raise RuntimeError(f"node class missing in this ComfyUI: {cls}")
        self.n += 1; nid = str(self.n); inputs = {}
        if pos:
            vals = list(pos)
            for name, ctl in widget_names(cls):
                if not vals: break
                inputs[name] = vals.pop(0)
                if ctl and vals and vals[0] in ("fixed", "randomize", "increment", "decrement"): vals.pop(0)
        inputs.update(named or {})
        for k, v in (links or {}).items(): inputs[k] = [v[0], v[1]]
        self.p[nid] = {"class_type": cls, "inputs": inputs}; return nid

def build(prompt, seed, prefix, image_name=None):
    g = G(); L = SECS * FPS + 1
    unet = g.add("UNETLoader", named={"unet_name": os.path.basename(FILES[0][1]), "weight_dtype": "default"})
    clip = g.add("CLIPLoader", pos=[os.path.basename(FILES[1][1]), "ltxv", "default"])
    vae = g.add("VAELoader", named={"vae_name": os.path.basename(FILES[2][1])})
    avae = g.add("VAELoader", named={"vae_name": os.path.basename(FILES[3][1])})
    ups = g.add("LatentUpscaleModelLoader", named={"model_name": os.path.basename(FILES[4][1])})
    pos_c = g.add("CLIPTextEncode", links={"clip": (clip, 0)}, named={"text": prompt})
    neg_c = g.add("CLIPTextEncode", links={"clip": (clip, 0)}, named={"text": NEG})
    cond = g.add("LTXVConditioning", links={"positive": (pos_c, 0), "negative": (neg_c, 0)}, named={"frame_rate": float(FPS)})
    vlat = g.add("EmptyLTXVLatentVideo", pos=[WIDTH // 2, HEIGHT // 2, L, 1])
    alat = g.add("LTXVEmptyLatentAudio", links={"audio_vae": (avae, 0)}, named={"frames_number": L, "frame_rate": FPS, "batch_size": 1})
    if image_name:
        img = g.add("LoadImage", named={"image": image_name})
        pre = g.add("LTXVPreprocess", links={"image": (img, 0)}, pos=[18])  # photos are already cropped to 1280x720
        vlat = g.add("LTXVImgToVideoInplace", links={"vae": (vae, 0), "image": (pre, 0), "latent": (vlat, 0)}, pos=[0.7, False])
    av1 = g.add("LTXVConcatAVLatent", links={"video_latent": (vlat, 0), "audio_latent": (alat, 0)})
    gd1 = g.add("LTXVDualCFGGuider", links={"model": (unet, 0), "positive": (cond, 0), "negative": (cond, 1)}, pos=[1, 1])
    s1 = g.add("SamplerCustomAdvanced", links={
        "noise": (g.add("RandomNoise", pos=[seed, "fixed"]), 0), "guider": (gd1, 0),
        "sampler": (g.add("KSamplerSelect", pos=["euler_ancestral"]), 0),
        "sigmas": (g.add("ManualSigmas", pos=["1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"]), 0),
        "latent_image": (av1, 0)})
    sep1 = g.add("LTXVSeparateAVLatent", links={"av_latent": (s1, 0)})
    upl = g.add("LTXVLatentUpsampler", links={"samples": (sep1, 0), "upscale_model": (ups, 0), "vae": (vae, 0)})
    if image_name:
        upl = g.add("LTXVImgToVideoInplace", links={"vae": (vae, 0), "image": (pre, 0), "latent": (upl, 0)}, pos=[1, False])
    av2 = g.add("LTXVConcatAVLatent", links={"video_latent": (upl, 0), "audio_latent": (sep1, 1)})
    gd2 = g.add("LTXVDualCFGGuider", links={"model": (unet, 0), "positive": (cond, 0), "negative": (cond, 1)}, pos=[1, 1])
    s2 = g.add("SamplerCustomAdvanced", links={
        "noise": (g.add("RandomNoise", pos=[42, "fixed"]), 0), "guider": (gd2, 0),
        "sampler": (g.add("KSamplerSelect", pos=["euler_ancestral"]), 0),
        "sigmas": (g.add("ManualSigmas", pos=["0.85, 0.7250, 0.4219, 0.0"]), 0), "latent_image": (av2, 0)})
    sep2 = g.add("LTXVSeparateAVLatent", links={"av_latent": (s2, 0)})
    frames = g.add("VAEDecodeTiled", links={"samples": (sep2, 0), "vae": (vae, 0)}, pos=[512, 64, 64, 16])
    audio = g.add("LTXVAudioVAEDecode", links={"samples": (sep2, 1), "audio_vae": (avae, 0)})
    vid = g.add("CreateVideo", links={"images": (frames, 0), "audio": (audio, 0)}, named={"fps": float(FPS)})
    g.add("SaveVideo", links={"video": (vid, 0)}, pos=[f"video/{prefix}", "auto", "auto"])
    return g.p

def main():
    T0 = time.time(); times = {}
    bake.fetch_photos()
    shots = [s for s in PHOTO_SHOTS if s.get("image")] + TEXT_SHOTS
    try: download()
    except Exception as e: log("LTX DOWNLOAD FAILED", repr(e)[:600]); return
    srv = subprocess.Popen(f"cd {COMFY} && exec python main.py --listen 127.0.0.1 --port 8188 > {W}/comfy.log 2>&1", shell=True, start_new_session=True)
    for _ in range(300):
        try: comfy_api("/system_stats"); break
        except Exception: time.sleep(2)
    INFO.update(comfy_api("/object_info")); log("comfy up, node classes", len(INFO))
    import torch; log("torch", torch.__version__, torch.version.cuda, torch.cuda.get_device_name(0))
    need = ["LTXVDualCFGGuider", "LTXVConcatAVLatent", "LTXVLatentUpsampler", "LTXVImgToVideoInplace", "ManualSigmas", "LTXVEmptyLatentAudio", "LTXVAudioVAEDecode", "LatentUpscaleModelLoader"]
    log("missing classes", [c for c in need if c not in INFO])
    for c in need[:2] + ["LTXVImgToVideoInplace", "LTXVPreprocess", "LTXVEmptyLatentAudio", "CLIPLoader"]:
        if c in INFO: log("widgets", c, widget_names(c))
    for k, s in enumerate(shots):
        sid = f"ltx_{s['id']}"; out = f"{OUT}/{sid}.mp4"; t0 = time.time()
        try:
            iname = None
            if s.get("image"):
                iname = f"{s['id']}.jpg"; shutil.copy(s["image"], f"{COMFY}/input/{iname}")
            wf = build(s["prompt"], 3000 + k, sid, iname)
            if k == 0: json.dump(wf, open(f"{OUT}/ltx_prompt_example.json", "w"), indent=1)
            try: r = comfy_api("/prompt", {"prompt": wf})
            except urllib.error.HTTPError as e: r = {"http_error": e.code, "body": e.read().decode()[:3000]}
            if "prompt_id" not in r: log("prompt rejected", sid, json.dumps(r)[:1500]); continue
            pid = r["prompt_id"]
            while True:
                time.sleep(3); h = comfy_api(f"/history/{pid}")
                if pid in h: break
            st = h[pid].get("status", {})
            if st.get("status_str") != "success": log("ltx failed", sid, json.dumps(st)[:1500]); continue
            vids = [v for o in h[pid]["outputs"].values() for key in ("images", "videos", "gifs") for v in o.get(key, [])]
            src = f"{COMFY}/output/{vids[0].get('subfolder','')}/{vids[0]['filename']}"
            shutil.copy(src, out); times[sid] = round(time.time() - t0)
            log("ltx ok", sid, times[sid], "s"); up(out, sid + ".mp4")
        except Exception as e:
            log("ltx exception", sid, repr(e)[:800]); traceback.print_exc(file=bake.LOG)
    try: up(f"{OUT}/ltx_prompt_example.json", "ltx_prompt_example.txt")
    except Exception: pass
    subprocess.run(f"tail -60 {W}/comfy.log > {OUT}/comfy_tail.txt", shell=True); up(f"{OUT}/comfy_tail.txt", "comfy_tail.txt")
    json.dump({"ltx": times, "total_s": round(time.time() - T0)}, open(f"{OUT}/times.json", "w")); up(f"{OUT}/times.json", "times.txt")
    log("ALL DONE", round(time.time() - T0))

if __name__ == "__main__":
    main()
