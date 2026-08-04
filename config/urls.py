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
from server.models.sessions.session import SessionModel
from ui.app_view import ui

#@login_required
@csrf_exempt # Only if not sending a CSRF token from the frontend
def agent_webapi_call(request, instance_id:int, method:str):
    print("agent_webapi_callagent_webapi_call")
    if request.method == 'GET':
        kwargs = request.GET.dict()
    elif request.method == 'POST':
        try:
            kwargs = json.loads(request.body)
        except json.JSONDecodeError:
            print("INVALIUD JSON")
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
    else:
        print("INVALIUD GET/POST")
        return HttpResponseBadRequest("GET|POST")
        
    try:
        session = SessionModel.objects.get(pk=int(instance_id))
    except:
        print("no agent_instance")
        return HttpResponseNotFound()
    session_version = session.latest_session_version
    rt = session_version.get_runtime()
    if not session_version.agent_version.task_definitions.filter(name=method, task_type=TaskType.WEBAPI).exists():
        print("NO WEBAPI")
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
        agent_instance = SessionModel.objects.get(pk=instance_id)
    except:
        return HttpResponseNotFound("session not found")
    session_version = agent_instance.latest_session_version
    if not session_version.agent_version.task_definitions.filter(name=method, task_type=TaskType.WEBVIEW).exists():
        return HttpResponseNotFound("method not found")
    rt = session_version.get_runtime()
    return HttpResponse(getattr(rt, method).func(rt, **kwargs))


urlpatterns = [
    path('', ui, name='ui'),
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('api/v1/', include('api.urls')),
    path('view/<instance_id>/<method>', agent_webapi_view    , name='agent_webapi_view'),
    path('call/<instance_id>/<method>', agent_webapi_call    , name='agent_webapi_call'),
    path('result/<call_id>'           , agent_webapi_response, name='agent_webapi_response'),
] + static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
