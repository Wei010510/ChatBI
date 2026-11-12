"""S5 lint 自检：五条规则（SDD §2.7 / §9.1）。"""
from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp


READONLY_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
    "CREATE", "REPLACE", "MERGE", "GRANT", "REVOKE",
}


@dataclass
class LintResult:
    ok: bool
    errors: list[str] = field(default_factory=list)


def _scope_columns(select_node: exp.Select) -> list[exp.Column]:
    """本 SELECT 作用域内的列引用（不深入子查询 / CTE / WITH / UNION）。"""
    cols: list[exp.Column] = []

    def walk(node: exp.Expression) -> None:
        for child in node.iter_expressions():
            if isinstance(child, (exp.Select, exp.Subquery, exp.CTE, exp.With, exp.Union)):
                continue
            if isinstance(child, exp.Column):
                cols.append(child)
            else:
                walk(child)

    walk(select_node)
    return cols


def _scope_sources(select_node: exp.Select) -> list[exp.Expression]:
    """本 SELECT 作用域直接的 FROM / JOIN 来源。"""
    sources: list[exp.Expression] = []
    from_expr = select_node.args.get("from")
    if from_expr is not None:
        if from_expr.this is not None:
            sources.append(from_expr.this)
        sources.extend(from_expr.expressions or [])
    for join in select_node.args.get("joins") or []:
        if join.this is not None:
            sources.append(join.this)
    return sources


def _check_column_attribution(
    statement: exp.Expression,
    table_columns: dict[str, list[str]],
    errors: list[str],
) -> None:
    """规则 4 列归属（SDD §2.7）：列必须存在于它所在那张表的 L0 列清单。

    按 SELECT 作用域逐个校验，表别名只在本作用域内解析：
    - 带前缀的列：前缀能解析到本作用域的真实表时校验该表；
      解析到 CTE / 派生表别名（或作用域外别名）时豁免；
    - 无前缀的列：本作用域来源全部为同一张真实表时按该表校验，否则不强行归属；
    - SELECT 输出别名（ORDER BY / GROUP BY 引用）不校验。
    同一问题列多次出现只报一次（报错原文会回炉给 LLM）。
    """
    cte_names = {cte.alias for cte in statement.find_all(exp.CTE)}
    seen: set[str] = set()

    def add(message: str) -> None:
        if message not in seen:
            seen.add(message)
            errors.append(message)

    for sel in statement.find_all(exp.Select):
        sources = _scope_sources(sel)

        # 本作用域的真实表别名映射（CTE 名与派生表不进映射）
        local: dict[str, str] = {}
        for s in sources:
            if isinstance(s, exp.Table) and s.name not in cte_names and s.name in table_columns:
                local.setdefault(s.alias_or_name, s.name)
                local.setdefault(s.name, s.name)

        # 无前缀列可唯一归属的前提：本作用域来源全是同一张真实表
        sole_table: str | None = None
        if sources and all(
            isinstance(s, exp.Table) and s.name not in cte_names for s in sources
        ):
            names = {s.name for s in sources}
            if len(names) == 1:
                only = next(iter(names))
                if only in table_columns:
                    sole_table = only

        select_aliases = {e.alias for e in sel.expressions if e.alias}

        for col in _scope_columns(sel):
            if isinstance(col.this, exp.Star):
                continue
            if col.table:
                tname = local.get(col.table)
                if tname and col.name not in table_columns[tname]:
                    add(f"列 {col.table}.{col.name} 在表 {tname} 中不存在（列归属校验）")
            elif col.name in select_aliases:
                continue
            elif sole_table and col.name not in table_columns[sole_table]:
                add(f"列 {col.name} 在表 {sole_table} 中不存在（列归属校验）")


def lint_sql(
    sql: str,
    allowed_tables: list[str],
    max_rows: int = 1000,
    table_columns: dict[str, list[str]] | None = None,
) -> LintResult:
    """对 SQL 做五条自检，返回 LintResult。

    1. 单条语句（只允许 1 条 SELECT/WITH）
    2. 只读（无写操作关键字）
    3. 表白名单（只能引用 allowed_tables）
    4. 列归属（列必须属于它所在那张表，按 L0 列清单；表别名按 SELECT 作用域解析）+ 聚合不套子查询
    5. 强制 LIMIT（无则补 max_rows，返回修改后的 sql）
    """
    errors: list[str] = []

    # 规则 2：只读（先做关键字检查，廉价）
    upper = sql.upper()
    for kw in READONLY_KEYWORDS:
        if kw in upper:
            errors.append(f"检测到写操作关键字: {kw}")
            return LintResult(ok=False, errors=errors)

    # 规则 1：单条语句 + 解析
    try:
        parsed = sqlglot.parse(sql)
    except Exception as e:
        errors.append(f"SQL 解析失败: {e}")
        return LintResult(ok=False, errors=errors)

    if len(parsed) != 1:
        errors.append(f"只允许单条语句，实际 {len(parsed)} 条")
        return LintResult(ok=False, errors=errors)

    statement = parsed[0]
    if not isinstance(statement, (exp.Select, exp.With, exp.Union)):
        errors.append("只允许 SELECT / WITH / UNION 语句")
        return LintResult(ok=False, errors=errors)

    # 规则 3：表白名单（WITH 定义的 CTE 名是本语句内部的派生表，不算引用外部表；
    # CTE 体内引用的真实表仍会被 find_all 找到，照常校验）
    cte_names = {cte.alias for cte in statement.find_all(exp.CTE)}
    tables = {t.name for t in statement.find_all(exp.Table)} - cte_names
    unknown = tables - set(allowed_tables)
    if unknown:
        errors.append(f"引用了未授权的表: {', '.join(unknown)}")

    # 规则 4：列归属（有 L0 列清单时校验）+ 聚合不套子查询
    if table_columns:
        _check_column_attribution(statement, table_columns, errors)

    for agg in statement.find_all(exp.AggFunc):
        # 聚合的参数应是列或星号，不允许套子查询
        args = agg.expressions
        for a in args:
            if isinstance(a, (exp.Select, exp.Subquery)):
                errors.append(f"聚合函数套了子查询: {agg.sql()}")

    if errors:
        return LintResult(ok=False, errors=errors)

    # 规则 5：强制 LIMIT
    has_limit = bool(statement.args.get("limit"))
    if not has_limit:
        # 补 LIMIT（简单字符串追加，避免重写 AST）
        if not sql.rstrip().endswith(";"):
            sql = sql.rstrip() + f" LIMIT {max_rows}"
        else:
            sql = sql.rstrip()[:-1] + f" LIMIT {max_rows};"

    return LintResult(ok=True, errors=[])
