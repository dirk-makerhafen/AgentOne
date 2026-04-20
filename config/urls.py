from django.urls import path, include
from django.contrib import admin
import json
from django.conf import settings
from django.conf.urls.static import static
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.http.response import HttpResponse, JsonResponse, HttpResponseNotFound, HttpResponseBadRequest
from server.models.tasks.agent_task_call import AgentTaskCall
from server.models.tasks.agent_task_run import AgentTaskRun
from server.models.enums.task_enums import TaskType, TaskCallStatusDetail
from server.models.agents.agent_instance import AgentInstance
from old.register_client_api import register_client
from ui.app_view import ui

@login_required
@csrf_exempt # Only if not sending a CSRF token from the frontend
def agent_webapi_call(request, instance_id:int, method:str):
    if request.method == 'GET':
        kwargs = request.GET.dict()
    elif request.method == 'POST':
        try:
            kwargs = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
    else:
        return HttpResponseBadRequest("GET|POST")
        
    try:
        agent_instance = AgentInstance.objects.get(pk=instance_id)
    except:
        return HttpResponseNotFound()
    agent_instance_version = agent_instance.latest_agent_instance_version
    rt = agent_instance_version.get_runtime_instance()
    if not agent_instance_version.agent_version.task_definitions.filter(name=method, task_type=TaskType.WEBAPI).exists():
        return HttpResponseNotFound()
    agent_task_call:AgentTaskCall = getattr(rt, method).delay(**kwargs)
    return JsonResponse({
        "call_id": agent_task_call.pk, 
        "status": agent_task_call.status_detail,
        "result_url": f'http{"s" if request.is_secure() else ''}://{request.get_host()}/result/{agent_task_call.pk}',
    })

@login_required
def agent_webapi_response(request, call_id:int):
    try:
        agent_task_call = AgentTaskCall.objects.get(pk=int(call_id))
    except:
        return HttpResponseNotFound()
    response_data = { "call_id": agent_task_call.pk, "status": agent_task_call.status_detail}
    try:
        response_data["result"] = agent_task_call.get_result(timeout=0)
    except TimeoutError:
        pass
    return JsonResponse(response_data)


@login_required
@csrf_exempt # Only if not sending a CSRF token from the frontend
def agent_webapi_view(request, instance_id:int, method:str):
    if request.method == 'GET':
        kwargs = request.GET.dict()
    elif request.method == 'POST':
        try:
            kwargs = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
    else:
        return HttpResponseBadRequest("GET|POST")
        
    try:
        agent_instance = AgentInstance.objects.get(pk=instance_id)
    except:
        return HttpResponseNotFound("instance not found")
    agent_instance_version = agent_instance.latest_agent_instance_version
    if not agent_instance_version.agent_version.task_definitions.filter(name=method, task_type=TaskType.WEBVIEW).exists():
        return HttpResponseNotFound("method not found")
    rt = agent_instance_version.get_runtime_instance()
    return HttpResponse(getattr(rt, method).func(rt, **kwargs))

urlpatterns = [
    path('', ui, name='ui'),
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('view/<instance_id>/<method>', agent_webapi_view    , name='agent_webapi_view'),
    path('call/<instance_id>/<method>', agent_webapi_call    , name='agent_webapi_call'),
    path('result/<call_id>'           , agent_webapi_response, name='agent_webapi_response'),
    path('register_client/'           , register_client      , name='register_client'),
] + static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
