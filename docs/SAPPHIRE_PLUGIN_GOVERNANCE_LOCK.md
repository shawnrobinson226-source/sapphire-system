# Sapphire Plugin Governance Lock

## Purpose

This document locks the governance classification for Sapphire plugins.

It is documentation only. It does not enable, disable, remove, or modify plugins.

The system law remains:

```text
Sapphire displays and orchestrates.
DES classifies and decides.
AXIS governs execution.
Operator authorizes.
```

## Governance Categories

### SAFE DEFAULT

Plugins that may run by default because they provide narrow, local, non-destructive runtime support.

Allowed properties:

- No shell execution
- No external mutation
- No financial movement
- No code generation or plugin installation
- Exact trigger or explicit user action only

Current plugin:

- `voice-commands`

### SAFE OPTIONAL

Plugins that may be available as opt-in capabilities when configured by the operator.

Allowed properties:

- Clear user-facing purpose
- Limited data or media access
- No hidden execution
- External mutation only when explicitly requested and gated

Current plugins:

- `google-calendar`, read paths safer than add/delete
- `image-gen`
- `webcam`
- `email`, only with strict recipient/send/archive gates

### DEFERRED

Plugins that should not be part of the normal governed runtime until their boundary behavior is reviewed, simplified, or replaced.

Current plugins:

- Any duplicated bridge/runtime plugin superseded by the governed web bridge
- Any plugin whose behavior is unclear or not yet locked by tests

### LEGACY/VANTA

Plugins that belong to older VANTA/System V1/AXIS-runtime work and must not define the current governing architecture.

Current plugins:

- `axis-runtime`
- `vanta-execution`

Rules:

- Keep isolated from normal runtime unless explicitly needed for legacy testing.
- Do not let legacy VANTA plugins redefine DES or AXIS responsibilities.
- Do not use legacy VANTA plugins as the canonical tri-system path.
- Prefer the locked Sapphire Web Hybrid Tri-System bridge for DES -> AXIS operator-gated flow.

### STORE-CAPABLE

Plugins that can browse, download, install, enable, or load plugin code.

Current plugin:

- `sapphire-store`

Rules:

- Never public default.
- Treat as internal/store infrastructure, not ordinary runtime behavior.
- Require explicit operator confirmation before install, update, enable, or load.
- Require signature/trust validation and source review for community plugins.
- Never allow automatic plugin installation or semantic routing into install behavior.

### GOVERNANCE RISK

Plugins that can mutate external systems, call governed APIs, or bypass normal operator control if exposed as normal LLM tools.

Current plugins:

- `axis-integration`
- `email`
- `homeassistant`

Rules:

- Disabled by default unless a specific governed workflow requires them.
- External mutation requires operator gating.
- AXIS execution tools must not be broadly LLM-callable.
- Device, message, and API mutations must be scoped, logged safely, and reversible where possible.

### CRITICAL RISK

Plugins that can execute commands, move funds, create executable code, or run remote commands.

Current plugins:

- `bitcoin`
- `commandline`
- `ssh`
- `toolmaker`

Rules:

- Must stay disabled by default.
- Should never be public default.
- Require sandboxing and explicit operator approval before any use.
- Must not be available to ordinary chat/tool routing.
- Must not be invoked automatically.

## Enabled Plugin Policy

Plugins that may stay enabled:

- `voice-commands`

Plugins that may stay enabled only in controlled local/operator development:

- `axis-integration`, only if AXIS execution remains operator-gated elsewhere
- `axis-runtime`, only for legacy testing and not as canonical runtime
- `vanta-execution`, only for legacy/System V1 inspection

Plugins that must stay disabled in normal governed runtime:

- `bitcoin`
- `commandline`
- `ssh`
- `toolmaker`
- `sapphire-store`
- `homeassistant`

Plugins that may be optional with operator configuration and gates:

- `google-calendar`
- `email`
- `image-gen`
- `webcam`

## Operator Gating Requirements

Operator gating is required for:

- AXIS execution
- Sending email
- Archiving email
- Adding or deleting calendar events
- Home Assistant device control
- Notifications to external devices
- Bitcoin sends
- Shell or SSH commands
- Plugin installation
- Plugin code creation or activation
- Any external mutation or irreversible operation

Read-only operations may be allowed with normal plugin opt-in, but sensitive reads still require privacy-aware scope controls.

## Plugins That Should Never Be Public Default

These plugins must never ship as public default runtime capabilities:

- `commandline`
- `ssh`
- `toolmaker`
- `bitcoin`
- `sapphire-store`

They expose system execution, code loading, funds movement, or plugin installation surfaces that are incompatible with safe default runtime.

## AXIS Execution Plugin Handling

AXIS execution plugins must obey:

```text
Sapphire displays/orchestrates.
AXIS governs.
Operator authorizes.
```

Rules:

- AXIS execution must never happen from automatic tool routing.
- AXIS execution must be scoped to a pending operator-confirmed action.
- Direct AXIS tools must not be broadly available in ordinary chat.
- The canonical path is the governed Hybrid Web Tri-System bridge.
- Legacy AXIS plugins must not bypass the confirmation gate.

## Sapphire Store Handling

Sapphire Store is store-capable infrastructure.

Rules:

- Disabled by default.
- Internal/operator use only.
- No automatic installs.
- No semantic routing into install/update behavior.
- Every install or update requires operator review and confirmation.
- Community plugins require source review, signature checks, and quarantine before runtime use.

## Legacy VANTA Isolation

Legacy VANTA plugins must be isolated from the locked tri-system architecture.

Rules:

- Do not treat legacy VANTA plugins as DES.
- Do not treat legacy VANTA plugins as AXIS.
- Do not use VANTA task routing as a replacement for DES classification.
- Do not allow VANTA plugins to execute AXIS without the locked operator gate.
- Keep legacy VANTA behavior disabled or development-only unless explicitly approved.

## Final Lock

Plugin governance is locked around explicit operator control.

No automatic plugin execution.

No semantic plugin routing.

No autonomous agents.

No hidden AXIS execution.

No plugin may collapse the system law.
