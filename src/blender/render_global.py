"""Blender CPU Cycles renderer for one global metric building scene.

Run with ``blender -b --python src/blender/render_global.py -- [arguments]``.
The only input geometry is the unified Metric Scene JSON; A and B share its
camera list exactly. Rendering writes RGB, metric Z-depth, and object index
from the same render pass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--scene", required=True, type=Path)
    p.add_argument("--variant", required=True, choices=("A", "B"))
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--size", type=int, default=256)
    p.add_argument("--samples", type=int, default=4)
    p.add_argument("--limit", type=int, default=0)
    return p.parse_args(sys.argv[sys.argv.index("--") + 1:])


def material(name: str, rgb: tuple[float, float, float]):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, 1)
    m.use_nodes = True
    m.node_tree.nodes.get("Principled BSDF").inputs["Base Color"].default_value = (*rgb, 1)
    return m


def add_box(spec: dict, mat, pass_index: int):
    bpy.ops.mesh.primitive_cube_add(size=1, location=spec["center_m"])
    obj = bpy.context.object
    obj.name = spec["id"]
    obj.dimensions = spec["size_m"]
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.pass_index = pass_index
    obj.data.materials.append(mat)
    obj["source_id"] = spec["source_id"]
    obj["kind"] = spec["kind"]
    return obj


def output_node(nodes):
    node = nodes.new("CompositorNodeOutputFile")
    node.file_name = "passes/pending_"
    node.file_output_items.new("RGBA", "Image")
    node.file_output_items.new("FLOAT", "Depth")
    node.file_output_items.new("FLOAT", "ObjectID")
    return node


def rendered_file(out: Path, temp_root: Path, camera_id: str) -> Path:
    candidates = sorted(temp_root.glob(f"{camera_id}_*.exr"))
    if len(candidates) != 1:
        raise RuntimeError(f"Expected one EXR file for {camera_id}, got {candidates}")
    dest = out / "passes" / f"{camera_id}.exr"
    os.replace(candidates[0], dest)
    return dest


def main():
    args = parse_args()
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root))
    from src.scene_graph.metric_scene import components, load_scene

    scene_json = load_scene(args.scene)
    out = args.out.resolve()
    for part in ("rgb", "depth", "object_id", "passes"):
        (out / part).mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = args.samples
    scene.render.threads_mode = "FIXED"
    scene.render.threads = 4
    scene.render.resolution_x = args.size
    scene.render.resolution_y = args.size
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "Standard"
    scene.world.color = (0.55, 0.55, 0.55)
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.65, 0.65, 0.65, 1)
    scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.65
    mats = {
        "wall": material("white_wall", (0.74, 0.74, 0.74)),
        "floor": material("white_floor", (0.83, 0.83, 0.83)),
        "ceiling": material("white_ceiling", (0.90, 0.90, 0.90)),
        "furniture": material("gray_furniture", (0.53, 0.53, 0.53)),
    }
    boxes = components(scene_json, args.variant == "B")
    object_map = {}
    for i, spec in enumerate(boxes, 1):
        add_box(spec, mats[spec["kind"]], i)
        object_map[str(i)] = {"id": spec["id"], "kind": spec["kind"], "source_id": spec["source_id"]}
    for i, room in enumerate(scene_json["spaces"]):
        x0, y0, x1, y1 = room["bounds_m"]
        data = bpy.data.lights.new(f"area_{room['id']}", type="AREA")
        data.energy = 45
        data.shape = "DISK"
        data.size = 3.0
        obj = bpy.data.objects.new(data.name, data)
        scene.collection.objects.link(obj)
        obj.location = ((x0 + x1) / 2, (y0 + y1) / 2, scene_json["height_m"] - .25)
        obj.rotation_euler = (0, 0, 0)
    bpy.ops.object.camera_add()
    camera = bpy.context.object
    camera.name = "global_camera"
    camera.data.sensor_fit = "HORIZONTAL"
    camera.data.sensor_width = 36.0
    camera.data.clip_start = 0.05
    camera.data.clip_end = 100.0
    scene.camera = camera
    view_layer = scene.view_layers[0]
    view_layer.use_pass_z = True
    view_layer.use_pass_object_index = True
    scene.use_nodes = True
    tree = bpy.data.node_groups.new("GlobalCPUCompositor", "CompositorNodeTree")
    scene.compositing_node_group = tree
    tree.nodes.clear()
    render_layer = tree.nodes.new("CompositorNodeRLayers")
    passes = output_node(tree.nodes)
    temp_token = hashlib.sha256(str(out).encode()).hexdigest()[:16]
    temp_root = Path("/tmp/native_first_blender") / temp_token
    temp_root.mkdir(parents=True, exist_ok=True)
    tree.links.new(render_layer.outputs["Image"], passes.inputs["Image"])
    tree.links.new(render_layer.outputs["Depth"], passes.inputs["Depth"])
    tree.links.new(render_layer.outputs["Object Index"], passes.inputs["ObjectID"])
    (out / "object_id_map.json").write_text(json.dumps(object_map, indent=2) + "\n")
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "building.blend"))
    try:
        bpy.ops.export_scene.gltf(filepath=str(out / "building.glb"), export_format="GLB", use_selection=False)
        bpy.ops.object.select_all(action="DESELECT")
        mesh_objects = [obj for obj in scene.objects if obj.type == "MESH"]
        for obj in mesh_objects:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = mesh_objects[0]
        bpy.ops.object.duplicate()
        bpy.ops.object.join()
        unified = bpy.context.object
        unified.name = "global_building_mesh"
        bpy.ops.export_scene.gltf(filepath=str(out / "building_unified.glb"), export_format="GLB", use_selection=True)
        bpy.ops.object.delete(use_global=False)
    except Exception as exc:
        print(f"GLB_EXPORT_FAILED: {exc}", file=sys.stderr)
        raise
    frames = []
    metadata = []
    cams = scene_json["cameras"][: args.limit or None]
    for idx, spec in enumerate(cams, 1):
        cid = spec["id"]
        camera.location = spec["eye_m"]
        direction = Vector(spec["target_m"]) - camera.location
        camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
        camera.data.lens = 36.0 / (2 * math.tan(math.radians(spec["fov_deg"]) / 2))
        bpy.context.view_layer.update()
        c2w = [[float(camera.matrix_world[r][c]) for c in range(4)] for r in range(4)]
        fov_x = float(camera.data.angle_x)
        f = args.size / (2 * math.tan(fov_x / 2))
        passes.file_name = f"native_first_blender/{temp_token}/{cid}_"
        for stale in temp_root.glob(f"{cid}_*.exr"):
            stale.unlink()
        scene.frame_set(idx)
        bpy.ops.render.render(write_still=False)
        exr_path = rendered_file(out, temp_root, cid)
        rgb_path = out / "rgb" / f"{cid}.png"
        depth_path = out / "depth" / f"{cid}.npy"
        id_path = out / "object_id" / f"{cid}.npy"
        frames.append({"file_path": f"rgb/{rgb_path.name}", "transform_matrix": c2w,
                       "camera_angle_x": fov_x, "camera_id": cid})
        metadata.append({"camera_id": cid, "space_id": spec["space_id"], "eye_m": spec["eye_m"],
                         "target_m": spec["target_m"], "K_px": [[f, 0, args.size / 2], [0, f, args.size / 2], [0, 0, 1]],
                         "c2w_blender": c2w, "rgb": str(rgb_path.relative_to(out)), "depth_npy": str(depth_path.relative_to(out)),
                         "object_id_npy": str(id_path.relative_to(out)), "passes_exr": str(exr_path.relative_to(out)),
                         "provenance": scene_json["provenance"]["kind"] + "_BLENDER_CPU"})
        print(f"RENDERED {args.variant} {idx}/{len(cams)} {cid}", flush=True)
    (out / "transforms.json").write_text(json.dumps({"camera_angle_x": frames[0]["camera_angle_x"], "frames": frames}, indent=2) + "\n")
    (out / "camera_metadata.json").write_text(json.dumps({"variant": args.variant, "frames": metadata}, indent=2) + "\n")
    (out / "render_manifest.json").write_text(json.dumps({"scene_id": scene_json["scene_id"],
        "provenance": scene_json["provenance"]["kind"], "variant": args.variant, "engine": "CYCLES_CPU",
        "samples": args.samples, "resolution": [args.size, args.size], "frame_count": len(frames),
        "object_count": len(boxes), "global_scene": True}, indent=2) + "\n")


if __name__ == "__main__":
    main()
