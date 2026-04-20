from django.db import models

class TaskExecutionMode(models.TextChoices):
    INTERRUPT = "interrupt"
    QUEUE = "queue"
    MERGE = "merge"
    PARALLEL = "parallel"


class TaskType(models.TextChoices):
    # User-facing / invocation roots
    CHAT   = "CHAT"          # main interaction path, top-level input
    COMMAND = "COMMAND"      # user commands like /stop, /retry
    
    # Executable units inside flows
    TASK    = "TASK"         # normal function – core business logic
    TOOL    = "TOOL"         # LLM-callable, optional bound/unbound
    
    # Flow controllers (Celery-equivalents)
    CHAIN   = "CHAIN"        # sequential t1 -> t2 -> t3
    GROUP   = "GROUP"        # parallel [a,b,c] -> join
    CHORD   = "CHORD"        # group + final callback
    MAP     = "MAP"        #

    WEBAPI  = "WEBAPI"  # JSON API
    WEBVIEW = "WEBVIEW" # HTML VIEW
    # System hooks and callbacks (currently not in use)
    #HOOK     = "HOOK"         # intercept execution – must pass value forward
    #EVENT    = "EVENT"        # triggered by runtime state, not calls
    #SETUP    = "SETUP"        # called on registration/version change
    #INSTANCE = "INSTANCE"     # called on agent instanciation, init subagents and stuff


class TaskCallStatus(models.TextChoices):
    NEW = 'NEW', 'NEW'
    WAITING = 'WAITING', 'WAITING, will continue automatically'
    ACTIVE = 'ACTIVE', 'ACTIVE'
    HALTED = 'HALTED', 'HALTED, requires user interaction'
    ENDED = 'ENDED', 'ENDED'

class TaskCallStatusDetail(models.TextChoices):
    # Not yet fully created
    NEW = 'NEW', 'NEW'

    # WAITING ( will continue automatically)
    WAITING_QUEUE  = 'WAITING_QUEUE', 'Waiting for execution queue'
    WAITING_RETRY = 'WAITING_RETRY', 'Waiting for Retry time'
    WAITING_DEPENDENCY = 'WAITING_DEPENDENCY', 'Waiting for Parent DEPENDENCY tasks'
    WAITING_SUBTASK = 'WAITING_SUBTASK', 'Waiting for Sub-tasks'
    WAITING_RATELIMIT = 'WAITING_RATELIMIT', 'Waiting for Rate Limited'

    # ACTIVE
    ACTIVE_QUEUED = 'ACTIVE_QUEUED', 'Queued'
    ACTIVE_RUNNING = 'ACTIVE_RUNNING', 'Running'

    # HALTED (requires user intervention or logic change)
    HALTED_INPUT = 'HALTED_INPUT', 'Awaiting User Input'
    HALTED_APPROVAL = 'HALTED_APPROVAL', 'Awaiting User Approval'
    HALTED_STAGNATED = 'HALTED_STAGNATED', 'Step Limit Reached'
    HALTED_PAUSED = 'HALTED_PAUSED', 'Paused by User'

    # Result Details (used for Terminal statuses)
    ENDED_SUCCESS = 'ENDED_SUCCESS', 'Completed Successfully'
    ENDED_FAILURE_EXCEPTION = 'ENDED_FAILURE_EXCEPTION', 'Technical Failure'
    ENDED_FAILURE_LOGIC = 'ENDED_FAILURE_LOGIC', 'Logical/Quality Failure'
    ENDED_CANCELLED = 'ENDED_CANCELLED', 'Cancelled before launch'
    ENDED_STOPPED = 'ENDED_STOPPED', 'Stopped after launch'


class TaskRunStatus(models.TextChoices):
    NEW                  = 'NEW',                  'New'
    QUEUED               = 'QUEUED',               'Queued'
    ACTIVE               = 'ACTIVE',               'Active'
    WAITING_RESULTTASKS  = 'WAITING_RESULTTASKS',  'Waiting for result tasks'
    RATE_LIMITED         = 'RATE_LIMITED',         'Rate limited — waiting for LLM capacity'
    SUCCESS              = 'SUCCESS',              'Success'
    FAILURE              = 'FAILURE',              'Failure'
 