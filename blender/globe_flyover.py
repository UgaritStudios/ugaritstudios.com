"""Ugarit Studios - Blender test: globe flyover with rising store pins.
Runs headless:  blender -b -P globe_flyover.py -- --out /path/frame_ --frames 1-120 --samples 32 --device CPU|GPU
or with the bpy module:  python3 globe_flyover.py --out ... (same args)
"""
import bpy, math, sys, os, argparse

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
ap = argparse.ArgumentParser()
ap.add_argument("--out", default="/tmp/globe/frame_")
ap.add_argument("--frames", default="1-120")
ap.add_argument("--samples", type=int, default=32)
ap.add_argument("--device", default="CPU")
ap.add_argument("--res", default="1280x720")
ap.add_argument("--tex", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "earth_albedo.png"))
a = ap.parse_args(argv)
f0, f1 = [int(x) for x in a.frames.split("-")]
W, H = [int(x) for x in a.res.split("x")]

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = "CYCLES"
sc.cycles.samples = a.samples
sc.cycles.use_denoising = True
sc.render.resolution_x, sc.render.resolution_y = W, H
sc.render.fps = 24
sc.frame_start, sc.frame_end = 1, 120
sc.render.film_transparent = False
sc.view_settings.view_transform = "AgX"
sc.view_settings.look = "AgX - Punchy"
if a.device == "GPU":
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for t in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = t; prefs.get_devices()
            for d in prefs.devices: d.use = True
            break
        except Exception: pass
    sc.cycles.device = "GPU"

# ---------- world: deep navy with faint stars ----------
w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True
nt = w.node_tree; nt.nodes.clear()
out = nt.nodes.new("ShaderNodeOutputWorld"); bg = nt.nodes.new("ShaderNodeBackground")
noise = nt.nodes.new("ShaderNodeTexVoronoi"); noise.inputs["Scale"].default_value = 400
ramp = nt.nodes.new("ShaderNodeValToRGB")
ramp.color_ramp.elements[0].position = 0.0; ramp.color_ramp.elements[0].color = (1, 1, 1, 1)
ramp.color_ramp.elements[1].position = 0.03; ramp.color_ramp.elements[1].color = (0.004, 0.008, 0.02, 1)
nt.links.new(noise.outputs["Distance"], ramp.inputs["Fac"])
nt.links.new(ramp.outputs["Color"], bg.inputs["Color"]); bg.inputs["Strength"].default_value = 1.0
nt.links.new(bg.outputs[0], out.inputs[0])

# ---------- globe ----------
pivot = bpy.data.objects.new("Pivot", None); sc.collection.objects.link(pivot)
bpy.ops.mesh.primitive_uv_sphere_add(segments=128, ring_count=64, radius=1)
g = bpy.context.object; g.name = "Globe"; bpy.ops.object.shade_smooth(); g.parent = pivot
m = bpy.data.materials.new("Earth"); m.use_nodes = True; g.data.materials.append(m)
n = m.node_tree.nodes; L = m.node_tree.links; n.clear()
o = n.new("ShaderNodeOutputMaterial"); bsdf = n.new("ShaderNodeBsdfPrincipled")
tc = n.new("ShaderNodeTexCoord"); norm = n.new("ShaderNodeVectorMath"); norm.operation = "NORMALIZE"
sep = n.new("ShaderNodeSeparateXYZ")
at = n.new("ShaderNodeMath"); at.operation = "ARCTAN2"
u1 = n.new("ShaderNodeMath"); u1.operation = "DIVIDE"; u1.inputs[1].default_value = 2 * math.pi
u2 = n.new("ShaderNodeMath"); u2.operation = "ADD"; u2.inputs[1].default_value = 0.5
asn = n.new("ShaderNodeMath"); asn.operation = "ARCSINE"
v1 = n.new("ShaderNodeMath"); v1.operation = "DIVIDE"; v1.inputs[1].default_value = math.pi
v2 = n.new("ShaderNodeMath"); v2.operation = "ADD"; v2.inputs[1].default_value = 0.5
comb = n.new("ShaderNodeCombineXYZ")
img = n.new("ShaderNodeTexImage"); img.image = bpy.data.images.load(a.tex); img.interpolation = "Cubic"
L.new(tc.outputs["Object"], norm.inputs[0]); L.new(norm.outputs[0], sep.inputs[0])
L.new(sep.outputs["Y"], at.inputs[0]); L.new(sep.outputs["X"], at.inputs[1])
L.new(at.outputs[0], u1.inputs[0]); L.new(u1.outputs[0], u2.inputs[0])
L.new(sep.outputs["Z"], asn.inputs[0]); L.new(asn.outputs[0], v1.inputs[0]); L.new(v1.outputs[0], v2.inputs[0])
L.new(u2.outputs[0], comb.inputs["X"]); L.new(v2.outputs[0], comb.inputs["Y"])
L.new(comb.outputs[0], img.inputs["Vector"])
L.new(img.outputs["Color"], bsdf.inputs["Base Color"])
bsdf.inputs["Roughness"].default_value = 0.55
# gold coast/land faint emission so the night side still reads
L.new(img.outputs["Color"], bsdf.inputs["Emission Color"]); bsdf.inputs["Emission Strength"].default_value = 0.08
L.new(bsdf.outputs[0], o.inputs[0])

# atmosphere shell (fresnel rim)
bpy.ops.mesh.primitive_uv_sphere_add(segments=96, ring_count=48, radius=1.035)
atm = bpy.context.object; atm.name = "Atmos"; bpy.ops.object.shade_smooth(); atm.parent = pivot
am = bpy.data.materials.new("Atmos"); am.use_nodes = True; atm.data.materials.append(am)
an = am.node_tree.nodes; al = am.node_tree.links; an.clear()
ao = an.new("ShaderNodeOutputMaterial"); em = an.new("ShaderNodeEmission"); tr = an.new("ShaderNodeBsdfTransparent")
mix = an.new("ShaderNodeMixShader"); lw = an.new("ShaderNodeLayerWeight"); lw.inputs["Blend"].default_value = 0.22
pw = an.new("ShaderNodeMath"); pw.operation = "POWER"; pw.inputs[1].default_value = 2.2
em.inputs["Color"].default_value = (0.25, 0.55, 1.0, 1); em.inputs["Strength"].default_value = 1.6
al.new(lw.outputs["Facing"], pw.inputs[0]); al.new(pw.outputs[0], mix.inputs[0])
al.new(tr.outputs[0], mix.inputs[1]); al.new(em.outputs[0], mix.inputs[2]); al.new(mix.outputs[0], ao.inputs[0])

# ---------- pins (lat, lon, relative height) ----------
PINS = [
    ("Zhengzhou HQ", 34.75, 113.62, 1.00), ("Shanghai", 31.23, 121.47, 0.85), ("Beijing", 39.90, 116.40, 0.80),
    ("Guangzhou", 23.13, 113.26, 0.75), ("Chengdu", 30.57, 104.07, 0.70), ("Wuhan", 30.59, 114.31, 0.65),
    ("Xi'an", 34.34, 108.94, 0.55), ("Hanoi", 21.03, 105.85, 0.45), ("Jakarta", -6.21, 106.85, 0.50),
    ("Bangkok", 13.75, 100.50, 0.35), ("Kuala Lumpur", 3.14, 101.69, 0.35), ("Manila", 14.60, 120.98, 0.30),
    ("Tokyo", 35.68, 139.69, 0.25), ("Seoul", 37.57, 126.98, 0.25),
]
pin_mat = bpy.data.materials.new("Pin"); pin_mat.use_nodes = True
pb = pin_mat.node_tree.nodes["Principled BSDF"]
pb.inputs["Base Color"].default_value = (0.9, 0.08, 0.06, 1)
pb.inputs["Emission Color"].default_value = (1.0, 0.12, 0.05, 1); pb.inputs["Emission Strength"].default_value = 2.5
cap_mat = bpy.data.materials.new("Cap"); cap_mat.use_nodes = True
cb = cap_mat.node_tree.nodes["Principled BSDF"]
cb.inputs["Emission Color"].default_value = (1.0, 0.7, 0.2, 1); cb.inputs["Base Color"].default_value = (1.0, 0.7, 0.2, 1); cb.inputs["Emission Strength"].default_value = 5.0

def surf(lat, lon, r=1.0):
    la, lo = math.radians(lat), math.radians(lon)
    return (r * math.cos(la) * math.cos(lo), r * math.cos(la) * math.sin(lo), r * math.sin(la))

for i, (name, lat, lon, h) in enumerate(PINS):
    stem = bpy.data.objects.new("pin_" + name, None); stem.parent = pivot
    sc.collection.objects.link(stem)
    stem.location = surf(lat, lon, 1.0)
    # orient local Z along the surface normal
    import mathutils
    nrm = mathutils.Vector(surf(lat, lon, 1.0)).normalized()
    stem.rotation_euler = nrm.to_track_quat("Z", "Y").to_euler()
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.0045, depth=1.0, location=(0, 0, 0.5))
    bar = bpy.context.object; bar.parent = stem; bar.location = (0, 0, 0.5); bar.data.materials.append(pin_mat)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=0.008, location=(0, 0, 1.0))
    cap = bpy.context.object; cap.parent = stem; cap.location = (0, 0, 1.0); cap.data.materials.append(cap_mat)
    hmax = 0.03 + 0.22 * h
    start = 52 + i * 3
    for fr, s in ((1, 0.0001), (start, 0.0001), (start + 14, hmax * 1.08), (start + 20, hmax)):
        stem.scale = (1, 1, s); stem.keyframe_insert("scale", frame=fr)
    # keep cap round: counter-scale it
    for fr, s in ((1, 0.0001), (start, 0.0001), (start + 14, hmax * 1.08), (start + 20, hmax)):
        cap.scale = (1, 1, 1 / max(s, 0.0001) if s > 0.001 else 0.0001); cap.keyframe_insert("scale", frame=fr)

# ---------- camera + motion ----------
cam_d = bpy.data.cameras.new("Cam"); cam_d.lens = 50
cam = bpy.data.objects.new("Cam", cam_d); sc.collection.objects.link(cam); sc.camera = cam
target = bpy.data.objects.new("Target", None); sc.collection.objects.link(target)
tc_ = cam.constraints.new("TRACK_TO"); tc_.target = target; tc_.track_axis = "TRACK_NEGATIVE_Z"; tc_.up_axis = "UP_Y"
cam_d.dof.use_dof = False

def cam_pos(dist, lat):
    la = math.radians(lat); return (dist * math.cos(la), 0, dist * math.sin(la))

# globe spins so that lon 112E ends up facing the camera (+X axis)
for fr, rotz, dist, lat, tz in ((1, math.radians(60), 5.2, 12, 0.0),
                                (40, math.radians(-40), 4.0, 20, 0.05),
                                (120, math.radians(-112), 2.55, 28, 0.38)):
    pivot.rotation_euler = (0, 0, rotz); pivot.keyframe_insert("rotation_euler", frame=fr)
    cam.location = cam_pos(dist, lat); cam.keyframe_insert("location", frame=fr)
    target.location = (0, 0, tz); target.keyframe_insert("location", frame=fr)
for ob in (pivot, cam, target):
    for fc in ob.animation_data.action.fcurves if hasattr(ob.animation_data.action, "fcurves") else []:
        for kp in fc.keyframe_points: kp.interpolation = "BEZIER"; kp.easing = "AUTO"

# ---------- light ----------
sun = bpy.data.lights.new("Sun", "SUN"); sun.energy = 3.2; sun.color = (1.0, 0.95, 0.88)
so = bpy.data.objects.new("Sun", sun); sc.collection.objects.link(so)
import mathutils as _mu
so.rotation_euler = _mu.Vector((-1.0, -0.55, -0.45)).to_track_quat("-Z", "Y").to_euler()
fill = bpy.data.lights.new("Fill", "SUN"); fill.energy = 0.35; fill.color = (0.4, 0.6, 1.0)
fo = bpy.data.objects.new("Fill", fill); sc.collection.objects.link(fo); fo.rotation_euler = (math.radians(-60), math.radians(40), 0)

# ---------- render ----------
os.makedirs(os.path.dirname(a.out), exist_ok=True)
sc.render.image_settings.file_format = "PNG"
sc.frame_start, sc.frame_end = f0, f1
sc.render.use_persistent_data = True
sc.render.filepath = a.out
bpy.ops.render.render(animation=True)
print("DONE", f0, f1)
