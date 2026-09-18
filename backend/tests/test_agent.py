import asyncio
from types import SimpleNamespace
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from app.order_agent import query_with_agent
from app import db


class ToolCallingModel(BaseChatModel):
    @property
    def _llm_type(self):
        return 'test-tool-model'

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        if isinstance(messages[-1], ToolMessage):
            message = AIMessage(content='查询完成')
        else:
            message = AIMessage(content='', tool_calls=[{'name': 'query_orders',
                'args': {'sql': 'SELECT customer_id, COUNT(*) AS count FROM orders GROUP BY customer_id'}, 'id': 'query-test', 'type': 'tool_call'}])
        return ChatResult(generations=[ChatGeneration(message=message)])


def test_live_agent_tool_enforces_customer_scope(tmp_path):
    from app.config import settings
    previous = (settings.database_url, settings.data_dir)
    previous_engine, previous_session = db.engine, db.SessionLocal
    try:
        settings.data_dir = tmp_path
        settings.database_url = 'sqlite:///' + (tmp_path / 'orders.db').as_posix()
        db.initialize()
        result = asyncio.run(query_with_agent(ToolCallingModel(), '统计订单', '', SimpleNamespace(id=2, role='customer')))
        assert result['rows'] == [{'customer_id': 2, 'count': 48}]
    finally:
        db.engine.dispose()
        db.engine, db.SessionLocal = previous_engine, previous_session
        settings.database_url, settings.data_dir = previous
