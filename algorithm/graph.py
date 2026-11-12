"""LangGraph 图编排：S1~S8 固定状态机（SDD §1.2 / §7.1）。"""
from langgraph.graph import END, StateGraph

from .state import ChatState
from .nodes import understand, template, retrieve, plan, gen_sql, execute, present, narrate


def _route_after_understand(state: ChatState) -> str:
    if state.get("action") == "reject":
        return "reject"
    return "template"


def _route_after_template(state: ChatState) -> str:
    if state.get("template_hit") or state.get("cache_hit"):
        return "execute"
    return "retrieve"


def _route_after_plan(state: ChatState) -> str:
    action = state.get("action")
    if action == "clarify":
        return "clarify"
    if action == "reject":
        return "reject"
    return "gen_sql"


def _route_after_gen_sql(state: ChatState) -> str:
    if state.get("action") == "reject":
        return "reject"
    if state.get("lint_ok"):
        return "execute"
    # lint 不过，回炉（≤2 轮由节点内部控制）
    return "gen_sql"


def _route_after_execute(state: ChatState) -> str:
    if state.get("action") == "reject":
        return "reject"
    # sql_error 存在且 retry_count 刚递增 → 回 S5 重写
    if state.get("sql_error"):
        return "gen_sql"
    return "present"


def build_graph():
    g = StateGraph(ChatState)

    # 8 个节点，命名与 SDD §7.1 一致
    g.add_node("understand", understand.understand)
    g.add_node("template", template.template)
    g.add_node("retrieve", retrieve.retrieve)
    g.add_node("plan", plan.plan)
    g.add_node("gen_sql", gen_sql.gen_sql)
    g.add_node("execute", execute.execute)
    g.add_node("present", present.present)
    g.add_node("narrate", narrate.narrate)

    g.set_entry_point("understand")

    # 条件边
    g.add_conditional_edges("understand", _route_after_understand, {
        "template": "template",
        "reject": END,
    })
    g.add_conditional_edges("template", _route_after_template, {
        "execute": "execute",
        "retrieve": "retrieve",
    })
    g.add_edge("retrieve", "plan")
    g.add_conditional_edges("plan", _route_after_plan, {
        "gen_sql": "gen_sql",
        "clarify": END,
        "reject": END,
    })
    g.add_conditional_edges("gen_sql", _route_after_gen_sql, {
        "execute": "execute",
        "gen_sql": "gen_sql",
        "reject": END,
    })
    g.add_conditional_edges("execute", _route_after_execute, {
        "present": "present",
        "gen_sql": "gen_sql",
        "reject": END,
    })
    g.add_edge("present", "narrate")
    g.add_edge("narrate", END)

    return g.compile()
