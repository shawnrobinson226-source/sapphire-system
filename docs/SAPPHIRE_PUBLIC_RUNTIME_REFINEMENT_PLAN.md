# Sapphire Public Runtime Refinement Plan

Status: planning document only.

This plan uses the completed Runtime Surface Refinement Audit to define how Sapphire can move from a builder-facing runtime toward a governed public-facing runtime without breaking architecture law.

No code, UI, runtime, plugin, DES, or AXIS changes are made by this document.

Locked system law:

- Sapphire displays and orchestrates.
- DES classifies and decides.
- AXIS governs execution.
- Operator authorizes.

## 1. Public Runtime Simplification Strategy

Sapphire should open as a simple, trustworthy runtime before exposing builder controls.

Public default experience:

- one visible chat input
- current mode label
- simple assistant style/persona selector
- visible action review only when needed
- clear confirmation before execution
- no forced exposure to prompt/tool/plugin internals

What remains visible:

- Chat
- current assistant style
- message input
- microphone/image attach controls
- active mode: Chat, Review Action, or Action Approved
- proposed action cards when applicable
- Confirm / Reject controls when applicable

What becomes advanced-only:

- prompt selection
- toolset selection
- spice sets
- provider/model controls
- memory/knowledge/goal scopes
- system prompt editing
- story engine controls
- document RAG context levels

What becomes internal-only:

- DES terminology
- AXIS payload internals
- operator identity internals
- plugin execution routing
- shell/file mutation tools
- legacy VANTA runtime surfaces
- prompt self-editing/meta-tool flows

## 2. Advanced / Internal Surface Isolation Strategy

The current runtime exposes advanced controls directly in the chat sidebar. Refinement should introduce layered access.

Recommended layers:

1. Public Runtime
   - normal chat and review-action workflow
   - public-safe personas
   - public-safe add-ons

2. Advanced User
   - model/provider selection
   - prompt customization
   - memory and document controls
   - tool capability visibility

3. Internal Operator
   - tri-system diagnostics
   - DES/AXIS debug data
   - restricted plugins
   - shell/file/email/smart-home controls
   - governance logs

4. Developer / Builder
   - prompt piece editor
   - toolset editor
   - plugin installation
   - signature/trust inspection
   - runtime configuration

Advanced mode should be deliberate, visibly entered, and reversible.

## 3. Public-Safe Navigation Structure

Recommended public nav:

- Chat
- Actions
- Memory
- Add-ons
- Settings

Optional public nav:

- Style
- History

Current labels to move or rename:

- `Persona` -> `Style` or `Assistant`
- `Prompts` -> Advanced-only `Prompt Builder`
- `Toolsets` -> Advanced-only `Capabilities`
- `Spices` -> Advanced-only `Tone`
- `Mind` -> `Memory`
- `Schedule` / `Continuity` -> Advanced-only `Automations` or public `Activity`

What should remain accessible but hidden:

- Prompts
- Toolsets
- Spices
- System Prompt
- Story Engine
- raw provider/model configuration
- detailed plugin install/update controls

## 4. Chat Mode Refinement

Chat mode should feel like normal conversation.

Public chat mode should show:

- message list
- input box
- send button
- mic button
- attachment button
- assistant style indicator
- simple mode label: `Chat`

Chat mode should not show by default:

- prompt selector
- toolset selector
- model/provider selector
- memory scope selector
- knowledge scope selector
- spice controls
- system prompt controls
- story engine controls

Behavioral message:

> Chat is conversation. Nothing is executed here unless you review and confirm an action.

## 5. Tri / Review Mode Refinement

Public-facing Tri mode should be renamed to Review Action mode.

Internal phrase:

- Tri-System

Public phrase:

- Review Action

Current technical output should be transformed conceptually:

- `Tri-System DES Question` -> `A few questions`
- `Tri-System DES Result` -> `Decision summary`
- `Tri-System AXIS Preview` -> `Proposed Action`
- `Tri-System AXIS Result` -> `Action Result`

DES remains behind the scenes. AXIS appears only as the governed execution layer when useful.

Review mode should show:

- question text
- answer options
- progress indication if multiple questions exist
- plain reason for asking
- no raw DES labels

## 6. Confirmation UX Refinement

Confirmation is the most important trust moment.

Required confirmation card:

- title: `Proposed Action`
- short summary
- category
- next step
- what will happen if confirmed
- what will happen if rejected
- Confirm button
- Reject button

Required trust line:

> Nothing is executed until you confirm.

Confirm behavior:

- one-shot
- scoped to the current proposed action
- clears pending state after result/error
- never inferred from chat text outside pending review state

Reject behavior:

- cancels the proposed action
- clears pending state
- returns to chat/input start
- does not revise in V1

What should not appear publicly:

- raw payload
- `operator_id`
- internal session state
- raw AXIS request/response unless advanced/debug mode

## 7. Continuity UX Simplification

Current Continuity reads as scheduler/task machinery. Public UX should explain continuity as visible progress.

Public framing:

> Continuity shows what changed during a session and helps keep progress understandable.

Public labels:

- Progress
- Session result
- What changed
- Before
- After
- Activity

Advanced-only labels:

- Tasks
- Timeline
- Iterations
- Chance
- Scheduler
- Run now

What remains visible:

- simple activity/result summaries
- progress after an approved action

What becomes advanced-only:

- scheduled task editor
- task chance
- iteration settings
- background activity logs

## 8. Plugin Visibility Refinement

Plugins should be reframed publicly as add-ons with visible capabilities.

Public-safe plugin view:

- Add-ons
- capability summary
- enabled/disabled state
- trust badge
- simple access explanation

Advanced/internal plugin view:

- plugin id
- manifest
- signature tier
- install from GitHub
- zip upload
- update checks
- unsigned plugin controls
- dangerous plugin warnings

Plugin categories:

- Public Add-ons
- Advanced Add-ons
- Restricted Tools
- Internal Tools
- Quarantined

What must not be public default:

- shell/SSH
- arbitrary file mutation
- Tool Maker
- Bitcoin/financial actions
- email send
- smart-home control
- AXIS execution plugins
- DES-to-AXIS bridge execution plugins
- legacy VANTA plugins
- prompt self-mutation tools

## 9. Persona Visibility Refinement

Personas should be presented publicly as assistant styles, not runtime authority.

Public-visible personas:

- `generic`
- `sapphire`
- `eddie`
- `cantos`
- selected safe variants after review

Advanced/private personas:

- `cobalt`
- `einstein`
- `anita`
- `yuki`
- girlfriend/story variants

Internal-only personas:

- `alfred`
- `claude`
- `lovelace`
- `Grim`
- `sapphire_trinity`

Restricted personas:

- `nexus`

Setup-only personas:

- `unset_persona`
- `discovery`
- `persona_architect`
- meta-tool flows

Public persona UI should show:

- name
- short style description
- voice/style preview

Advanced persona UI may show:

- prompt
- toolset
- scopes
- model/provider
- TTS
- spice set

## 10. Runtime Terminology Cleanup Map

| Current Term | Public Term | Visibility |
|---|---|---|
| Tri-System | Review Action | Public |
| DES Question | A few questions | Public |
| DES Result | Decision summary | Public |
| AXIS Preview | Proposed Action | Public |
| AXIS Result | Action Result | Public |
| classification | Category | Public |
| next_action | Next step | Public |
| payload | Details | Advanced only |
| operator_id | Approved identity / operator setting | Internal only |
| prompt | Assistant style | Public; Prompt in advanced |
| toolset | Capabilities | Public/Advanced |
| spice | Tone | Public/Advanced |
| System Prompt | Prompt Builder | Advanced only |
| Mind | Memory | Public |
| Continuity | Progress / Activity | Public |
| TTS | Voice output | Public/Advanced |
| STT | Speech input | Public/Advanced |
| LLM | AI provider | Public/Advanced |
| plugin | Add-on | Public |
| unsigned plugin | Unverified add-on | Public/Advanced |
| governance | Review and approval | Public |

Terms to avoid in public default UX:

- friction classifier
- payload
- operator identity
- semantic routing
- autonomous routing
- VANTA
- doctrine
- meta tools
- prompt self-editing
- shell execution
- critical-risk plugin

## 11. DES Invisibility Strategy

DES should stay invisible unless the operator enters advanced/debug mode.

Public DES role:

- internal helper
- question organizer
- decision support infrastructure

Public UX should not show:

- DES name
- DES endpoint state
- DES final raw output
- DES friction fields
- DES metadata

Advanced/debug may show:

- DES health
- DES question/answer flow
- DES result object
- DES-to-AXIS mapping diagnostics

DES must remain the decision/classification layer, but public UX should not require users to understand it.

## 12. AXIS Public Framing Strategy

AXIS should be framed as governed execution.

Public explanation:

> AXIS handles approved actions after you confirm them.

Public UX should show AXIS only at trust moments:

- proposed action confirmation
- execution result
- failed execution
- advanced system details

Public language:

- governed execution
- approved action
- result
- outcome
- session result

Avoid:

- taxonomy
- payload contract
- raw API response
- operator header
- continuity internals

AXIS must not become a persona or assistant identity.

## 13. Beginner-Safe Default Runtime State

Beginner default should be:

- Chat mode
- simple assistant style
- no advanced sidebar expanded
- public-safe persona
- public-safe add-ons only
- no shell/file/plugin execution tools
- no smart-home/financial/email-send controls
- no prompt self-editing
- no semantic plugin routing
- no auto-execution

Recommended default visible state:

- Chat nav selected
- input focused
- small “Chat” mode label
- simple line: “Review required before controlled actions.”

## 14. Advanced Mode Containment Strategy

Advanced mode should be clear and deliberate.

Recommended entry:

- `Advanced`
- `Developer tools`
- `Runtime settings`

Advanced mode should contain:

- prompt builder
- toolsets/capabilities editor
- spice/tone internals
- provider/model settings
- memory scopes
- plugin installation/update
- signature/trust details
- DES/AXIS debug panels

Containment rules:

- Public users should not land here by accident.
- Advanced mode should show a plain warning when enabling state-changing capabilities.
- Returning to public mode should not mutate settings.
- Advanced views should not auto-enable restricted tools.

## 15. Public Onboarding Flow Refinement

Recommended public onboarding:

1. Welcome
   - “Sapphire helps you chat, plan, and review actions before anything important happens.”

2. Choose assistant style
   - public-safe personas only

3. Choose AI provider
   - plain provider language, no LLM-first framing

4. Voice optional
   - speech input/output as optional comfort features

5. Trust explanation
   - “Sapphire asks before controlled actions.”

6. Start in chat
   - first action is typing a message

7. Teach Review Action in context
   - show proposed action only when the user starts that flow

Onboarding should not front-load:

- DES
- AXIS taxonomy
- toolsets
- prompt pieces
- plugins
- continuity scheduler
- governance jargon

## 16. Future Homepage / Runtime Direction

Recommended positioning:

> Sapphire is a governed AI workspace for conversation, planning, and controlled execution.

Short public line:

> Think clearly. Review actions. Stay in control.

Homepage/runtime should emphasize:

- normal chat first
- action review before execution
- visible approval
- safe add-ons
- continuity as progress
- advanced controls when needed

Do not lead with:

- DES internals
- AXIS payloads
- plugin manifests
- prompt architecture
- VANTA
- autonomous execution claims
- AI consciousness framing

## Visibility Summary

### Remain Visible

- Chat
- assistant style
- Memory/Activity
- Add-ons
- Settings
- Review Action card
- Confirm / Reject
- Action Result

### Advanced-Only

- prompt builder
- toolsets/capabilities editor
- tone/spice settings
- provider/model controls
- document context tuning
- memory scopes
- plugin install/update/signature details
- continuity scheduler

### Internal-Only

- DES internals
- AXIS payload/debug internals
- operator identity internals
- legacy VANTA surfaces
- shell/file mutation tools
- Tool Maker
- tri-system diagnostics

### Accessible But Hidden

- raw prompt editing
- full persona editor
- restricted plugin toggles
- advanced logs
- system health/debug details
- DES/AXIS trace details

## Implementation Guardrails For Future Phases

Future implementation should be incremental:

1. Rename public labels without changing behavior.
2. Collapse advanced controls behind an explicit advanced layer.
3. Add Review Action card language.
4. Hide DES labels from public mode.
5. Reframe AXIS as governed execution.
6. Add public-safe persona/add-on filtering.
7. Add tests for mode visibility and no execution drift.

Every phase must preserve:

- normal chat behavior
- explicit tri trigger behavior
- confirmation before AXIS execution
- no DES edits
- no AXIS edits
- no auto-execution
- no semantic routing

The public runtime should feel simpler because governance is clearer, not because governance is removed.
