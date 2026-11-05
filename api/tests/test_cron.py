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
        job = Cronjob.objects.get(name='test-cron')
        assert job.next_run_at is not None
        assert job.is_active is True

    def test_create_cron_with_message(self, auth_client):
        resp = auth_client.post('/api/v1/cron/', {
            'name': 'message-cron',
            'schedule': '0 9 * * *',
            'session_mode': 'existing',
            'message': 'run the daily report',
        })
        assert resp.status_code == 201
        job = Cronjob.objects.get(name='message-cron')
        assert job.message.get() == 'run the daily report'

        detail = auth_client.get(f'/api/v1/cron/{job.id}/')
        assert detail.status_code == 200
        assert detail.data['message'] == 'run the daily report'

    def test_create_cron_with_shorthand_schedule(self, auth_client):
        resp = auth_client.post('/api/v1/cron/', {
            'name': 'shorthand-cron',
            'schedule': 'every 15 min',
            'session_mode': 'existing',
        })
        assert resp.status_code == 201
        job = Cronjob.objects.get(name='shorthand-cron')
        assert job.next_run_at is not None

    def test_create_function_cron_requires_json_message(self, auth_client):
        resp = auth_client.post('/api/v1/cron/', {
            'name': 'bad-json-cron',
            'schedule': '0 9 * * *',
            'session_mode': 'existing',
            'function_type': 'tool',
            'function_name': 'shell',
            'message': 'not json',
        })
        assert resp.status_code == 400
        assert not Cronjob.objects.filter(name='bad-json-cron').exists()

    def test_get_cron_detail(self, auth_client):
        c = Cronjob.objects.create(name='detail-cron', schedule='*/5 * * * *', session_mode='existing')
        resp = auth_client.get(f'/api/v1/cron/{c.id}/')
        assert resp.status_code == 200
