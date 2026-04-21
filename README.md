# Sapphire System

Sapphire is the runtime host and integration surface around AXIS.

## What Sapphire Is

Sapphire is:
- Host/runtime
- Adapter and execution layer
- Plugin/tool surface
- Orchestration shell for routes, hooks, and UI-facing flows

## What Sapphire Is Not

Sapphire is not:
- The source-of-truth decision kernel
- The taxonomy owner
- The continuity/scoring authority
- A replacement for AXIS policy or enforcement logic

## AXIS Relationship

AXIS is the source-of-truth deterministic engine.

Sapphire calls AXIS through controlled integration boundaries and presents AXIS outputs to users and tools. Sapphire may format or route AXIS outputs, but does not redefine their meaning.

## High-Level Architecture

AXIS:
- Source-of-truth decisions and enforcement

Sapphire:
- Runtime host
- Adapter boundary layer
- API/plugin execution surface
- UI/orchestration shell

## Repository Shape (High Level)

- `core/`: runtime services, routing, integration boundaries, security hooks
- `plugins/`: plugin capability surface
- `functions/`: callable function/tool implementations
- `interfaces/`: UI/web integration assets
- `tests/` and `core/tests/`: validation and boundary enforcement tests

## Local Run

```bash
conda activate sapphire
python main.py
# Runs at https://localhost:8073
```
