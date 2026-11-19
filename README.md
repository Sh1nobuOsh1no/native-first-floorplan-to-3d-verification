# Floorplan → one globally consistent building scene

**Research target:** complete multiroom floorplan → global metric JSON → one Blender building mesh and shared RGB/Depth/Object-ID/Camera world → GenRecon 3D prior → full building 3D world. The final learned reconstruction and a real drawing ingestion remain **unverified**.

## CPU status — 2026-11-19

Two **SYNTHETIC** layouts were run in Blender CPU with the unmodified GenRecon `Sage_gt` Chunker and ImageSelecter. The 12 × 9 × 2.7 m four-room/corridor building has four physical doors. Automatic room/chunk camera planning raised its view count from 16 to 20. Both A (structure) and B (structure plus gray furniture) deliver **30/30 native chunks with an accepted selected camera and 0 fallback**. All four doors have selected cameras on both sides and Blender B reprojects the same object across each door with 99.25–99.65% depth/ID agreement. A second 6 × 9 × 2.7 m layout at world origin (−4, 10), with two rooms and two doors, delivers **20/20 chunks and 0 fallback** using 13 views. **29/29 CPU tests passed.** See [validation](docs/validation.md).

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

`--scene` accepts a validated `metric_scene_v1` building JSON; the two fixtures are regression examples, not special cases in the runner. The runner logs argv, output and exit code for every stage. The compact public log archive is `evidence/cpu/execution_2026-11-19.jsonl.gz`; full local EXRs, `Sage_gt` copies and per-frame NPYs regenerate from the commands. The original GenRecon checkout and pretrained weights stay outside this repository.

## Repository map

- `src/scene_graph`, `src/cameras`, `src/blender`, `src/genrecon`, `src/runner`: one global scene compiler, camera planner/checks, CPU renderer, external native adapter, runner.
- `fixtures/multiroom/`: two synthetic full-building schemas, including nonzero x/y world origin.
- `tests/`: 29 CPU unit and evidence-backed integration tests.
- `evidence/cpu/`: plans, layouts, aligned compact passes, cross-door RGB collage, native Reader reports and command records.
- `docs/`: [architecture](docs/architecture.md), [interfaces](docs/interfaces.md), [validation](docs/validation.md), [future GPU experiments](docs/gpu_experiments.md).
