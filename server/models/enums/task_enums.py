from __future__ import annotations

from django.db import models


class TaskExecutionMode(models.TextChoices):
    """How a task definition is executed."""

    FUNCTION = "FUNCTION"
    SCRIPT = "SCRIPT"
    CHAIN = "CHAIN"  # sequential t1 -> t2 -> t3
    GROUP = "GROUP"  # parallel [a,b,c] -> join
    MAP = "MAP"


class TaskSchedulerStrategy(models.TextChoices):
    """Strategy used to schedule task calls."""

    INTERRUPT = "interrupt"
    QUEUE = "queue"
    MERGE = "merge"
    PARALLEL = "parallel"


class TaskType(models.TextChoices):
    """Classification of a task definition's purpose."""

    COMMAND = "COMMAND"  # user commands like /stop, /retry
    TASK = "TASK"  # normal function – core business logic
    TOOL = "TOOL"  # LLM-callable, optional bound/unbound
    WEBAPI = "WEBAPI"  # JSON API
    WEBVIEW = "WEBVIEW"  # HTML VIEW


class TaskCallStatus(models.TextChoices):
    """High-level status of an agent task call."""

    NEW = "NEW", "NEW"
    WAITING = "WAITING", "WAITING, will continue automatically"
    ACTIVE = "ACTIVE", "ACTIVE"
    HALTED = "HALTED", "HALTED, requires user interaction"
    ENDED = "ENDED", "ENDED"


class TaskCallStatusDetail(models.TextChoices):
    """Granular status detail for an agent task call."""

    NEW = "NEW", "NEW"

    WAITING_QUEUE = "WAITING_QUEUE", "Waiting for execution queue"
    WAITING_RETRY = "WAITING_RETRY", "Waiting for Retry time"
    WAITING_DEPENDENCY = "WAITING_DEPENDENCY", "Waiting for Parent DEPENDENCY tasks"
    WAITING_SUBTASKS_OR_HOOKS = "WAITING_SUBTASKS_OR_HOOKS", "Waiting for Sub-tasks"
    WAITING_RATELIMIT = "WAITING_RATELIMIT", "Waiting for Rate Limited"

    ACTIVE_QUEUED = "ACTIVE_QUEUED", "Queued"
    ACTIVE_RUNNING = "ACTIVE_RUNNING", "Running"

    HALTED_INPUT = "HALTED_INPUT", "Awaiting User Input"
    HALTED_APPROVAL = "HALTED_APPROVAL", "Awaiting User Approval"
    HALTED_STAGNATED = "HALTED_STAGNATED", "Step Limit Reached"
    HALTED_PAUSED = "HALTED_PAUSED", "Paused by User"

    ENDED_SUCCESS = "ENDED_SUCCESS", "Completed Successfully"
    ENDED_FAILURE_EXCEPTION = "ENDED_FAILURE_EXCEPTION", "Technical Failure"
    ENDED_FAILURE_LOGIC = "ENDED_FAILURE_LOGIC", "Logical/Quality Failure"
    ENDED_CANCELLED = "ENDED_CANCELLED", "Cancelled before launch"
    ENDED_STOPPED = "ENDED_STOPPED", "Stopped after launch"


class TaskRunStatus(models.TextChoices):
    """Status of a single execution attempt (run) of a task."""

    NEW = "NEW", "New"
    QUEUED = "QUEUED", "Queued"
    ACTIVE = "ACTIVE", "Active"
    WAITING_RESULTTASKS = "WAITING_RESULTTASKS", "Waiting for result tasks"
    RATE_LIMITED = "RATE_LIMITED", "Rate limited — waiting for LLM capacity"
    SUCCESS = "SUCCESS", "Success"
    FAILURE = "FAILURE", "Failure"
