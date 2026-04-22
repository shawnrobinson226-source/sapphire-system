# Sapphire System

Sapphire is the host/runtime layer for executing and presenting AXIS-aligned workflows.

## What Sapphire Is

Sapphire is:
- host runtime
- adapter layer
- execution surface
- orchestration shell
- plugin environment and interaction layer

## What Sapphire Does

Sapphire:
- accepts user/system input into controlled execution flow
- routes AXIS-bound requests through Sapphire boundary/adapter layers
- presents AXIS responses in structured, readable interaction surfaces
- handles orchestration, interaction, and execution flow around AXIS outputs

## What Sapphire Does NOT Own

Sapphire does not own:
- source-of-truth decision logic
- taxonomy definitions
- classification authority
- scoring authority
- continuity authority
- outcome authority

## How Sapphire Relates To AXIS

AXIS remains the deterministic source-of-truth engine.

Sapphire calls AXIS; Sapphire does not redefine AXIS.

AXIS owns classification, scoring, continuity, outcomes, and contracts. Sapphire acts as host/runtime and execution surface around those AXIS outputs.

## High-Level Architecture

AXIS:
- source-of-truth decisions and enforcement

Sapphire:
- runtime host
- adapter boundary layer
- API/plugin execution surface
- UI/orchestration shell

## Repository Shape (High Level)

- `core/`: runtime services, routing, integration boundaries, security hooks
- `plugins/`: plugin capability surface
- `functions/`: callable function/tool implementations
- `interfaces/`: UI/web integration assets
- `tests/` and `core/tests/`: validation and boundary enforcement tests

## Current Scope / Stopping Point

- Sapphire execution surface is implemented as an orchestration and rendering layer.
- AXIS remains external source-of-truth authority.
- This repository does not implement AXIS decision authority internally.

## Manual Public Metadata Actions Still Required

- GitHub About description suggestion:
  `Sapphire — host/runtime and execution surface for AXIS-aligned workflows.`
- GitHub Website field:
  Use the correct Sapphire public link only if one exists.
  If no public Sapphire link exists, leave it unset until one is available.

## Local Run (Optional)

```bash
conda activate sapphire
python main.py
# Runs at https://localhost:8073
```
