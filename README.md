# Sapphire System — VANTA Execution Engine

A task execution system built on [Sapphire](https://github.com/ddxfish/sapphire), powering the VANTA AI platform.

## What This Is

Sapphire extended with **System V1** — a deterministic task execution engine that converts intent into structured, trackable, step-based action.

## System V1

- Converts raw input into structured task objects
- Classifies tasks and assigns execution routes
- Breaks tasks into ordered steps
- Tracks state transitions (pending → active → complete)
- Returns one clear next action at all times

## REST API

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/tasks/create` | Create a task |
| GET | `/api/v1/tasks/recent` | Get recent tasks |
| GET | `/api/v1/tasks/{task_id}` | Get task by ID |
| POST | `/api/v1/tasks/start` | Activate a task |
| POST | `/api/v1/tasks/step` | Update a step |
| POST | `/api/v1/tasks/block` | Block a task |
| POST | `/api/v1/tasks/complete` | Complete a task |

## Plugin Tools

`create_task_plan` · `update_step_status` · `get_recent_tasks` · `start_task` · `block_task` · `complete_task`

## Architecture
VANTA (decision layer)
↓ HTTP
Sapphire + System V1 (execution layer)
↓
Task objects → step tracking → state persistence

## Setup
```bash
conda activate sapphire
python main.py
# Runs at https://localhost:8073
```

## System V1 Status

VERSION: V1.0 · STATUS: LOCKED · DATE: 2026-04-04
