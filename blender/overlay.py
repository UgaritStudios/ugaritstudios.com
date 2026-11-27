"""2D typography over Blender frames: pin labels that track the 3D pins, plus a title card.
python3 overlay.py spec.json track.json frames_dir out_dir font_bold.ttf font_regular.ttf
"""
import json, sys, os, math
from PIL import Image, ImageDraw, ImageFont

spec, track = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
src, dst, fb, fr_ = sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6]
os.makedirs(dst, exist_ok=True)
P = spec.get("palette", {}); W, H, N = track["w"], track["h"], track["frames"]
txt = tuple(P.get("text", (245, 240, 230))); acc = tuple(P.get("accent", (214, 160, 58)))
s = H / 1080
F_lab = ImageFont.truetype(fb, int(30 * s)); F_t = ImageFont.truetype(fb, int(64 * s)); F_sub = ImageFont.truetype(fr_, int(34 * s))
ease = lambda x: 0 if x <= 0 else 1 if x >= 1 else 1 - (1 - x) ** 3

for f in range(1, N + 1):
    p = os.path.join(src, f"frame_{f:04d}.png")
    if not os.path.exists(p): continue
    im = Image.open(p).convert("RGBA"); ov = Image.new("RGBA", im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    # pin labels: fade + slide in after the pin appears; skip labels that would collide
    placed = []
    title_zone = (0, H - 290 * s, 1150 * s, H) if spec.get("title") else None
    if title_zone and f >= N * 0.18: placed.append(title_zone)
    for pin in track["pins"]:
        x, y, vis = pin["pts"][f - 1]
        t = ease((f - pin["appear"]) / 10)
        if not vis or t <= 0: continue
        X, Y = x * W, y * H
        label = pin["label"]; tw = d.textlength(label, font=F_lab); th = F_lab.size
        bx, by = X + 14 * s, Y - th - 18 * s + (1 - t) * 12 * s
        box = (bx - 10 * s, by - 6 * s, bx + tw + 10 * s, by + th + 8 * s)
        if any(not (box[2] < b[0] or box[0] > b[2] or box[3] < b[1] or box[1] > b[3]) for b in placed): continue
        if box[2] > W - 10 or box[1] < 10: continue
        placed.append(box); a = int(255 * t)
        d.line([(X, Y), (bx - 10 * s, by + th + 8 * s)], fill=acc + (a,), width=max(1, int(2 * s)))
        d.rounded_rectangle(box, radius=int(8 * s), fill=(8, 14, 28, int(200 * t)), outline=acc + (a,), width=max(1, int(2 * s)))
        d.text((bx, by), label, font=F_lab, fill=txt + (a,))
    # title card: lower-left, slides up in the second half
    title, sub = spec.get("title", ""), spec.get("subtitle", "")
    if title:
        t = ease((f - N * 0.18) / 16)
        if t > 0:
            x0, y0 = int(80 * s), int(H - 230 * s + (1 - t) * 40 * s); a = int(255 * t)
            tw = max(d.textlength(title, font=F_t), d.textlength(sub, font=F_sub) if sub else 0)
            d.rounded_rectangle((x0 - int(24 * s), y0 - int(22 * s), x0 + int(60 * s) + tw, y0 + int(162 * s)), radius=int(14 * s), fill=(6, 10, 22, int(205 * t)))
            d.rectangle((x0, y0, x0 + int(10 * s), y0 + int(140 * s)), fill=acc + (a,))
            d.text((x0 + int(30 * s), y0), title, font=F_t, fill=txt + (a,))
            if sub: d.text((x0 + int(32 * s), y0 + int(86 * s)), sub, font=F_sub, fill=acc + (a,))
    Image.alpha_composite(im, ov).convert("RGB").save(os.path.join(dst, f"frame_{f:04d}.png"))
print("overlay done", N)
