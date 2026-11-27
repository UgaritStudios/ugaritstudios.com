"""BoomDoom gladiator verdict scene: Wan 2.2 image-to-video from checked keyframes (brand element).
Reads shots from $REPO/$SHOTS. Optional Kokoro narrator samples. Uploads every mp4/mp3 to the Render Receiver."""
import os, sys, json, time, subprocess, urllib.request
sys.path.insert(0, '/w')
import bake
from bake import log, up, run_wan, OUT, W
REPO = os.environ['REPO']
SH = json.loads(urllib.request.urlopen(f"{REPO}/{os.environ['SHOTS']}", timeout=60).read())
os.makedirs(f'{W}/kf', exist_ok=True)

def kokoro(cfg):
    try:
        subprocess.run('pip install -q --break-system-packages kokoro', shell=True)
        from kokoro import KPipeline
        import soundfile as sf, numpy as np
        for lang, voices in cfg['voices'].items():
            pipe = KPipeline(lang_code=lang)
            for v in voices:
                try:
                    chunks = [a for _, _, a in pipe(cfg['text'], voice=v, speed=cfg.get('speed', 0.95))]
                    wav = np.concatenate([c.numpy() if hasattr(c, 'numpy') else c for c in chunks])
                    p = f'{OUT}/kokoro_{v}.wav'; sf.write(p, wav, 24000)
                    m = p[:-4] + '.mp3'; subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', p, '-b:a', '128k', m])
                    up(m, f'kokoro_{v}.mp3'); log('kokoro ok', v)
                except Exception as e: log('kokoro voice fail', v, repr(e)[:300])
    except Exception as e: log('kokoro fail', repr(e)[:400])

if __name__ == '__main__':
    T0 = time.time()
    shots = []
    for s in SH['shots']:
        p = f"{W}/kf/{s['id']}.jpg"
        if not os.path.exists(p):
            subprocess.run(['bash', '-c', f'curl -sfL "{s["image_url"]}" -o /tmp/kf_in && ffmpeg -y -loglevel error -i /tmp/kf_in -vf scale=1280:720 -q:v 2 {p}'])
        if os.path.exists(p): shots.append(dict(id=s['id'], prompt=s['prompt'], image=p))
        else: log('keyframe missing', s['id'])
    log('shots', [s['id'] for s in shots])
    tw = run_wan(shots); log('WAN TIMES', json.dumps(tw), 'elapsed', round(time.time() - T0))
    if SH.get('kokoro'): kokoro(SH['kokoro'])
    log('ALL DONE', round(time.time() - T0))
