from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError

from . import repository as repo

router = APIRouter(prefix='/operations', tags=['operations'])
Kind = Literal['inventory_check', 'daily_report']


class RunInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Kind
    threshold: int = Field(default=20, ge=1, le=100000)
    idempotency_key: str = Field(min_length=1, max_length=128, pattern=r'^[A-Za-z0-9_:.-]+$')


class TodoInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: Literal['open', 'done']


class NotificationInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    is_read: Literal[True]


class ScheduleInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: bool
    daily_time: str = Field(pattern=r'^([01]\d|2[0-3]):[0-5]\d$')
    threshold: int = Field(default=20, ge=1, le=100000)


def call(function, *args):
    try:
        return function(*args)
    except SQLAlchemyError:
        raise HTTPException(503, detail='operations_storage_unavailable') from None


@router.get('/overview')
def overview():
    return call(repo.overview)


@router.get('/inventory')
def inventory(sku: str | None = Query(default=None, min_length=1, max_length=128),
              limit: int = Query(default=200, ge=1, le=500),
              threshold: int = Query(default=20, ge=1, le=100000)):
    return {'data_source': 'synthetic_demo', 'items': call(repo.inventory, sku, limit, threshold), 'threshold': threshold}


@router.post('/runs', status_code=202)
def create_run(body: RunInput):
    try:
        return call(repo.create_run, body.kind, body.threshold, body.idempotency_key)
    except ValueError:
        raise HTTPException(409, detail='idempotency_conflict') from None


@router.get('/runs')
def runs(limit: int = Query(default=20, ge=1, le=100)):
    return call(repo.list_rows, 'ops_automation_runs', repo.RUN_FIELDS, limit)


@router.get('/runs/{run_id}')
def run(run_id: str):
    item = call(repo.get_run, run_id)
    if item is None:
        raise HTTPException(404, detail='run_not_found')
    return item


@router.get('/todos')
def todos(limit: int = Query(default=100, ge=1, le=500)):
    return call(repo.list_rows, 'ops_automation_todos', '*', limit)


@router.patch('/todos/{todo_id}')
def patch_todo(todo_id: int, body: TodoInput):
    item = call(repo.patch_item, 'ops_automation_todos', todo_id, 'status', body.status)
    if item is None:
        raise HTTPException(404, detail='todo_not_found')
    return item


@router.get('/notifications')
def notifications(limit: int = Query(default=100, ge=1, le=500)):
    return call(repo.list_rows, 'ops_automation_notifications', '*', limit)


@router.patch('/notifications/{notification_id}')
def patch_notification(notification_id: int, body: NotificationInput):
    item = call(repo.patch_item, 'ops_automation_notifications', notification_id, 'is_read', body.is_read)
    if item is None:
        raise HTTPException(404, detail='notification_not_found')
    return item


@router.get('/schedules')
def schedules():
    return call(repo.list_rows, 'ops_automation_schedules')


@router.put('/schedules/{kind}')
def schedule(kind: Kind, body: ScheduleInput):
    return call(repo.save_schedule, kind, body.enabled, body.daily_time, body.threshold)
