"""Read-only operational view of governed offline AI improvement assets."""

from __future__ import annotations

import streamlit as st
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from executive_health_ai.models import FeedbackDatasetVersion, FeedbackRecord, ModelVersionRegistry


_FEEDBACK_LABELS = {
    "AI_CONTENT_FEEDBACK": "AI 内容纠错",
    "WORKFLOW_FEEDBACK": "流程反馈",
    "RISK_RULE_FEEDBACK": "风险规则复核建议",
}
_STATUS_LABELS = {
    "CAPTURED": "已记录", "REVIEWED": "已审核",
    "ACCEPTED_FOR_DATASET": "已纳入 AI 改进", "REJECTED": "未采用",
    "CANDIDATE": "候选", "EVALUATING": "评测中", "APPROVED": "已批准",
    "ACTIVE": "当前使用", "RETIRED": "已停用",
}


def render_ai_improvement(session_factory: sessionmaker) -> None:
    st.title("AI 改进")
    st.caption("人工反馈经审核和去标识化后，仅用于离线评测、Prompt 优化或后续模型训练；不会在线学习或修改风险规则。")
    with session_factory() as session:
        feedback_total = int(session.scalar(select(func.count()).select_from(FeedbackRecord)) or 0)
        pending = int(session.scalar(select(func.count()).select_from(FeedbackRecord).where(FeedbackRecord.review_status == "CAPTURED")) or 0)
        dataset_total = int(session.scalar(select(func.count()).select_from(FeedbackDatasetVersion)) or 0)
        model_total = int(session.scalar(select(func.count()).select_from(ModelVersionRegistry)) or 0)
        feedback = list(session.scalars(select(FeedbackRecord).order_by(FeedbackRecord.created_at.desc()).limit(20)))
        datasets = list(session.scalars(select(FeedbackDatasetVersion).order_by(FeedbackDatasetVersion.created_at.desc()).limit(10)))
        models = list(session.scalars(select(ModelVersionRegistry).order_by(ModelVersionRegistry.created_at.desc()).limit(10)))

    cards = st.columns(4)
    cards[0].metric("反馈记录", feedback_total)
    cards[1].metric("待审核", pending)
    cards[2].metric("离线数据集版本", dataset_total)
    cards[3].metric("候选 / 模型版本", model_total)

    st.subheader("待审核与近期反馈")
    if feedback:
        st.dataframe([{
            "类型": _FEEDBACK_LABELS.get(item.feedback_type, "人工反馈"),
            "功能": item.feature,
            "状态": _STATUS_LABELS.get(item.review_status, "待确认"),
            "是否可进入离线数据集": "是" if item.eligible_for_training and item.deidentified else "否",
            "记录时间": item.created_at,
        } for item in feedback], hide_index=True, width="stretch")
    else:
        st.info("暂无反馈记录。人工纠错不会自动触发训练。")

    st.subheader("离线数据集与版本门禁")
    if datasets:
        st.dataframe([{
            "数据集": item.dataset_id, "版本": f"v{item.dataset_version:03d}",
            "样本数": item.record_count, "Schema": item.schema_version,
            "创建时间": item.created_at,
        } for item in datasets], hide_index=True, width="stretch")
    else:
        st.caption("尚未生成经审核、去标识化的离线数据集快照。")
    if models:
        st.dataframe([{
            "Provider": item.provider, "版本": item.model_version,
            "Prompt": item.prompt_version or "未记录",
            "状态": _STATUS_LABELS.get(item.status, "待确认"),
        } for item in models], hide_index=True, width="stretch")
    else:
        st.caption("尚无候选模型版本。新版本必须通过固定评测和人工批准后才能启用。")

    st.info("风险反馈只进入 Clinical Rule Review Queue；不会自动更新阈值、风险等级或 Clinical Rule。")
