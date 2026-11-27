"""Equirectangular globe texture with country borders and highlighted countries.
python3 make_globe_texture.py spec.json countries.geojson out.png [width]
"""
import json, sys
from PIL import Image, ImageDraw

spec = json.load(open(sys.argv[1])); geo = json.load(open(sys.argv[2])); out = sys.argv[3]
W = int(sys.argv[4]) if len(sys.argv) > 4 else 8192
H = W // 2
P = spec.get("palette", {})
ocean = tuple(P.get("ocean", (11, 26, 51)))
land = tuple(P.get("land", (38, 62, 96)))
hi = tuple(P.get("highlight", (217, 164, 65)))
border = tuple(P.get("border", (120, 150, 190)))
highlight = set(spec.get("highlight", []))

img = Image.new("RGB", (W, H), ocean); d = ImageDraw.Draw(img)

def xy(lon, lat):
    return ((lon + 180.0) / 360.0 * W, (90.0 - lat) / 180.0 * H)

def polys(g):
    if g["type"] == "Polygon": return [g["coordinates"]]
    if g["type"] == "MultiPolygon": return g["coordinates"]
    return []

feats = geo["features"]
def iso(f):
    p = f["properties"]
    for k in ("ISO_A3", "ADM0_A3", "ISO_A3_EH"):
        v = p.get(k)
        if v and v != "-99": return v
    return ""

for pass_ in ("fill", "line"):
    for f in feats:
        code = iso(f)
        for poly in polys(f["geometry"]):
            ring = [xy(*pt[:2]) for pt in poly[0]]
            if len(ring) < 3: continue
            # skip rings that wrap the antimeridian badly
            if max(p[0] for p in ring) - min(p[0] for p in ring) > W * 0.9: continue
            if pass_ == "fill":
                d.polygon(ring, fill=hi if code in highlight else land)
                for hole in poly[1:]:
                    h = [xy(*pt[:2]) for pt in hole]
                    if len(h) >= 3: d.polygon(h, fill=ocean)
            else:
                d.line(ring + [ring[0]], fill=border, width=max(1, W // 4096))
img.save(out)
print("texture", out, W, H)
