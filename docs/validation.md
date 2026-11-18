# CPU validation executed 2026-11-18

## Scope and measured outcomes

All building results below use **SYNTHETIC** geometry. No complete real floorplan image or real drawing end-to-end extraction was tested. No NVIDIA GPU, training, checkpoint forward or learned 3D mesh generation ran.

| Check | Actual result | Evidence / limit |
| --- | --- | --- |
| Whole-building metric scene | **PASS CPU**: 12 × 9 × 2.7 m, four rooms, corridor, four physical doors, six windows; source labels and unique IDs | `fixtures/multiroom/synthetic_building.json`, layout PNG, 21 tests |
| Pixel-to-metre affine | **PASS UNIT INTERFACE** on synthetic polygons, including negative world coordinates and missing scale rejection | `tests/unit/test_metric_scene.py`; this is not real floorplan understanding |
| One Blender Scene / unified mesh | **PASS CPU**: A 36 global primitives, B 40 including four gray furniture blocks; `building_unified.glb` made by joining copies inside Blender, 16 renders each | render manifests, GLB, EXR; glTF splits material primitives |
| RGB / depth / K / pose / object ID | **PASS CPU**: 16 aligned 256² frames per variant, A/B K and c2w equal; metric Z pass and EXR channels checked | camera metadata, `decode_check.json`, images, tests |
| Same object across doors | **PASS SYNTHETIC CPU**: each of four blocks visible from corridor and its own room; bedroom jamb depth 1.219 m before bed depth 2.856 m | object IDs, depth, integration test |
| Cross-view reprojection | **PASS SYNTHETIC CPU**: projected object pixels matched object ID and depth within 0.1 m: bed 3123/3134 (99.65%), desk 3111/3118 (99.78%), sofa 3847/3876 (99.25%), counter 3948/3970 (99.45%) | `evidence/cpu/validation_summary.json`; whitebox only |
| GenRecon native `Sage_gt` Reader/Chunker | **PASS CPU INPUT** for A/B: original classes read 16 images, output 30 chunks and tensors | `native_A_report.json`, `native_B_report.json`; **4/30 chunks have zero accepted cameras and native fallback**: 3, 5, 17, 27 |
| Door vicinity camera acceptance | **PARTIAL**: 1–2 chunks near each of four doors have accepted cameras from both connected spaces | `native_*_report.json`; does not guarantee model output consistency |
| GenRecon CFG parameter/source | **PASS STATIC CPU**: original config 7.5/7.5/1.0; external 3/3/1, 1/1/1, 7.5/7.5/0.5 JSONs parsed; CLI and condition/stage source symbols checked | `cfg_preflight.json`, `configs/genrecon_cfg/`; no CFG effect measured |
| Official SAGE single room | **PASS PRIOR CPU INPUT**, kept separately as native interface evidence: official SAGE scene `84b703fb`, 67 ZIP files CRC identical, author Blender CPU output 16 views, native reader 12 chunks without fallback | `evidence/cpu/official_sage/`; it does **not** validate a multiroom building |
| Real building inference and final PBR world | **NOT RUN** | needs a real source drawing and GPU model forward; hypothesis unresolved |

## Native reader coverage risk

Official GenRecon source at `eaf1468118d20469d17079a4a19737297d2ef87b` is unchanged. `inference/get_chunks.py` uses the first `rooms[0].dimensions.width/length` and fixed ceiling 2.7 m to place 30 overlapping chunks. `inference/get_images.py` accepts camera views by frustum/area and falls back to nearest camera where none passes. We measured zero accepted cameras and fallback in chunks **3, 5, 17, 27** for both variants. At the four door vicinities, at least one nearby chunk sees accepted cameras from both connected spaces, but this is a sampling check, not a cross-room learned geometry constraint.

The `Sage_gt` adapter passes RGB and original Blender poses; its layout file cannot impose the internal wall or door graph. Depth and object ID are measured evidence and future acceptance references, **not inputs consumed by this native pipeline**. Consequently, CPU reader success must never be presented as structural preservation or a GenRecon generated world.

## Commands, failures and outputs

The single formal entry is:

```bash
python -m src.runner.run_cpu --repo /absolute/path/to/clean/GenRecon --blender /absolute/path/to/blender
```

The 2026-11-18 run used Blender 5.3.0 CPU, 256², 8 samples, 16 cameras per variant and a clean official GenRecon checkout. `evidence/cpu/command_index.csv` records **58** actual logged invocations, argv, working directory, UTC start, elapsed time and exit status. Final success logs for fixture, layout, A/B Blender render, EXR decode, `Sage_gt` packaging, native reader, CFG and **21 passing tests** are in `evidence/cpu/logs/`. The clean public package was independently retested against its packed depth/object-ID evidence: 21/21 passed. Full local raw EXR, all PNG/depth arrays, `.blend`, GLB and command logs were retained in the engineering workspace; the public repository carries 16 RGB frames per variant, packed depth/object-ID arrays, contact sheets, JSON, mesh and compact final logs.

During implementation, nine Blender probe invocations returned nonzero while adapting Blender 5.3's compositor API and output path. Two early wrapper calls returned 127 because `--log-dir` was placed after the positional command name. An initial test discovery returned 5 because `tests/` subdirectories had no `__init__.py`. These are recorded in the command index and were corrected; the final 21-test run returned 0. Blender was invoked with `--python-exit-code 2` after discovering the first Python exception could otherwise leave process exit 0. No failed probe is counted as an accepted result.

## Next minimum actions

1. Acquire a **complete real multiroom floorplan with scale and source rights**, extract global walls, doors and topology, and rerun this CPU contract. The current affine calibration test is only an interface unit test.
2. Improve or document 16-view coverage so all 30 native chunks have an accepted camera; do not reinterpret closest-camera fallback as valid coverage.
3. On a separately approved NVIDIA host, run official GenRecon baseline on this same A/B input, then fixed-seed CFG ablations. Verify generated mesh against all four door rays and the reference global geometry. See `gpu_experiments.md`.
