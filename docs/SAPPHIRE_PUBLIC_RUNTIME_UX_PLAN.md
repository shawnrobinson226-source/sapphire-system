# Sapphire Public Runtime / UX Architecture Plan

Status: planning document only.

This document defines a public-facing runtime and UX direction for Sapphire. It does not implement UI changes, alter runtime behavior, modify plugins, or change DES/AXIS integration.

Locked system law:

- Sapphire displays and orchestrates.
- DES classifies and decides.
- AXIS governs execution.
- Operator authorizes.

## 1. Public-Facing Runtime Philosophy

Sapphire should feel approachable, useful, and trustworthy before it feels technical.

Public runtime should emphasize:

- clear conversation
- guided next steps
- visible confirmation before action
- safe defaults
- plain explanations
- no hidden execution
- no pressure to understand internal architecture

The public user should not need to know the internal names of every subsystem. They should understand what is happening, what Sapphire is asking permission to do, and what happens next.

## 2. How Sapphire Should Present Itself Publicly

Sapphire should present itself as:

- a guided assistant interface
- a place to think, plan, and review actions
- a display and coordination layer
- a system that asks before doing anything consequential

Public positioning:

> Sapphire helps you turn thoughts into clear next steps, shows you what it plans to do, and asks before anything important happens.

Sapphire should not present itself as:

- an autonomous operator
- an authority over the user
- a hidden decision engine
- a system that executes without review
- a mystical or unknowable intelligence

## 3. How AXIS Should Be Explained Publicly

AXIS should be described as the governed execution layer.

Plain-language explanation:

> AXIS is the safety and execution layer. When an action is ready, AXIS handles the governed execution after you approve it.

Public-facing AXIS language should focus on:

- governed action
- controlled execution
- confirmation
- continuity
- outcome tracking

Avoid implying AXIS is a personality, persona, or assistant identity. AXIS is governance infrastructure, not a chat character.

## 4. How DES Should Remain Mostly Invisible Infrastructure

DES should remain mostly invisible to public users.

Public explanation when needed:

> Sapphire may use an internal decision helper to organize what kind of action is being proposed.

DES should not be front-and-center in beginner UX because its role is technical and easy to over-explain.

DES should be visible only when:

- debugging
- advanced mode is enabled
- explaining why a proposed action has a certain category
- showing transparent system flow to technical operators

DES should not be framed as a user-facing persona or authority.

## 5. How Tri-Flow Should Be Explained To Users

Tri-flow should be described as a review-before-action path.

Plain-language explanation:

> When a message needs controlled execution, Sapphire turns it into a proposed action, shows you the details, and waits for you to approve or reject it.

Simple public flow:

1. You ask for something.
2. Sapphire prepares a proposed action.
3. You review it.
4. You approve or reject.
5. Approved actions are executed through AXIS.

Developer/internal flow may still be documented as:

> Sapphire Web -> DES -> AXIS Preview -> Operator Confirm/Reject -> AXIS Execute -> Sapphire Result

The public UI should use the simpler explanation first.

## 6. Public Onboarding Flow

Recommended beginner onboarding:

1. Welcome
   - Explain Sapphire in one sentence.
   - Do not mention every subsystem.

2. Choose a style
   - Let user select a public-safe persona or default assistant style.

3. Explain safe action review
   - Tell user Sapphire asks before actions that matter.

4. Start in chat mode
   - Let user type normally.

5. Show first proposed action only when needed
   - Teach confirmation in context, not as a long setup lecture.

6. Offer advanced details later
   - DES/AXIS details belong behind "Learn more" or advanced mode.

Onboarding should not require understanding plugins, prompt pieces, governance layers, or internal runtime terms.

## 7. Runtime-Safe Terminology

Recommended public terms:

- Chat
- Proposed Action
- Review
- Confirm
- Reject
- Approved
- Not approved
- Safe mode
- Action history
- Continuity
- Session
- Outcome
- Controlled execution
- Assistant style
- Add-on
- Capability

Recommended advanced/operator terms:

- Tri-System
- DES
- AXIS
- payload preview
- operator gate
- classification
- governed execution
- plugin capability
- restricted action

## 8. Terms To Avoid Publicly

Avoid using these terms in beginner/public UX:

- friction classifier
- governance engine
- payload
- operator identity
- execution authority
- autonomous routing
- semantic routing
- VANTA
- doctrine
- sovereign system
- runtime mutation
- hidden state
- prompt self-editing
- meta tools
- shell execution
- critical-risk plugin

These terms can exist in developer docs, but beginner UX should translate them into plain action language.

## 9. Continuity Explained Simply

Continuity should be explained as memory of progress, not as mystical persistence.

Plain-language explanation:

> Continuity helps Sapphire keep track of what changed during a session so progress is visible over time.

Good public labels:

- Before
- After
- Progress
- Session result
- What changed

Avoid:

- metaphysical framing
- consciousness framing
- destiny/prophecy language
- opaque scores without explanation

Continuity values should be shown only when they help the user understand an outcome.

## 10. Confirmation / Authority In UX

Confirmation should appear as a clear review step, not a technical modal full of internal fields.

Required UX elements:

- title: "Proposed Action"
- plain-language summary
- visible classification/category when useful
- visible next action
- Confirm button
- Reject button
- short explanation that rejecting cancels the action

Authority message:

> Nothing is executed until you confirm.

Confirmation should be:

- explicit
- one-shot
- scoped to the current proposed action
- visually distinct from normal chat
- impossible to confuse with a normal assistant reply

Reject should be as safe and visible as Confirm.

## 11. Runtime Modes

### Chat Mode

Chat mode is normal conversation.

Behavior:

- user sends a message
- Sapphire responds normally
- no governed execution occurs
- no AXIS call occurs
- no tri-flow starts unless explicitly triggered or intentionally invoked by an approved UX control

Public label:

> Chat

### Tri Mode

Tri mode is review-before-action preparation.

Behavior:

- Sapphire prepares a proposed action
- DES may classify behind the scenes
- Sapphire shows a preview
- user must confirm or reject
- no execution happens yet

Public label:

> Review Action

### Execution-Confirmed Mode

Execution-confirmed mode begins only after the user confirms.

Behavior:

- Sapphire sends the approved action to AXIS
- AXIS executes under governance
- Sapphire renders the result
- pending confirmation is cleared

Public label:

> Action Approved

The UI should make mode transitions obvious:

- Chat -> Review Action
- Review Action -> Approved Result
- Review Action -> Cancelled

## 12. Public-Safe Plugin Visibility Model

Public plugin visibility should be capability-based.

Recommended layers:

1. Public Add-ons
   - safe, low-risk, readable descriptions
   - no hidden write/execute capability

2. Advanced Add-ons
   - require visible capability review
   - may use network, memory, or workspace context

3. Restricted Add-ons
   - require operator gating
   - not shown by default to beginners

4. Internal Tools
   - developer/operator only
   - hidden from public runtime

5. Quarantined
   - disabled, inspection only

Public users should see what a plugin can do before enabling it.

## 13. Runtime Trust / Safety Messaging

Trust messaging should be calm and concrete.

Recommended messages:

- "Sapphire asks before taking controlled actions."
- "You can review or reject proposed actions."
- "Add-ons declare what they can access."
- "Restricted actions require confirmation."
- "Normal chat does not execute AXIS actions."

Avoid fear-heavy warnings unless risk is genuinely high. The product should feel trustworthy, not alarming.

## 14. Beginner-Safe Runtime Defaults

Recommended beginner defaults:

- normal chat mode first
- public-safe persona
- low-risk toolset
- no shell execution
- no prompt self-editing
- no smart-home control
- no email send
- no AXIS execution unless explicitly triggered and confirmed
- no semantic plugin routing
- no autonomous background tasks

Recommended default persona options:

- `generic`
- `sapphire`
- `eddie`

Recommended hidden-by-default areas:

- internal operational personas
- restricted plugins
- meta tools
- shell/file tools
- legacy VANTA tools
- tri-system debug internals

## 15. UX Principles

### Clarity Over Mystique

Use plain language. Let the system feel powerful because it is understandable.

### Interruption Over Overload

Interrupt the user only when a meaningful decision is needed. Do not front-load every technical detail.

### One Next Step

At each moment, the user should know the next available action:

- send a message
- review proposed action
- confirm
- reject
- read the result

### Visible Governance

Governance should be seen at the moment it matters:

- before execution
- before permission expansion
- before risky plugin activation
- before state-changing actions

### Explicit Execution Approval

Execution must require a deliberate approval action. Approval should never be inferred from silence, persona choice, plugin installation, or normal chat.

## 16. Recommended Future Homepage / Runtime Positioning

Homepage positioning:

> Sapphire is a governed AI workspace for conversation, planning, and controlled execution.

Short version:

> Think clearly. Review actions. Stay in control.

Public value points:

- Conversational by default.
- Shows proposed actions before execution.
- Keeps technical systems behind a clear interface.
- Lets users approve or reject controlled actions.
- Supports add-ons with visible capabilities.

Avoid leading with:

- DES internals
- AXIS taxonomy
- plugin manifests
- governance jargon
- legacy VANTA naming
- autonomous execution claims

Recommended first-screen runtime:

- visible chat input
- current mode label
- simple persona/style selector
- clear "Review Action" state when needed
- no dense control panels by default

## Public Runtime Summary

Sapphire should make advanced governance feel simple:

- normal chat stays normal
- proposed actions are visible
- approval is explicit
- execution is governed
- technical layers stay available without overwhelming beginners

The public experience should invite trust through clarity, not mystique.
