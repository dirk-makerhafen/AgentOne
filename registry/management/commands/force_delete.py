from typing import Any, Optional

from django.core.management.base import BaseCommand, CommandError

from server.models.agents.agent import AgentModel
from server.models.agents.agent_version import AgentVersionModel
from server.models.settings import SettingsModel
from server.models.tasks.task_instance import TaskInstance
from server.models.tasks.task_definition_version import TaskDefinitionVersion


class Command(BaseCommand):
    """Force-delete a model instance by primary key."""

    help = ""

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("model", type=str, help="name of model")
        parser.add_argument("pk", type=str, help="primary key")
        parser.add_argument(
            "--gte",
            type=bool,
            help="delete all models >= pk",
            default=False,
            required=False,
        )

    def handle(self, *args: Any, **options: Any) -> None:
        model: str = options["model"]
        pk: str = options["pk"]
        gte: bool = options["gte"]
        modelobj: Optional[Any] = None
        if model == "Agent":
            modelobj = AgentModel
        elif model == "SettingsModel":
            modelobj = SettingsModel
        elif model == "AgentVersion":
            modelobj = AgentVersionModel
        elif model == "TaskInstance":
            modelobj = TaskInstance
        elif model == "TaskDefinitionVersion":
            modelobj = TaskDefinitionVersion
        else:
            raise CommandError(f"Invalid model {model}")

        if gte is True:
            modelobj.objects.filter(pk__gte=pk).delete()
        else:
            modelobj.objects.get(pk=pk).delete()
