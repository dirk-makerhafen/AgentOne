from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

from api.views.health import HealthView
from api.views.me import MeView
from api.views.agents import AgentViewSet
from api.views.sessions import SessionViewSet
from api.views.queries import QueryViewSet
from api.views.collections import CollectionViewSet
from api.views.cron import CronViewSet
from api.views.providers import ProviderViewSet, AiModelViewSet
from api.views.skills import SkillViewSet
from api.views.projects import ProjectViewSet
from api.views.systems import SystemViewSet
from api.views.tasks import TaskCallViewSet, TaskRunViewSet
from api.views.workspaces import WorkspaceViewSet

router = DefaultRouter()
router.register(r'agents', AgentViewSet, basename='agent')
router.register(r'sessions', SessionViewSet, basename='session')
router.register(r'queries', QueryViewSet, basename='query')
router.register(r'collections', CollectionViewSet, basename='collection')
router.register(r'cron', CronViewSet, basename='cron')
router.register(r'providers', ProviderViewSet, basename='provider')
router.register(r'models', AiModelViewSet, basename='model')
router.register(r'skills', SkillViewSet, basename='skill')
router.register(r'projects', ProjectViewSet, basename='project')
router.register(r'systems', SystemViewSet, basename='system')
router.register(r'task-calls', TaskCallViewSet, basename='task-call')
router.register(r'task-runs', TaskRunViewSet, basename='task-run')
router.register(r'workspaces', WorkspaceViewSet, basename='workspace')

urlpatterns = [
    path('auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('health/', HealthView.as_view(), name='health'),
    path('me/', MeView.as_view(), name='me'),
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    path('', include(router.urls)),
]
