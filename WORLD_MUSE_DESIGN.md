# World Muse Design

## Purpose

World Muse is a GUI-first story development assistant. It guides a user through structured, wizard-style interviews to capture story intent, setting, characters, and plot signals, then uses connected tools to refine and persist that information.

The app does not replace WorldCodex, StoryCodex, or agent_foundry. It orchestrates them:

- `agent_foundry`: generate adaptive, high-quality questions and follow-up prompts.
- `worldcodex`: store world canon, setting details, entities, and relationships.
- `storycodex`: build and maintain story structure and outline artifacts.

## Product Goals (Initial Scope)

1. Deliver a stable NiceGUI shell with a four-panel workspace.
2. Deliver a mock "Create Setting" wizard to validate UX and data capture flow.
3. Integrate `agent_foundry` enough to connect to an LLM and support AI-guided wizard prompts.
4. Integrate `storycodex` enough to generate/persist a structured story outline from collected answers.

No direct prose generation is required in this phase. The focus is guided capture + structure building.

## User Workflow (Phase 1-4)

1. User launches app and selects global parameters (project/world/provider/model).
2. User launches `Create Setting` wizard.
3. Wizard asks one question at a time and stores answers in local session state.
4. User submits wizard answers.
5. App persists captured data and updates left-panel story structure view.
6. Later milestones replace static questions with AI-generated questions and push structured outputs into StoryCodex (and world references in WorldCodex).

## UI Layout

The app uses a four-panel layout:

1. Top Panel (narrow horizontal)
   - App-level controls and current context:
     - Current Story Project
     - Current World
     - LLM Provider
     - LLM Model
     - Test LLM Connection button
     - Launch wizard controls (starting with `Create Setting`)

2. Left Panel (structure tree)
   - Story structure outline and captured assets:
     - Story premise
     - Setting
     - Characters
     - Plot spine / acts / chapters (as available)
   - Clicking a node refreshes right panel details.

3. Right Panel (detail view)
   - Displays selected node details:
     - summary text
     - captured fields
     - source metadata (wizard/manual/imported)

4. Bottom Panel (status rail)
   - Timestamped status messages:
     - Info (blue/green)
     - Warning (amber)
     - Error (red)

## Architecture

## Application Layers

1. UI Layer (NiceGUI)
   - Layout, controls, wizard dialog, tree view, detail rendering.

2. State Layer
   - In-memory session state for active wizard.
   - Persisted app settings and project data references.

3. Service Layer
   - `agent_foundry` adapter (LLM connection + question generation).
   - `storycodex` adapter (outline generation/update).
   - `worldcodex` adapter (world lookup/write hooks where needed).

4. Command Runner
   - Structured subprocess execution wrapper:
     - command argv
     - working directory
     - timeout
     - stdout/stderr/return code/duration.

## Data Ownership

- World canon and setting atoms live in WorldCodex.
- Story structure artifacts live in StoryCodex.
- World Muse stores:
  - GUI settings
  - wizard session answers
  - mappings between wizard outputs and external artifact IDs/paths.

## Suggested Project Files

For implementation planning (not yet created):

- `src/world_muse/main.py` (NiceGUI app entry)
- `src/world_muse/config.py` (settings load/save)
- `src/world_muse/state.py` (UI/session state models)
- `src/world_muse/runner.py` (subprocess command runner)
- `src/world_muse/status.py` (status message model/log)
- `src/world_muse/adapters/agent_foundry.py`
- `src/world_muse/adapters/storycodex.py`
- `src/world_muse/adapters/worldcodex.py`
- `src/world_muse/wizards/setting_wizard.py`
- `config/app_settings.json`
- `config/wizard_templates.json`

## Milestone Plan

## Milestone 1: NiceGUI Shell + Four Panels

### Goal
Create the application shell and static layout with functional panel interactions.

### Scope
- Initialize project packaging and NiceGUI entrypoint.
- Render four-panel layout exactly as specified.
- Add top-panel placeholder controls for world/provider/model.
- Add left panel with placeholder story tree nodes.
- Add right panel placeholder that updates on left node click.
- Add bottom status panel with color-coded message rendering.
- Add settings load/save for top panel selections.

### Acceptance Criteria
- App launches and renders four distinct panels.
- Left-node click updates right detail panel.
- Top control changes persist across restarts.
- Status messages render with Info/Warning/Error styling.

### Tests
- Settings persistence unit tests.
- Basic import/startup test.
- Tree selection state test.

## Milestone 2: Mock "Create Setting" Wizard

### Goal
Validate wizard UX and answer capture flow with static sample questions.

### Scope
- Add `Create Setting` action in top panel.
- Open modal dialog with 5 predefined questions.
- Show one question at a time.
- Provide:
  - `Prev` button
  - `Next` button
  - `Submit` button on final question
- Capture per-question text response in session state.
- On submit:
  - close modal
  - write summary node to left panel under `Setting`
  - post success status message.

### Acceptance Criteria
- Wizard navigation works with no index errors.
- Answers persist while moving back/forward.
- Submit only enabled on final step (or only shown there).
- Submitted answer bundle visible in right detail panel when selecting Setting node.

### Tests
- Wizard navigation logic unit tests.
- Response capture tests.
- Submit result/state mutation tests.

## Milestone 3: agent_foundry LLM Connection

### Goal
Replace static-only wizard mode with AI-capable question generation plumbing.

### Scope
- Add `agent_foundry` adapter with command execution wrapper.
- Add provider/model controls and `Test LLM Connection` action wired to `agent_foundry`.
- Add fallback mode:
  - if connection fails, wizard uses static template questions.
- Add a simple AI question mode for setting wizard:
  - generate next question based on prior answers and wizard goal.
  - keep deterministic guardrails (max question length, no empty output).

### Acceptance Criteria
- User can test provider/model connection from top panel.
- Successful connection reports Info status.
- Failed connection reports Error with stderr detail.
- Wizard can operate in static mode when AI mode fails.
- At least one AI-generated follow-up question appears when connection is valid.

### Tests
- Adapter command assembly tests.
- Connection success/failure behavior tests.
- Fallback-to-static tests.

## Milestone 4: StoryCodex Integration for Outline Construction

### Goal
Use captured wizard data to create/update structured story outline artifacts in StoryCodex.

### Scope
- Add `storycodex` adapter for selected commands (initial minimal surface):
  - workspace init/check
  - story spec/seed apply
  - plot/spine/scenes planning entrypoints
- Define mapping from wizard answer bundle to StoryCodex input structures.
- Add action from UI to "Build Outline" from captured data.
- Update left panel tree from returned StoryCodex artifacts (acts/chapters/scenes summary).
- Persist artifact references in local project metadata.

### Acceptance Criteria
- User can trigger outline construction after wizard submission.
- StoryCodex command execution results are displayed in status panel.
- Left panel shows generated structure nodes from StoryCodex output.
- Right panel displays selected structure item details.

### Tests
- Mapping transform tests (wizard answers -> StoryCodex input).
- Adapter command tests with fake runner.
- Structure-tree hydration tests from StoryCodex outputs.

## Milestone 5 (Planning Stub): WorldCodex Write-Back + Multi-Wizard Foundation

This milestone is out of current requested scope for implementation, but should be prepared in design:

- Add write-back hooks for setting/character entities into WorldCodex.
- Add wizard framework reusable by future wizards (Character, Factions, History, Relationships).
- Add provenance tracking for which wizard response produced which external artifact change.

## Configuration

## `config/app_settings.json`

Suggested fields:

- `current_project_root`
- `current_world`
- `provider`
- `model`
- `tools.agent_foundry.executable`
- `tools.storycodex.executable`
- `tools.worldcodex.executable`
- per-tool working directories

## `config/wizard_templates.json`

Initial use:
- static question templates for Setting wizard.

Later use:
- prompt skeletons for AI-generated question strategies.

## Error Handling Strategy

- All external tool calls return structured result objects.
- Non-zero return codes are never silent.
- Status panel always includes command context and first error line.
- Wizard submission path validates required answers before external calls.

## Non-Goals (Current Phase)

- Full prose drafting/editor.
- Rich timeline or graph visualizations.
- Collaborative multi-user editing.
- Deep automated canon reconciliation in GUI.

## Risks and Mitigations

1. Tool command surface drift
   - Mitigation: keep adapters narrow, version-checked, and config-driven.

2. LLM instability/latency
   - Mitigation: timeout controls, retry policy, static fallback mode.

3. Inconsistent data mapping into StoryCodex
   - Mitigation: explicit schema validation before command submission.

4. UX confusion in wizard progression
   - Mitigation: single-question stepper, clear progress indicator, explicit submit confirmation.

## Milestone Exit Summary

- M1 exits with a stable GUI shell.
- M2 exits with fully testable mock wizard flow.
- M3 exits with reliable AI connection + fallback behavior.
- M4 exits with StoryCodex-backed outline generation visible in GUI structure panel.

