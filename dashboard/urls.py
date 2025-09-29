from django.urls import path, include
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('systems/api/', include('systems.urls')),
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', views.dashboard, name='dashboard'),
] + static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
