from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter

from server.models.sessions.session import SessionModel
from server.models.sessions.session_version import SessionVersionModel
from server.models.agents.agent import AgentModel
from server.models.message import Message
from api.serializers.sessions import (
    SessionListSerializer, SessionDetailSerializer, SessionWriteSerializer,
    MessageSerializer, SessionVersionSerializer,
)
from api.serializers.agents import TaskDefinitionVersionSerializer


class SessionViewSet(viewsets.ModelViewSet):
    queryset = SessionModel.objects.all().order_by('-created_at')
    permission_classes = [IsAuthenticated]
    ordering = ['-created_at']
    filterset_fields = ['name', 'is_active', 'is_archived']
    search_fields = ['name']

    def get_serializer_class(self):
        if self.action == 'list':
            return SessionListSerializer
        if self.action in ('create', 'partial_update', 'update'):
            return SessionWriteSerializer
        return SessionDetailSerializer

    def create(self, request, *args, **kwargs):
        serializer = SessionWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        agent_id = serializer.validated_data['agent_id']
        name = serializer.validated_data.get('name', '')

        try:
            agent_model = AgentModel.objects.get(pk=agent_id)
        except AgentModel.DoesNotExist:
            return Response({'error': 'Agent not found'}, status=status.HTTP_404_NOT_FOUND)

        session = SessionModel.objects.create(name=name or f'session-{agent_model.name}')
        SessionVersionModel.objects.create(
            session=session,
            agent=agent_model,
            version_number=0,
        )
        session.latest_session_version = session.related_session_versions.first()
        session.save(update_fields=['latest_session_version'])

        detail_serializer = SessionDetailSerializer(session)
        return Response(detail_serializer.data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        session_model = self.get_object()
        try:
            rt = session_model.get_runtime()
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        data = request.data
        if 'name' in data:
            session_model.name = data['name']
            session_model.save(update_fields=['name'])
            from runtime.events import publish_model_event
            publish_model_event(session_model, "update")

        settings_map = {
            'aimodel': 'set_aimodel',
            'reasoning_effort': 'set_reasoning_effort',
            'scheduler_strategy': 'set_scheduler_strategy',
            'tool_call_syntax': 'set_tool_call_syntax',
            'subagentResultDelivery': 'set_subagentResultDelivery',
            'max_retries': 'set_max_retries',
            'max_turns': 'set_max_turns',
            'max_unattended_turns': 'set_max_unattended_turns',
            'precision': 'set_precision',
            'max_history_messages': 'set_max_history_messages',
            'priority': 'set_priority',
        }
        for field, method_name in settings_map.items():
            if field in data and data[field] is not None:
                try:
                    getattr(rt, method_name)(data[field])
                except Exception:
                    pass

        detail_serializer = SessionDetailSerializer(session_model)
        return Response(detail_serializer.data)

    @action(detail=True, methods=['post'])
    def message(self, request, pk=None):
        session_model = self.get_object()

        parts = request.data.get('parts')
        content = request.data.get('content')

        if parts is not None:
            if not isinstance(parts, list) or not parts:
                return Response({'error': 'parts must be a non-empty list'},
                                status=status.HTTP_400_BAD_REQUEST)
            message_parts = parts
        elif content:
            # TODO this might need content_type, ai: double check
            message_parts = [{'type': 'text', 'content': content}]
        else:
            return Response({'error': 'Provide either "content" (string) or "parts" (list of dicts)'},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            rt = session_model.get_runtime()
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = rt.add_user_message(message_parts)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        from api.serializers.queries import QueryDetailSerializer
        return Response(QueryDetailSerializer(result).data, status=status.HTTP_201_CREATED)

    @action(detail=True)
    def messages(self, request, pk=None):
        session_model = self.get_object()
        try:
            rt = session_model.get_runtime()
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        qs = rt.get_messages().order_by('created_at')
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = MessageSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = MessageSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True)
    def tasks(self, request, pk=None):
        session_model = self.get_object()
        try:
            rt = session_model.get_runtime()
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        data = []
        for tdv in rt.allowedTasks:
            data.append({
                'id': tdv.id,
                'name': tdv.task_definition.name if tdv.task_definition else '',
                'description': tdv.description,
                'task_type': tdv.task_type,
                'function_name': tdv.function_name,
                'requires_approval': tdv.requires_approval,
                'bound': tdv.bound,
            })
        return Response(data)

    @extend_schema(parameters=[OpenApiParameter('task_name', str, description='Task, tool, or command name', location='path')], request=dict, responses={201: dict})
    @action(detail=True, methods=['post'], url_path='call/(?P<task_name>[^/.]+)')
    def call_task(self, request, pk=None, task_name=None):
        session_model = self.get_object()
        try:
            rt = session_model.get_runtime()
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        bound_task = rt.get_task(task_name) or rt.get_tool(task_name) or rt.get_command(task_name)
        if not bound_task:
            return Response({'error': f'Task "{task_name}" not found'}, status=status.HTTP_404_NOT_FOUND)

        args = request.data.get('args', [])
        kwargs = request.data.get('kwargs', {})
        try:
            result = bound_task.delay(*args, **kwargs)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_ERROR)

        call_id = result.pk if hasattr(result, 'pk') else None
        return Response({
            'task_name': task_name,
            'call_id': call_id,
            'url': request.build_absolute_uri(f'/api/v1/task-calls/{call_id}/') if call_id else None,
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def reset(self, request, pk=None):
        session_model = self.get_object()
        try:
            rt = session_model.get_runtime()
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        rt.reset_turn_count()
        rt.reset_unattended_turn_count()
        return Response({'status': 'reset'})
