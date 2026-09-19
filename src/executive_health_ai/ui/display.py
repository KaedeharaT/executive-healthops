"""Business-facing display adapters for HealthOps UI surfaces.

Persistence keeps stable English contracts.  Renderers must use these helpers
instead of exposing those contracts, actor codes, or synthetic fixture names.
"""
from __future__ import annotations

from pathlib import Path


from executive_health_ai.ui.status_dictionary import STATUS as _STATUS, CONTEXT_STATUS as _CONTEXT_STATUS, status_label

_ROLE = {
    "doctor": "内部医生", "internal_doctor": "内部医生", "external_doctor": "外部医生",
    "manager": "健康管理师", "health_manager": "健康管理师", "member": "成员本人",
    "patient": "成员本人", "system": "系统", "care_team": "健康管理团队",
}

_ENTITY = {
    "RiskEvent": "风险事项", "ReportExtractionCandidate": "报告资料", "Document": "体检报告",
    "DoctorReview": "医生复核", "ServiceRequest": "服务申请", "HealthProblem": "健康问题",
    "MedicationPlan": "用药记录", "HealthEvent": "医疗记录", "Task": "执行任务",
}

_EVENT = {
    "medication_start": "开始用药", "medication_change": "调整用药", "medication_stop": "停止用药",
    "procedure": "医疗处置", "surgery": "手术", "hospitalization": "住院", "report": "体检",
    "doctor_review": "医生复核", "external_referral": "外部医疗协同", "service": "服务",
    "risk": "风险", "assessment": "健康评估", "health_data_summary": "健康数据汇总",
}

_SOURCE = {
    "REPORT_TEXT": "体检报告原文", "REPORT_TABLE": "体检报告表格", "EXCEL": "表格资料",
    "DEVICE_DATA": "健康设备数据", "RISK": "风险触发数据", "DOCTOR_REVIEW": "医生复核记录",
    "MEMBER_REPORTED": "成员自述", "MANAGER_CONFIRMED": "健康管理确认记录",
}

_PROVIDER = {
    "apple_health": "Apple Health",
    "mock_oura": "演示健康设备（Oura）",
    "mock_yuwell": "演示血压设备",
    "mock_cgm": "演示连续血糖设备",
    "glucose_meter_interface": "血糖仪",
    "manual": "手工录入",
    "report": "体检报告",
    "pdf": "健康报告文件",
    "csv": "导入数据文件",
    "excel": "导入数据文件",
    "json": "设备数据接口",
}

_QUALITY = {
    "VALID": "数据正常",
    "SUSPECT": "数据需确认",
    "INVALID": "数据不可用",
    "MISSING": "暂无数据",
    "DUPLICATE": "重复数据",
    "MANUALLY_CORRECTED": "已人工修正",
}

_AUDIT_ACTION = {
    "confirmed_alert": "确认健康异常",
    "recorded_doctor_review": "记录医生复核",
    "closed_follow_up": "完成随访",
    "created_task": "创建跟进任务",
    "member_plan_choice": "成员确认计划",
    "outcome_decision": "确认阶段结果后的管理决定",
}


def get_status_display(value: str | None, *, context: str | None = None) -> str:
    return status_label(value, context=context)


def get_role_display(value: str | None, *, name: str | None = None) -> str:
    person = (name or "").strip()
    if person.lower() in _ROLE:
        return _ROLE[person.lower()]
    if person and person.lower() not in {"doctor", "manager", "member", "none", "null", "unknown"}:
        return person
    return _ROLE.get((value or "").strip().lower(), "负责人待分配")


def get_entity_type_display(value: str | None) -> str:
    return _ENTITY.get((value or "").strip(), "健康记录")


def get_event_type_display(value: str | None) -> str:
    return _EVENT.get((value or "").strip().lower(), "健康记录")


def get_source_type_display(value: str | None) -> str:
    raw = (value or "").strip()
    if raw and any("\u4e00" <= char <= "\u9fff" for char in raw):
        return raw
    return _SOURCE.get(raw.upper(), "来源信息待补充")


def get_provider_display(value: str | None) -> str:
    raw = (value or "").strip().lower()
    return _PROVIDER.get(raw, "健康数据来源")


def get_quality_display(value: str | None) -> str:
    return _QUALITY.get((value or "").strip().upper(), "数据状态待确认")


def get_audit_action_display(value: str | None) -> str:
    return _AUDIT_ACTION.get((value or "").strip().lower(), "已记录处理")


def get_risk_display(value: str | None) -> str:
    return {"RED": "高风险", "HIGH": "高风险", "YELLOW": "中风险", "MEDIUM": "中风险", "GREEN": "低风险", "LOW": "低风险"}.get((value or "").strip().upper(), "暂无正式风险评估")


def humanize_source_name(value: str | None, *, fallback: str = "来源资料") -> str:
    name = (value or "").strip()
    if not name:
        return fallback
    normalized = name.lower()
    if normalized.startswith(("synthetic_", "synthetic-", "demo_", "demo-", "test_", "test-")):
        stem = Path(name).stem.lower()
        if "progress" in stem:
            return "演示资料 · 健康进度记录"
        if "report" in stem or "体检" in name:
            return "演示资料 · 年度体检报告"
        if "medication" in stem or "用药" in name:
            return "演示资料 · 用药记录"
        return "演示资料 · 健康记录"
    return name
