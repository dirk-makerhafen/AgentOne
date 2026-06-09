import pytest
from server.models.skills.skill import SkillModel


@pytest.mark.django_db
class TestSkills:
    def test_list_skills(self, auth_client):
        resp = auth_client.get('/api/v1/skills/')
        assert resp.status_code == 200

    def test_skill_detail(self, auth_client):
        s = SkillModel.objects.create(name='test-skill')
        resp = auth_client.get(f'/api/v1/skills/{s.id}/')
        assert resp.status_code == 200
