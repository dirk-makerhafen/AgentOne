from django.urls import path, include
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static

from old.register_client_api import register_client
from ui.main_view import ui

app_name = 'Agent'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', ui, name='ui'),
    path('register_client/', register_client, name='register_client'),

] + static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
