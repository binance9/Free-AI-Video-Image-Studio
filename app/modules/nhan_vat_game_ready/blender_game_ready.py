from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path

import bpy
from mathutils import Vector

# Fraction of mesh vertices that must carry a non-trivial total bone weight
# for a skin to be considered usable. Blender's "Automatic Weights" (bone
# heat) can fail to solve for one or more bones on the kind of disconnected/
# non-manifold geometry TripoSR/Hunyuan tend to output - when that happens
# bpy.ops.object.parent_set(type="ARMATURE_AUTO") does NOT raise a Python
# exception, it just prints a warning and leaves some/most vertices with
# zero weight. Blender's own glTF exporter then silently drops the whole
# skin ("has no skin, skipping") - so JOINTS_0/WEIGHTS_0 end up in the file
# but bound to nothing, and the character never visibly moves. This
# threshold is what makes that failure mode detectable instead of silent.
MIN_WEIGHT_COVERAGE = 0.85

# ---- run cycle tuning (radians unless noted) - see bake_run_cycle() ----
RUN_FPS = 24
RUN_CYCLE_FRAMES = 24  # 24 frames @ 24fps = 1.0s/cycle, top of the 0.7-1.0s target
RUN_THIGH_AMP = 0.55       # forward/back thigh swing - shorter than a human stride (chibi)
RUN_KNEE_AMP = 0.85        # knee bend during swing only - a bit pronounced (chibi)
RUN_ARM_AMP = 0.5          # arm swing amplitude, opposite phase to the same-side leg
RUN_FOREARM_BEND = -0.35   # constant relaxed elbow bend (keeps forearm/hand off the torso)
RUN_FOOT_AMP = 0.35        # ankle articulation (lift/plant)
RUN_HIPS_ROT_AMP = 0.05    # subtle pelvis twist
RUN_HIPS_DIP = 0.02        # hips lower slightly at the two mid-swing passes, never rises hard
RUN_CHEST_LEAN = -0.10     # small constant forward lean, not an oscillation
RUN_HEAD_BOB_AMP = 0.02    # tiny stabilizing counter-bob only


def args_after_dash():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--report", required=True)
    p.add_argument("--target-faces", type=int, default=45000)
    p.add_argument("--weapon-type", default="bow")
    return p.parse_args(argv)


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def import_glb(path: Path):
    bpy.ops.import_scene.gltf(filepath=str(path))
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not meshes:
        raise RuntimeError("GLB không có mesh")
    return meshes


def triangulated_face_count(obj):
    # Stable approximation without mutating the object.
    return sum(max(1, len(p.vertices) - 2) for p in obj.data.polygons)


def join_meshes(meshes):
    bpy.ops.object.select_all(action="DESELECT")
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    obj.name = "CharacterMesh"
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    return obj


def optimize_mesh(obj, target_faces: int):
    before = triangulated_face_count(obj)
    if before > target_faces:
        ratio = max(0.05, min(1.0, target_faces / float(before)))
        dec = obj.modifiers.new("AIVF_GameReady_Decimate", "DECIMATE")
        dec.decimate_type = "COLLAPSE"
        dec.ratio = ratio
        dec.use_collapse_triangulate = True
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=dec.name)
    # Make normals predictable after decimation.
    for poly in obj.data.polygons:
        poly.use_smooth = True
    after = triangulated_face_count(obj)
    return before, after


def world_bbox(obj):
    pts = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return mn, mx


def add_bone(arm, name, head, tail, parent=None, connected=False):
    b = arm.edit_bones.new(name)
    b.head = head
    b.tail = tail
    if parent:
        b.parent = parent
        b.use_connect = connected
    return b


def create_rig(mesh):
    mn, mx = world_bbox(mesh)
    size = mx - mn
    cx = (mn.x + mx.x) * 0.5
    cy = (mn.y + mx.y) * 0.5
    h = max(size.z, 0.001)
    w = max(size.x, h * 0.25)
    z = lambda t: mn.z + h * t
    shoulder = w * 0.30
    elbow = w * 0.46
    hand = w * 0.60
    hip_x = w * 0.12

    arm_data = bpy.data.armatures.new("AIVF_Armature")
    rig = bpy.data.objects.new("AIVF_Rig", arm_data)
    bpy.context.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")

    root = add_bone(arm_data, "root", (cx, cy, mn.z), (cx, cy, z(.08)))
    hips = add_bone(arm_data, "hips", (cx, cy, z(.38)), (cx, cy, z(.50)), root)
    spine = add_bone(arm_data, "spine", (cx, cy, z(.50)), (cx, cy, z(.64)), hips, True)
    chest = add_bone(arm_data, "chest", (cx, cy, z(.64)), (cx, cy, z(.77)), spine, True)
    neck = add_bone(arm_data, "neck", (cx, cy, z(.77)), (cx, cy, z(.83)), chest, True)
    head = add_bone(arm_data, "head", (cx, cy, z(.83)), (cx, cy, z(.97)), neck, True)
    # Jaw hinge near the base of the head, tail pushed toward the front (lower
    # y, same "front" convention feet already use below) and slightly down -
    # this only ever needs to carry whatever chin/lower-face vertices the
    # zone fallback assigns to it, not be anatomically exact.
    jaw = add_bone(arm_data, "jaw", (cx, cy - w*.10, z(.855)), (cx, cy - w*.32, z(.835)), head)

    def arm(side, sign):
        upper = add_bone(arm_data, f"upper_arm.{side}", (cx + sign*shoulder*.65, cy, z(.74)), (cx + sign*elbow, cy, z(.67)), chest)
        fore = add_bone(arm_data, f"forearm.{side}", upper.tail, (cx + sign*hand, cy, z(.59)), upper, True)
        add_bone(arm_data, f"hand.{side}", fore.tail, (cx + sign*(hand+w*.08), cy, z(.57)), fore, True)

    arm("L", 1); arm("R", -1)

    def leg(side, sign):
        thigh = add_bone(arm_data, f"thigh.{side}", (cx + sign*hip_x, cy, z(.40)), (cx + sign*hip_x, cy, z(.23)), hips)
        shin = add_bone(arm_data, f"shin.{side}", thigh.tail, (cx + sign*hip_x, cy, z(.08)), thigh, True)
        add_bone(arm_data, f"foot.{side}", shin.tail, (cx + sign*hip_x, cy - max(size.y*.18, h*.04), z(.035)), shin, True)

    leg("L", 1); leg("R", -1)
    bpy.ops.object.mode_set(mode="OBJECT")
    return rig


def _weight_coverage(mesh) -> float:
    """Fraction of vertices whose total weight across all vertex groups is
    non-trivial. This is what actually reveals a silent bone-heat failure -
    the operator itself reports success either way."""
    verts = mesh.data.vertices
    if not verts:
        return 0.0
    weighted = sum(1 for v in verts if sum(g.weight for g in v.groups) > 0.01)
    return weighted / len(verts)


def _clear_skinning(mesh, rig):
    """Undo whatever a failed/partial automatic-weights attempt left behind
    so the deterministic fallback starts from a clean slate."""
    for mod in list(mesh.modifiers):
        if mod.type == "ARMATURE":
            mesh.modifiers.remove(mod)
    for vg in list(mesh.vertex_groups):
        mesh.vertex_groups.remove(vg)
    if mesh.parent == rig:
        mesh.parent = None


def _zone_fallback_weights(mesh, rig):
    """Deterministic body-zone weights - pure vertex position math, so it
    cannot fail the way geometry-dependent bone-heat solving can. Always
    produces a fully-weighted, genuinely skinned mesh."""
    bpy.ops.object.select_all(action="DESELECT")
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = mesh
    mod = mesh.modifiers.get("AIVF_Armature") or mesh.modifiers.new("AIVF_Armature", "ARMATURE")
    mod.object = rig
    mesh.parent = rig
    mn, mx = world_bbox(mesh); h = max(mx.z-mn.z, .001); cx=(mn.x+mx.x)*.5; cy=(mn.y+mx.y)*.5
    groups = {b.name: mesh.vertex_groups.new(name=b.name) for b in rig.data.bones}
    has_jaw = "jaw" in groups
    for v in mesh.data.vertices:
        co = mesh.matrix_world @ v.co
        t = (co.z-mn.z)/h
        x = co.x-cx
        name = "hips"
        if t > .82:
            # Lower-front slice of the head (same "front = lower y" convention
            # feet already use below) goes to jaw instead of head, so a jaw
            # rotation moves chin/mouth-area geometry without dragging the
            # whole skull. Front-ness is a heuristic, not measured - if this
            # mesh's forward axis differs, the jaw just ends up owning some
            # other lower-head slice instead of failing outright.
            name = "jaw" if (has_jaw and t < .90 and co.y < cy - h*.06) else "head"
        elif t > .68:
            name = "upper_arm.L" if x > h*.16 else ("upper_arm.R" if x < -h*.16 else "chest")
        elif t > .48:
            name = "forearm.L" if x > h*.28 else ("forearm.R" if x < -h*.28 else "spine")
        elif t > .25: name = "thigh.L" if x >= 0 else "thigh.R"
        else: name = "shin.L" if x >= 0 else "shin.R"
        groups[name].add([v.index], 1.0, "REPLACE")


def auto_skin(mesh, rig):
    bpy.ops.object.select_all(action="DESELECT")
    mesh.select_set(True); rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    automatic_ran = False
    try:
        bpy.ops.object.parent_set(type="ARMATURE_AUTO")
        automatic_ran = True
    except Exception:
        automatic_ran = False

    if automatic_ran and _weight_coverage(mesh) >= MIN_WEIGHT_COVERAGE:
        return "automatic"

    # Automatic weights either raised OR (much more common on AI-generated
    # meshes) silently solved for almost no vertices - either way, do NOT
    # trust it. Clear any partial state and use the deterministic fallback
    # so we never export a mesh with an unusable/empty skin (section 12).
    _clear_skinning(mesh, rig)
    _zone_fallback_weights(mesh, rig)
    coverage = _weight_coverage(mesh)
    if coverage < MIN_WEIGHT_COVERAGE:
        raise RuntimeError(f"Skinning thất bại cả automatic và fallback (coverage={coverage:.2f})")
    return "zone_fallback"


def set_pose_rotation(rig, bone, values, frame):
    pb = rig.pose.bones.get(bone)
    if not pb:
        return
    pb.rotation_mode = "XYZ"
    pb.rotation_euler = values
    pb.keyframe_insert(data_path="rotation_euler", frame=frame, group=bone)


def set_pose_location(rig, bone, values, frame):
    pb = rig.pose.bones.get(bone)
    if not pb:
        return
    pb.location = values
    pb.keyframe_insert(data_path="location", frame=frame, group=bone)


def reset_pose(rig):
    for pb in rig.pose.bones:
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = (0,0,0)
        pb.location = (0,0,0)
        pb.scale = (1,1,1)


def new_action(rig, name):
    action = bpy.data.actions.new(name)
    rig.animation_data_create()
    rig.animation_data.action = action
    return action


def bake_run_cycle(rig):
    """Bake a visibly readable chibi run cycle on EVERY frame.

    The old implementation keyed only five poses. Numerically it could be
    anti-phase while still looking like a body wobble after interpolation on a
    short-legged/chibi mesh. This version samples every frame and gives each
    leg a clear contact -> down -> passing -> up -> contact path.

    The cycle is in-place: root never translates. Game code owns locomotion.
    """
    action = new_action(rig, "run")
    reset_pose(rig)

    # Slightly stronger than the old values so motion is readable on a chibi
    # silhouette, but still conservative enough to avoid self-intersection.
    thigh_amp = 0.72       # ~41 deg forward/back from neutral
    knee_amp = 1.02        # ~58 deg peak bend on airborne leg
    ankle_amp = 0.42
    arm_amp = 0.46
    hip_bob = 0.026
    hip_twist = 0.045

    total = RUN_CYCLE_FRAMES
    for i in range(total + 1):
        frame = i + 1
        t = i / float(total)
        phase_l = 2.0 * math.pi * t
        phase_r = phase_l + math.pi

        # Thighs are guaranteed exact anti-phase.
        thigh_l = thigh_amp * math.cos(phase_l)
        thigh_r = thigh_amp * math.cos(phase_r)

        # A leg bends mainly while it travels forward through its airborne
        # half. max(0, -sin()) and the pi-shift guarantee alternating knees.
        knee_l = -knee_amp * max(0.0, -math.sin(phase_l))
        knee_r = -knee_amp * max(0.0, -math.sin(phase_r))

        # Feet toe-up during recovery and toe-down shortly before contact.
        foot_l = ankle_amp * math.sin(phase_l + 0.35)
        foot_r = ankle_amp * math.sin(phase_r + 0.35)

        # Arms counter-swing against the same-side leg. Keep forearm bend
        # relaxed so held props stay nearer the body and intersect less.
        arm_l = -arm_amp * math.cos(phase_l)
        arm_r = -arm_amp * math.cos(phase_r)
        elbow_l = RUN_FOREARM_BEND - 0.10 * max(0.0, -math.sin(phase_l))
        elbow_r = RUN_FOREARM_BEND - 0.10 * max(0.0, -math.sin(phase_r))

        # Two small vertical dips per cycle at passing phases, plus a tiny
        # pelvis twist. Root remains fixed.
        hips_z = -hip_bob * (0.5 - 0.5 * math.cos(2.0 * phase_l))
        hips_rot_z = hip_twist * math.cos(phase_l)
        chest_x = -0.11 + 0.018 * math.sin(2.0 * phase_l)
        head_x = -0.012 * math.sin(2.0 * phase_l)

        set_pose_rotation(rig, "thigh.L", (thigh_l, 0, 0), frame)
        set_pose_rotation(rig, "thigh.R", (thigh_r, 0, 0), frame)
        set_pose_rotation(rig, "shin.L", (knee_l, 0, 0), frame)
        set_pose_rotation(rig, "shin.R", (knee_r, 0, 0), frame)
        set_pose_rotation(rig, "foot.L", (foot_l, 0, 0), frame)
        set_pose_rotation(rig, "foot.R", (foot_r, 0, 0), frame)
        set_pose_rotation(rig, "upper_arm.L", (arm_l, 0, 0), frame)
        set_pose_rotation(rig, "upper_arm.R", (arm_r, 0, 0), frame)
        set_pose_rotation(rig, "forearm.L", (elbow_l, 0, 0), frame)
        set_pose_rotation(rig, "forearm.R", (elbow_r, 0, 0), frame)
        set_pose_rotation(rig, "hips", (0, 0, hips_rot_z), frame)
        set_pose_location(rig, "hips", (0, 0, hips_z), frame)
        set_pose_rotation(rig, "chest", (chest_x, 0, 0), frame)
        set_pose_rotation(rig, "head", (head_x, 0, 0), frame)

    # Linear interpolation makes planted/swing phases visually predictable;
    # every frame is already baked so there is no loss of smoothness. This is
    # set globally in main() via keyframe_new_interpolation_type before any
    # keyframe_insert() call, so every curve is already linear at insertion
    # time - no need to walk action.fcurves after the fact (that attribute
    # moved under action.layers[...].strips[...].channelbags[...] on newer
    # Blender's layered-action model and would raise AttributeError here).
    action.frame_range = (1, total + 1)
    return action

BLADE_WEAPON_TYPES = {"sword", "blade", "katana", "dao", "kiem", "kiếm", "đao"}
STAFF_WEAPON_TYPES = {"staff", "rod", "wand", "gay", "gậy", "truong", "trượng", "quyen truong", "quyền trượng"}
SPEAR_WEAPON_TYPES = {"spear", "lance", "polearm", "giao", "giáo", "thuong", "thương"}


def bake_sword_attack(rig):
    """Right-hand blade combo: horizontal slash -> diagonal downcut -> overhead
    chop, so 'vung theo mọi góc' is a representative multi-angle combo rather
    than a single swing. Same action name/frame convention as the bow clip
    (attack_01) so validate_game_ready.py's REQUIRED_CLIPS check needs no
    change - only the pose content differs by weapon."""
    a = new_action(rig, "attack_01"); reset_pose(rig)
    # frame, chest_x, chest_z, arm_x(shoulder pitch), arm_z(shoulder swing), elbow_x, off_arm_x, off_arm_z, head_z
    sword_poses = [
        (1,  -0.05,  0.00, -0.20,  0.35, -0.35, -0.15,  0.10,  0.00),  # guard, blade raised right
        (6,  -0.10,  0.30, -0.55,  0.85, -0.55, -0.20,  0.20,  0.10),  # wind-up for horizontal slash
        (10, -0.15, -0.35, -0.30, -0.60, -0.20, -0.15, -0.10, -0.12),  # horizontal slash follow-through (right-to-left)
        (16, -0.22, -0.05, -0.95, -0.15, -0.70, -0.10, -0.05, -0.05),  # wind-up high for diagonal downcut
        (21, -0.02,  0.10, -0.10,  0.30, -0.15, -0.08,  0.08,  0.06),  # diagonal downcut follow-through
        (27, -0.32,  0.00, -1.15,  0.05, -0.80, -0.05,  0.00, -0.16),  # raise overhead
        (32,  0.08,  0.00, -0.05,  0.05, -0.10, -0.10,  0.00,  0.10),  # overhead chop straight down
        (38,  0.00,  0.00, -0.20,  0.35, -0.35, -0.15,  0.10,  0.00),  # recover to guard
    ]
    for f, chest_x, chest_z, arm_x, arm_z, elbow_x, off_x, off_z, head_z in sword_poses:
        set_pose_rotation(rig, "chest", (chest_x, 0, chest_z), f)
        # Right arm holds the blade for every angle of the combo.
        set_pose_rotation(rig, "upper_arm.R", (arm_x, 0, arm_z), f)
        set_pose_rotation(rig, "forearm.R", (elbow_x, 0, 0), f)
        # Left arm counter-balances rather than staying dead still.
        set_pose_rotation(rig, "upper_arm.L", (off_x, 0, off_z), f)
        set_pose_rotation(rig, "forearm.L", (-0.10, 0, 0), f)
        set_pose_rotation(rig, "head", (0.0, 0.0, head_z), f)
    a.frame_range = (1, 38)
    return a


def bake_staff_attack(rig):
    """Two-handed staff/rod: both arms move together (gripping a long pole)
    through a spin wind-up into an overhead downward strike - visually
    distinct from the one-armed sword combo and the bow draw."""
    a = new_action(rig, "attack_01"); reset_pose(rig)
    # frame, chest_x, chest_z, armL_x, armL_z, armR_x, armR_z, elbowL, elbowR, head_z
    staff_poses = [
        (1,  -0.05,  0.00, -0.20,  0.15, -0.20, -0.15, -0.30, -0.30,  0.00),  # ready, staff held across body
        (7,  -0.08,  0.55, -0.35,  0.65, -0.55, -0.60, -0.35, -0.55,  0.14),  # spin wind-up, staff sweeps right
        (14, -0.08, -0.55, -0.55, -0.60, -0.35,  0.65, -0.55, -0.35, -0.14),  # spin continues, staff sweeps left
        (20, -0.35,  0.00, -1.05,  0.05, -1.05,  0.05, -0.75, -0.75,  0.00),  # both arms raise staff overhead
        (25,  0.10,  0.00, -0.10,  0.05, -0.10,  0.05, -0.15, -0.15,  0.10),  # overhead strike straight down
        (32,  0.00,  0.00, -0.20,  0.15, -0.20, -0.15, -0.30, -0.30,  0.00),  # recover to ready
    ]
    for f, chest_x, chest_z, arm_lx, arm_lz, arm_rx, arm_rz, elbow_l, elbow_r, head_z in staff_poses:
        set_pose_rotation(rig, "chest", (chest_x, 0, chest_z), f)
        set_pose_rotation(rig, "upper_arm.L", (arm_lx, 0, arm_lz), f)
        set_pose_rotation(rig, "forearm.L", (elbow_l, 0, 0), f)
        set_pose_rotation(rig, "upper_arm.R", (arm_rx, 0, arm_rz), f)
        set_pose_rotation(rig, "forearm.R", (elbow_r, 0, 0), f)
        set_pose_rotation(rig, "head", (0.0, 0.0, head_z), f)
    a.frame_range = (1, 32)
    return a


def bake_spear_attack(rig):
    """Two-handed thrust: front (right) hand drives the spear straight
    forward while the back (left) hand anchors near the torso, then both
    retract - a linear thrust reads as distinct from the sword's arcing
    slashes and the staff's spin."""
    a = new_action(rig, "attack_01"); reset_pose(rig)
    # frame, chest_x, front_arm_x(R), front_elbow(R), back_arm_x(L), back_elbow(L), head_z
    spear_poses = [
        (1,  -0.05, -0.15, -0.55, -0.10, -0.35,  0.00),  # ready, spear held level
        (6,  -0.20, -0.65, -0.85, -0.05, -0.20,  0.05),  # draw back for thrust
        (11,  0.05, -0.05, -0.05, -0.20, -0.45, -0.05),  # full thrust forward, arms extend
        (16,  0.05, -0.05, -0.05, -0.20, -0.45, -0.05),  # brief hold at full extension
        (22, -0.10, -0.40, -0.65, -0.12, -0.30,  0.02),  # retract
        (28, -0.05, -0.15, -0.55, -0.10, -0.35,  0.00),  # recover to ready
    ]
    for f, chest_x, front_x, front_elbow, back_x, back_elbow, head_z in spear_poses:
        set_pose_rotation(rig, "chest", (chest_x, 0, 0), f)
        set_pose_rotation(rig, "upper_arm.R", (front_x, 0, 0), f)
        set_pose_rotation(rig, "forearm.R", (front_elbow, 0, 0), f)
        set_pose_rotation(rig, "upper_arm.L", (back_x, 0, 0), f)
        set_pose_rotation(rig, "forearm.L", (back_elbow, 0, 0), f)
        set_pose_rotation(rig, "head", (0.0, 0.0, head_z), f)
    a.frame_range = (1, 28)
    return a


def bake_talk_cycle(rig):
    """Cyclic jaw open/close, independent of weapon - a crude 'talking' loop,
    not real lip-sync (no audio/viseme input exists anywhere in this app).
    Whether this reads as a mouth opening or moves some other lower-head
    geometry depends entirely on where the zone fallback's front-ness guess
    actually landed on a given mesh - there is no way to confirm that without
    looking at the render, only that SOME real motion exists (checked below
    via the same has-motion evidence the validator already uses)."""
    a = new_action(rig, "talk"); reset_pose(rig)
    for f, jaw_x in [(1, 0.0), (6, -0.16), (11, -0.03), (16, -0.20), (21, -0.02), (26, -0.14), (30, 0.0)]:
        set_pose_rotation(rig, "jaw", (jaw_x, 0, 0), f)
    a.frame_range = (1, 30)
    return a


def bake_starter_actions(rig, weapon_type="bow"):
    actions=[]
    # Idle: tiny breathing/bob only.
    a=new_action(rig,"idle"); reset_pose(rig)
    for f, z, chest in [(1,0,0),(24,.012,.035),(48,0,0)]:
        set_pose_location(rig,"hips",(0,0,z),f); set_pose_rotation(rig,"chest",(chest,0,0),f)
        set_pose_rotation(rig,"upper_arm.L",(0,0,.04 if f==24 else 0),f)
        set_pose_rotation(rig,"upper_arm.R",(0,0,-.04 if f==24 else 0),f)
    a.frame_range=(1,48); actions.append(a)

    if rig.pose.bones.get("jaw"):
        actions.append(bake_talk_cycle(rig))

    actions.append(bake_run_cycle(rig))

    weapon_key = str(weapon_type or "").strip().lower()
    if weapon_key in BLADE_WEAPON_TYPES:
        actions.append(bake_sword_attack(rig))
    elif weapon_key in STAFF_WEAPON_TYPES:
        actions.append(bake_staff_attack(rig))
    elif weapon_key in SPEAR_WEAPON_TYPES:
        actions.append(bake_spear_attack(rig))
    else:
        # Bow-oriented starter attack: raise bow -> draw string -> short aim
        # hold -> release -> recover. The rig cannot physically simulate a bow
        # string/arrow, but the body/arms now read as an archer shot instead of a
        # generic melee swing. Weapon-specific meshes can replace this clip later.
        a = new_action(rig, "attack_01"); reset_pose(rig)
        bow_poses = [
            # frame, chest_z, bow_arm_x, bow_arm_z, draw_arm_x, draw_arm_z, draw_elbow
            (1,   0.00, -0.10,  0.15, -0.10, -0.10, -0.20),  # ready
            (6,  -0.06, -0.55,  0.42, -0.42, -0.55, -0.75),  # raise bow
            (12, -0.10, -0.72,  0.52, -0.30, -0.95, -1.20),  # full draw
            (16, -0.10, -0.72,  0.52, -0.30, -0.95, -1.20),  # aim hold
            (18, -0.04, -0.68,  0.48, -0.08, -0.25, -0.18),  # release
            (24,  0.00, -0.30,  0.28, -0.15, -0.18, -0.20),  # follow-through
            (30,  0.00, -0.10,  0.15, -0.10, -0.10, -0.20),  # recover
        ]
        for f, chest_z, bow_x, bow_z, draw_x, draw_z, draw_elbow in bow_poses:
            set_pose_rotation(rig, "chest", (-0.04, 0, chest_z), f)
            # Left arm acts as bow arm: mostly extended and raised forward.
            set_pose_rotation(rig, "upper_arm.L", (bow_x, 0, bow_z), f)
            set_pose_rotation(rig, "forearm.L", (-0.08, 0, 0), f)
            # Right arm draws back toward the face, then snaps forward on release.
            set_pose_rotation(rig, "upper_arm.R", (draw_x, 0, draw_z), f)
            set_pose_rotation(rig, "forearm.R", (draw_elbow, 0, 0), f)
            set_pose_rotation(rig, "head", (0.0, 0.0, chest_z * 0.25), f)
        a.frame_range = (1, 30)
        actions.append(a)

    # Put each action into its own NLA track; glTF exports tracks as clips.
    rig.animation_data.action = None
    for action in actions:
        track=rig.animation_data.nla_tracks.new(); track.name=action.name
        strip=track.strips.new(action.name,1,action); strip.action_frame_start=action.frame_range[0]; strip.action_frame_end=action.frame_range[1]
    return [a.name for a in actions]


def export_glb(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(path), export_format="GLB", export_animations=True,
        export_skins=True, export_morph=False, export_apply=False,
        export_materials="EXPORT", export_yup=True,
    )


def main():
    a=args_after_dash(); src=Path(a.input); out=Path(a.output); report=Path(a.report)
    out_dir = out.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    # Every keyframe_insert() below picks up this interpolation at insertion
    # time - a stable, version-safe way to get linear curves without touching
    # Action.fcurves (data model changed under newer "layered actions").
    try:
        bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"
    except Exception:
        pass

    # section 2: every intermediate stage saved under a fixed, predictable
    # name so a failed job still leaves inspectable checkpoints behind.
    source_glb = out_dir / "source.glb"
    optimized_glb = out_dir / "optimized.glb"
    rigged_glb = out_dir / "rigged.glb"
    shutil.copy2(src, source_glb)

    bpy.context.scene.render.fps = RUN_FPS  # explicit, so exported clip durations are predictable
    clear_scene(); meshes=import_glb(src); mesh=join_meshes(meshes)
    before, after=optimize_mesh(mesh,a.target_faces)
    export_glb(optimized_glb)

    rig=create_rig(mesh); skin_method=auto_skin(mesh,rig)
    export_glb(rigged_glb)  # bind pose only, no baked animation yet - isolates skin issues from animation issues

    animations=bake_starter_actions(rig, a.weapon_type)
    export_glb(out)
    data={
        "ok": True, "rigged": True, "skin_method": skin_method, "animations": animations,
        "bones": len(rig.data.bones), "faces_before": before, "faces_after": after,
        "output": str(out), "source_glb": str(source_glb), "optimized_glb": str(optimized_glb),
        "rigged_glb": str(rigged_glb), "weapon_type": a.weapon_type,
    }
    report.parent.mkdir(parents=True,exist_ok=True); report.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    print("AIVF_GAME_READY_REPORT="+json.dumps(data,ensure_ascii=False))


if __name__ == "__main__":
    main()
