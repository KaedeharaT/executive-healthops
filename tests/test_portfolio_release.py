"""Regression checks for the intentionally isolated portfolio release surface."""

from pathlib import Path

import pytest

from scripts.build_portfolio_demo import DEFAULT_DATABASE, _safe_target


ROOT = Path(__file__).resolve().parents[1]
LANDING_SHELL = ROOT / "src" / "executive_health_ai" / "ui" / "pages" / "shell.py"


def test_portfolio_release_assets_are_present() -> None:
    for relative_path in (
        "README.md",
        "portfolio/RESUME_PROJECT_ENTRY_ZH.md",
        "portfolio/DEMO_VIDEO_SCRIPT_ZH.md",
        "portfolio/PORTFOLIO_RELEASE_NOTES.md",
        "portfolio/DEMO_DATA_DESCRIPTION.md",
        "scripts/build_portfolio_demo.py",
        "scripts/start_portfolio_demo.ps1",
    ):
        assert (ROOT / relative_path).is_file(), relative_path


def test_portfolio_builder_can_only_rebuild_its_isolated_database() -> None:
    assert _safe_target(DEFAULT_DATABASE) == DEFAULT_DATABASE.resolve()
    with pytest.raises(ValueError):
        _safe_target(ROOT / "executive_health_ai.db")


def test_portfolio_readme_states_non_clinical_and_privacy_boundaries() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Research / Portfolio Prototype" in readme
    assert "不自动诊断" in readme
    assert "Clinical RiskRule" in readme
    assert "真实成员资料" in readme


def test_portfolio_landing_is_opt_in_and_uses_the_isolated_demo_mode() -> None:
    app = (ROOT / "streamlit_app.py").read_text(encoding="utf-8")
    landing = LANDING_SHELL.read_text(encoding="utf-8")
    assert "PORTFOLIO_DEMO_ENABLED" in app
    assert "_render_portfolio_landing" in app
    assert "render_portfolio_landing" in app
    assert "进入成员健康中心" in landing
    assert "进入 HealthOps 运营后台" in landing
