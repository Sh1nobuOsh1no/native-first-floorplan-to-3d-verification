# Architecture

```text
complete multiroom drawing (real source extraction pending)
  → validated global metric_scene_v1 JSON, topology and provenance
  → automatic room/door/chunk camera plan in one RH_Z_UP metre frame
  → one Blender Scene, A/B mesh and identical cameras
  → CPU RGB + Z-depth + object ID + K/c2w, cross-door check
  → external Sage_gt adapter: outer dimensions + normalized x/y poses
  → unmodified GenRecon CPU Chunker and ImageSelecter
  → future pretrained GPU inference and generated-mesh acceptance
```

The scene compiler makes one list of global primitives and splits each wall at openings. Blender builds a single building Scene and exports a joined mesh. The two regression layouts are 12 × 9 m with four rooms/four corridor doors, and 6 × 9 m with two rooms/two corridor doors and world x/y origin (−4, 10). A contains the shell; B adds gray furniture with stable IDs. Both variants use the exact same planned camera list.

`src/cameras/plan_native.py` calls the official `SageGtChunker` and `SageImageSelecter._check_acceptance` on CPU. It generates candidates from rooms and currently uncovered chunks, requires a clear ray to each candidate's covered chunk centre, and greedily adds cameras until every native chunk is covered or the `--n-views` budget is reached. Existing cameras keep the four door-side observation pairs. The official acceptance samples eight chunk corners and its centre, projects them through the camera and requires clipped normalized image area ≥0.4. This ignores wall occlusion; the adapter's ray check prevents a newly added camera from counting a solid-wall-only view. The native Reader and actual rendered passes remain the final evidence.

`prepare_sage_gt.py` copies rendered RGB and camera poses into `renders_room/<scene_id>` and writes `rooms_raw/<scene_id>/layout_<scene_id>.json`. The original global x/y coordinates stay in Blender metadata. For the native copy, the adapter subtracts the scene's x/y minimum from each camera translation and records `global_to_sage_translation_m`; this matches `Sage_gt`'s hardcoded zero x/y minimum. A height other than 2.7 m is rejected for this native mode. The current schema fixes floor z=0.

The official Reader selects at most `num_imgs_per_scene` source views before assigning each chunk its 2D condition image. The default CLI limit is 32; the 20-view main plan and 13-view alternate plan are therefore fully selected. A measured 8-view control had 11 fallback chunks despite 20 source images. The full-scene GPU path can pass these selected views to conditioning stages, but actual checkpoint behavior and memory with 20 views are not validated here.

GenRecon's native `Sage_gt` layout consumes only outer width/length and fixes floor/ceiling at 0/2.7 m. Interior walls, doors, depth and object IDs are **not hard constraints** in that interface. The generated world's geometry and cross-room identity require a later GPU run and independent evaluation; CPU Reader success cannot establish them.
