# Interfaces

## `metric_scene_v1`

Invoke the CPU runner with `--scene /absolute/path/to/building.json`. Required fields: `schema`, unique `scene_id`, `units: "m"`, `world_frame: "RH_Z_UP"`, four-number global `bounds_m=[x0,y0,x1,y1]`, `height_m`, `provenance`, at least two spaces plus a corridor, wall segments and physical door links connecting all spaces. Multiple corridors and any connected room count are allowed. Optional furniture boxes and cameras use global metres and unique IDs. Walls are axis aligned in this schema. Floor z=0; an explicit nonzero `floor_z_m` is rejected. Blender can render other heights, but the `Sage_gt` adapter rejects any height other than 2.7 m.

Walls carry `p0_m`, `p1_m`, `thickness_m`, and openings with wall-local `u0_m/u1_m` and floor-relative `z0_m/z1_m`. A door's two `connects` IDs must match the actual spaces on opposite wall sides; all spaces must be reachable through doors. Validation rejects invalid bounds, units, IDs, disconnected topology, overlapping openings, mismatched door sides and cameras outside their declared space.

The backward-compatible real-drawing extension accepts `footprint_mode: SPACE_UNION` so floors and ceilings are generated from the union of rectangular spaces instead of a full outer rectangle. `exterior_door` has one interior `connects` ID and must have exactly one space on its physical sides. Interior `door` retains two endpoints and drives the connectivity graph. Each room/wall/opening can carry `confidence` and an SVG element reference. `agent_revisions` records bounded edits; an empty list means no Agent geometry change. `SOURCE_DRAWING` may include `annotation_file` and `annotation_sha256`, both checked by `load_scene`. Existing synthetic JSON remains unchanged.

The raster parser writes `raw_prediction.json` with pixel-space `wall_traces`, `room_candidates`, and empty unverified `door_candidates`/`window_candidates`; these **cannot** be passed to Blender as `metric_scene_v1`. `revised_prediction.json` and `agent_revision.json` preserve the candidate changes. `reference_evaluation.json` uses the human SVG only after prediction, for scoring. With `--annotation-sidecars`, a distinct control writes `metric_scene.json` with `parser_kind: CUBICASA5K_HUMAN_SVG_ANNOTATION_ADAPTER` and `automatic_raster_inference: false`.

`provenance.kind` is `SYNTHETIC` or `SOURCE_DRAWING`. A `SOURCE_DRAWING` JSON must set `source_file`, its actual SHA256, `scale_evidence`, `real_floorplan_parsed: true`, and non-synthetic evidence for rooms, walls and objects. `load_scene` verifies the referenced local file and hash. This is an input provenance gate, **not** evidence that this repository implements a floorplan predictor or can independently prove the annotations correct. Both committed fixtures remain `SYNTHETIC`.

## Blender output

For each camera ID: `rgb/<id>.png`, `depth/<id>.npy`, `object_id/<id>.npy`, plus the raw multilayer EXR. `camera_metadata.json` records 3×3 pixel `K_px` and 4×4 Blender `c2w_blender` in original global metres. Blender points along camera `−Z`; depth is camera-axis Z distance in metres; pixel centres use `(u+0.5,v+0.5)`. A/B camera IDs, intrinsics and poses must match. `object_id_map.json` resolves integer pass IDs to global objects. Compact Git evidence packs aligned arrays in `depth_all.npz` and `object_id_all.npz`; raw EXRs and NPYs regenerate locally.

## Native GenRecon `Sage_gt`

The adapter writes `renders_room/<scene_id>/transforms.json` and PNG basenames, plus sibling `rooms_raw/<scene_id>/layout_<scene_id>.json`. `adapter_transform.json` records the global-to-Sage translation. The native `SageGtChunker` uses outer width/length and fixed z range; `SageImageSelecter` filters cameras visible to at least one chunk, then applies an evenly spaced `num_imgs_per_scene` cap. It picks one accepted image per chunk or a closest-camera fallback. Reports distinguish the source camera set, actually selected scene images, each chunk's accepted selected cameras and fallback. Native acceptance does not check wall occlusion or preserve interior structure by itself.
