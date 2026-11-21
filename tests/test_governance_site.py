"""Public synthetic governance UI mount and isolation smoke tests."""
from fastapi.testclient import TestClient
from server import app

def test_governance_site_static_resources():
    with TestClient(app) as client:
        home = client.get('/governance/')
        assert home.status_code == 200
        assert 'CompanyAgent · 安全治理与迁云验证站' in home.text
        assert '公司内部 API' in home.text
        assert "Content-Security-Policy" in home.text
        for asset in ('core.js', 'app.js', 'styles.css'):
            response = client.get('/governance/' + asset)
            assert response.status_code == 200
            assert len(response.content) > 1000

def test_governance_does_not_expose_api_secrets():
    with TestClient(app) as client:
        content = client.get('/governance/core.js').text
        assert '真实数据验收' in content
        assert '禁止直连公司内网 API' in content
        assert 'BEGIN PRIVATE KEY' not in content
