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

AXIS owns scoring, continuity, outcomes, and contracts. Sapphire acts as host/runtime and execution surface around those AXIS outputs.

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

## Current State

Status as of the S4.2 merge (c0319be).

Sapphire displays. DES decides. AXIS governs. The Operator authorizes. Sapphire
runs the interface and orchestration, and it never substitutes its own
decision logic for DES or AXIS.

Three independent authentication secrets live in the config directory.
`secret_key` is the login password verifier only. `session_secret` signs
browser session cookies. `api_key` authenticates internal `X-API-Key` callers.
Startup fails closed if `api_key` or `session_secret` cannot be loaded or
created.

The web TRI flow is entered explicitly with the message "tri" or "/tri"
(case-insensitive, surrounding whitespace ignored) and runs through the per-tab
bridge: DES decision, preview, Operator confirmation, then AXIS execution.
Chat messages outside an active TRI flow go to normal chat and do not enter
DES. This path is covered by code audit and offline tests. No live end-to-end
run against AXIS has been recorded since S5 retired the direct-execution paths.

Open before live confirmation: test containment, a real-browser two-tab
isolation check, credential setup, and the S6 decision on the inert
AxisAdapter.

S1 through S5, S4.1 and S4.2 are recorded in the merged pull requests and
commit history.

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
