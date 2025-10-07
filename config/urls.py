from django.urls import path, include
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from ui.views import ui

app_name = 'Agent'

urlpatterns = [
    path('systems/api/', include('systems.urls')),
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', ui, name='ui'),
] + static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
