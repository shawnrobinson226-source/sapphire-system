# TRI-SYSTEM V2 Identity Layer

## Scope

V2 adds a Sapphire-side operator identity helper for the tri-system flow.

Sapphire owns operator identity.

DES never receives operator_id.

AXIS receives operator_id only after explicit operator confirmation.

## Identity Source

The first identity source is the local environment variable:

```text
SAPPHIRE_OPERATOR_ID
```

The value is valid only when it is a non-empty trimmed string.

Whitespace-only values are rejected.

## Prompt Behavior

If `SAPPHIRE_OPERATOR_ID` is missing or invalid, Sapphire prompts for operator identity only after the operator confirms AXIS execution.

Declining execution does not read or prompt for operator identity.

Prompted identity is scoped to the current run/process only.

Operator identity is not persisted to disk.

## Boundary Rules

Sapphire owns orchestration and identity.

DES decides.

AXIS governs.

Sapphire does not place `operator_id` in DES trigger, start, answer, result, or preview payloads.

Sapphire passes `operator_id` only to the existing AXIS execution tool at execution time.

No auto-execution exists.

## Validation Coverage

The V2 tests cover:

1. Decline path does not read operator_id.
2. DES payloads never include operator_id.
3. Missing environment value prompts only after yes.
4. Valid environment value avoids prompt.
5. Invalid environment value prompts after yes.
6. AXIS payload preview does not include operator_id.
