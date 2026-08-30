"""Business UI must translate persistence contracts and never invent evidence."""

from pathlib import Path

from executive_health_ai.ui.display import (
    get_entity_type_display,
    get_event_type_display,
    get_role_display,
    get_source_type_display,
    get_status_display,
    humanize_source_name,
)


APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"


def _source(name: str, next_marker: str) -> str:
    return APP.read_text(encoding="utf-8").split(f"def {name}", 1)[1].split(next_marker, 1)[0]


def test_context_aware_status_and_role_display_never_expose_open_or_doctor_codes() -> None:
    assert get_status_display("OPEN", context="doctor_review") == "等待医生复核"
    assert get_status_display("OPEN", context="risk_event") == "等待处理"
    assert get_status_display("REQUESTED", context="service_request") == "已申请"
    assert get_status_display("INCOMPLETE", context="report_candidate") == "原文不完整，需要人工核对"
    assert get_role_display("doctor") == "内部医生"
    assert get_role_display("health_manager") == "健康管理师"
    assert get_role_display("external_doctor") == "外部医生"


def test_common_entities_events_sources_and_synthetic_filenames_are_humanized() -> None:
    assert get_entity_type_display("RiskEvent") == "风险事项"
    assert get_event_type_display("medication_change") == "调整用药"
    assert get_source_type_display("DEVICE_DATA") == "健康设备数据"
    assert humanize_source_name("synthetic_progress_ui.txt") == "演示资料 · 健康进度记录"
    assert humanize_source_name("demo_medication_a.csv") == "演示资料 · 用药记录"


def test_timeline_detail_translates_status_owner_and_keeps_rule_code_out_of_business_copy() -> None:
    timeline = _source("render_longitudinal_timeline", "def _client_device_status")
    assert '"当前状态": _label(' in timeline
    assert '"负责人": _role_label(' in timeline
    risk_block = timeline.split('if event.event_type == "risk" and not client_view:', 1)[1].split('if event.event_type == "assessment":', 1)[0]
    assert "details.get('rule_code'" not in risk_block
    assert "触发指标：" in risk_block


def test_evidence_renderer_is_type_aware_and_honest_when_no_raw_excerpt_exists() -> None:
    renderer = _source("render_evidence_panel", "def evidence_action")
    assert "file_evidence" in renderer and "data_evidence" in renderer
    assert "数据来源" in renderer and "来源文件" in renderer
    assert "当前未保存精确位置" in renderer
    assert "当前未保存可展示的原文片段。" in renderer
    assert "相关正式记录" not in renderer
    assert "来源位置待补充" not in renderer


def test_timeline_evidence_does_not_use_summary_as_fake_original_text() -> None:
    payload = _source("_timeline_evidence_payload", "def render_evidence_panel")
    assert '"raw_evidence": event.summary' not in payload
    assert '"location": "相关正式记录"' not in payload
    assert "MANAGER_CONFIRMED" in payload and "DEVICE_DATA" in payload


def test_technical_ids_remain_inside_the_advanced_information_branch() -> None:
    renderer = _source("render_evidence_panel", "def evidence_action")
    advanced = renderer.split('with st.expander("高级信息"):', 1)[1]
    assert "technical" in advanced
    assert "rule_code" not in renderer.split('with st.expander("高级信息"):', 1)[0]


def test_service_request_states_are_business_facing() -> None:
    assert get_status_display("REQUESTED", context="service_request") == "已申请"
    assert get_status_display("REVIEWING", context="service_request") == "审核中"
    assert get_status_display("SCHEDULED", context="service_request") == "已安排"
    assert get_status_display("DECLINED", context="service_request") == "未通过"


def test_candidate_statuses_are_business_facing() -> None:
    assert get_status_display("EVIDENCE_MISMATCH", context="report_candidate") == "提取内容与原始依据不一致"
    assert get_status_display("AMBIGUOUS", context="report_candidate") == "内容存在歧义，需要人工判断"
    assert get_status_display("UNKNOWN") == "暂无正式风险评估"


def test_missing_role_does_not_render_none_or_unknown() -> None:
    assert get_role_display(None) == "负责人待分配"
    assert get_role_display("doctor", name="王医生") == "王医生"


def test_source_types_cover_report_table_device_risk_and_doctor_records() -> None:
    assert get_source_type_display("REPORT_TEXT") == "体检报告原文"
    assert get_source_type_display("REPORT_TABLE") == "体检报告表格"
    assert get_source_type_display("DEVICE_DATA") == "健康设备数据"
    assert get_source_type_display("RISK") == "风险触发数据"
    assert get_source_type_display("DOCTOR_REVIEW") == "医生复核记录"


def test_source_name_never_exposes_test_or_synthetic_filename() -> None:
    assert humanize_source_name("test_report_result.pdf") == "演示资料 · 年度体检报告"
    assert humanize_source_name("demo_unknown.json") == "演示资料 · 健康记录"


def test_report_timeline_uses_confirmed_candidate_evidence_when_available() -> None:
    payload = _source("_timeline_evidence_payload", "def render_evidence_panel")
    assert "ReportExtractionCandidate.status == \"CONFIRMED\"" in payload
    assert "_candidate_evidence_payload(candidate, document)" in payload


def test_missing_report_evidence_is_explicitly_honest() -> None:
    payload = _source("_timeline_evidence_payload", "def render_evidence_panel")
    assert '"raw_evidence": None' in payload
    assert "当前未关联可展示的原文片段" in payload


def test_device_evidence_is_not_rendered_as_a_source_file() -> None:
    renderer = _source("render_evidence_panel", "def evidence_action")
    assert 'data_evidence = evidence_type in {"OBSERVATION", "DEVICE_DATA", "RISK"}' in renderer
    assert "**数据来源**" in renderer


def test_risk_payload_marks_demo_rules_and_never_invents_samples() -> None:
    payload = _source("_risk_evidence_payload", "def _baseline_evidence_payload")
    assert "演示风险；" in payload
    assert '"raw_evidence": raw or None' in payload
    assert "当前未保存可展示的触发数据样本" in payload


def test_generic_timeline_evidence_does_not_use_vague_health_record_fallback() -> None:
    payload = _source("_timeline_evidence_payload", "def render_evidence_panel")
    assert "相关正式记录" not in payload
    assert "已确认的业务记录；当前未保存更细的来源说明" in payload


def test_raw_ingestion_json_is_only_in_advanced_information() -> None:
    queue = _source("_render_data_review_queue", "def render_member_device_assignments")
    assert 'with st.expander("高级信息：处理详情"):' in queue
    assert queue.index('with st.expander("高级信息：处理详情"):') < queue.index("st.json(record.normalization_json)")


def test_device_assignment_control_has_no_provider_code_label() -> None:
    assignments = _source("render_member_device_assignments", "def render_risk_rules")
    assert 'st.selectbox("设备",' in assignments
    assert "设备/Provider" not in assignments
