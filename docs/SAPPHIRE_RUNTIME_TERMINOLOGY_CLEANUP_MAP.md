# Sapphire Runtime Terminology Cleanup Map

Status: planning document only.

This document maps current builder-facing/internal Sapphire terminology to public-safe runtime terminology. It is based on the Runtime Surface Refinement Audit, the Public Runtime / UX Architecture Plan, and the Public Runtime Refinement Plan.

No code, UI, runtime, plugin, DES, or AXIS changes are made by this document.

Locked system law:

- Sapphire displays and orchestrates.
- DES classifies and decides.
- AXIS governs execution.
- Operator authorizes.

## 1. Internal Terminology Map

| Current label / term | Proposed public replacement | Keep visible where | Rationale | Governance consideration |
|---|---|---|---|---|
| `Tri-System` | Review Action | Public may see replacement; internal/debug may see original | Describes user experience instead of architecture | Do not hide confirmation requirement |
| `DES` | Internal decision helper | Advanced/debug/operator only | DES is infrastructure, not a public UX concept | DES remains classifier/decision layer |
| `AXIS` | Governed execution | Public when explaining approved action; full AXIS term in advanced/debug | Explains role without taxonomy | AXIS remains governance/execution layer |
| `payload` | Details | Advanced/debug only | Payload is API language | Never expose editable execution payload in public runtime |
| `classification` | Category | Public in review card | Category is understandable | Must reflect DES-to-AXIS mapping without reinterpretation |
| `next_action` | Next step | Public in review card | Plain action language | Must not invent new decision logic |
| `operator_id` | Operator setting / approval identity | Internal/operator only | Avoids confusing persona identity with authorization identity | Operator identity must not come from persona |
| `execution` | Approved action | Public | Less intimidating, still clear | Execution remains gated |
| `governance` | Review and approval | Public | Plain language | Keep stronger term in docs/operator mode |
| `runtime` | Workspace / app | Public | Friendlier than runtime | Runtime remains valid in developer docs |
| `toolset` | Capabilities | Public/advanced | Describes what can be used | Tool escalation must be visible |
| `prompt` | Assistant style | Public | Prompt is builder-facing | Prompt editor remains advanced |
| `spice` | Tone | Public/advanced | More intuitive | Keep spice as internal/product flavor term if desired |
| `System Prompt` | Prompt Builder | Advanced only | Reduces exposure of system internals | Prompt mutation must be gated |
| `LLM` | AI provider | Public/advanced | Beginner-safe | Advanced may still show LLM |
| `STT` | Speech input | Public/advanced | Plain language | Does not change STT behavior |
| `TTS` | Voice output | Public/advanced | Plain language | Does not change TTS behavior |
| `Mind` | Memory | Public | Mind is vague and loaded | Memory scopes still advanced |
| `Continuity` | Progress / Activity | Public | Explains outcome simply | Scheduler remains advanced |
| `Plugin` | Add-on | Public | More familiar | Plugin manifests remain advanced |
| `Unsigned Plugin` | Unverified add-on | Public/advanced | Plain trust language | Signature details stay advanced |
| `VANTA` | Hide | Internal/legacy only | Legacy architecture leaks into UX | Must not define current governance |

## 2. Public-Safe Replacement Terminology

Recommended public words:

- Chat
- Review Action
- Proposed Action
- Confirm
- Reject
- Approved
- Cancelled
- Category
- Next step
- Action Result
- Progress
- Activity
- Memory
- Assistant style
- Capabilities
- Add-ons
- Voice output
- Speech input
- AI provider
- Safe defaults
- Review required

Public trust line:

> Nothing is executed until you confirm.

Public mode line:

> Chat is conversation. Review Action is for controlled actions.

Public AXIS line:

> Approved actions are handled by Sapphire's governed execution layer.

Public DES line, only if needed:

> Sapphire may use an internal decision helper to organize the proposed action.

## 3. Advanced / Internal-Only Terminology

These terms may remain visible in advanced, debug, operator, or developer views:

- DES
- AXIS
- Tri-System
- payload
- operator_id
- classification
- next_action
- stability
- impact
- reference
- sessionId
- continuity_before
- continuity_after
- prompt
- system prompt
- toolset
- spice set
- LLM
- STT
- TTS
- plugin manifest
- signature tier
- verified author
- unsigned plugin
- quarantine
- execution service
- route
- hook
- pre_chat
- System V1

Rule:

Advanced terminology is allowed when the operator has intentionally entered an advanced/debug/operator surface.

## 4. Terms To Fully Hide From Public Runtime

These should not appear in beginner/public runtime:

- `friction_type`
- `output_type`
- `payload`
- `operator_id`
- `distortion_class`
- `semantic routing`
- `autonomous routing`
- `VANTA`
- `System V1`
- `meta_tools`
- `prompt self-editing`
- `shell execution`
- `critical-risk plugin`
- `governance engine`
- `taxonomy`
- `continuity_before`
- `continuity_after`
- raw API request/response
- raw DES response
- raw AXIS response
- plugin hook names

Rationale:

These terms either expose implementation details, imply authority the public user does not need to reason about, or make the interface feel like a developer console.

## 5. DES Visibility Rules

DES should be invisible by default.

Public runtime:

- Do not show `DES`.
- Do not show raw DES output.
- Do not show DES metadata.
- Do not show DES endpoint or health unless in diagnostics.
- Show user-facing questions as normal review questions.

Public replacements:

| Current DES-facing label | Public label |
|---|---|
| `Tri-System DES Question` | A few questions |
| `DES Result` | Decision summary |
| `DES unavailable` | Review system is unavailable |
| `DES trigger check failed` | Could not start review |
| `DES not triggered` | No review action started |
| `DES returned an invalid question` | Could not continue review |

Advanced/debug/operator:

- DES health may be shown.
- DES request/response flow may be shown.
- DES result object may be inspected.
- DES-to-AXIS mapping diagnostics may be shown.

Governance:

- DES remains the classifier/decision layer.
- Hiding DES terminology must not move DES logic into Sapphire.
- Public wording must not reinterpret DES output.

## 6. AXIS Public Wording Rules

AXIS may be public-facing only as governed execution, not as a persona or mystical authority.

Public runtime:

- Use `governed execution`.
- Use `approved action`.
- Use `action result`.
- Show AXIS only when a proposed action is approved or fails.

Public replacements:

| Current AXIS-facing label | Public label |
|---|---|
| `AXIS Preview` | Proposed Action |
| `AXIS Result` | Action Result |
| `AXIS execution failed` | Action could not be completed |
| `AXIS payload is not ready` | Proposed action is not ready |
| `Send this execution payload to AXIS?` | Confirm this action? |
| `Confirm Execution` | Confirm |

Advanced/debug/operator:

- AXIS payload preview may be shown.
- AXIS response fields may be shown.
- AXIS endpoint/configuration may be shown.
- AXIS contract details may be shown.

Governance:

- AXIS execution requires explicit confirmation.
- Public wording must not imply Sapphire itself governs execution.
- Operator identity must remain separate from persona identity.

## 7. Continuity Wording Simplification

Current terms:

- Continuity
- Tasks
- Timeline
- Activity
- Running
- Stopped
- iterations
- chance
- schedule
- Run Now

Public replacements:

| Current label | Public replacement |
|---|---|
| Continuity | Progress |
| Activity | Recent activity |
| Timeline | Upcoming |
| Tasks | Automations |
| Running | Active |
| Stopped | Paused |
| iterations | steps |
| chance | likelihood |
| Run Now | Start now |
| Last run | Last activity |

Recommended public explanation:

> Progress shows what changed and what Sapphire is keeping track of.

Advanced-only:

- scheduler details
- chance
- iteration count
- task internals
- timeline debugging
- background execution logs

Governance:

- Continuity should not imply autonomous execution authority.
- Scheduled/background behavior must remain visible and operator-controlled.

## 8. Plugin / Settings Wording Cleanup

Plugin public wording:

| Current label | Public replacement |
|---|---|
| Plugins | Add-ons |
| Enable plugin | Enable add-on |
| Disable plugin | Disable add-on |
| Plugin settings | Add-on settings |
| Unsigned | Unverified |
| Tampered | Failed verification |
| Official | Official |
| Verified Author | Verified publisher |
| Rescan Plugins | Check for add-ons |
| Install | Add |
| Upload | Upload package |
| Check Update | Check for update |
| Tool Maker | Tool builder |

Settings public wording:

| Current label | Public replacement |
|---|---|
| LLM | AI provider |
| STT | Speech input |
| TTS | Voice output |
| Wakeword | Wake word |
| Embedding | Search memory index |
| Network | Connection |
| Tools | Capabilities |
| System | Advanced system |

Advanced-only:

- plugin install URL
- zip upload
- signature verification controls
- unsigned global toggle
- shell/SSH warnings
- manifest settings
- plugin hooks
- arbitrary tool creation

Governance:

- Public add-ons must show capability summaries.
- Restricted add-ons require operator gates.
- Installing must not imply activation.
- Activation must not imply execution.

## 9. Persona / Runtime Wording Cleanup

Persona public wording:

| Current label | Public replacement |
|---|---|
| Persona | Assistant style |
| Personas | Assistant styles |
| Prompt | Style prompt / Advanced prompt |
| Toolset | Capabilities |
| Spice | Tone |
| Default AI | Default assistant |
| Save As New Persona | Save as new style |
| Activate | Use this style |
| Set Default | Use by default |

Runtime public wording:

| Current label | Public replacement |
|---|---|
| Runtime | Workspace |
| System Prompt | Prompt Builder |
| Custom Context | Extra instructions |
| Provider | AI provider |
| Model | Model |
| Memory scope | Memory set |
| Knowledge scope | Knowledge set |
| Goal scope | Goal set |
| Story Engine | Story mode |

Advanced-only:

- prompt components
- monolith
- assembled
- token counts
- prompt privacy internals
- toolset function counts
- model override internals

Governance:

- Persona identity must not become operator identity.
- Persona style must not grant execution authority.
- Tool/capability expansion must be visible.

## 10. Chat vs Review vs Approved Action Wording

### Chat Mode

Current implied state:

- normal chat input
- `Type message...`
- `Connecting...`
- `Generating...`

Public wording:

- Mode: `Chat`
- Help line: `Ask anything. Controlled actions require review first.`
- Status: `Thinking...` or `Writing...`

Governance:

- Chat mode must not execute AXIS actions.
- Chat mode should not imply hidden routing.

### Review Action Mode

Current internal state:

- `tri`
- `/tri`
- `Tri-System`
- DES questions
- AXIS preview

Public wording:

- Mode: `Review Action`
- Question header: `A few questions`
- Result header: `Decision summary`
- Preview header: `Proposed Action`
- Prompt: `Review this action before anything happens.`

Governance:

- No execution in review mode.
- Pending action must be scoped and expire safely.

### Approved Action Mode

Current internal state:

- confirm
- AXIS execution
- AXIS result

Public wording:

- Mode: `Action Approved`
- Status: `Sending approved action...`
- Result header: `Action Result`
- Success line: `Completed through governed execution.`
- Failure line: `Action could not be completed. No retry was attempted.`

Governance:

- Confirm is one-shot.
- Reject cancels.
- Failure does not retry silently.
- Pending state clears after result/error.

## Advanced / Debug / Operator Visibility

The following should remain accessible, but only behind an intentional advanced/debug/operator boundary:

- DES health and response details
- AXIS payload and raw response
- operator identity resolver state
- plugin manifest and signature details
- prompt piece editor
- toolset function editor
- continuity scheduler internals
- runtime logs/traces
- restricted plugin controls
- legacy VANTA references

## Cleanup Priority

Recommended future implementation order:

1. Rename public labels without changing behavior.
2. Add explicit mode labels: Chat, Review Action, Action Approved.
3. Hide DES wording from public tri-flow.
4. Reframe AXIS as governed execution.
5. Collapse prompt/toolset/spice controls into Advanced.
6. Rename Plugins to Add-ons publicly.
7. Rename Persona to Assistant Style publicly.
8. Simplify Continuity to Progress/Activity.
9. Add debug/operator views for raw internals.

Every cleanup step must preserve:

- normal chat behavior
- explicit tri/review triggers
- confirmation before AXIS execution
- no DES edits
- no AXIS edits
- no payload contract changes
- no auto-execution

The terminology goal is not to hide power. It is to make power understandable before it is available.
