from pathlib import Path

Path("core/routes").mkdir(parents=True, exist_ok=True)

content = """from fastapi import APIRouter, HTTPException, Query
from core.system_v1.service import (
    create_task_plan,
    get_recent_tasks,
    get_task,
    start_task,
    update_step_status,
    block_task,
    complete_task,
)

router = APIRouter(prefix="/api/v1/tasks", tags=["system_v1"])


@router.post("/create")
def create_task(payload: dict):
    try:
        return create_task_plan(
            task=payload.get("task", ""),
            goal=payload.get("goal", ""),
            constraints=payload.get("constraints", []),
            urgency=payload.get("urgency", "normal"),
            route_override=payload.get("route_override"),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/recent")
def recent_tasks(limit: int = Query(default=10, ge=1, le=100)):
    return get_recent_tasks(limit=limit)


@router.get("/{task_id}")
def read_task(task_id: str):
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/start")
def start_route(payload: dict):
    r = start_task(
        task_id=payload.get("task_id", ""),
        note=payload.get("note", ""),
    )
    if "error" in r:
        raise HTTPException(status_code=404, detail=r["error"])
    return r


@router.post("/step")
def step_route(payload: dict):
    r = update_step_status(
        task_id=payload.get("task_id", ""),
        step_id=payload.get("step_id", ""),
        new_status=payload.get("new_status", ""),
        note=payload.get("note", ""),
    )
    if "error" in r:
        raise HTTPException(status_code=404, detail=r["error"])
    return r


@router.post("/block")
def block_route(payload: dict):
    r = block_task(
        task_id=payload.get("task_id", ""),
        note=payload.get("note", ""),
    )
    if "error" in r:
        raise HTTPException(status_code=404, detail=r["error"])
    return r


@router.post("/complete")
def complete_route(payload: dict):
    r = complete_task(
        task_id=payload.get("task_id", ""),
        note=payload.get("note", ""),
    )
    if "error" in r:
        raise HTTPException(status_code=404, detail=r["error"])
    return r
"""

Path("core/routes/system_v1_api.py").write_text(content, encoding="utf-8")
print("system_v1_api.py written")
