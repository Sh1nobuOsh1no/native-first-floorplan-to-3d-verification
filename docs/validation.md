# CPU validation — executed 2026-11-19

## Real floorplan batch: executed results

Source: five distinct CubiCasa5K `F1_scaled.png` drawings (`2055`, `4702`, `4790`, `8741`, `9557`) from the [official dataset](https://zenodo.org/records/2613548), under [CC BY-NC 4.0](https://github.com/CubiCasa/CubiCasa5k/blob/master/LICENSE). Images and official `model.svg` **human annotations** are in `fixtures/real_floorplans/` with source hashes in each case manifest. The original 5.4 GB archive was accessed by HTTP range; only these samples were extracted. Different room counts and layouts were observed. No dataset label was used as raster-parser input.

The raster baseline is `opencv_morphology_cpu_v1` implemented in `src/floorplan/parse_cpu.py`; it takes whole PNG/JPG or one-page PDF, extracts pixel-space axis-aligned dark traces and enclosed region candidates, and leaves doors, windows and scale unconfirmed. Its deterministic bounded revision stage made 6 source-pixel-supported trace merges across the five drawings. **No LLM/VLM Agent model ran**, and the revisions did not infer missing rooms or doors. All five parser-only cases remain `NEEDS_REVIEW`: **0/5 autonomous metric scenes, 0/5 autonomous GLBs**.

Model inventory: the local untouched [Raster2Seq official repository](https://github.com/Raster2Seq/Raster2Seq) is at `d938188027cd4f2bed9f95c883e5cc6d80b507f5`, with official `predict.py` and `tools/predict_cc5k.sh`. No Raster2Seq checkpoint exists locally; the official CubiCasa5K checkpoint is [1.45 GB on Hugging Face](https://huggingface.co/haopt/Raster2Seq/tree/main/cubicasa5k). Its `predict.py` defaults to CUDA and calls `torch.cuda.Event`/`torch.cuda.synchronize`. The unmodified `--help` import preflight actually exited 1 on missing `tqdm` in the current environment; see `upstream_logs/`. No Raster2Seq model inference was run, and none is counted in the accuracy table. The older CubiCasa baseline targets Python 3.6/PyTorch 1.0/CUDA and was not installed into this Mac venv.

The official human SVG reference was used after prediction for an independent count/box check (IoU ≥0.5):

| Drawing | Room candidates | Reference rooms | Matched | Wall traces | Annotated doors | Annotation-assisted control |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 2055 | 2 | 10 | 1 | 224 | 10 | `UNSUPPORTED_GEOMETRY`: nonrectangular kitchen |
| 4702 | 6 | 6 | 4 | 45 | 7 | `PARTIAL_ANNOTATION_ASSISTED_CROSS_DOOR_FAILURE` |
| 4790 | 12 | 8 | 5 | 202 | 9 | `UNSUPPORTED_GEOMETRY`: nonrectangular bath |
| 8741 | 15 | 9 | 6 | 120 | 10 | `UNSUPPORTED_GEOMETRY`: nonrectangular living room |
| 9557 | 3 | 3 | 1 | 151 | 6 | `UNSUPPORTED_GEOMETRY`: nonrectangular bedroom |

Totals: 17/38 room candidates and 17/36 reference rooms matched, for a **0.447 room-box precision and 0.472 recall at IoU 0.5**. The baseline proposed **0/42 doors**, so door recall is 0. The raw wall trace counts include furniture/text/dimension strokes; `reference_evaluation.json` gives a pixel-overlap proxy, not wall instance F1. We did not measure a valid room/door topology error reduction because the raster baseline never established a topology. The same five images were also run in parser-only batch mode; its summary is preserved separately. These are limited five-sample results, not dataset-wide accuracy.

### Real drawing `4702`: labelled vector control

The separate adapter used the **human `model.svg` annotations** plus printed metre room dimensions. Their six room width/height ratios agreed within 3%, giving approximately **0.01 m/px**. This is a legitimate source-derived scale for the control, but the SVG geometry is manual annotation, **not a Raster2Seq or OpenCV prediction**. The 2.7 m ceiling height was assumed to satisfy `Sage_gt`; the drawing did not establish it. The adapter rejected nonrectangular rooms and ambiguous openings rather than changing geometry to fit `metric_scene_v1`.

Actual outputs: six indoor spaces (including entry/corridor), 10 wall segments, five physically linked interior doors, two exterior doors, four windows, and one global 9.1794 × 7.88164 m scene with L-shaped `SPACE_UNION` footprint. The annotated outdoor balcony and two balcony-edge walls were excluded; this is a partial indoor-building control, not a full-fidelity rendering of every exterior feature. Blender 5.3 Cycles CPU exported `building_unified.glb` (44 KB) and 13 aligned 128×128 RGB/metric Depth/Object ID views, with K and original global c2w per view. The source and annotation SHA256 were checked on reload; the GenRecon checkout remained clean at `eaf1468118d20469d17079a4a19737297d2ef87b`.

All five interior doors had a clear wall-free 1.55 m-high ray between the paired door-side cameras. In actual Blender passes, the same structural wall component passed 0.1 m depth plus Object ID reprojection for **4/5** doors; the fifth (`opening_009_Door`) matched **0.668** of 794 reprojected pixels, below the fixed 0.8 threshold. The cross-door checker exited **2**, and its failure is retained. The whitebox images and per-door report are `cross_door_structure.{png,json}`. No furniture was inferred from this plan.

The unmodified official `Sage_gt` CPU Reader accepted the directory and selected all **13** scene images at cap 32. It produced **20 chunks**, of which **18/20** had an accepted selected camera and chunks **0 and 5 fell back**. The missing chunks lie in the L-shaped building's rectangular outer bounds but outside reliable interior observation. Reader success therefore does not imply full coverage or GenRecon generated-scene consistency. Interior walls, doors, Depth and Object IDs are not hard constraints in the native `Sage_gt` network input.

### Commands and files

```bash
python -m src.runner.batch_floorplans --input-dir fixtures/real_floorplans --output-dir outputs/batch_parser_only --mode cpu --repo /absolute/path/to/GenRecon
python -m src.runner.batch_floorplans --input-dir fixtures/real_floorplans --output-dir outputs/batch_real --mode cpu --repo /absolute/path/to/GenRecon --annotation-sidecars --size 128 --samples 4
python -m src.runner.batch_floorplans --input-dir fixtures/real_floorplans --output-dir outputs/batch_real --mode cpu --repo /absolute/path/to/GenRecon --annotation-sidecars --resume --size 128 --samples 4
python -m src.cameras.check_structural_cross_door --scene outputs/batch_real/4702_F1_scaled_6a267a93/planned_scene.json --render outputs/batch_real/4702_F1_scaled_6a267a93/render_A --out outputs/batch_real/4702_F1_scaled_6a267a93/cross_door_structure.json
python -m unittest discover -s tests -p 'test_*.py' -v
```

The two batch commands and 34-test run exited 0; the cross-door command exited 2 as described. `evidence/cpu/real_floorplans/` contains per-drawing raw predictions, audited revision histories, independent reference checks, error logs, the successful metric JSON/GLB/13-view outputs and native reports. Full local raw EXR passes and `.blend` are retained in `outputs/batch_real/` and omitted from Git evidence; the committed RGB, depth/ID arrays and camera files support reprojection reruns. `batch_resume.stdout.log` and the per-step JSON records show which successful stages were skipped on resume.

## Prior synthetic building regression (unchanged)

**Scope of this earlier baseline:** both inputs are **SYNTHETIC**. Blender 5.3/Cycles ran on CPU at 256×256, eight samples per frame. GenRecon official source remained clean at `eaf1468118d20469d17079a4a19737297d2ef87b`. No NVIDIA GPU, model checkpoint forward, training or learned 3D output ran.

## Results

| Check | Main, 12×9×2.7 m, 4 rooms + corridor | Alternate, 6×9×2.7 m, origin (−4,10), 2 rooms + corridor |
| --- | --- | --- |
| Physical doors | 4, topology connected | 2, topology connected |
| Planned A/B cameras | 20 / 20, same K and global c2w | 13 / 13, same K and global c2w |
| Real Blender RGB/Depth/Object ID | 20 aligned frames per variant | 13 aligned frames per variant |
| Official `Sage_gt` CPU chunks | 30 / 30 have accepted **selected** cameras | 20 / 20 have accepted **selected** cameras |
| Closest-camera fallback | 0 in A, 0 in B | 0 in A, 0 in B |
| Native selected scene images with cap 32 | 20 in A, 20 in B | 13 in A, 13 in B |
| Cross-door same-object depth/ID reprojection | 4 / 4 doors pass | 2 / 2 doors pass |
| Provenance | SYNTHETIC | SYNTHETIC |

All **29 CPU unit and integration tests passed**, exit code 0. The tests check invalid doors, closed walls, disconnected spaces, metric units, nonzero x/y origin, real-source hash rejection, invalid camera matrices, A/B K/c2w alignment, aligned real rendered passes, both layouts' native Reader, and all door pairs. Logs and exact commands are in `evidence/cpu/execution_2026-11-19.jsonl.gz` and `command_index_2026-11-19.csv`; the final test log is in that archive. Local raw EXRs, NPY arrays and full native input copies are retained outside the compact Git evidence and regenerate with the README commands.
The staged public snapshot was materialized with `git checkout-index` into a separate directory and independently reran **29/29 tests with exit 0**, using only committed compact evidence. Its log and exit record are `staged_snapshot_test.log` and `staged_snapshot_test.json`.

An additional **planner-only CPU precheck** removed every source camera from the alternate JSON. Topology-derived placement produced four door-side cameras and a nine-camera plan with 20/20 chunks covered by the official acceptance rule. That no-camera variant was **not rendered or passed through the native image Reader**; see `alternate/no_camera_plan.json`.

## Why chunks 3, 5, 17 and 27 originally failed

The original 16 cameras all had horizontal FOV 78°. The official rule projects the eight corners and centre of each 2.85 m chunk through each view, clips projected coordinates to `[0,1]`, and requires resulting image area ≥ **0.4**. For these four chunks, **every original camera was below 0.4**; the best original values are below. Positions are global metres in the main layout.

| Chunk | Centre (x, y, z) m | Best original camera | Best clipped projected area | Cause |
| --- | --- | --- | ---: | --- |
| 3 | (7.069, 0.581, 1.425) | `c06_office_to_desk` | 0.368 | 78° frustum and oblique/offset view leave insufficient projected area near south office edge |
| 5 | (11.344, 0.581, 1.425) | `c06_office_to_desk` | 0.381 | far southeast edge insufficient in the existing office and corridor views |
| 17 | (11.344, 4.500, 1.425) | `c05_corridor_to_office` | 0.211 | east corridor end lies outside strong coverage of door-directed views |
| 27 | (7.069, 8.419, 1.425) | `c13_kitchen_to_counter` | 0.362 | northeast-side chunk coverage is insufficient from the kitchen views |

The per-camera eye, target, FOV, front-point count, area and rejection reason are preserved in `evidence/cpu/camera_plan.json`. The planner generated candidates from room bounds and uncovered chunk centres, evaluated the original official acceptance function, and required a clear ray through the building mesh to each newly covered chunk centre. A first 19-camera plan reached native 30/30 but produced a wall-only view; an integration test rejected it. The corrected plan used 20 cameras: original 16 plus 4 selected automatic candidates. A/B were re-rendered from this final plan and the native Reader measured **30/30, 0 fallback**.

`num_imgs_per_scene` is a real selection limit. With the final 20 source images and the native CLI default cap 32, all 20 enter `scene_images_512`, and every chunk has an accepted view in that **selected** set. A measured control at cap **8** selected only eight views and produced **11 fallback chunks**: `[0,2,5,6,12,14,15,18,24,26,27]`. Adding source photos while keeping an inadequate cap would not solve conditioning coverage.

## Four-door physical cross-view check

In the final Blender B output, cameras on opposite sides of each door see the same unique furniture ID. Reprojecting the corridor-side object's rendered metric depth into the room-side view, requiring the same Object ID and depth difference <0.1 m, gave:

| Door | Cameras (corridor → room) | Same object | Reprojected pixels | Depth/ID match |
| --- | --- | --- | ---: | ---: |
| bedroom | `c00_corridor_to_bed` → `c01_bed_to_bed` | `bed_01` | 3134 | 99.65% |
| office | `auto_05_corridor_2` → `c06_office_to_desk` | `desk_01` | 5905 | 99.64% |
| living | `c08_corridor_to_living` → `c09_living_to_sofa` | `sofa_01` | 3876 | 99.25% |
| kitchen | `c12_corridor_to_kitchen` → `c13_kitchen_to_counter` | `counter_01` | 3970 | 99.45% |

The alternate layout's two door pairs also pass at 99.56% and 99.25%. The full per-door camera IDs, pixel counts and ratios are in `cross_door_check.json` for each layout; `cross_door_check.png` is the actual rendered RGB collage. The main bedroom jamb precedes the bed in rendered depth. These are **Blender whitebox** consistency results, not GenRecon output consistency.

## Constraints and failures

- `Sage_gt` fixes floor/ceiling at 0/2.7 m. `prepare_sage_gt.py` now rejects another height; a unit/integration test covers this. Nonzero global x/y is translated only in the native adapter, with the inverse mapping recorded. `metric_scene_v1` rejects a nonzero floor z.
- The official native layout accepts outer width/length only. Internal wall geometry, door connectivity, Blender Depth and Object ID are not hard constraints for GenRecon. Camera frustum acceptance does not prove a useful image; the corrected planner and rendered-pass checks address the specific wall-only candidate found here.
- `SOURCE_DRAWING` requires a present source file with matching SHA256, scale evidence, explicit parsed status and non-synthetic per-element evidence. The new real-drawing control uses official human SVG geometry; the raster baseline still cannot autonomously establish a valid metric scene.
- The full-scene pretrained model has **not** been run with 20 views. Training configs mention up to 16 conditioning views; whether 20 views with the official full-scene inference path meet memory and output-quality requirements remains a GPU-stage risk.
- The command archive includes unsuccessful development attempts, including a first camera plan rejected for a wall-only view, Blender 5.3 compositor output-path probes and stale-pass packing attempts. Their nonzero exits are retained, not counted as passes. The final pipeline and 29-test run exited 0.

## Evidence index

`evidence/cpu/camera_plan.json`, `planned_scene.json`, `layout_camera_map.png`, `render_A/`, `render_B/`, `native_A_report.json`, `native_B_report.json`, `native_B_cap8_report.json`, `cross_door_check.{json,png}`, and the corresponding `alternate/` files are the primary outputs. `validation_summary_2026-11-19.json` summarizes measured values. The separate `official_sage/` evidence is a prior **single-room native input check** and is not counted as a multiroom result.
