import re
import sqlglot
from sqlglot import exp
from sqlalchemy import text
from . import db

SCHEMA = 'orders(id, order_no, customer_id, product, category, amount, status, created_at)'
ALLOWED_FUNCTIONS = {'COUNT', 'SUM', 'AVG', 'MIN', 'MAX', 'ROUND', 'COALESCE', 'CAST', 'DATE', 'SUBSTRING', 'STRFTIME', 'DATE_FORMAT', 'TO_CHAR', 'LOWER', 'UPPER', 'ABS'}


def dialect():
    return {'postgresql': 'postgres', 'mysql': 'mysql', 'sqlite': 'sqlite'}[db.engine.dialect.name]


def secure_sql(sql: str, user):
    """Parse a single SELECT and scope every orders reference before any aggregation."""
    trees = sqlglot.parse(sql, read=dialect())
    if len(trees) != 1 or not isinstance(trees[0], exp.Select):
        raise ValueError('只允许单条 SELECT 查询')
    tree = trees[0]
    if tree.find(exp.With) or tree.find(exp.Into) or tree.find(exp.Lock) or tree.find(exp.Join):
        raise ValueError('不允许 CTE、写入、锁或连接查询')
    tables = list(tree.find_all(exp.Table))
    if not tables:
        raise ValueError('必须查询 orders 表')
    for table in tables:
        if table.name.lower() != 'orders' or table.db or table.catalog:
            raise ValueError('只能访问订单表')
    for func in tree.find_all(exp.Func):
        if isinstance(func, (exp.And, exp.Or)):
            continue
        name = func.name.upper() if isinstance(func, exp.Anonymous) else func.sql_name().upper()
        if name not in ALLOWED_FUNCTIONS:
            raise ValueError(f'不允许函数 {name}')
    if user.role != 'admin':
        for table in tables:
            alias = table.alias or table.name
            scoped = sqlglot.parse_one("SELECT * FROM orders WHERE customer_id = '__TENANT_BIND__'", read=dialect())
            table.replace(exp.Subquery(this=scoped, alias=exp.TableAlias(this=exp.to_identifier(alias))))
    rendered = tree.sql(dialect=dialect()).replace("'__TENANT_BIND__'", ':tenant_id')
    # A wrapper caps model-supplied limits and protects browser payload size.
    return f'SELECT * FROM ({rendered}) AS scoped_result LIMIT 100', {'tenant_id': user.id}


def execute(sql, user):
    safe, params = secure_sql(sql, user)
    with db.engine.connect() as conn:
        with conn.begin():
            if db.engine.dialect.name == 'postgresql':
                conn.execute(text('SET TRANSACTION READ ONLY'))
                conn.execute(text("SET LOCAL statement_timeout = '5000'"))
            elif db.engine.dialect.name == 'mysql':
                conn.execute(text('SET TRANSACTION READ ONLY'))
            rows = conn.execute(text(safe), params).mappings().all()
    return [dict(row) for row in rows]


def demo_sql(question, history=''):
    human_history = ' '.join(line[6:] for line in history.splitlines() if line.startswith('user: '))
    q = question + (' ' + human_history if any(w in question for w in ['它', '这些', '改成', '折线']) else '')
    if any(w in q for w in ['图', '趋势', '统计', '分类', '销售额', '金额分布']):
        if any(w in q for w in ['趋势', '日期', '每日']):
            return 'SELECT CAST(created_at AS DATE) AS label, SUM(amount) AS value FROM orders GROUP BY CAST(created_at AS DATE) ORDER BY label' if dialect() != 'sqlite' else 'SELECT DATE(created_at) AS label, SUM(amount) AS value FROM orders GROUP BY DATE(created_at) ORDER BY label'
        group = 'status' if '状态' in q else 'category'
        return f'SELECT {group} AS label, SUM(amount) AS value, COUNT(*) AS count FROM orders GROUP BY {group} ORDER BY value DESC'
    if any(w in q for w in ['总额', '总金额', '多少钱']):
        return 'SELECT SUM(amount) AS total_amount, COUNT(*) AS order_count FROM orders'
    filters = []
    order_no = re.search(r'SO\d{10}', q, re.I)
    if order_no:
        filters.append(f"order_no = '{order_no.group().upper()}'")
    for status in ['已完成', '已发货', '待支付', '退款中']:
        if status in q:
            filters.append(f"status = '{status}'")
    where = ' WHERE ' + ' AND '.join(filters) if filters else ''
    return 'SELECT order_no, product, category, amount, status, created_at FROM orders' + where + ' ORDER BY created_at DESC LIMIT 20'
