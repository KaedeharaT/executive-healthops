"""Read actual renderer boundaries after role-page extraction."""
import ast
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src/executive_health_ai/ui"
MOVED = {
    "render_manager_dashboard": ("pages/manager/workbench.py", "today"),
    "render_members_workspace": ("pages/manager/workbench.py", "directory"),
    "render_service_operations_workspace": ("pages/manager/services.py", "services"),
    "render_member_detail": ("pages/manager/experience.py", "member_detail"),
    "_render_client_home": ("pages/member/experience.py", "home"),
    "_render_client_plan": ("pages/member/experience.py", "plan"),
    "_render_client_health_overview": ("pages/member/experience.py", "overview"),
}
def source(name, next_marker):
    if name in MOVED:
        file, function = MOVED[name]
        text = (UI / file).read_text(encoding="utf-8")
        node = next(n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef) and n.name == function)
        return ast.get_source_segment(text, node)
    return (ROOT / "streamlit_app.py").read_text(encoding="utf-8").split(f"def {name}", 1)[1].split(next_marker, 1)[0]
def all_ui_source():
    return (ROOT / "streamlit_app.py").read_text(encoding="utf-8") + "\n".join(p.read_text(encoding="utf-8") for p in UI.rglob("*.py"))
