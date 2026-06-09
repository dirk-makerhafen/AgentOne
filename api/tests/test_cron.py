import pytest
from server.models.cron import Cronjob


@pytest.mark.django_db
class TestCron:
    def test_list_cron(self, auth_client):
        resp = auth_client.get('/api/v1/cron/')
        assert resp.status_code == 200

    def test_create_cron(self, auth_client):
        resp = auth_client.post('/api/v1/cron/', {
            'name': 'test-cron',
            'schedule': '* * * * *',
            'session_mode': 'existing',
        })
        assert resp.status_code == 201
        assert Cronjob.objects.filter(name='test-cron').exists()

    def test_get_cron_detail(self, auth_client):
        c = Cronjob.objects.create(name='detail-cron', schedule='*/5 * * * *', session_mode='existing')
        resp = auth_client.get(f'/api/v1/cron/{c.id}/')
        assert resp.status_code == 200
