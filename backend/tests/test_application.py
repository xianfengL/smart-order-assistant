import asyncio
import json
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from app.config import settings
from app.main import app
from app.sql_service import execute, secure_sql
from app.charts import chart_option, build_option
from app import db


@pytest.fixture(scope='module')
def client(tmp_path_factory):
    path = tmp_path_factory.mktemp('assistant')
    settings.data_dir = path
    settings.database_url = 'sqlite:///' + (path / 'orders.db').as_posix()
    settings.demo_mode = True
    settings.jwt_secret = 'test-secret-at-least-thirty-two-characters'
    settings.admin_password = 'Admin123!'
    settings.customer_password = 'Demo123!'
    with TestClient(app) as test_client:
        yield test_client


def auth(client, username='demo', password='Demo123!'):
    response = client.post('/api/auth/login', json={'username': username, 'password': password})
    assert response.status_code == 200
    return {'Authorization': 'Bearer ' + response.json()['access_token']}


def parse_events(response):
    assert response.status_code == 200
    events = []
    for block in response.text.strip().split('\n\n'):
        lines = block.splitlines()
        events.append((lines[0].removeprefix('event: '), json.loads(lines[1].removeprefix('data: '))))
    return events


def test_login_and_health(client):
    assert client.get('/api/health').json() == {'status': 'ok', 'mode': 'demo'}
    assert client.get('/api/conversations').status_code in {401, 403}
    assert client.post('/api/auth/login', json={'username': 'demo', 'password': 'wrong'}).status_code == 401
    assert client.get('/api/auth/me', headers=auth(client)).json()['role'] == 'customer'
    assert client.get('/api/auth/me', headers={'Authorization': 'Bearer fake'}).status_code == 401


def test_tenant_scope_before_aggregation(client):
    user = SimpleNamespace(id=2, role='customer')
    assert execute('SELECT customer_id, COUNT(*) AS n FROM orders GROUP BY customer_id', user) == [{'customer_id': 2, 'n': 48}]
    bypass = execute('SELECT * FROM orders WHERE customer_id = 3 OR 1=1', user)
    assert len(bypass) == 48 and all(row['customer_id'] == 2 for row in bypass)
    assert execute('SELECT * FROM orders WHERE id IN (SELECT id FROM orders WHERE customer_id = 3)', user) == []
    assert execute('SELECT COUNT(*) AS n FROM orders', SimpleNamespace(id=1, role='admin')) == [{'n': 72}]


@pytest.mark.parametrize('sql', ['DELETE FROM orders', 'SELECT * FROM users', 'SELECT * FROM orders; DROP TABLE orders',
    'SELECT * FROM public.orders', 'SELECT pg_sleep(999) FROM orders', 'SELECT * INTO other FROM orders',
    'SELECT * FROM orders FOR UPDATE', 'WITH x AS (SELECT * FROM orders) SELECT * FROM x',
    'SELECT * FROM orders JOIN users ON orders.customer_id = users.id'])
def test_reject_unsafe_sql(client, sql):
    with pytest.raises(ValueError):
        secure_sql(sql, SimpleNamespace(id=2, role='customer'))


def test_conversation_isolation(client):
    customer = auth(client)
    alice = auth(client, 'alice')
    cid = client.post('/api/conversations', headers=customer).json()['id']
    assert client.get(f'/api/conversations/{cid}/messages', headers=alice).status_code == 404
    assert client.post(f'/api/conversations/{cid}/chat', headers=alice, json={'message': '查订单'}).status_code == 404
    assert cid not in [row['id'] for row in client.get('/api/conversations', headers=alice).json()]


def test_order_stream_and_persisted_history(client):
    headers = auth(client)
    cid = client.post('/api/conversations', headers=headers).json()['id']
    events = parse_events(client.post(f'/api/conversations/{cid}/chat', headers=headers, json={'message': '查询我的订单'}))
    assert events[-1][0] == 'done'
    assert any(kind == 'token' for kind, _ in events)
    rows = next(data['rows'] for kind, data in events if kind == 'data')
    assert len(rows) == 20
    with db.SessionLocal() as session:
        allowed = {row.order_no for row in session.query(db.Order).filter_by(customer_id=2)}
    assert all(row['order_no'] in allowed for row in rows)
    persisted = client.get(f'/api/conversations/{cid}/messages', headers=headers).json()
    assert [row['role'] for row in persisted] == ['user', 'assistant']
    assert persisted[-1]['rows'] == rows
    assert any(row['title'] == '查询我的订单' for row in client.get('/api/conversations', headers=headers).json())


def test_rag_and_no_stale_rows(client):
    headers = auth(client)
    cid = client.post('/api/conversations', headers=headers).json()['id']
    client.post(f'/api/conversations/{cid}/chat', headers=headers, json={'message': '查询我的订单'})
    events = parse_events(client.post(f'/api/conversations/{cid}/chat', headers=headers, json={'message': '七天无理由退货政策是什么？'}))
    assert events[-1][0] == 'done'
    sources = next(data['sources'] for kind, data in events if kind == 'sources')
    assert any('7 天' in source['text'] for source in sources)
    persisted = client.get(f'/api/conversations/{cid}/messages', headers=headers).json()
    assert persisted[-1]['rows'] == [] and persisted[-1]['chart'] == {}


def test_chart_and_followup(client):
    headers = auth(client)
    cid = client.post('/api/conversations', headers=headers).json()['id']
    first = parse_events(client.post(f'/api/conversations/{cid}/chat', headers=headers, json={'message': '按分类统计销售额并画柱状图'}))
    assert len(next(data['chart'] for kind, data in first if kind == 'chart')['series']) == 2
    events = parse_events(client.post(f'/api/conversations/{cid}/chat', headers=headers, json={'message': '改成饼图'}))
    assert next(data['chart'] for kind, data in events if kind == 'chart')['series'][0]['type'] == 'pie'
    assert events[-1][0] == 'done'


def test_real_mcp_stdio_roundtrip(client):
    rows = [{'label': '数码', 'value': 299, 'count': 2}, {'label': '家居', 'value': 189, 'count': 1}]
    assert asyncio.run(chart_option(rows, 'bar', 'stdio')) == build_option(rows, 'bar')


def test_checkpoint_and_session_survive_restart(client):
    headers = auth(client)
    cid = client.post('/api/conversations', headers=headers).json()['id']
    client.post(f'/api/conversations/{cid}/chat', headers=headers, json={'message': '按状态统计销售额并画柱状图'})
    assert (settings.data_dir / 'checkpoints.db').exists()
    with TestClient(app) as restarted:
        assert len(restarted.get(f'/api/conversations/{cid}/messages', headers=headers).json()) == 2
        events = parse_events(restarted.post(f'/api/conversations/{cid}/chat', headers=headers, json={'message': '改成饼图'}))
        chart = next(data['chart'] for kind, data in events if kind == 'chart')
        assert all(item['name'] in ['已完成', '已发货', '待支付', '退款中'] for item in chart['series'][0]['data'])


def test_live_configuration_requires_secrets():
    from app.config import Settings
    with pytest.raises(ValueError, match='Live mode requires'):
        Settings(demo_mode=False, jwt_secret='', admin_password='', customer_password='', openai_api_key='', llm_model='').prepare()
