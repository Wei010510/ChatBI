"""S3 检索：捞四类弹药，不做决定。表/列/口径/实体 → S4；示例 → S5 few_shot。"""
import re

from ._common import add_trace, get_resources

_TOP_K = 3
_TOPN_RE = re.compile(r"(?:top|前)\s*(?:\d{1,3}|[一二三四五六七八九十])|排名|最高|最多")
_COMPARISON_TAGS = {"同比", "环比", "yoy", "mom", "wow"}


def _norm(value) -> str:
    return str(value).strip().lower()


def _def_terms(definition: dict) -> set[str]:
    terms = {_norm(definition.get("key") or ""), _norm(definition.get("name") or "")}
    terms |= {_norm(a) for a in (definition.get("aliases") or []) if a}
    terms.discard("")
    return terms


def _resolve_keys(values, definitions) -> tuple[set[str], set[str]]:
    """意图词 → (命中的 L1 key 集合, 原始词集合)。"""
    keys: set[str] = set()
    raw: set[str] = set()
    for value in values or []:
        term = _norm(value)
        if not term:
            continue
        raw.add(term)
        for definition in definitions:
            if isinstance(definition, dict) and term in _def_terms(definition):
                keys.add(_norm(definition.get("key")))
                break
    return keys, raw


def _pick_exemplars(
    exemplars: list[dict],
    question: str,
    metric_terms: set[str],
    dimension_terms: set[str],
    intent_spec: dict | None = None,
    k: int = _TOP_K,
) -> list[dict]:
    """按 tags + 问题关键词（或 metric/dimension key 交集）筛 top_k；筛不到返回空列表。"""
    q = _norm(question)
    intent_terms = metric_terms | dimension_terms

    # 问题没要 TopN / 对比时，不让对应示例抢占 few-shot
    skip_tags: set[str] = set()
    if not _TOPN_RE.search(q):
        skip_tags |= {"topn", "排名"}
    comparison = (intent_spec or {}).get("comparison") if isinstance(intent_spec, dict) else None
    if not comparison and not any(tag in q for tag in _COMPARISON_TAGS):
        skip_tags |= _COMPARISON_TAGS

    scored: list[tuple[int, int, dict]] = []

    for index, example in enumerate(exemplars):
        if not isinstance(example, dict):
            continue
        score = 0
        for tag in example.get("tags") or []:
            tag_text = _norm(tag)
            if tag_text in skip_tags:
                # 形态不符的示例降权，避免 TopN / 对比示例抢占普通问句
                score -= 2
                continue
            if tag_text and (tag_text in q or tag_text in intent_terms):
                score += 2
        spec = example.get("query_spec") or {}
        if isinstance(spec, dict):
            example_metrics = {_norm(m) for m in (spec.get("metrics") or [])}
            example_dimensions = {_norm(d) for d in (spec.get("dimensions") or [])}
            score += 2 * len(example_metrics & metric_terms)
            score += 2 * len(example_dimensions & dimension_terms)
        if score > 0:
            scored.append((score, index, example))

    scored.sort(key=lambda item: (-item[0], item[1]))
    return [example for _, _, example in scored[:k]]


def _match_alias_entities(aliases: dict, question: str) -> list[dict]:
    """aliases.yaml 的三段结构：dimensions / channels / entities。"""
    matched: list[dict] = []
    if not isinstance(aliases, dict):
        return matched
    q = _norm(question)

    dimensions = aliases.get("dimensions") or {}
    if isinstance(dimensions, dict):
        for key, terms in dimensions.items():
            terms = [terms] if isinstance(terms, str) else (terms or [])
            for term in terms:
                if term and _norm(term) in q:
                    matched.append({"dimension": key, "alias": str(term)})
                    break

    channels = aliases.get("channels") or {}
    if isinstance(channels, dict):
        for code, terms in channels.items():
            terms = [terms] if isinstance(terms, str) else (terms or [])
            for term in terms:
                if term and _norm(term) in q:
                    matched.append({"dimension": "channel", "alias": str(term), "value": code})
                    break

    entities = aliases.get("entities") or {}
    if isinstance(entities, dict):
        for alias, spec in entities.items():
            if alias and _norm(alias) in q:
                item = {"alias": alias}
                if isinstance(spec, dict):
                    item.update(spec)
                else:
                    item["expanded"] = spec
                matched.append(item)

    return matched


def _load_exemplars(resources, question: str) -> list[dict]:
    """优先按问题走向量召回；provider 不支持带参调用时退回全量。"""
    try:
        return resources.exemplars(question) or []
    except TypeError:
        return resources.exemplars() or []


def retrieve(state, config) -> dict:
    resources = get_resources(config)
    trace = add_trace(state, "retrieve", "S3 检索")

    raw_question = state.get("question") or ""
    l0 = resources.l0()
    l1 = resources.l1() or {}
    aliases = resources.aliases() or {}
    exemplars = _load_exemplars(resources, raw_question)

    question = raw_question.lower()
    intent_spec = state.get("intent_spec") or {}

    # 口径词典缺失 / 为空 / 结构不对 → 降级，不报错
    metric_defs = (l1.get("metrics") or []) if isinstance(l1, dict) else []
    dimension_defs = (l1.get("dimensions") or []) if isinstance(l1, dict) else []
    l1_available = bool(metric_defs)

    # ① 表/字段：从 L0 全量结构取，按问题关键词过滤
    all_columns = l0.get("columns", [])
    matched_columns = [
        c for c in all_columns
        if any(kw in question for kw in (c.get("name", "") + c.get("comment", "")).lower())
    ] or all_columns[:20]  # 无匹配时取部分

    # ② 口径：只捞问题里出现（或 S1 意图点名）的指标，整本字典不往 S4 塞
    intent_terms = {
        _norm(v)
        for field in ("metrics", "dimensions")
        for v in (intent_spec.get(field) or [])
        if v
    }
    matched_metrics = []
    for metric in metric_defs:
        if not isinstance(metric, dict):
            continue
        if any(t in question or t in intent_terms for t in _def_terms(metric)):
            matched_metrics.append({
                "key": metric.get("key") or "",
                "name": metric.get("name") or "",
                "formula": metric.get("formula") or "",
                "ambiguity": metric.get("ambiguity") or [],
            })

    # ③ 实体/维度：维度同义词命中 + aliases.yaml 展开
    matched_entities = []
    for dim in dimension_defs:
        if not isinstance(dim, dict):
            continue
        if any(t in question or t in intent_terms for t in _def_terms(dim)):
            matched_entities.append({
                k: dim.get(k)
                for k in ("key", "name", "column", "lookup_table", "lookup_key", "lookup_label")
            })
    matched_entities.extend(_match_alias_entities(aliases, question))

    # ④ 示例：按 tags + metric/dimension key 交集筛 top_k，筛不到空列表
    metric_keys, metric_raw = _resolve_keys(intent_spec.get("metrics"), metric_defs)
    dimension_keys, dimension_raw = _resolve_keys(intent_spec.get("dimensions"), dimension_defs)
    few_shot = _pick_exemplars(
        exemplars,
        question,
        metric_keys | metric_raw,
        dimension_keys | dimension_raw,
        intent_spec,
    )

    evidence = {
        "tables": l0.get("tables", []),
        "columns": matched_columns,
        "metrics": matched_metrics,
        "entities": matched_entities,
        "examples": few_shot,
        "l1_available": l1_available,
    }

    return {
        **state,
        "evidence": evidence,
        "plan": {**(state.get("plan") or {}), "few_shot": few_shot},
        "trace": trace,
    }
