# Sapphire ↔ AXIS Integration Proof

## Status

SUPERSEDED (S5). The execution flow recorded below no longer exists.

The live test in this document went through the `execute_axis` model tool
and `AxisAdapter`. S5 removed that path: `axis_tools` registers no model
tools, the `execute_axis` dispatcher is gone, and no runtime caller constructs
`AxisAdapter`. The contract alignment and endpoint list below still describe
what Sapphire sends. The "Execution Flow Verified" and "Live Test" sections are
kept as a historical record only.

### Current AXIS paths (S5)

- Execution: web chat (`/api/chat`, `/api/chat/stream`) → governed tri bridge
  (`core/des/web_tri_system.py`, S4 principal + tab token) → `TriSystemFlow`
  (DES decision → preview → operator confirm) →
  `plugins/axis_integration/axis_tools._execute_axis` → strict transport
  (`core/sapphire/axis_http.py`) → `POST /api/v2/execute`. The UI tri flow
  (`ui/app.py`) uses the same `TriSystemFlow`.
- Read-only: Test AXIS Identity (`POST /api/settings/operator-id/test-axis-identity`)
  → `axis_tools._fetch_axis_operator_profile` → strict transport →
  `GET /api/v2/operator-profile`.
- Removed: the `axis-runtime` pre_chat hook, the `execute_axis` dispatcher,
  the `fetch_axis_*` model tools, CLI and SapphireUIApp direct execution, and
  `ExecutionService`.
- `AxisAdapter` is kept as an inert, tested reference (endpoint allowlist,
  payload allowlist, boundary-violation logging, distortion-class lock). It is
  not on any live path.

This S5 update is based on a code audit and offline tests only. No new live
AXIS test was run.

---

## Purpose

Confirm that Sapphire correctly interfaces with AXIS using the current execution contract.

---

## Contract Alignment

### AXIS accepts:

- trigger
- classification
- next_action
- stability (optional)
- reference (optional)
- impact (optional)

### AXIS rejects:

- distortion_class

---

## Sapphire Changes

- Removed all outbound usage of `distortion_class`
- Replaced with `classification`
- Added optional guard inputs:
  - stability
  - reference
  - impact
- Maintained boundary validation
- Preserved endpoint allowlist

---

## Execution Flow Verified (historical, pre-S5)

Sapphire → execute_axis tool  
→ AxisAdapter  
→ POST /api/v2/execute  
→ AXIS engine  
→ Response returned to Sapphire  

---

## Live Test (historical, pre-S5)

Command:

POST /api/chat  
Tool call: execute_axis  

Payload:

- classification: narrative  
- next_action: Write facts vs assumptions  
- reference: true  
- stability: 6  
- impact: 4  

Result:

AXIS executed successfully.

---

## Boundary Integrity

- No distortion_class sent to AXIS
- Invalid classification blocked at adapter (pre-S5; since S5 the adapter is
  not on a live path, and the tri flow's classification comes from a fixed
  DES friction-type map in `core/des/axis_preview.py`)
- AXIS endpoints restricted to (since S5 there is no runtime allowlist check:
  the live callers are `_execute_axis` and `_fetch_axis_*`, which can only
  build these paths):
  - POST /api/v2/execute
  - GET /api/v2/analytics
  - GET /api/v2/operator-profile

---

## Conclusion

Pre-S5: Sapphire was aligned with the AXIS contract on the path tested above.

Since S5, see "Current AXIS paths" above.