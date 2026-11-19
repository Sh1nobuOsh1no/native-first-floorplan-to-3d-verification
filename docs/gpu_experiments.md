# Future native GenRecon GPU experiment — NOT RUN

The real CubiCasa5K `4702` CPU control added this round uses **human SVG annotations**, 13 Blender views and 2/20 native chunk fallbacks. It is not yet an all-chunk-covered GPU input, and the raster parser has not produced a trustworthy metric building unaided. Any future real-drawing GPU run must keep this provenance and failure separate from the synthetic baseline below. No GPU work was performed in this round.

This is an execution plan, **not** a GPU result. It uses the same synthetic A/B input and 20 Blender poses. A real whole-floorplan source remains a separate prerequisite for the final research claim. The CPU Reader has now measured 30/30 chunks with 0 fallback at cap 32, selecting all 20 source views. At cap 8 it measured 11 fallback chunks. Preserve cap 32 for the first native attempt and verify the saved selected-image list. The training configs reference up to 16 conditioning views; GPU behavior with 20 selected views is untested. Do not train, edit upstream GenRecon or weights, or interpret CPU Reader success as output consistency.

## Resources and fixed inputs

- **Estimated, unmeasured for this 30-chunk building:** one NVIDIA Linux GPU with **80 GB VRAM recommended for first smoke**, ≥64 GB host RAM and ≥100 GB free local disk. An 80 GB card is a conservative planning target, **not a verified minimum**; measure peak GPU memory and reduce scope only with a documented new run if OOM. Official GenRecon setup expects CUDA 12.x, Python 3.10, PyTorch 2.6 CUDA build, Flash-Attention and its CUDA extensions. Use the pinned official `setup.sh` in an isolated environment; no source edits.
- Locally preserved checkpoints: `sparse_structure.pt` 2,862,971,400 bytes, `shape_slat.pt` 5,410,532,174 bytes, `texture_slat.pt` 5,410,728,782 bytes. Prior verified SHA256 respectively `e18c1caddb2357dbf5839f0f7e1569c50d855fcb47e0871483d99c91a14e2bb7`, `d9e13be151a213bf67565d2a17341fe97328e455814fb2328a59366344e122fb`, `28f99217a4fbcd04f36a5f576905975ae8b874ad63548d6ab8afdb96cf03ed47`. Recheck after transfer. Files stay outside Git.
- Source checkout SHA must be `eaf1468118d20469d17079a4a19737297d2ef87b` and clean. Official code's `--pipeline_config` selects external JSON. `--mode Sage_gt`, `--path`, `--output_path`, three checkpoint flags, `--num_imgs_per_scene`, `--seed` and `--save_imgs` are native CLI parameters.
- First run the **official SAGE single-room sample** once as an independent model/environment sanity check if a fresh GPU stack has not yet been proven. Keep its result separate from this building study.

## Exact proposed commands on the future GPU host

Set paths explicitly and copy the full local `evidence/cpu/sage_gt_A` and `sage_gt_B` input directories, including all 20 PNGs, `transforms.json` and sibling `rooms_raw`, to the GPU host. Alternatively regenerate these on the host with the documented CPU runner. The compact GitHub evidence alone is not a full model input. `Sage_gt` uses original global poses shifted by the adapter only for nonzero-origin scenes; the main 12 × 9 m scene has zero shift.

```bash
set -euo pipefail
export PROJECT=/absolute/path/to/this/repo
export GENRECON=/absolute/path/to/clean/GenRecon
export INPUT_ROOT=/absolute/path/to/full/cpu/evidence
export WEIGHTS=/absolute/path/to/verified/GenRecon/weights
export OUT=/absolute/path/to/gpu_outputs
mkdir -p "$OUT"
test "$(git -C "$GENRECON" rev-parse HEAD)" = eaf1468118d20469d17079a4a19737297d2ef87b
test -z "$(git -C "$GENRECON" status --porcelain)"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
python -c 'import torch; assert torch.cuda.is_available(); print(torch.__version__, torch.version.cuda)'
sha256sum "$WEIGHTS/sparse_structure.pt" "$WEIGHTS/shape_slat.pt" "$WEIGHTS/texture_slat.pt"
test -f "$INPUT_ROOT/sage_gt_B/renders_room/synthetic_multiroom_4r1c/transforms.json"
python - "$INPUT_ROOT/sage_gt_B/renders_room/synthetic_multiroom_4r1c/transforms.json" <<'PY2'
import json,sys
f=json.load(open(sys.argv[1]))["frames"]
assert len(f)==20, len(f)
print("source_views",len(f))
PY2
test -f "$INPUT_ROOT/sage_gt_B/rooms_raw/synthetic_multiroom_4r1c/layout_synthetic_multiroom_4r1c.json"
```

Run baseline A and B, then B's three ablations. Every run uses `seed=42`, the same 20 source camera matrices and unchanged weights. Execute the following block in the **official** checkout; capture its full stdout/stderr, process exit, peak GPU memory (`nvidia-smi` sampler) and wall time for each run.

```bash
cd "$GENRECON"
for spec in A:official_baseline B:official_baseline B:geometry_cfg_3 B:no_extra_cfg B:texture_cfg_0_5; do
  variant=${spec%%:*}; cfg=${spec##*:}
  input="$INPUT_ROOT/sage_gt_${variant}/renders_room/synthetic_multiroom_4r1c"
  run="$OUT/${variant}_${cfg}"
  mkdir -p "$run"
  python reconstruct_scene.py \
    --mode Sage_gt --path "$input" --output_path "$run" \
    --ss_ckpt "$WEIGHTS/sparse_structure.pt" \
    --shape_ckpt "$WEIGHTS/shape_slat.pt" \
    --tex_ckpt "$WEIGHTS/texture_slat.pt" \
    --pipeline 512 --pipeline_config "$PROJECT/configs/genrecon_cfg/${cfg}.json" \
    --num_imgs_per_scene 32 --seed 42 --save_imgs \
    >"$run/reconstruct.stdout.log" 2>"$run/reconstruct.stderr.log"
  printf '%s\n' "$?" >"$run/reconstruct.exit_code"
  test -s "$run/to_glb_inputs.pt" && test -s "$run/chunk_inputs.pt"
  python chunked_to_glb.py --inputs "$run/to_glb_inputs.pt" \
    --chunk_inputs "$run/chunk_inputs.pt" --output_dir "$run" \
    >"$run/glb.stdout.log" 2>"$run/glb.stderr.log"
  printf '%s\n' "$?" >"$run/glb.exit_code"
  test -s "$run/scene.glb"
  python - "$run/scene.glb" <<'PY'
import sys, trimesh
mesh = trimesh.load(sys.argv[1], force='scene')
assert len(mesh.geometry) and all(len(g.faces) > 0 for g in mesh.geometry.values())
print('geometry_count', len(mesh.geometry), 'bounds', mesh.bounds.tolist())
PY
done
```

The block above uses `set -e`, so a failed native command stops before the following exit-code write. Wrap each command with the repository logger or explicitly capture `$?` without `set -e` when executing on GPU; preserve both raw logs and nonzero exit records. Before interpreting results, inspect the emitted selected images and confirm 20 distinct main-scene source views and zero fallback messages. For a production execution, wrap each command with the repository's `log_command.py` to capture nonzero exits in JSON as done in CPU validation. No script in this repository invokes a GPU experiment during this round.

## Acceptance gates and comparison

1. **Native execution:** each requested run must exit 0, produce nonempty `to_glb_inputs.pt`, `chunk_inputs.pt`, `mesh.ply` where emitted, and parseable `scene.glb`; preserve exact SHA256 and logs. A failed or OOM run is **blocked**, not success.
2. **Structural fidelity:** transform generated mesh into the fixture's RH_Z_UP metre frame, check global bounds against 12 × 9 × 2.7 m; inspect all four door openings for traversable 0.8 m width and an unobstructed 1.3 m high ray; verify surrounding walls remain closed. Check corridor-to-room and in-room views of the same four regions against fixed reference cameras. Record per-door status, broken connections and wall displacement. These checks are **not measured yet** and cannot be inferred from GLB existence.
3. **Appearance and CFG:** compare A/B baseline and B ablations with identical source frames, camera poses, seed, pipeline and weights. Evaluate visual quality and PBR plausibility separately from geometry and connectivity. No claim that a lower CFG improves realism is allowed until the five native outputs are scored.
4. **Final research gate:** only a complete real floorplan with scale/source evidence, followed by passing generated-mesh topology and cross-room checks, can support the target building-level claim. This synthetic experiment is an interface and risk discovery stage.
