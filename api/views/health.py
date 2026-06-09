from django.db import connection
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status
from drf_spectacular.utils import extend_schema


@extend_schema(request=None, responses={200: dict})
class HealthView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        db_ok = False
        try:
            connection.ensure_connection()
            db_ok = True
        except Exception:
            pass

        redis_ok = False
        try:
            import redis
            r = redis.from_url(settings.REDIS_URL)
            r.ping()
            redis_ok = True
        except Exception:
            pass

        data = {
            "status": "ok" if db_ok else "degraded",
            "database": "connected" if db_ok else "unavailable",
            "redis": "connected" if redis_ok else "unavailable",
        }
        code = status.HTTP_200_OK if db_ok else status.HTTP_503_SERVICE_UNAVAILABLE
        return Response(data, status=code)
