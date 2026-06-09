import pytest
from django.contrib.auth.models import User
from django.test import Client
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user():
    user, _ = User.objects.get_or_create(
        username='admin',
        defaults={'is_staff': True, 'is_superuser': True},
    )
    user.set_password('adminpass')
    user.save()
    return user


@pytest.fixture
def auth_client(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)
    return api_client


@pytest.fixture
def jwt_client(api_client, admin_user):
    response = api_client.post('/api/v1/auth/token/', {
        'username': 'admin',
        'password': 'adminpass',
    })
    if response.status_code == 200:
        token = response.data['access']
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return api_client


@pytest.fixture
def django_client():
    return Client()
