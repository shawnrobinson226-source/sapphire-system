# Sapphire Tri-System Web Runtime Lock

Status: dated record. For the current state, see the Current State section of README.md.

## Current System Law

Sapphire displays and orchestrates.

DES classifies and decides.

AXIS governs execution.

The operator authorizes.

## Local Run Order

1. Start DES locally.
2. Start AXIS or ensure the configured AXIS endpoint is reachable.
3. Start Sapphire web runtime.
4. Open Sapphire Web and use the visible chat input.

## Web Trigger

Hybrid Web Tri-System flow starts only from one of these exact chat messages:

- `tri`
- `/tri`

No semantic detection or extra trigger phrases are part of this lock.

## Confirmed Flow

```text
Sapphire Web
-> DES
-> AXIS Preview
-> Operator Confirm/Reject
-> AXIS Execute
-> Sapphire Result
```

AXIS execution is allowed only after an explicit operator confirm while a pending Hybrid execution exists.

## Operator Identity Source

Sapphire Web Hybrid confirm resolves the operator ID from, in order:

```text
SAPPHIRE_OPERATOR_ID
OPERATOR_ID setting
```

If neither holds a valid value, Hybrid confirm fails closed with a visible Tri-System error. Sapphire does not prompt for operator ID from the web request path.

## Intentionally Not Included

- Semantic detection
- Autonomous routing
- UI buttons
- Plugin/tool execution routing
- DES edits
- AXIS edits

## Governance Rules

- Normal Sapphire chat is preserved.
- Tri-System flow is explicit only.
- Confirm is scoped to pending Hybrid state.
- Reject clears pending execution.
- Missing operator ID fails closed.
- No AXIS execution occurs from preview creation alone.
- No stale pending execution may execute after expiry or cancellation.

## Tests Passed

These focused tests passed for the locked Hybrid Web runtime behavior:

```text
tests/test_web_tri_system_bridge.py
tests/test_tri_system_identity.py
```

## Known Unrelated Failing Test

At lock time, `tests/test_browser_mic_binding.py` failed because it expected browser `SpeechRecognition`. That assertion was removed on 2026-08-09; the test's current result is not recorded here.

## Lock Boundary

This document locks the completed Sapphire Hybrid Web Tri-System integration as a Sapphire-side orchestration layer. It does not move DES decision logic into Sapphire and does not move AXIS governance into Sapphire.
