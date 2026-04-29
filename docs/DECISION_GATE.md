# Decision Gate

## Purpose

The Decision Gate is a Sapphire control layer between the DES bridge payload and AXIS execution.

The system structures.

The operator decides.

AXIS execution must never happen without explicit operator confirmation.

## Flow

```text
DES -> Bridge -> Decision Gate -> AXIS
```

The bridge builds the canonical AXIS payload. Sapphire stores that payload as pending execution state and renders the proposed action. AXIS is called only from the confirm handler.

## Pending State Shape

```json
{
  "payload": {
    "trigger": "string",
    "classification": "string",
    "next_action": "string",
    "reference": true,
    "stability": 6,
    "impact": 4
  },
  "operator_id": "string",
  "created_at": 0,
  "expires_at": 0,
  "status": "pending"
}
```

Creating pending execution state does not call AXIS.

## Expiry Rule

Pending execution expires after 30 minutes.

Expired pending execution is discarded before confirm or reject handling.

Pending execution also ends when the Sapphire session/process ends because the state is in memory only.

## Confirm Behavior

On confirm, Sapphire:

1. Verifies pending execution exists.
2. Verifies pending execution is not expired.
3. Resolves the operator identity.
4. Calls AXIS execution with the existing payload fields and `x-operator-id`.
5. Renders the AXIS response or error.
6. Clears pending execution state after response or error.

## Reject Behavior

On reject, Sapphire:

1. Does not call AXIS.
2. Discards pending execution state.
3. Returns to the idle/input start state.

Revision is not supported in V1. Reject means the pending execution is stopped and the operator may restart the flow.

## Logging Rule

Gate events are local Sapphire integration events only.

Sapphire records:

```json
{
  "action": "confirmed | rejected | expired",
  "classification": "string",
  "timestamp": 0
}
```

Sapphire does not store full trigger text or full payload history in gate events.

Gate events are not written to AXIS session tables, AXIS logs, or AXIS continuity.

## What Was Not Changed

DES classifier logic was not changed.

DES trigger logic was not changed.

DES output structure was not changed.

AXIS engine logic was not changed.

AXIS taxonomy, outcomes, continuity logic, and API contracts were not changed.

Bridge canonical mapping, payload structure, and outcome rule were not changed.
