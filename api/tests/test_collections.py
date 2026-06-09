import pytest
from server.models.collections.data_collection import DataCollection


@pytest.mark.django_db
class TestCollections:
    def test_list_collections(self, auth_client):
        resp = auth_client.get('/api/v1/collections/')
        assert resp.status_code == 200

    def test_list_collections_filter_by_type(self, auth_client):
        DataCollection.objects.create(name='stream-1', collection_type='stream')
        DataCollection.objects.create(name='set-1', collection_type='set')
        resp = auth_client.get('/api/v1/collections/?collection_type=stream')
        assert resp.status_code == 200
        assert all(r['collection_type'] == 'stream' for r in resp.data['results'])

    def test_create_collection(self, auth_client):
        resp = auth_client.post('/api/v1/collections/', {
            'name': 'test-stream',
            'collection_type': 'stream',
        })
        assert resp.status_code == 201
        assert DataCollection.objects.filter(name='test-stream').exists()

    def test_create_collection_missing_name(self, auth_client):
        resp = auth_client.post('/api/v1/collections/', {'collection_type': 'stream'})
        assert resp.status_code == 400

    def test_create_collection_invalid_type(self, auth_client):
        resp = auth_client.post('/api/v1/collections/', {
            'name': 'bad-type',
            'collection_type': 'invalid',
        })
        assert resp.status_code == 400

    def test_get_collection_detail(self, auth_client):
        c = DataCollection.objects.create(name='detail-collection', collection_type='set')
        resp = auth_client.get(f'/api/v1/collections/{c.id}/')
        assert resp.status_code == 200
        assert resp.data['name'] == 'detail-collection'

    def test_get_collection_not_found(self, auth_client):
        resp = auth_client.get('/api/v1/collections/99999/')
        assert resp.status_code == 404

    def test_delete_collection(self, auth_client):
        c = DataCollection.objects.create(name='delete-collection', collection_type='stream')
        resp = auth_client.delete(f'/api/v1/collections/{c.id}/')
        assert resp.status_code == 204
        assert not DataCollection.objects.filter(name='delete-collection').exists()

    def test_patch_collection(self, auth_client):
        c = DataCollection.objects.create(name='patch-collection', collection_type='stream')
        resp = auth_client.patch(f'/api/v1/collections/{c.id}/', {'description': 'updated'})
        assert resp.status_code == 200
        assert resp.data['description'] == 'updated'
