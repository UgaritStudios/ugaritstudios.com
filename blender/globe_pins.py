"""Blender template: globe flyover with rising pins. Data-driven from a JSON spec.
blender -b -P globe_pins.py -- --spec spec.json --tex globe_tex.png --out /w/f/frame_ --track track.json --device GPU
Writes PNG frames plus track.json (per-frame screen positions of pin tops, used by overlay.py for labels).
"""
import bpy, math, sys, os, json, argparse, mathutils
from bpy_extras.object_utils import world_to_camera_view

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
ap = argparse.ArgumentParser()
ap.add_argument("--spec", required=True); ap.add_argument("--tex", required=True)
ap.add_argument("--out", default="/tmp/gp/frame_"); ap.add_argument("--track", default="/tmp/gp/track.json")
ap.add_argument("--samples", type=int, default=48); ap.add_argument("--device", default="CPU")
ap.add_argument("--res", default=None); ap.add_argument("--frames", default=None)
a = ap.parse_args(argv)
S = json.load(open(a.spec)); P = S.get("palette", {})
fps = 24; N = int(S.get("seconds", 6) * fps)
W, H = [int(x) for x in (a.res or S.get("res", "1920x1080")).split("x")]
c = lambda k, d: tuple(v / 255 for v in P.get(k, d)) + (1,)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = "CYCLES"; sc.cycles.samples = a.samples; sc.cycles.use_denoising = True
sc.render.resolution_x, sc.render.resolution_y = W, H; sc.render.fps = fps
sc.frame_start, sc.frame_end = 1, N
sc.view_settings.view_transform = "AgX"; sc.view_settings.look = "AgX - Medium High Contrast"
if a.device == "GPU":
    prefs = bpy.context.preferences.addons["cycles"].preferences; found = None
    for t in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = t; prefs.refresh_devices()
            devs = [d for d in prefs.devices if d.type == t]
            if devs:
                for d in prefs.devices: d.use = (d.type == t)
                found = t; print("GPU_DEVICE", t, [d.name for d in devs], flush=True); break
        except Exception as e: print("GPU_ERR", t, repr(e), flush=True)
    if not found: print("NO_GPU_FOUND", flush=True); sys.exit(3)
    sc.cycles.device = "GPU"

# world: deep navy gradient + sparse stars
w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True; nt = w.node_tree; nt.nodes.clear()
o = nt.nodes.new("ShaderNodeOutputWorld"); bg = nt.nodes.new("ShaderNodeBackground")
vor = nt.nodes.new("ShaderNodeTexVoronoi"); vor.inputs["Scale"].default_value = 500
rp = nt.nodes.new("ShaderNodeValToRGB")
rp.color_ramp.elements[0].color = (0.9, 0.9, 1, 1); rp.color_ramp.elements[1].position = 0.025
rp.color_ramp.elements[1].color = (0.003, 0.006, 0.016, 1)
nt.links.new(vor.outputs["Distance"], rp.inputs["Fac"]); nt.links.new(rp.outputs[0], bg.inputs["Color"])
nt.links.new(bg.outputs[0], o.inputs[0])

pivot = bpy.data.objects.new("Pivot", None); sc.collection.objects.link(pivot)
bpy.ops.mesh.primitive_uv_sphere_add(segments=160, ring_count=80, radius=1)
g = bpy.context.object; bpy.ops.object.shade_smooth(); g.parent = pivot
m = bpy.data.materials.new("Earth"); m.use_nodes = True; g.data.materials.append(m)
n = m.node_tree.nodes; L = m.node_tree.links; n.clear()
out = n.new("ShaderNodeOutputMaterial"); bs = n.new("ShaderNodeBsdfPrincipled")
tc = n.new("ShaderNodeTexCoord"); nm = n.new("ShaderNodeVectorMath"); nm.operation = "NORMALIZE"
sp = n.new("ShaderNodeSeparateXYZ")
def mth(op, v=None):
    x = n.new("ShaderNodeMath"); x.operation = op
    if v is not None: x.inputs[1].default_value = v
    return x
at = mth("ARCTAN2"); u1 = mth("DIVIDE", 2 * math.pi); u2 = mth("ADD", 0.5)
asn = mth("ARCSINE"); v1 = mth("DIVIDE", math.pi); v2 = mth("ADD", 0.5)
cb = n.new("ShaderNodeCombineXYZ"); im = n.new("ShaderNodeTexImage")
im.image = bpy.data.images.load(a.tex); im.interpolation = "Cubic"; im.extension = "EXTEND"
L.new(tc.outputs["Object"], nm.inputs[0]); L.new(nm.outputs[0], sp.inputs[0])
L.new(sp.outputs["Y"], at.inputs[0]); L.new(sp.outputs["X"], at.inputs[1])
L.new(at.outputs[0], u1.inputs[0]); L.new(u1.outputs[0], u2.inputs[0])
L.new(sp.outputs["Z"], asn.inputs[0]); L.new(asn.outputs[0], v1.inputs[0]); L.new(v1.outputs[0], v2.inputs[0])
L.new(u2.outputs[0], cb.inputs["X"]); L.new(v2.outputs[0], cb.inputs["Y"]); L.new(cb.outputs[0], im.inputs["Vector"])
L.new(im.outputs["Color"], bs.inputs["Base Color"]); bs.inputs["Roughness"].default_value = 0.6
L.new(im.outputs["Color"], bs.inputs["Emission Color"]); bs.inputs["Emission Strength"].default_value = 0.12
L.new(bs.outputs[0], out.inputs[0])

bpy.ops.mesh.primitive_uv_sphere_add(segments=96, ring_count=48, radius=1.03)
at_o = bpy.context.object; bpy.ops.object.shade_smooth(); at_o.parent = pivot
am = bpy.data.materials.new("Atm"); am.use_nodes = True; at_o.data.materials.append(am)
an = am.node_tree.nodes; al = am.node_tree.links; an.clear()
ao = an.new("ShaderNodeOutputMaterial"); em = an.new("ShaderNodeEmission"); tr = an.new("ShaderNodeBsdfTransparent")
mx = an.new("ShaderNodeMixShader"); lw = an.new("ShaderNodeLayerWeight"); lw.inputs["Blend"].default_value = 0.2
pw = an.new("ShaderNodeMath"); pw.operation = "POWER"; pw.inputs[1].default_value = 2.5
em.inputs["Color"].default_value = (0.3, 0.55, 1.0, 1); em.inputs["Strength"].default_value = 1.4
al.new(lw.outputs["Facing"], pw.inputs[0]); al.new(pw.outputs[0], mx.inputs[0])
al.new(tr.outputs[0], mx.inputs[1]); al.new(em.outputs[0], mx.inputs[2]); al.new(mx.outputs[0], ao.inputs[0])

def mat(name, col, strength):
    mm = bpy.data.materials.new(name); mm.use_nodes = True; b = mm.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = col; b.inputs["Emission Color"].default_value = col
    b.inputs["Emission Strength"].default_value = strength; return mm
pin_m = mat("Pin", c("pin", (235, 60, 45)), 0.8); cap_m = mat("Cap", c("cap", (255, 196, 90)), 3.0)

def surf(lat, lon, r=1.0):
    la, lo = math.radians(lat), math.radians(lon)
    return mathutils.Vector((r * math.cos(la) * math.cos(lo), r * math.cos(la) * math.sin(lo), r * math.sin(la)))

pins = S.get("pins", []); caps = []
pin_start = int(N * 0.42); stagger = max(2, int(N * 0.35 / max(1, len(pins))))
for i, p in enumerate(pins):
    st = bpy.data.objects.new(f"pin{i}", None); st.parent = pivot; sc.collection.objects.link(st)
    nv = surf(p["lat"], p["lon"]); st.location = nv; st.rotation_euler = nv.normalized().to_track_quat("Z", "Y").to_euler()
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.0042, depth=1.0)
    bar = bpy.context.object; bar.parent = st; bar.location = (0, 0, 0.5); bar.data.materials.append(pin_m)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=0.0075)
    cap = bpy.context.object; cap.parent = pivot; cap.data.materials.append(cap_m); caps.append(cap)
    hmax = 0.03 + 0.2 * float(p.get("value", 0.5)); s0 = pin_start + i * stagger
    keys = ((1, 0.0001), (s0, 0.0001), (s0 + 12, hmax * 1.1), (s0 + 18, hmax))
    for fr, s in keys:
        st.scale = (1, 1, s); st.keyframe_insert("scale", frame=fr)
        cap.location = surf(p["lat"], p["lon"], 1.0 + s); cap.keyframe_insert("location", frame=fr)
    p["_appear"] = s0 + 6

cam_d = bpy.data.cameras.new("Cam"); cam_d.lens = 50
cam = bpy.data.objects.new("Cam", cam_d); sc.collection.objects.link(cam); sc.camera = cam
tgt = bpy.data.objects.new("Tgt", None); sc.collection.objects.link(tgt)
tk = cam.constraints.new("TRACK_TO"); tk.target = tgt; tk.track_axis = "TRACK_NEGATIVE_Z"; tk.up_axis = "UP_Y"
A, B = S["start"], S["end"]
def cpos(dist, lat):
    la = math.radians(lat); return (dist * math.cos(la), 0, dist * math.sin(la))
mid = int(N * 0.35)
for fr, lon, lat, dist, tz in ((1, A["lon"], A["lat"], A["dist"], 0.0),
                               (mid, (A["lon"] + B["lon"]) / 2, (A["lat"] + B["lat"]) / 2, (A["dist"] + B["dist"]) / 2 + 0.4, 0.05),
                               (N, B["lon"], B["lat"], B["dist"], 0.35 * math.sin(math.radians(B["lat"])))):
    pivot.rotation_euler = (0, 0, math.radians(-lon)); pivot.keyframe_insert("rotation_euler", frame=fr)
    cam.location = cpos(dist, lat); cam.keyframe_insert("location", frame=fr)
    tgt.location = (0, 0, tz); tgt.keyframe_insert("location", frame=fr)

sun = bpy.data.lights.new("Sun", "SUN"); sun.energy = 3.0; sun.angle = math.radians(8)
so = bpy.data.objects.new("Sun", sun); sc.collection.objects.link(so)
so.rotation_euler = mathutils.Vector((-1.0, -0.5, -0.45)).to_track_quat("-Z", "Y").to_euler()
fl = bpy.data.lights.new("Fill", "SUN"); fl.energy = 0.4; fl.color = (0.45, 0.6, 1.0)
fo = bpy.data.objects.new("Fill", fl); sc.collection.objects.link(fo); fo.rotation_euler = (math.radians(-60), math.radians(40), 0)

# per-frame label track (screen coords, 0..1 from top-left) + visibility (front-facing)
track = {"w": W, "h": H, "fps": fps, "frames": N, "pins": []}
for i, p in enumerate(pins):
    track["pins"].append({"label": p["label"], "appear": p["_appear"], "pts": []})
for fr in range(1, N + 1):
    sc.frame_set(fr)
    camloc = cam.matrix_world.translation
    for i, cap in enumerate(caps):
        wp = cap.matrix_world.translation
        v = world_to_camera_view(sc, cam, wp)
        front = (wp.normalized().dot((camloc - wp).normalized()) > 0.15)
        track["pins"][i]["pts"].append([round(v.x, 4), round(1 - v.y, 4), bool(front and 0 <= v.x <= 1 and 0 <= v.y <= 1)])
os.makedirs(os.path.dirname(a.track) or ".", exist_ok=True); json.dump(track, open(a.track, "w"))

os.makedirs(os.path.dirname(a.out), exist_ok=True)
sc.render.image_settings.file_format = "PNG"; sc.render.use_persistent_data = True
if a.frames:
    f0, f1 = [int(x) for x in a.frames.split("-")]; sc.frame_start, sc.frame_end = f0, f1
sc.render.filepath = a.out
bpy.ops.render.render(animation=True)
print("DONE", flush=True)
