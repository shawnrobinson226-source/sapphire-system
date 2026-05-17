# Sapphire Store Architecture Plan

Status: planning document only.

This document defines the intended governance architecture for a future Sapphire Store. It does not implement a store, modify plugin loading, change runtime behavior, or alter DES/AXIS integrations.

Locked system law:

- Sapphire displays and orchestrates.
- DES classifies and decides.
- AXIS governs execution.
- Operator authorizes.

## 1. What the Sapphire Store Is

The Sapphire Store is a governed distribution layer for Sapphire extensions.

It may eventually provide:

- discovery of approved plugins
- installation of signed plugin packages
- update management
- capability review before activation
- operator-visible trust metadata
- quarantine and disable flows
- separation between public-safe extensions and private/internal tools

The store is a packaging and trust surface. It is not an execution authority.

## 2. What the Sapphire Store Is Not

The Sapphire Store is not:

- an autonomous plugin runner
- a semantic router
- a hidden tool activation layer
- a replacement for DES
- a replacement for AXIS
- an operator authorization bypass
- a place for unreviewed shell/file/network execution by default
- a mechanism for plugins to silently grant themselves capabilities
- a public distribution path for legacy, private, or critical-risk runtime tools

Installing a plugin must not imply activating it. Activating a plugin must not imply executing it.

## 3. Public-Safe Plugin Rules

Public-safe plugins are suitable for normal runtime availability when installed and enabled by the operator.

Requirements:

- Read-only or low-risk by default.
- No shell execution.
- No arbitrary file mutation.
- No hidden credential access.
- No hidden outbound network calls.
- No execution of DES or AXIS flows without the locked operator gate.
- No background task creation unless explicitly approved.
- Clear manifest-declared capabilities.
- Clear user-facing description of what the plugin does.
- Safe failure mode when dependencies are unavailable.

Examples of public-safe capability classes:

- UI widgets
- local formatting helpers
- read-only reference tools
- read-only search or lookup tools with visible network disclosure
- visualization/rendering helpers

## 4. Internal-Only Plugin Rules

Internal-only plugins are useful for operator/developer workflows but should not be public default.

Internal-only plugins may include:

- repo maintenance tools
- development helpers
- prompt management tools
- controlled integration tools
- private workspace utilities
- plugins requiring local secrets or private infrastructure

Requirements:

- Hidden from public default store listings unless the operator enables internal mode.
- Capability warnings before activation.
- Operator gate before any mutation, external execution, privileged network action, or sensitive data access.
- No automatic routing from normal chat unless explicitly configured.
- Clear separation from public runtime personas.

## 5. Critical-Risk Plugin Rules

Critical-risk plugins can mutate files, execute code, call external execution APIs, manage credentials, control physical devices, or affect governance boundaries.

Critical-risk plugins must:

- never be public default
- never auto-enable after install
- require explicit operator activation
- require per-action operator confirmation for state-changing behavior
- expose exact capability declarations
- support immediate disable/quarantine
- fail closed on missing credentials, invalid state, or unavailable services
- avoid persistent sensitive logs
- avoid hidden retries or background execution

Critical-risk surfaces include:

- shell/terminal execution
- arbitrary file writes/deletes
- plugin installation or mutation
- email send
- calendar mutation
- smart-home control
- financial or wallet actions
- AXIS execution
- DES-to-AXIS bridge execution
- credential or secret handling
- external deployment or production mutation

## 6. Required Operator Gating

Operator gating is required whenever a plugin action can change state, expose sensitive information, or cross a governance boundary.

Required gate contents:

- plugin name
- requested action
- capability being used
- target system or boundary
- risk class
- expected result
- confirm/reject options

Gate rules:

- Reject must cancel cleanly.
- Confirm must be one-shot.
- Stale confirmations must not execute.
- No silent retries.
- No background execution after rejection.
- No execution from preview state alone.

AXIS execution must always remain operator-confirmed.

## 7. Signature and Trust Policy

Future store packages should use a signed trust model.

Required trust metadata:

- plugin id
- publisher id
- version
- package hash
- manifest hash
- signature
- signing key id
- declared capabilities
- required dependencies
- risk classification

Trust levels:

- `official`: maintained by Sapphire core maintainers
- `verified`: reviewed publisher and signed package
- `local`: operator-installed local package
- `untrusted`: unsigned or unknown package
- `quarantined`: disabled due to failed validation, policy violation, or operator action

Policy:

- Unsigned plugins may be inspected locally but should not be public-installable by default.
- Signature mismatch must block activation.
- Capability mismatch between manifest and package behavior must quarantine the plugin.
- Updates must be revalidated before activation.

## 8. Capability Declaration

Every store plugin should declare capabilities in its manifest.

Suggested capability fields:

```json
{
  "capabilities": {
    "network": {
      "allowed": true,
      "domains": ["example.com"],
      "methods": ["GET"]
    },
    "filesystem": {
      "read": ["workspace"],
      "write": []
    },
    "shell": false,
    "secrets": [],
    "memory": {
      "read": false,
      "write": false
    },
    "external_execution": false,
    "smart_home": false,
    "email": {
      "read": false,
      "send": false
    },
    "des": {
      "uses_des": false,
      "modifies_des": false
    },
    "axis": {
      "uses_axis": false,
      "executes_axis": false,
      "modifies_axis": false
    },
    "operator_gate_required": false
  }
}
```

Capability declarations must be operator-visible before activation.

## 9. DES / AXIS Dependency Declaration

Plugins that depend on DES or AXIS must explicitly declare that dependency.

DES dependency policy:

- Plugins may call DES only through approved Sapphire-side clients.
- Plugins must not modify DES logic.
- Plugins must not reinterpret DES output as a new decision layer.
- Plugins must not pass operator identity to DES.

AXIS dependency policy:

- Plugins may call AXIS only through approved gated execution paths.
- Plugins must not modify AXIS logic.
- Plugins must not change AXIS payload contracts.
- Plugins must not send unknown fields.
- Plugins must not place operator identity in payload bodies.
- AXIS execution requires operator confirmation.

Suggested manifest fields:

```json
{
  "dependencies": {
    "des": {
      "required": false,
      "endpoint": "local",
      "purpose": "classification"
    },
    "axis": {
      "required": false,
      "endpoint": "configured",
      "purpose": "governed execution",
      "operator_gate_required": true
    }
  }
}
```

## 10. Tri-System Bridge Packaging

The Tri-System Bridge should be packaged as an internal governed integration, not a general public default plugin.

Package role:

- Sapphire-side orchestration bridge
- explicit trigger handling
- DES call
- AXIS payload preview
- pending confirmation state
- confirm/reject handling
- AXIS execution only after confirmation
- structured result rendering

Packaging requirements:

- Declare DES dependency.
- Declare AXIS dependency.
- Declare operator gate requirement.
- Declare no DES modification.
- Declare no AXIS modification.
- Declare no semantic routing.
- Declare no auto-execution.
- Declare no hidden retries.
- Declare no operator identity in DES payloads.
- Declare operator identity is used only at AXIS execution time.

The bridge must remain Sapphire-owned orchestration. It must not become DES logic or AXIS governance.

## 11. What Must Never Be Public Default

The following must never be public default:

- shell or terminal execution plugins
- arbitrary file mutation plugins
- plugin creation or plugin installation tools
- credential management plugins
- email send plugins
- calendar mutation plugins
- wallet or financial action plugins
- smart-home state-changing plugins
- AXIS execution plugins
- DES-to-AXIS bridge execution plugins
- legacy VANTA execution plugins
- prompt self-mutation/meta-tool plugins
- autonomous routing or background execution plugins
- plugins that claim governance authority

These may exist only as internal, restricted, or quarantined tools with explicit operator control.

## 12. Future Install / Update / Quarantine Flow

### Install Flow

1. Operator selects plugin.
2. Sapphire displays manifest, publisher, signature, risk class, and capabilities.
3. Sapphire verifies package signature and hashes.
4. Operator approves install.
5. Plugin is installed disabled by default.
6. Operator separately approves activation.
7. High-risk capabilities require separate gates before use.

### Update Flow

1. Sapphire downloads update metadata.
2. Sapphire verifies signature and package hash.
3. Sapphire compares new capabilities to old capabilities.
4. Capability expansion requires operator approval.
5. Update installs disabled or staged until approved if risk increases.
6. Failed validation blocks update and preserves prior working version.

### Quarantine Flow

Triggers for quarantine:

- invalid signature
- hash mismatch
- undeclared capability use
- execution outside declared boundaries
- failed dependency validation
- operator quarantine action
- repeated unsafe failure mode

Quarantine behavior:

- Disable plugin immediately.
- Prevent runtime execution.
- Preserve files for inspection.
- Show reason to operator.
- Do not delete local data automatically.
- Require explicit operator approval to restore.

## Governance Summary

The Sapphire Store should make extension power visible, reviewable, and reversible.

Store governance must preserve:

- normal chat safety
- public/internal separation
- explicit capability declaration
- operator confirmation for state changes
- DES and AXIS boundary integrity
- no auto-execution
- no hidden escalation

The store distributes capability. It does not grant authority.
