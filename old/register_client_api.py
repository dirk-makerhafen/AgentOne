import json
import secrets
from django.conf import settings
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone

from server.models.system import System, SystemStatus

@csrf_exempt
@require_POST
def register_client(request):
    try:
        data = json.loads(request.body)
        server_secret = data.get('server_secret')
        client_name = data.get('client_name')
        client_url = data.get('client_url')  # Optional
        client_port = data.get('client_port', '8123')  # Default port
    except json.JSONDecodeError:
        return HttpResponseBadRequest('Invalid JSON.')

    if not all([server_secret, client_name]):
        return HttpResponseBadRequest('Missing required parameters: server_secret, client_name.')

    # 1. Authenticate the request
    if not secrets.compare_digest(server_secret, str(settings.AGENT_SERVER_SECRET_KEY)):
        return HttpResponseForbidden('Invalid server secret.')

    # 2. Infer client_url if not provided
    resolved_client_url = client_url
    if not resolved_client_url:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            client_ip = x_forwarded_for.split(',')[0]
        else:
            client_ip = request.META.get('REMOTE_ADDR')

        if not client_ip:
            return HttpResponseBadRequest('Could not determine client IP address from request.')

        resolved_client_url = f"http://{client_ip}:{client_port}"

    # 3. Get or create the System (client) session
    system, created = System.objects.get_or_create(
        name=client_name,
        defaults={
            'description': f'Automatically registered client: {client_name}',
            'status': 'offline',
            'executor_mode': 'http',
            'platform_os': data.get('platform_os') # Add platform_os
        }
    )

    # 4. Provision API key
    if created or not system.executor_api_key:
        system.executor_api_key = secrets.token_urlsafe(32)

    # 5. Update the client's URL and save
    system.executor_url = resolved_client_url
    system.last_heartbeat = timezone.now()
    system.status = SystemStatus.ONLINE
    system.save()

    # 6. Return credentials and the resolved URL
    return JsonResponse({
        'client_name': system.name,
        'client_api_key': system.executor_api_key,
        'resolved_client_url': resolved_client_url
    })
