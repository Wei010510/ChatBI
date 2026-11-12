"""10 个接口注册测试（AC-2）。"""
from app.main import app


def test_all_10_routes_registered():
    schema = app.openapi()
    paths = schema.get("paths", {})
    expected = {
        "/api/chat/ask": {"post"},
        "/api/chat/clarify": {"post"},
        "/api/sessions": {"get"},
        "/api/sessions/{session_id}/messages": {"get"},
        "/api/reports": {"post", "get"},
        "/api/reports/{report_id}": {"get", "patch", "delete"},
        "/api/health": {"get"},
    }
    for path, methods in expected.items():
        assert path in paths, f"路由缺失: {path}"
        actual = set(paths[path].keys())
        assert methods <= actual, f"{path} 方法缺失: 期望 {methods}, 实际 {actual}"

