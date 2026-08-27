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


def args_after_dash():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--report", required=True)
    p.add_argument("--target-faces", type=int, default=45000)
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
    mn, mx = world_bbox(mesh); h = max(mx.z-mn.z, .001); cx=(mn.x+mx.x)*.5
    groups = {b.name: mesh.vertex_groups.new(name=b.name) for b in rig.data.bones}
    for v in mesh.data.vertices:
        co = mesh.matrix_world @ v.co
        t = (co.z-mn.z)/h
        x = co.x-cx
        name = "hips"
        if t > .82: name = "head"
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


def bake_starter_actions(rig):
    actions=[]
    # Idle: tiny breathing/bob only.
    a=new_action(rig,"idle"); reset_pose(rig)
    for f, z, chest in [(1,0,0),(24,.012,.035),(48,0,0)]:
        set_pose_location(rig,"hips",(0,0,z),f); set_pose_rotation(rig,"chest",(chest,0,0),f)
        set_pose_rotation(rig,"upper_arm.L",(0,0,.04 if f==24 else 0),f)
        set_pose_rotation(rig,"upper_arm.R",(0,0,-.04 if f==24 else 0),f)
    a.frame_range=(1,48); actions.append(a)

    # Run in-place: root translation is intentionally zero; game owns movement.
    a=new_action(rig,"run"); reset_pose(rig)
    for f, s in [(1,1),(7,-1),(13,1),(19,-1),(25,1)]:
        set_pose_rotation(rig,"thigh.L",(s*.72,0,0),f); set_pose_rotation(rig,"thigh.R",(-s*.72,0,0),f)
        set_pose_rotation(rig,"shin.L",(-max(0,s)*.55,0,0),f); set_pose_rotation(rig,"shin.R",(-max(0,-s)*.55,0,0),f)
        set_pose_rotation(rig,"upper_arm.L",(-s*.55,0,0),f); set_pose_rotation(rig,"upper_arm.R",(s*.55,0,0),f)
        set_pose_location(rig,"hips",(0,0,.018 if f in (7,19) else 0),f)
    a.frame_range=(1,25); actions.append(a)

    # Generic starter attack; later clips can replace it without re-rigging.
    a=new_action(rig,"attack_01"); reset_pose(rig)
    poses=[(1,0,0),(8,-.55,.8),(14,.35,-1.05),(22,.12,-.35),(30,0,0)]
    for f,chest_z,arm_x in poses:
        set_pose_rotation(rig,"chest",(0,0,chest_z),f)
        set_pose_rotation(rig,"upper_arm.R",(arm_x,0,-.45),f)
        set_pose_rotation(rig,"forearm.R",(-.55 if f in (8,14) else -.15,0,0),f)
        set_pose_rotation(rig,"upper_arm.L",(-.25,0,.2),f)
    a.frame_range=(1,30); actions.append(a)

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

    # section 2: every intermediate stage saved under a fixed, predictable
    # name so a failed job still leaves inspectable checkpoints behind.
    source_glb = out_dir / "source.glb"
    optimized_glb = out_dir / "optimized.glb"
    rigged_glb = out_dir / "rigged.glb"
    shutil.copy2(src, source_glb)

    clear_scene(); meshes=import_glb(src); mesh=join_meshes(meshes)
    before, after=optimize_mesh(mesh,a.target_faces)
    export_glb(optimized_glb)

    rig=create_rig(mesh); skin_method=auto_skin(mesh,rig)
    export_glb(rigged_glb)  # bind pose only, no baked animation yet - isolates skin issues from animation issues

    animations=bake_starter_actions(rig)
    export_glb(out)
    data={
        "ok": True, "rigged": True, "skin_method": skin_method, "animations": animations,
        "bones": len(rig.data.bones), "faces_before": before, "faces_after": after,
        "output": str(out), "source_glb": str(source_glb), "optimized_glb": str(optimized_glb),
        "rigged_glb": str(rigged_glb),
    }
    report.parent.mkdir(parents=True,exist_ok=True); report.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    print("AIVF_GAME_READY_REPORT="+json.dumps(data,ensure_ascii=False))


if __name__ == "__main__":
    main()
