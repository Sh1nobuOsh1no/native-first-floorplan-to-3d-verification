# Architecture and scope

```text
complete floorplan (real source pending)
    ↓ source-backed metric extraction / Agent (not validated on a real whole building)
global Metric Scene JSON: metres, RH_Z_UP, spaces, door links, walls, cameras, provenance
    ↓ one scene graph, one world origin, one Blender Scene
building mesh + A/B 16-view RGB / depth / object IDs / K / c2w
    ↓ separate packaging adapter; PNG and original Blender poses
GenRecon Sage_gt native CPU Chunker and ImageSelecter
    ↓ GPU stage pending; three pretrained flow stages + joint decode
candidate 3D World → structural and cross-door evaluation (pending)
```

The CPU fixture is one **synthetic** 12 × 9 m, 2.7 m high building. Room bounds and the corridor share coordinates. Four physical door openings connect the corridor to bedroom, office, living room and kitchen. The Blender geometry compiler splits each global wall around its door/window openings, creates a single scene, and exports a merged Blender mesh as `building_unified.glb`. A has structure only; B adds four simple gray blocks with unique IDs. Both use the same 16 cameras.

The renderer uses Cycles CPU. Multilayer OpenEXR stores Image, Z Depth and Object Index from the same render. The decoder writes aligned PNG, float32 depth in metres and integer object IDs; `camera_metadata.json` preserves the global metric pose and pixel K. glTF stores a Y-up transform; the JSON remains RH_Z_UP in metres.

GenRecon is pinned to `eaf1468118d20469d17079a4a19737297d2ef87b` and never edited. `prepare_sage_gt.py` copies the Blender PNGs and poses into the official `renders_room/<scene>/` layout and writes `rooms_raw/<scene>/layout_<scene>.json`. The original `SageGtChunker` and `SageImageSelecter` execute on CPU. Their success establishes parsing and selection only. The native `Sage_gt` layout reader takes just the first room's outer width and length, fixes height to 2.7 m and does not read interior walls, door links, depth or object IDs as hard constraints. These fields remain in independent evidence and evaluation.

The model stages in the untouched source are DINOv3 image conditioning, `cond_2D`, camera-projected `cond_3D`, Sparse Structure, Shape SLat and Texture SLat with CFG. Four external config JSONs change only sampler `guidance_strength`. Their effect on output is unmeasured without GPU forward.
