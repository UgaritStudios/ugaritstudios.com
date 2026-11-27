"""Typography for bars3d: counting values above each bar, labels under them, title card.
python3 overlay_bars.py spec.json track.json frames_dir out_dir font_bold.ttf font_regular.ttf
"""
import json, sys, os
from PIL import Image, ImageDraw, ImageFont

spec, track = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
src, dst, fb, fr_ = sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6]
os.makedirs(dst, exist_ok=True)
P = spec.get("palette", {}); W, H, N = track["w"], track["h"], track["frames"]
txt = tuple(P.get("text", (245, 240, 230))); acc = tuple(P.get("accent", (214, 160, 58)))
s = H / 1080
F_v = ImageFont.truetype(fb, int(40 * s)); F_l = ImageFont.truetype(fr_, int(30 * s))
F_t = ImageFont.truetype(fb, int(60 * s)); F_sub = ImageFont.truetype(fr_, int(32 * s))
fmt = spec.get("format", "{:,.0f}"); pre, suf = spec.get("prefix", ""), spec.get("suffix", "")
ease = lambda x: 0 if x <= 0 else 1 if x >= 1 else 1 - (1 - x) ** 3

for f in range(1, N + 1):
    p = os.path.join(src, f"frame_{f:04d}.png")
    if not os.path.exists(p): continue
    im = Image.open(p).convert("RGBA"); ov = Image.new("RGBA", im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    for i, b in enumerate(track["bars"]):
        t = ease((f - b["start"]) / 6)
        if t <= 0: continue
        a = int(255 * t); hi = spec["bars"][i].get("highlight")
        tx, ty = b["top"][f - 1]; v = b["cur"][f - 1]
        s_v = pre + fmt.format(v) + suf; tw = d.textlength(s_v, font=F_v)
        d.text((tx * W - tw / 2, ty * H - 60 * s), s_v, font=F_v, fill=(acc if hi else txt) + (a,))
        bx, by = b["base"][f - 1]; lw = d.textlength(b["label"], font=F_l)
        d.text((bx * W - lw / 2, by * H + 10 * s), b["label"], font=F_l, fill=txt + (int(a * 0.85),))
    title, sub = spec.get("title", ""), spec.get("subtitle", "")
    t = ease((f - 4) / 14)
    if title and t > 0:
        x0, y0 = int(80 * s), int(70 * s - (1 - t) * 30 * s); a = int(255 * t)
        tw = max(d.textlength(title, font=F_t), d.textlength(sub, font=F_sub) if sub else 0)
        d.rounded_rectangle((x0 - int(24 * s), y0 - int(18 * s), x0 + int(60 * s) + tw, y0 + int(150 * s)), radius=int(14 * s), fill=(6, 10, 22, int(205 * t)))
        d.rectangle((x0, y0, x0 + int(10 * s), y0 + int(130 * s)), fill=acc + (a,))
        d.text((x0 + int(30 * s), y0), title, font=F_t, fill=txt + (a,))
        if sub: d.text((x0 + int(32 * s), y0 + int(82 * s)), sub, font=F_sub, fill=acc + (a,))
    Image.alpha_composite(im, ov).convert("RGB").save(os.path.join(dst, f"frame_{f:04d}.png"))
print("overlay done", N)
