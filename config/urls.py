from django.urls import path, include
from django.contrib import admin
import json
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.http.response import HttpResponse, JsonResponse, HttpResponseNotFound, HttpResponseBadRequest
from django.shortcuts import redirect
from server.models.tasks.agent_task_call import AgentTaskCall
from server.models.tasks.agent_task_run import AgentTaskRun
from server.models.enums.task_enums import TaskType, TaskCallStatusDetail
from server.models.sessions.session import SessionModel



@login_required
def home(request):
    """Default entry point: the server-rendered htmx UI."""
    return redirect("/app/")

urlpatterns = [
    path('', home, name='home'),
    path('app/', include('webui.urls')),
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('api/v1/', include('api.urls')),
]
