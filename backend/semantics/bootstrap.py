"""由 L0 introspection 起草增强包草稿（不覆盖正式文件）。

正式文件（templates.yaml / exemplars.yaml / aliases.yaml）只能人工审核后手动转正（SDD §4.8）。
可选：不跑也能问数（NFR-5）。
用法：python -m semantics.bootstrap
"""
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.query.introspection import PgIntrospector  # noqa: E402

logger = logging.getLogger(__name__)
_SEMANTICS_DIR = Path(__file__).resolve().parent

_NUMERIC_TYPES = {
    "smallint", "integer", "bigint", "decimal", "numeric",
    "real", "double precision", "money",
}
_LOW_CARD_TEXT_COLUMNS = {"order_status", "pay_status", "doc_type", "promotion_type", "channel_type"}


def _header(version: str) -> dict:
    return {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source": "schema",
        "reviewed": False,
        "version": version,
    }


def _write_draft(filename: str, payload: dict) -> None:
    path = _SEMANTICS_DIR / filename
    with path.open("w", encoding="utf-8") as f:
        f.write("# bootstrap 自动起草，未人工审核，不得直接作为正式增强包使用。\n")
        f.write("# 人工确认后，手动整理进正式 YAML（version 变化会让 S2 缓存自然失效）。\n")
        yaml.safe_dump(payload, f, allow_unicode=True, sort_keys=False)
    logger.info("草稿已生成：%s", path.name)


def _table_skeletons(l0: dict) -> tuple[list[dict], list[dict], dict]:
    templates: list[dict] = []
    exemplars: list[dict] = []
    entities: dict = {}

    for table in l0.get("tables", []):
        name = table.get("name")
        columns = table.get("columns") or []
        if not name or not columns:
            continue

        numeric_cols = [
            c["name"] for c in columns
            if str(c.get("type")) in _NUMERIC_TYPES and c.get("name")
        ]
        date_cols = [c["name"] for c in columns if str(c.get("type")) == "date" and c.get("name")]

        for column in columns:
            if column.get("name") in _LOW_CARD_TEXT_COLUMNS and column.get("enum_values"):
                entities[f"{name}.{column['name']}"] = {
                    "column": f"{name}.{column['name']}",
                    "values": column["enum_values"],
                    "note": "bootstrap 从 L0 低基数列采样，待人工确认",
                }

        # 只为事实表（dwd_*）起草模板/示例；维度表只抽枚举
        if not name.startswith("dwd_") or not date_cols or not numeric_cols:
            continue

        templates.append({
            "id": f"draft_tpl_{name}_single_period",
            "name": f"{name} 单期聚合（草稿）",
            "required_slots": ["metrics", "time_range"],
            "metric_columns": {col: f"{name}.{col}" for col in numeric_cols[:5]},
            "sql_template": (
                "SELECT SUM({metric_col}) AS v\n"
                f"FROM data.{name}\n"
                f"WHERE {date_cols[0]} BETWEEN '{{start_date}}' AND '{{end_date}}'"
            ),
            "verified": False,
            "notes": "bootstrap 自动起草：口径、过滤条件与日期列均需人工确认后转正",
        })
        exemplars.append({
            "id": f"draft_ex_{name}_summary",
            "question": f"{name} 在指定时间范围内的 {numeric_cols[0]} 汇总是多少",
            "sql": "",
            "query_spec": {
                "metrics": [numeric_cols[0]],
                "dimensions": [],
                "time_range": {"start": "", "end": ""},
                "comparison": None,
            },
            "tags": [name, numeric_cols[0]],
            "difficulty": "easy",
            "source": "bootstrap",
            "verified": False,
        })

    return templates, exemplars, entities


def bootstrap() -> None:
    l0 = PgIntrospector().l0()
    templates, exemplars, entities = _table_skeletons(l0)

    _write_draft("templates.draft.yaml", {
        **_header("tpl-draft"),
        "note": "草稿模板未经实跑验证，reviewed=false；转正前必须逐条执行 SQL 并确认口径。",
        "templates": templates,
    })
    _write_draft("exemplars.draft.yaml", {
        **_header("ex-draft"),
        "note": "草稿示例的 sql 为空，需人工补全并实跑验证；reviewed=false。",
        "exemplars": exemplars,
    })
    _write_draft("aliases.draft.yaml", {
        **_header("aliases-draft"),
        "note": "dimensions / channels 需人工维护；entities 为 L0 低基数列采样候选。",
        "dimensions": {},
        "channels": {},
        "entities": entities,
    })


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    bootstrap()
