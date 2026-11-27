"""Wan 2.2 vs LTX-2.5 bake-off on one Runpod GPU.
Same shots on both models: 3 real-photo animations (image-to-video) + 3 imagined scenes (text-to-video).
Uploads each clip, a labelled side-by-side per shot and one combined reel to the Render Receiver.
Env: DROP, JOB, REPO (raw base for fonts), optional HF_TOKEN.
"""
import os, re, sys, json, time, glob, shutil, subprocess, urllib.request, urllib.parse, inspect, traceback

JOB, DROP = os.environ["JOB"], os.environ["DROP"]
W = "/w"; OUT = f"{W}/out"; os.makedirs(OUT, exist_ok=True)
LOG = open(f"{W}/log.txt", "a", buffering=1)
def log(*a):
    s = time.strftime("%H:%M:%S ") + " ".join(str(x) for x in a); print(s, flush=True); LOG.write(s + "\n")
def up(path, name):
    r = subprocess.run(["curl", "-s", "-m", "900", "-X", "POST", "-H", "Content-Type: application/octet-stream",
                        "--data-binary", "@" + path, f"{DROP}?job={JOB}&name={name}"], capture_output=True, text=True)
    log("upload", name, r.stdout[:120])
UA = {"User-Agent": "UgaritStudiosBakeoff/1.0 (admin@ugaritstudios.com)"}
def get_json(url):
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read())

# ---------------- shots ----------------
PHOTO_SHOTS = [
    {"id": "p1_store", "query": "Mixue Ice Cream Tea shop Zhengzhou",
     "prompt": "Real street photo comes alive: pedestrians walk past the ice cream shop at a natural pace, a scooter passes, leaves move slightly in the breeze, slow gentle camera push-in. The shop sign and its lettering stay perfectly still and sharp. Photorealistic, natural daylight."},
    {"id": "p2_historic", "query": "Fifth Avenue New York 1920s street",
     "prompt": "Vintage black and white street photo comes alive: pedestrians in 1920s clothing walk along the sidewalk, early automobiles drive slowly down the avenue, slight film grain, slow camera drift to the right. Buildings stay solid and straight. Authentic archival film look."},
    {"id": "p3_product", "query": "soft serve ice cream cone",
     "prompt": "Close-up product shot comes alive: the soft serve ice cream cone turns slowly, a tiny drip of melting ice cream runs down the side, soft background bokeh shifts gently, subtle slow camera orbit. Appetizing, photorealistic, warm light."},
]
TEXT_SHOTS = [
    {"id": "t1_ships", "prompt": "Wide cinematic shot, year 1627: two dark wooden three-masted sailing ships with plain grey canvas sails emerge from thick sea fog toward a rocky black volcanic coastline of Iceland, cold grey waves, seabirds, overcast sky, slow aerial camera move forward. Photorealistic, desaturated, film grain."},
    {"id": "t2_fishermen", "prompt": "Medium shot, year 1627 Iceland: three fishermen in thick brown wool tunics and woollen caps drag a small wooden rowing boat up a black sand beach, wind blowing, cold grey surf behind them, they strain and pull at real-time speed. Photorealistic, overcast, desaturated, film grain."},
    {"id": "t3_woman", "prompt": "Close-up portrait, year 1627 Iceland: an elderly woman wearing a dark wool shawl over her head looks out toward the sea with a worried, frightened expression, wind moves loose grey hair across her face, her eyes narrow, slow push-in. Photorealistic, soft overcast light, desaturated, film grain."},
]
ALLOWED = re.compile(r"^(cc0|public domain|pd|cc by(-sa)? ?[0-9.]*|cc-by(-sa)?-[0-9.]+)", re.I)

def fetch_photos():
    credits = []
    for s in PHOTO_SHOTS:
        s["image"] = None
        try:
            q = urllib.parse.quote(s["query"])
            res = get_json(f"https://commons.wikimedia.org/w/api.php?action=query&format=json&generator=search&gsrnamespace=6&gsrlimit=15&gsrsearch={q}&prop=imageinfo&iiprop=url|extmetadata|size&iiurlwidth=1600")
            pages = sorted(res.get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 99))
            for p in pages:
                ii = (p.get("imageinfo") or [{}])[0]; md = ii.get("extmetadata", {})
                lic = md.get("LicenseShortName", {}).get("value", ""); mime_ok = p["title"].lower().endswith((".jpg", ".jpeg", ".png"))
                if not mime_ok or not ALLOWED.match(lic.strip()) or ii.get("width", 0) < 1000: continue
                path = f"{W}/img_{s['id']}.jpg"
                req = urllib.request.Request(ii.get("thumburl") or ii["url"], headers=UA)
                open(path, "wb").write(urllib.request.urlopen(req, timeout=120).read())
                # crop to 16:9 1280x720
                from PIL import Image
                im = Image.open(path).convert("RGB"); w, h = im.size; tw, th = (w, int(w * 9 / 16)) if w / h < 16 / 9 else (int(h * 16 / 9), h)
                im = im.crop(((w - tw) // 2, (h - th) // 2, (w - tw) // 2 + tw, (h - th) // 2 + th)).resize((1280, 720), Image.LANCZOS); im.save(path, quality=95)
                s["image"] = path
                artist = re.sub("<[^>]+>", "", md.get("Artist", {}).get("value", "")).strip()
                credits.append({"shot": s["id"], "file": p["title"], "license": lic, "artist": artist, "url": ii.get("descriptionurl")})
                log("photo", s["id"], p["title"], lic); break
        except Exception as e:
            log("photo fail", s["id"], repr(e)[:300])
    json.dump(credits, open(f"{OUT}/photo_credits.json", "w"), indent=1); up(f"{OUT}/photo_credits.json", "photo_credits.txt")

# ---------------- Wan 2.2 via ComfyUI ----------------
COMFY = f"{W}/ComfyUI"
def comfy_api(path, data=None):
    req = urllib.request.Request("http://127.0.0.1:8188" + path, data=json.dumps(data).encode() if data else None, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r: return json.loads(r.read())

def wan_models():
    from huggingface_hub import list_repo_files, hf_hub_download
    repos = ["Comfy-Org/Wan_2.2_ComfyUI_Repackaged", "Comfy-Org/Wan_2.1_ComfyUI_repackaged", "lightx2v/Wan2.2-Lightning", "Kijai/WanVideo_comfy"]
    files = {}
    for r in repos:
        try: files[r] = list_repo_files(r)
        except Exception as e: log("repo fail", r, e)
    def pick(dest, must, avoid=(), prefer=()):
        best = None
        for r, fl in files.items():
            for f in fl:
                lf = f.lower()
                if lf.endswith(".safetensors") and all(m in lf for m in must) and not any(a in lf for a in avoid):
                    sc = sum(p in lf for p in prefer) * 10 - repos.index(r)
                    if best is None or sc > best[0]: best = (sc, r, f)
        if not best: return None
        _, r, f = best; d = f"{COMFY}/models/{dest}"; os.makedirs(d, exist_ok=True)
        name = re.sub(r"[^A-Za-z0-9_.-]", "_", f.replace("/", "__")); t = f"{d}/{name}"
        if not os.path.exists(t):
            t0 = time.time(); p = hf_hub_download(r, f, local_dir=f"{W}/hf"); shutil.move(p, t); log("dl", f, f"{time.time()-t0:.0f}s")
        return name
    m = {}
    for kind in ("t2v", "i2v"):
        other = "i2v" if kind == "t2v" else "t2v"
        m[kind + "_hi"] = pick("diffusion_models", [kind, "high_noise", "14b", "fp8"], [other, "5b"])
        m[kind + "_lo"] = pick("diffusion_models", [kind, "low_noise", "14b", "fp8"], [other, "5b"])
        m[kind + "_lhi"] = pick("loras", [kind, "4step", "high"], [other], ["lightx2v", "v1.1", "comfy-org"])
        m[kind + "_llo"] = pick("loras", [kind, "4step", "low"], [other], ["lightx2v", "v1.1", "comfy-org"])
    m["te"] = pick("text_encoders", ["umt5", "fp8"], [], ["scaled"]); m["vae"] = pick("vae", ["wan_2.1_vae"], [])
    log("wan models", json.dumps(m)); return m

def wan_wf(m, kind, prompt, seed, prefix, image=None, frames=81, w=1280, h=720):
    fast = bool(m.get(kind + "_lhi") and m.get(kind + "_llo")); steps, split, cfg = (4, 2, 1.0) if fast else (20, 10, 3.5)
    wf = {"1": {"class_type": "UNETLoader", "inputs": {"unet_name": m[kind + "_hi"], "weight_dtype": "default"}},
          "2": {"class_type": "UNETLoader", "inputs": {"unet_name": m[kind + "_lo"], "weight_dtype": "default"}},
          "5": {"class_type": "CLIPLoader", "inputs": {"clip_name": m["te"], "type": "wan", "device": "default"}},
          "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["5", 0]}},
          "7": {"class_type": "CLIPTextEncode", "inputs": {"text": "blurry, low quality, distorted, watermark", "clip": ["5", 0]}},
          "8": {"class_type": "VAELoader", "inputs": {"vae_name": m["vae"]}},
          "14": {"class_type": "VAEDecode", "inputs": {"samples": ["13", 0], "vae": ["8", 0]}},
          "15": {"class_type": "SaveImage", "inputs": {"images": ["14", 0], "filename_prefix": prefix}}}
    pos, neg = ["6", 0], ["7", 0]
    if kind == "i2v":
        shutil.copy(image, f"{COMFY}/input/{prefix}.jpg")
        wf["20"] = {"class_type": "LoadImage", "inputs": {"image": f"{prefix}.jpg"}}
        wf["9"] = {"class_type": "WanImageToVideo", "inputs": {"positive": ["6", 0], "negative": ["7", 0], "vae": ["8", 0], "width": w, "height": h, "length": frames, "batch_size": 1, "start_image": ["20", 0]}}
        pos, neg, lat = ["9", 0], ["9", 1], ["9", 2]
    else:
        wf["9"] = {"class_type": "EmptyHunyuanLatentVideo", "inputs": {"width": w, "height": h, "length": frames, "batch_size": 1}}; lat = ["9", 0]
    hi, lo = ["1", 0], ["2", 0]
    if fast:
        wf["3"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "lora_name": m[kind + "_lhi"], "strength_model": 1.0}}
        wf["4"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["2", 0], "lora_name": m[kind + "_llo"], "strength_model": 1.0}}
        hi, lo = ["3", 0], ["4", 0]
    wf["10"] = {"class_type": "ModelSamplingSD3", "inputs": {"model": hi, "shift": 5.0}}
    wf["11"] = {"class_type": "ModelSamplingSD3", "inputs": {"model": lo, "shift": 5.0}}
    common = {"noise_seed": seed, "steps": steps, "cfg": cfg, "sampler_name": "euler", "scheduler": "simple", "positive": pos, "negative": neg}
    wf["12"] = {"class_type": "KSamplerAdvanced", "inputs": dict(common, model=["10", 0], add_noise="enable", latent_image=lat, start_at_step=0, end_at_step=split, return_with_leftover_noise="enable")}
    wf["13"] = {"class_type": "KSamplerAdvanced", "inputs": dict(common, model=["11", 0], add_noise="disable", latent_image=["12", 0], start_at_step=split, end_at_step=10000, return_with_leftover_noise="disable")}
    return wf

def run_wan(shots):
    times = {}
    try:
        m = wan_models()
    except Exception as e:
        log("wan models failed", repr(e)); return times
    srv = subprocess.Popen(f"cd {COMFY} && exec python main.py --listen 127.0.0.1 --port 8188 > {W}/comfy.log 2>&1", shell=True, start_new_session=True)
    for _ in range(300):
        try: comfy_api("/system_stats"); break
        except Exception: time.sleep(2)
    log("comfy up")
    for k, s in enumerate(shots):
        kind = "i2v" if s.get("image") else "t2v"
        if kind == "i2v" and not (m.get("i2v_hi") and m.get("i2v_lo")): log("no wan i2v models"); continue
        sid = f"wan_{s['id']}"; out = f"{OUT}/{sid}.mp4"; t0 = time.time()
        try:
            pid = comfy_api("/prompt", {"prompt": wan_wf(m, kind, s["prompt"], 2000 + k, sid, s.get("image"))})["prompt_id"]
            while True:
                time.sleep(3); h = comfy_api(f"/history/{pid}")
                if pid in h:
                    st = h[pid].get("status", {})
                    if st.get("status_str") == "error": log("wan error", sid, json.dumps(st)[:800]); break
                    if h[pid].get("outputs"): break
            fr = sorted(glob.glob(f"{COMFY}/output/{sid}_*.png"))
            if fr:
                subprocess.run(f'ffmpeg -y -loglevel error -framerate 16 -pattern_type glob -i "{COMFY}/output/{sid}_*.png" -c:v libx264 -crf 16 -pix_fmt yuv420p "{out}"', shell=True)
                for f in fr: os.remove(f)
                times[sid] = round(time.time() - t0); log("wan ok", sid, times[sid], "s"); up(out, sid + ".mp4")
        except Exception as e:
            log("wan exception", sid, repr(e)[:400])
    try: os.killpg(os.getpgid(srv.pid), 15)
    except Exception: pass
    time.sleep(5); return times

# ---------------- LTX-2.5 via Diffusers ----------------
def run_ltx(shots):
    times = {}
    try:
        import torch, diffusers
        from diffusers import LTX2Pipeline
        try: from diffusers import LTX2ImageToVideoPipeline
        except Exception: LTX2ImageToVideoPipeline = None
        from diffusers.utils import load_image
        try: from diffusers.utils import encode_video
        except Exception:
            try: from diffusers.pipelines.ltx2.export_utils import encode_video
            except Exception: encode_video = None
        try: from diffusers.pipelines.ltx2.utils import DISTILLED_SIGMA_VALUES
        except Exception: DISTILLED_SIGMA_VALUES = None
        log("diffusers", diffusers.__version__, "sigmas", DISTILLED_SIGMA_VALUES is not None, "i2v", LTX2ImageToVideoPipeline is not None)
        from huggingface_hub import snapshot_download
        t0 = time.time()
        path = snapshot_download("Lightricks/LTX-2.5-Diffusers", ignore_patterns=["transformer_full/*", "*.md"], local_dir=f"{W}/ltx")
        log("ltx downloaded", f"{time.time()-t0:.0f}s", subprocess.run(f"du -sh {W}/ltx", shell=True, capture_output=True, text=True).stdout.strip())
        pipe = LTX2Pipeline.from_pretrained(path, dtype=torch.bfloat16)
        pipe.enable_model_cpu_offload()
        log("ltx call signature", str(inspect.signature(pipe.__call__))[:1500])
        if encode_video: log("encode_video signature", str(inspect.signature(encode_video))[:400])
        ipipe = None
        if LTX2ImageToVideoPipeline:
            try: ipipe = LTX2ImageToVideoPipeline.from_pipe(pipe); ipipe.enable_model_cpu_offload()
            except Exception as e: log("i2v from_pipe failed", repr(e)[:300])
    except Exception as e:
        log("LTX SETUP FAILED", repr(e)[:800]); traceback.print_exc(file=LOG); return times
    for k, s in enumerate(shots):
        sid = f"ltx_{s['id']}"; out = f"{OUT}/{sid}.mp4"; t0 = time.time()
        p = ipipe if s.get("image") else pipe
        if p is None: log("no ltx pipe for", sid); continue
        kw = dict(prompt=s["prompt"], width=1280, height=704, num_frames=121, frame_rate=24.0,
                  generator=torch.Generator("cuda").manual_seed(3000 + k), output_type="np", return_dict=False)
        if DISTILLED_SIGMA_VALUES is not None: kw.update(sigmas=DISTILLED_SIGMA_VALUES, guidance_scale=1.0)
        else: kw.update(num_inference_steps=8, guidance_scale=1.0)
        if s.get("image"): kw["image"] = load_image(s["image"])
        try:
            params = inspect.signature(p.__call__).parameters
            kw = {a: b for a, b in kw.items() if a in params or "kwargs" in params}
            res = p(**kw); video = res[0]; audio = res[1] if len(res) > 1 else None
            import numpy as np
            v = np.asarray(video[0]) if not hasattr(video, "frames") else np.asarray(video.frames[0])
            saved = False
            if encode_video is not None:
                try:
                    a = audio[0].float().cpu() if audio is not None and hasattr(audio[0], "float") else None
                    sr = getattr(getattr(p, "vocoder", None), "config", None); sr = getattr(sr, "output_sampling_rate", 24000) if sr else 24000
                    encode_video(v, fps=24, audio=a, audio_sample_rate=sr, output_path=out); saved = os.path.exists(out)
                except Exception as e: log("encode_video failed", repr(e)[:300])
            if not saved:
                fd = f"{W}/ltxf_{sid}"; os.makedirs(fd, exist_ok=True)
                from PIL import Image
                vv = v if v.max() > 1.5 else (v * 255)
                for i, fr in enumerate(vv.astype("uint8")): Image.fromarray(fr).save(f"{fd}/{i:04d}.png")
                subprocess.run(f'ffmpeg -y -loglevel error -framerate 24 -i "{fd}/%04d.png" -c:v libx264 -crf 16 -pix_fmt yuv420p "{out}"', shell=True)
            times[sid] = round(time.time() - t0); log("ltx ok", sid, times[sid], "s", "shape", getattr(v, "shape", None)); up(out, sid + ".mp4")
        except Exception as e:
            log("ltx shot failed", sid, repr(e)[:800]); traceback.print_exc(file=LOG)
    return times

# ---------------- side-by-sides ----------------
def side_by_side(shots, font):
    parts = []
    for s in shots:
        a, b = f"{OUT}/wan_{s['id']}.mp4", f"{OUT}/ltx_{s['id']}.mp4"
        if not (os.path.exists(a) and os.path.exists(b)): continue
        o = f"{OUT}/cmp_{s['id']}.mp4"
        lab = lambda t: f"drawtext=fontfile={font}:text='{t}':x=24:y=20:fontsize=34:fontcolor=white:box=1:boxcolor=black@0.6:boxborderw=10"
        fc = (f"[0:v]fps=24,scale=960:540,setpts=PTS-STARTPTS,{lab('WAN 2.2')}[a];"
              f"[1:v]fps=24,scale=960:540,setpts=PTS-STARTPTS,{lab('LTX-2.5')}[b];[a][b]hstack=inputs=2,"
              f"drawtext=fontfile={font}:text='{s['id']}':x=(w-tw)/2:y=h-50:fontsize=28:fontcolor=white:box=1:boxcolor=black@0.6:boxborderw=8[v]")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", a, "-i", b, "-filter_complex", fc, "-map", "[v]", "-t", "5", "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", o])
        if os.path.exists(o): parts.append(o); up(o, f"cmp_{s['id']}.mp4")
    if parts:
        lst = f"{OUT}/list.txt"; open(lst, "w").write("".join(f"file '{p}'\n" for p in parts))
        subprocess.run(f"ffmpeg -y -loglevel error -f concat -safe 0 -i {lst} -c copy {OUT}/bakeoff_reel.mp4", shell=True)
        if os.path.exists(f"{OUT}/bakeoff_reel.mp4"): up(f"{OUT}/bakeoff_reel.mp4", "bakeoff_reel.mp4")

if __name__ == "__main__":
    T0 = time.time()
    fetch_photos()
    shots = [s for s in PHOTO_SHOTS if s.get("image")] + TEXT_SHOTS
    ONLY = os.environ.get("ONLY", "")
    tw = {} if ONLY == "ltx" else run_wan(shots); log("WAN TIMES", json.dumps(tw), "elapsed", round(time.time() - T0))
    tl = {} if ONLY == "wan" else run_ltx(shots); log("LTX TIMES", json.dumps(tl), "elapsed", round(time.time() - T0))
    if not ONLY: side_by_side(shots, f"{W}/Inter-Bold.otf")
    json.dump({"wan": tw, "ltx": tl, "total_s": round(time.time() - T0)}, open(f"{OUT}/times.json", "w")); up(f"{OUT}/times.json", "times.txt")
    log("ALL DONE", round(time.time() - T0))
