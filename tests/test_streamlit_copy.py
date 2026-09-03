"""Regression checks for non-diagnostic Streamlit status wording."""

from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_streamlit_status_copy_describes_data_not_medical_conclusions() -> None:
    app_source = Path("streamlit_app.py").read_text(encoding="utf-8")

    assert '"normal": "数据完整，可进行趋势分析"' in app_source
    assert '"insufficient_data": "数据不足，暂无法判断趋势"' in app_source
    assert "今日跟进" in app_source
    assert '"今日", "成员", "医疗协同", "服务运营", "更多"' in app_source
    assert '"成员页面", ["概览", "管理", "健康", "医疗", "历程"]' in app_source
    assert "_render_lifecycle_grid" in app_source
    assert "timeline-spine-" in app_source
    assert "render_health_data(patient.id)" in app_source
    assert "健康监测" in app_source
    assert "今天的生活状态" in app_source
    assert "长期健康趋势" in app_source
    assert "查看全部健康数据" in app_source
    assert "查看详细趋势" in app_source
    assert "高级信息" in app_source
    assert "cgm-window-" in app_source
    assert "long-range-" in app_source
    assert "render_knowledge_library_entry" in app_source
    assert "待处理" in app_source
    assert "设备数据接入" in app_source
    assert "<span class=\"badge\"" not in app_source
    assert "NINETY_DAY" not in app_source.split("def render_programs", 1)[1].split("def render_outcomes", 1)[0]
    assert 'st.subheader("医生复核")' in app_source
    assert "系统不提供自动处方、停药、换药或剂量调整" in app_source
    assert "解析方式" in app_source
    assert "本地AI辅助：已使用" in app_source
    assert "本地AI辅助：本次未调用" in app_source
    assert "本地AI辅助：当前不可用" in app_source
    assert "混合解析" in app_source
    assert "重新整理报告" in app_source
    assert "规则识别结构化指标，并使用本地AI辅助整理复杂检查结论" in app_source
    assert "已使用当前规则和本地AI创建新的解析结果" in app_source
    assert "查看历史解析" in app_source
    assert "本地AI辅助解析" in app_source
    assert "正在解析体检报告…" in app_source
    assert "本地AI辅助解析中" in app_source
    assert "本地AI调用进度" in app_source
    assert "已完成：{completed} · 待处理：{remaining}" in app_source
    assert "已用时：" in app_source
    assert "解析进行中…" in app_source
    assert "disabled=in_progress" in app_source
    assert "disabled=is_processing" in app_source
    assert "_run_report_parse_with_progress" in app_source
    assert "血压正常" not in app_source
    assert "健康正常" not in app_source
    assert "无高血压风险" not in app_source


def test_streamlit_default_page_smoke_loads() -> None:
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "streamlit_app.py")
    app.run(timeout=30)

    assert not app.exception
    assert [title.value for title in app.title] == ["今日"]


def test_platform_launcher_uses_fixed_ports_safe_project_restart_and_single_browser_open() -> None:
    root = Path(__file__).resolve().parents[1]
    launcher = (root / "scripts" / "start_platform.ps1").read_text(encoding="utf-8")
    assert "--server.headless" in launcher and '"true"' in launcher
    assert "--server.port" in launcher and '"8501"' in launcher
    assert '"--port", "8000"' in launcher
    assert launcher.count('Start-Process "http://127.0.0.1:8501"') == 1
    assert "local LLM" in launcher
    assert "8505" not in launcher
    assert "Stop-ProjectService 8501" in launcher and "Stop-ProjectService 8000" in launcher
    assert "Get-NetTCPConnection" in launcher and "Is-ThisProjectProcess" in launcher
    assert "-m alembic upgrade head" in launcher
    assert "git pull" not in launcher and "git checkout" not in launcher
