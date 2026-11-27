"""Blender template: 3D bar chart that grows bar by bar with a slow camera move. Data-driven.
blender -b -P bars3d.py -- --spec spec.json --out /w/f/frame_ --track track.json --device GPU
track.json holds per-frame screen positions of each bar's top and base, plus its current value,
so overlay_bars.py can draw value counters and labels.
"""
import bpy, math, sys, os, json, argparse, mathutils
from bpy_extras.object_utils import world_to_camera_view

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
ap = argparse.ArgumentParser()
ap.add_argument("--spec", required=True); ap.add_argument("--out", default="/tmp/b3/frame_")
ap.add_argument("--track", default="/tmp/b3/track.json"); ap.add_argument("--samples", type=int, default=48)
ap.add_argument("--device", default="CPU"); ap.add_argument("--res", default=None); ap.add_argument("--frames", default=None)
a = ap.parse_args(argv)
S = json.load(open(a.spec)); P = S.get("palette", {})
fps = 24; N = int(S.get("seconds", 6) * fps)
W, H = [int(x) for x in (a.res or S.get("res", "1920x1080")).split("x")]
col = lambda k, d: tuple(v / 255 for v in P.get(k, d)) + (1,)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = "CYCLES"; sc.cycles.samples = a.samples; sc.cycles.use_denoising = True
sc.render.resolution_x, sc.render.resolution_y = W, H; sc.render.fps = fps; sc.frame_start, sc.frame_end = 1, N
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

w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs["Color"].default_value = col("bg", (8, 14, 28))
w.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0

def mat(name, c, rough=0.35, emit=0.0, metal=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True; b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = c; b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit: b.inputs["Emission Color"].default_value = c; b.inputs["Emission Strength"].default_value = emit
    return m

bars = S["bars"]; n = len(bars); vmax = max(b["value"] for b in bars) or 1
gap, bw, hmax = 1.6, 1.0, 5.0
x0 = -(n - 1) * gap / 2
# floor: dark glossy plane with faint grid
bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 0)); fl = bpy.context.object
fm = bpy.data.materials.new("Floor"); fm.use_nodes = True; fn = fm.node_tree.nodes; flk = fm.node_tree.links
fb = fn["Principled BSDF"]; fb.inputs["Base Color"].default_value = col("floor", (14, 22, 40)); fb.inputs["Roughness"].default_value = 0.6
br = fn.new("ShaderNodeTexBrick"); br.inputs["Scale"].default_value = 30; br.inputs["Mortar Size"].default_value = 0.01
br.inputs["Color1"].default_value = col("floor", (14, 22, 40)); br.inputs["Color2"].default_value = col("floor", (14, 22, 40))
br.inputs["Mortar"].default_value = col("grid", (28, 42, 70)); br.offset = 0; br.squash = 1
flk.new(br.outputs["Color"], fb.inputs["Base Color"]); fl.data.materials.append(fm)

base_m = mat("Bar", col("bar", (60, 110, 190)), 0.3)
hi_m = mat("BarHi", col("accent", (214, 160, 58)), 0.25, emit=0.15, metal=0.3)
grow0 = int(N * 0.12); per = max(6, int(N * 0.55 / n)); objs = []
for i, b in enumerate(bars):
    h = max(0.05, hmax * b["value"] / vmax)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x0 + i * gap, 0, 0))
    ob = bpy.context.object; ob.data.materials.append(hi_m if b.get("highlight") else base_m)
    bev = ob.modifiers.new("bev", "BEVEL"); bev.width = 0.04; bev.segments = 3
    # origin at base: shift mesh up by 0.5
    for v in ob.data.vertices: v.co.z += 0.5
    ob.scale = (bw, bw, 0.001)
    s0 = grow0 + i * per; e0 = s0 + int(per * 1.6)
    for fr, z in ((1, 0.001), (s0, 0.001), (e0, h * 1.04), (e0 + 6, h)):
        ob.scale = (bw, bw, z); ob.keyframe_insert("scale", frame=fr)
    objs.append((ob, b, s0, e0, h))

cam_d = bpy.data.cameras.new("Cam"); cam_d.lens = 35
cam = bpy.data.objects.new("Cam", cam_d); sc.collection.objects.link(cam); sc.camera = cam
tgt = bpy.data.objects.new("Tgt", None); sc.collection.objects.link(tgt)
tk = cam.constraints.new("TRACK_TO"); tk.target = tgt; tk.track_axis = "TRACK_NEGATIVE_Z"; tk.up_axis = "UP_Y"
span = (n - 1) * gap + 2
for fr, pos, tz in ((1, (-span * 0.45, -span * 1.25 - 4, 2.6), hmax * 0.3), (N, (span * 0.2, -span * 1.15 - 5, hmax * 0.95), hmax * 0.5)):
    cam.location = pos; cam.keyframe_insert("location", frame=fr); tgt.location = (0, 0, tz); tgt.keyframe_insert("location", frame=fr)

key = bpy.data.lights.new("Key", "AREA"); key.energy = 1500; key.size = 12
ko = bpy.data.objects.new("Key", key); sc.collection.objects.link(ko); ko.location = (-6, -8, 12)
ko.rotation_euler = (mathutils.Vector((0, 0, 0)) - ko.location).to_track_quat("-Z", "Y").to_euler()
rim = bpy.data.lights.new("Rim", "AREA"); rim.energy = 1200; rim.size = 8; rim.color = (0.5, 0.65, 1.0)
ro = bpy.data.objects.new("Rim", rim); sc.collection.objects.link(ro); ro.location = (8, 10, 6)
ro.rotation_euler = (mathutils.Vector((0, 0, 2)) - ro.location).to_track_quat("-Z", "Y").to_euler()

track = {"w": W, "h": H, "fps": fps, "frames": N, "bars": []}
for ob, b, s0, e0, h in objs:
    track["bars"].append({"label": b["label"], "value": b["value"], "start": s0, "end": e0, "top": [], "base": [], "cur": []})
for fr in range(1, N + 1):
    sc.frame_set(fr)
    for k, (ob, b, s0, e0, h) in enumerate(objs):
        z = ob.scale.z; loc = ob.matrix_world.translation
        top = world_to_camera_view(sc, cam, mathutils.Vector((loc.x, loc.y, z)))
        base = world_to_camera_view(sc, cam, mathutils.Vector((loc.x, loc.y - 0.6, 0)))
        tr = track["bars"][k]
        tr["top"].append([round(top.x, 4), round(1 - top.y, 4)]); tr["base"].append([round(base.x, 4), round(1 - base.y, 4)])
        tr["cur"].append(round(b["value"] * min(1.0, z / h), 4))
os.makedirs(os.path.dirname(a.track) or ".", exist_ok=True); json.dump(track, open(a.track, "w"))

os.makedirs(os.path.dirname(a.out), exist_ok=True)
sc.render.image_settings.file_format = "PNG"; sc.render.use_persistent_data = True
if a.frames:
    f0, f1 = [int(x) for x in a.frames.split("-")]; sc.frame_start, sc.frame_end = f0, f1
sc.render.filepath = a.out
bpy.ops.render.render(animation=True)
print("DONE", flush=True)
