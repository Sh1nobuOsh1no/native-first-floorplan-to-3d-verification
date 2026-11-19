# Floorplan → one globally consistent building scene

**Research target:** complete multiroom floorplan → global metric JSON → one Blender building mesh and shared RGB/Depth/Object-ID/Camera world → GenRecon 3D prior → full building 3D world. Learned reconstruction and independent raster-to-metric interpretation remain **unverified**.

## Real drawing CPU batch — 2026-11-19

Five different real CubiCasa5K floorplan images were run through an OpenCV whole-image candidate parser and a bounded deterministic revision stage. **Parser-only: 0/5 reached a trustworthy metric scene**; the baseline finds no verified doors or scale. Against separate official human SVG labels, room-box matches at IoU ≥0.5 were 17/36 and door recall 0/42. Six evidence-checked trace merges occurred; no language/vision Agent model was invoked.

An explicitly **annotation-assisted vector control** used the official human SVG for sample `4702`. Dimension labels supplied the 0.01 m/pixel scale. It produced one six-space global `metric_scene_v1`, a Blender CPU unified GLB, 13 aligned RGB/Depth/Object-ID views and a successful unmodified GenRecon `Sage_gt` CPU Reader run. Five interior doors have clear physical rays between paired cameras; structural depth/ID reprojection passed **4/5**, and **2/20** native chunks used fallback. The 2.7 m height is an assumption. Four other drawings were rejected for nonrectangular rooms. **This does not prove autonomous image parsing or GenRecon network generation.** Full results and logs are in [validation](docs/validation.md) and `evidence/cpu/real_floorplans/`.

## CPU status — 2026-11-19

Two **SYNTHETIC** layouts were run in Blender CPU with the unmodified GenRecon `Sage_gt` Chunker and ImageSelecter. The 12 × 9 × 2.7 m four-room/corridor building has four physical doors. Automatic room/chunk camera planning raised its view count from 16 to 20. Both A (structure) and B (structure plus gray furniture) deliver **30/30 native chunks with an accepted selected camera and 0 fallback**. All four doors have selected cameras on both sides and Blender B reprojects the same object across each door with 99.25–99.65% depth/ID agreement. A second 6 × 9 × 2.7 m layout at world origin (−4, 10), with two rooms and two doors, delivers **20/20 chunks and 0 fallback** using 13 views. **34/34 CPU tests passed**, including the preserved synthetic regressions. See [validation](docs/validation.md).

These results establish CPU geometry, rendering, camera selection and native input parsing only. The Blender images are whitebox renders, not photographs; GenRecon network forward, generated geometry and preservation of door connectivity have not been tested. `Sage_gt` receives outer bounds and images, not interior walls and doors as hard constraints.

## Reproduce

Use Python with `requirements/cpu.txt`, Blender 5.3, and a clean official GenRecon checkout at `eaf1468118d20469d17079a4a19737297d2ef87b`:

```bash
python -m pip install -r requirements/cpu.txt
python -m src.runner.run_cpu --scene fixtures/multiroom/synthetic_building.json --repo /absolute/path/to/GenRecon --output-root evidence/cpu --n-views 32
python -m src.cameras.check_cross_door --scene evidence/cpu/planned_scene.json --render evidence/cpu/render_B --out evidence/cpu/cross_door_check.json
python -m src.runner.run_cpu --scene fixtures/multiroom/synthetic_offset_2r1c.json --repo /absolute/path/to/GenRecon --output-root evidence/cpu/alternate --n-views 32
python -m src.cameras.check_cross_door --scene evidence/cpu/alternate/planned_scene.json --render evidence/cpu/alternate/render_B --out evidence/cpu/alternate/cross_door_check.json
python -m src.runner.pack_evidence --root evidence/cpu
python -m src.runner.pack_evidence --root evidence/cpu/alternate
python -m unittest discover -s tests -p 'test_*.py' -v
```

Run the real-image baseline; add `--annotation-sidecars` only for the separately labelled CubiCasa vector control:

```bash
python -m src.runner.batch_floorplans --input-dir fixtures/real_floorplans --output-dir outputs/buildings --mode cpu --repo /absolute/path/to/GenRecon
python -m src.runner.batch_floorplans --input-dir fixtures/real_floorplans --output-dir outputs/annotated_control --mode cpu --repo /absolute/path/to/GenRecon --annotation-sidecars --resume
python -m src.cameras.check_structural_cross_door --scene outputs/annotated_control/4702_F1_scaled_6a267a93/planned_scene.json --render outputs/annotated_control/4702_F1_scaled_6a267a93/render_A --out outputs/annotated_control/4702_F1_scaled_6a267a93/cross_door_structure.json
```

The last command currently exits 2 because one of five wall reprojections fails. The 5/5 unobstructed door rays are reported separately. The original source images and author SVG annotations are retained with CC BY-NC 4.0 attribution under `fixtures/real_floorplans/`.

`--scene` accepts a validated `metric_scene_v1` building JSON; the two fixtures are regression examples, not special cases in the runner. The runner logs argv, output and exit code for every stage. The compact public log archive is `evidence/cpu/execution_2026-11-19.jsonl.gz`; full local EXRs, `Sage_gt` copies and per-frame NPYs regenerate from the commands. The original GenRecon checkout and pretrained weights stay outside this repository.

## Repository map

- `src/scene_graph`, `src/cameras`, `src/blender`, `src/genrecon`, `src/runner`: one global scene compiler, camera planner/checks, CPU renderer, external native adapter, runner.
- `fixtures/multiroom/`: two synthetic full-building schemas, including nonzero x/y world origin.
- `tests/`: 34 CPU unit and evidence-backed integration tests.
- `evidence/cpu/`: plans, layouts, aligned compact passes, cross-door RGB collage, native Reader reports and command records.
- `docs/`: [architecture](docs/architecture.md), [interfaces](docs/interfaces.md), [validation](docs/validation.md), [future GPU experiments](docs/gpu_experiments.md).
