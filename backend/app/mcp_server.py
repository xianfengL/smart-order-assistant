from mcp.server.fastmcp import FastMCP
from .charts import build_option

mcp = FastMCP('Order ECharts')


@mcp.tool()
def generate_chart(rows: list[dict], kind: str = 'bar') -> dict:
    """Convert trusted query rows into an ECharts option with multiple series."""
    if kind not in {'bar', 'line', 'pie'}:
        raise ValueError('Unsupported chart kind')
    return {'option': build_option(rows, kind)}


if __name__ == '__main__':
    mcp.run(transport='stdio')
