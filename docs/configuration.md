# Configuration

Runtime behaviour is driven by YAML/JSON merged on top of defaults in `ppe_monitoring/config.py`. Entry point: `main.py --config <path>`.

## Top-level groups

| Group | Purpose |
| --- | --- |
| `pipeline` | Source (`file` path, camera index, or `rtsp://…`), resize, sampling FPS, `motion_gated` vs `every_sample`, `max_frames`, preview, RTSP reconnect. |
| `motion` | Motion detector thresholds and hold time for inference gating. |
| `model` | Weights paths, confidence thresholds, image sizes, device, optional person fallback, optional binary hardhat backend, class aliases. |
| `roi` | Manual or auto ROI, person-centre rules, optional drawing. |
| `filters` | Person / head–hardhat geometry and confirmation gates. |
| `event_logic` | Temporal confirmation, revocation, cooldown for `no_hardhat` / `no_vest`. |
| `output` | Annotated video path, `events.csv`, `events.jsonl`, `frame_metrics.csv`, `runtime_profile.json`. |

## Presets shipped in `configs/`

| File | Role |
| --- | --- |
| `configs/baseline.yaml` | Frame-first baseline: no motion gate, no ROI, minimal temporal smoothing (isolates pipeline overhead vs proposed). |
| `configs/proposed.yaml` | Video-first default: sampling + motion gating + ROI + temporal logic aligned with industrial use. |
| `configs/ablation_proposed_without_*.yaml` | Single-factor removals for ablation studies (`motion`, `roi`, `temporal`, `person` fallback). |
| `configs/experiments_extended/*.yaml` | Additional sweeps and demo presets. |

## Examples

- `examples/sample_config.yaml` — copy of the annotated `config.example.yaml` at repository root.
- `config.example.yaml` — same content, kept at root for backward compatibility with existing docs.

For reproducible latency comparisons, pin `model.auto_backend_resolve`, `model.backend_priority`, and `model.device` consistently across runs (`docs/e2_evaluation_protocol.md`).
