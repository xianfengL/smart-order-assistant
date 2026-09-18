import json
import sys
from pathlib import Path


def build_option(rows: list[dict], kind='bar') -> dict:
    if not rows:
        return {}
    keys = list(rows[0])
    label_key = 'label' if 'label' in keys else next((key for key in keys if isinstance(rows[0][key], str)), keys[0])
    numeric_keys = [key for key in keys if key != label_key and any(isinstance(row.get(key), (int, float)) for row in rows)]
    if not numeric_keys:
        raise ValueError('查询结果没有可绘图的数值列')
    labels = [str(row.get(label_key, '')) for row in rows]
    if kind == 'pie':
        return {'tooltip': {'trigger': 'item'}, 'legend': {'bottom': 0}, 'series': [
            {'name': numeric_keys[0], 'type': 'pie', 'radius': ['40%', '70%'],
             'data': [{'name': label, 'value': row.get(numeric_keys[0], 0)} for label, row in zip(labels, rows)]}]}
    return {'tooltip': {'trigger': 'axis'}, 'legend': {'top': 0},
            'grid': {'left': 50, 'right': 24, 'bottom': 50, 'top': 45},
            'xAxis': {'type': 'category', 'data': labels}, 'yAxis': {'type': 'value'},
            'series': [{'name': key, 'type': kind, 'smooth': kind == 'line', 'data': [row.get(key, 0) for row in rows]} for key in numeric_keys]}


def normalize_mcp(result):
    if result.isError:
        raise ValueError('图表 MCP 工具返回错误')
    payload = result.structuredContent
    if not payload:
        for block in result.content:
            if getattr(block, 'type', '') == 'text':
                payload = json.loads(block.text)
                break
    if not isinstance(payload, dict):
        raise ValueError('图表 MCP 结果格式无效')
    option = payload.get('option', payload)
    if not isinstance(option, dict) or not isinstance(option.get('series'), list):
        raise ValueError('图表缺少 series')
    return option


async def chart_option(rows, kind, transport='local'):
    if transport == 'local':
        return build_option(rows, kind)
    if transport != 'stdio':
        raise ValueError('CHART_TRANSPORT 必须为 local 或 stdio')
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    params = StdioServerParameters(command=sys.executable, args=['-m', 'app.mcp_server'], cwd=str(Path(__file__).resolve().parent.parent))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool('generate_chart', {'rows': rows, 'kind': kind})
            return normalize_mcp(result)
