# Floorplan to one consistent 3D building world

**Target:** complete multiroom floorplan → global metric scene JSON → one Blender building mesh and shared camera world → GenRecon 3D prior → building level 3D world.

**Current status (2026-11-18):** a **SYNTHETIC** 12 × 9 × 2.7 m building with four rooms, one corridor and four doors passed the CPU geometry/render/interface checks. Two variants, empty shell A and shell plus four gray furniture blocks B, each rendered 16 RGB/depth/object ID frames from identical global camera poses. The unmodified GenRecon `Sage_gt` CPU reader accepted both, but **4 of 30 chunks use closest-camera fallback**. GenRecon network inference and structural preservation **have not run**. No real full floorplan was validated. No GPU was used.

The hypothesis that GenRecon can turn geometrically consistent whitebox views into realistic geometry and PBR material while preserving connected rooms is **unproven**. Its `Sage_gt` layout reads outer width/length and a fixed 2.7 m height, not internal walls or doors as hard constraints.

## Reproduce CPU work

Requirements: Blender 5.3, Python with `requirements/cpu.txt`, and a clean checkout of official GenRecon fixed at `eaf1468118d20469d17079a4a19737297d2ef87b`. The paper repository is read only. No model checkpoint is needed for the CPU tests.

```bash
python -m pip install -r requirements/cpu.txt
python -m src.runner.run_cpu --repo /absolute/path/to/GenRecon --blender /absolute/path/to/blender
```

The runner logs each command, stdout, stderr, exit code and timing under `evidence/cpu/logs/`. The checked in evidence retains all 16 RGB frames per variant plus compressed aligned depth/object-ID arrays, camera JSON, mesh and native-reader reports. `python -m unittest discover -s tests` runs directly against this evidence. The complete multilayer EXRs and full native input directories are regenerated locally by the runner.

## Files

- `fixtures/multiroom/synthetic_building.json`: one global metric coordinate frame and explicit provenance.
- `src/`: one scene compiler, one Blender CPU renderer, camera checks, native input adapter, CFG preflight, runner.
- `tests/`: topology, invalid input, aligned passes, cross-door reprojection and native reader assertions.
- `docs/architecture.md`: dataflow and scope.
- `docs/interfaces.md`: exact JSON/camera/`Sage_gt` contract.
- `docs/validation.md`: executed results and limitations.
- `docs/gpu_experiments.md`: future native inference and controlled CFG ablation; **not executed**.
- `evidence/cpu/`: selected images, layout, command records, measured JSON and separate official SAGE single-room evidence.

Official GenRecon weights and source SAGE data are retained outside Git and are not distributed here. Their validation receipts remain in the local protected workspace. Do not treat this synthetic building evidence as real drawing ingestion or generated 3D output.
