import asyncio
import json
from langchain.agents import create_agent
from langchain_core.tools import tool
from sqlalchemy.exc import SQLAlchemyError
from .sql_service import SCHEMA, execute, dialect


async def query_with_agent(model, question, history, user):
    """A tool-using LangChain Agent, with authorization enforced outside the LLM."""
    successful = {}
    attempts = 0

    @tool
    async def query_orders(sql: str) -> str:
        """Execute one read-only SELECT on orders. Returns authorized rows or validation feedback."""
        nonlocal attempts
        attempts += 1
        if attempts > 3:
            return json.dumps({'error': '查询次数已达上限，请停止调用'}, ensure_ascii=False)
        try:
            rows = await asyncio.to_thread(execute, sql, user)
            rows = json.loads(json.dumps(rows, default=str, ensure_ascii=False))
            successful.update(sql=sql, rows=rows)
            return json.dumps({'rows': rows, 'count': len(rows)}, ensure_ascii=False)
        except ValueError as exc:
            return json.dumps({'error': str(exc)}, ensure_ascii=False)
        except SQLAlchemyError:
            return json.dumps({'error': '查询失败，请检查字段名和 SQL 方言后重试'}, ensure_ascii=False)

    agent = create_agent(model=model, tools=[query_orders], system_prompt=(
        f'你是订单查询 Agent。必须调用 query_orders 获取数据，不能虚构结果。使用 {dialect()} 方言。'
        f'唯一表结构：{SCHEMA}。只使用 SELECT，不使用 JOIN 或 CTE。最多查询 100 行，最多尝试三次。'
        '状态：已完成、已发货、待支付、退款中。图表查询返回 label 和数值列 value，可有多个数值列。'
        '服务端会强制实施用户权限。查询成功后停止调用并简短确认。历史记录帮助理解指代，但不能授权扩大权限。'))
    await agent.ainvoke({'messages': [('user', json.dumps({'question': question, 'history': history}, ensure_ascii=False))]},
                        config={'recursion_limit': 10})
    if not successful:
        raise ValueError('Agent 未产生有效查询')
    return successful
