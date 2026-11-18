# Interface contract

## Global Metric Scene JSON

`fixtures/multiroom/synthetic_building.json` is the reference. Required: `units: "m"`, `world_frame: "RH_Z_UP"`, `bounds_m`, `height_m`, `provenance.kind`, spaces with unique IDs, semantic types and global bounds, axis-aligned walls with endpoints/thickness and door/window intervals, door `connects` matching the actual two wall sides, optional globally identified objects, and cameras with globally measured eye/target/FOV. Every space/wall has source evidence. `SOURCE_DRAWING` additionally needs a source file and SHA256 and cannot reuse synthetic room/wall evidence. The current fixture is `SYNTHETIC`; no real source image was used.

The wall openings use `u0_m/u1_m` along the wall from `p0_m` and `z0_m/z1_m` above the global floor. The validation rejects nonmetric units, overlapping or out-of-wall openings, wrong door side links, disconnected topology, nonphysical camera locations, degenerate poses and forged real provenance. A door is a true hole in the **one** wall mesh, not a visual marker.

## Camera and render

Each frame has `rgb/<camera_id>.png`, `depth/<camera_id>.npy`, `object_id/<camera_id>.npy`, `passes/<camera_id>.exr`, 3×3 `K_px`, and 4×4 Blender `c2w_blender`. Image origin is top left; pixel centre is `(u+0.5,v+0.5)`. Blender view points along camera `-Z`; unprojection uses `[(u+.5-cx)/fx*d, -(v+.5-cy)/fy*d, -d]`, where `d` is the Blender Z pass camera-axis depth in metres. The renderer stores the unmodified world coordinate and source camera ID. Object ID 0 is background; positive IDs resolve through `object_id_map.json`.

A and B share exactly the same camera ID, K and c2w matrices. All 16 frames are 256×256 RGB with same-resolution depth and object IDs. `building_unified.glb` has one joined Blender mesh object; glTF material primitives may appear as separate mesh entries after export. glTF Y-up axes map from Blender `(x,y,z)` to `(x,z,-y)`; compare physical extents after this transform.

## Native GenRecon `Sage_gt`

Directory contract: `renders_room/<scene_id>/transforms.json` plus image basenames; sibling `rooms_raw/<scene_id>/layout_<scene_id>.json`. `transforms.json` frames have `file_path`, `camera_angle_x`, `transform_matrix` (Blender c2w). The adapter copies RGB and preserves original c2w/FOV. The native reader normalizes K and transforms Blender to OpenCV; it selects scene views, then one 2D conditioning view per chunk. `Sage_gt` sees the **outer** width/length and hardcoded 2.7 m height. It does not consume the global scene's doors, interior walls, depth pass or object IDs as geometric constraints. CPU reader acceptance cannot establish learned structural preservation.
