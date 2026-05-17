# Sapphire Persona Separation Plan

Status: planning document only.

This plan separates Sapphire persona presentation from runtime authority. It does not remove personas, modify runtime settings, change plugins, or alter DES/AXIS behavior.

Locked system law:

- Sapphire displays and orchestrates.
- DES classifies and decides.
- AXIS governs execution.
- Operator authorizes.

## Purpose

Sapphire personas currently combine identity, prompt style, toolset selection, voice settings, memory scopes, and runtime presentation. That is useful for operator experience, but it creates governance risk when a persona also implies execution authority.

The goal is to define clear runtime layers so public personas remain expressive while operational or restricted personas cannot accidentally become decision-makers.

## Persona Layers

### Public Runtime

Public Runtime personas are safe for normal chat selection. They may affect tone, voice, formatting, and general assistant behavior. They must not imply governance authority, autonomous execution, or privileged system control.

Recommended public-visible personas:

- `generic`
- `sapphire`
- `eddie`
- `cantos`
- `cobalt`
- `einstein`

Conditions:

- Tool access should be visible before use.
- Public runtime personas should default to low-risk or personality-level toolsets.
- Any memory, research, email, file, smart-home, plugin, or execution surface must remain separately visible and governed.

### Internal Operational

Internal Operational personas support development, administration, or controlled work sessions. They may use stronger workflow language and may be paired with work-capable toolsets, but only in internal/operator contexts.

Recommended internal-only personas:

- `alfred`
- `claude`
- `lovelace`
- `Grim`
- `sapphire_trinity`

Conditions:

- These personas may assist with planning, coding, review, and orchestration.
- They must not bypass operator checkpoints.
- They must not move DES decision logic into Sapphire.
- They must not move AXIS governance into Sapphire.
- They must not execute plugins, shell actions, file edits, or external calls without explicit operator approval where required.

### Restricted / Governance Risk

Restricted personas can touch real-world, privileged, or control surfaces. They require explicit operator gating and should not appear as ordinary public runtime choices.

Restricted persona:

- `nexus`

Reason:

- `nexus` is framed as a smart-home/system persona and can pair with Home Assistant controls.
- This creates a physical-environment control surface.

Requirements:

- Smart-home actions must be explicitly visible before execution.
- Operator confirmation must be required for state-changing actions.
- `nexus` must not be treated as a governor, classifier, or execution authority.

### Experimental

Experimental personas are expressive, relationship-oriented, roleplay-heavy, or tone-risky. They may be useful in private contexts but should not define default public runtime behavior.

Recommended experimental/private personas:

- `anita`
- `yuki`
- girlfriend-style variants

Conditions:

- Keep outside default public runtime.
- Avoid pairing with broad toolsets.
- Do not use experimental personas for governance, execution, DES classification, or AXIS control.

### Setup / Discovery

Setup and discovery personas are used to help configure identity and prompt preferences. They should not remain active during normal runtime.

Setup/discovery surfaces:

- `unset_persona`
- `discovery`
- `persona_architect`
- `meta_tools`
- `unset`

Requirements:

- Visible as setup tools, not normal personas.
- Prompt mutation must be operator-approved.
- Meta tools should not be implied as normal public runtime capability.
- Setup sessions should clearly show when prompt/persona configuration is being changed.

### Legacy / Deferred

Legacy/deferred persona-related surfaces should remain isolated until they are intentionally reworked.

Current finding:

- No dedicated VANTA persona file was found.
- No dedicated Reaper/Reapers persona file was found.
- VANTA appears as plugin/runtime legacy, not a persona layer.

Policy:

- Legacy VANTA behavior must not define current persona governance.
- Future Reapers/AXIS persona work should be product-layer identity only, not governance authority.
- Deferred personas should stay hidden from normal selection until reviewed.

## Visibility Plan

Recommended UI/runtime visibility layers:

1. Public
   - Normal chat persona selector.
   - Includes only Public Runtime personas.

2. Private
   - Operator-only persona selector or advanced mode.
   - Includes Internal Operational and Experimental personas.

3. Restricted
   - Requires explicit warning and operator gate before use.
   - Includes personas tied to real-world controls or privileged execution surfaces.

4. Setup
   - Prompt/persona editor workflows only.
   - Includes discovery and meta-tool configuration flows.

5. Deferred
   - Hidden from normal runtime selection.
   - Used for archived, legacy, or unreviewed persona surfaces.

## Runtime-Safe Defaults

Future public runtime default:

- Primary: `generic` or `sapphire`
- Alternate friendly helper: `eddie`

Runtime-safe defaults should use:

- Low-risk toolsets.
- No hidden tool escalation.
- No prompt self-editing by default.
- No smart-home, shell, file mutation, email send, AXIS execution, or plugin execution authority by persona alone.

## Internal Developer Defaults

Future internal developer defaults:

- `sapphire_trinity` for governed Sapphire-native work.
- `lovelace` for coding/system design.
- `claude` for collaborative problem solving.
- `alfred` for concise operational assistance.

Internal defaults must preserve:

- Inspection before mutation.
- Plan before structural change.
- Operator approval before coding or runtime mutation.
- No autonomous execution.
- No DES/AXIS law drift.

## Reapers / AXIS Persona Direction

Future Reapers/AXIS persona direction should remain product-layer and display-layer only.

Allowed:

- Brand voice.
- UI presentation.
- Operator-facing explanation.
- Narrative or symbolic framing when clearly separated from execution authority.

Not allowed:

- Personas that classify DES friction.
- Personas that govern AXIS outcomes.
- Personas that imply direct execution rights.
- Personas that blur operator identity with system authority.
- Personas that create an alternate governance chain.

AXIS remains governed by AXIS. DES remains the decision/classification layer. Sapphire personas may explain and display, but not decide or govern.

## Identity Separation

### Persona Identity

Persona identity is the assistant-facing character, style, tone, and presentation. It may shape language and interface feel.

Persona identity must not be used as:

- operator identity
- execution credential
- governance authority
- DES classification authority
- AXIS authority

### Operator Identity

Operator identity is the human authorization identity used for gated execution paths.

Operator identity must:

- come from an approved operator identity resolver or controlled setting
- be passed to AXIS only at execution time when required
- never be inferred from the selected persona
- never be stored in persona prompt text

### Governance Authority

Governance authority belongs to the system architecture, not personas.

Authority chain:

- DES decides/classifies.
- AXIS governs execution.
- Operator authorizes.
- Sapphire displays/orchestrates.

No persona may override this chain.

## Migration Planning

### Grim Decoupling

Current state:

- `Grim` is used as the character for `sapphire_trinity`.
- Some AXIS runtime surfaces have also used `Grim` as an operator label in prior integrations.

Migration goal:

- Keep `Grim` as a persona identity only.
- Do not use `Grim` as a governance identity or implicit operator identity.
- Operator identity should come from the Sapphire operator identity helper or controlled local configuration.

Safe migration sequence:

1. Inventory every runtime use of `Grim`.
2. Classify each use as persona identity, display label, or operator identity.
3. Replace operator identity usages with the approved identity resolver.
4. Keep persona/display references only where intentional.
5. Add tests where execution headers or logs could confuse persona with operator.

### Discovery / Meta Tools Isolation

Current risk:

- Discovery prompts encourage prompt mutation and meta-tool activation.

Migration goal:

- Move discovery/meta-tool behavior into a setup-only layer.
- Hide setup flows from normal runtime persona selection.
- Make prompt mutation visibly operator-approved.

Safe migration sequence:

1. Label discovery/meta-tool presets as setup-only in UI metadata.
2. Prevent setup-only personas from becoming default chat personas.
3. Add explicit UI copy when prompt mutation tools are active.
4. Keep existing prompt pieces intact until runtime visibility metadata exists.

### Nexus Gating

Current risk:

- `nexus` can represent smart-home awareness and may pair with Home Assistant actions.

Migration goal:

- Treat `nexus` as Restricted.
- Require operator confirmation for state-changing smart-home actions.
- Show action previews before execution.

Safe migration sequence:

1. Mark `nexus` as restricted in persona metadata.
2. Ensure smart-home tool calls are visibly gated.
3. Separate household status reads from state-changing actions.
4. Keep physical actions out of public/default runtime.

### Toolset Escalation Visibility

Current risk:

- Persona selection can silently change toolsets.

Migration goal:

- Make toolset escalation visible whenever a persona loads.
- Require confirmation when a persona activates high-risk toolsets.

Safe migration sequence:

1. Classify toolsets by risk.
2. Show persona toolset changes in the UI.
3. Gate transitions into `all`, `smarthome`, shell/file mutation, email send, plugin execution, and AXIS execution surfaces.
4. Keep persona styling separate from tool activation.

## Future Policy

1. Personas may style, explain, and assist.
2. Personas may not decide DES classifications.
3. Personas may not govern AXIS execution.
4. Personas may not authorize execution.
5. Personas may not silently escalate tools.
6. Public personas should be safe without operator training.
7. Internal personas may support work, but only inside governed workflows.
8. Restricted personas require explicit operator gates.
9. Setup personas must be visibly separate from normal runtime.
10. Legacy/VANTA persona-adjacent behavior must remain isolated from current tri-system governance.

This plan is intentionally non-mutating. Implementation should happen in later governed phases with inspection, operator approval, focused tests, and no DES/AXIS architecture drift.
