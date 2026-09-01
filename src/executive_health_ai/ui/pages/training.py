"""Health Manager Training Copilot page backed by approved knowledge."""

from __future__ import annotations

import logging
import streamlit as st
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from uuid import UUID

from executive_health_ai.models import TrainingSession
from executive_health_ai.services.training_copilot import TRAINING_CASES, TrainingCopilotService
from executive_health_ai.services.schema_guard import DatabaseSchemaOutdated, require_training_schema
from executive_health_ai.ui.components.ai_citations import render_ai_citations


LOGGER = logging.getLogger(__name__)


def _render_database_error(exc: Exception) -> None:
    """Keep technical details in logs while giving operators a safe recovery path."""
    LOGGER.exception("Training Copilot database operation failed", exc_info=exc)
    st.error("培训数据暂时不可用，请确认数据库已升级后重试。")
    st.caption("开发环境请执行：.\\.venv\\Scripts\\python.exe -m alembic upgrade head")


def render_training_copilot(session_factory: sessionmaker) -> None:
    st.title("健管培训助手")
    st.caption("通过标准流程、已审核知识和模拟案例，练习健康管理工作与跨角色协同。")
    st.info("Portfolio Training Prototype · 仅用于岗位流程训练，不用于诊断、处方或正式绩效考核。")
    try:
        with session_factory() as schema_session:
            require_training_schema(schema_session)
    except DatabaseSchemaOutdated as exc:
        LOGGER.warning("Training Copilot schema is not current: %s", exc)
        st.error("培训数据结构尚未初始化，请完成数据库升级后重试。")
        st.caption("开发环境请执行：.\\.venv\\Scripts\\python.exe -m alembic upgrade head")
        return
    except SQLAlchemyError as exc:
        _render_database_error(exc)
        return
    mode = st.radio("训练模式", ["问答学习", "案例训练", "能力评估"], horizontal=True, key="training-mode")
    left, right = st.columns([1.9, 1], gap="large")
    service = TrainingCopilotService()

    if mode == "问答学习":
        with left:
            question = st.text_area("输入问题", placeholder="例如：Yellow Risk 接手后下一步做什么？", key="training-question")
            if st.button("查找已审核资料并回答", type="primary", key="training-ask") and question.strip():
                try:
                    with session_factory() as session:
                        answer = service.answer_question(session, question.strip())
                        session.commit()
                except SQLAlchemyError as exc:
                    _render_database_error(exc)
                    return
                st.session_state["training-last-answer"] = answer
            answer = st.session_state.get("training-last-answer")
            if answer:
                st.markdown("#### 培训回答")
                st.write(answer.content)
                render_ai_citations(answer, key="training-qa")
        with right:
            st.markdown("#### 学习边界")
            st.write("回答只使用当前知识库中已批准且有效的资料。")
            st.write("医学判断应提交医生；健管师负责流程、沟通与闭环。")
    else:
        labels = {case.case_id: f"{case.category_label} · {case.title}" for case in TRAINING_CASES}
        with left:
            case_key = f"training-case-{mode}"
            pending_case = st.session_state.pop(f"training-next-case-{mode}", None)
            if pending_case:
                st.session_state[case_key] = pending_case
            selected = st.selectbox("选择模拟案例", list(labels), format_func=labels.get, key=case_key)
            case = service.get_case(selected)
            with st.container(border=True):
                st.markdown(f"#### {case.title}")
                st.write(case.scenario)
                st.markdown(f"**任务：{case.question}**")
            response = st.text_area("你的处理思路", height=150, key=f"training-response-{mode}")
            action_label = "提交案例" if mode == "案例训练" else "提交完整评估"
            if st.button(action_label, type="primary", key=f"training-submit-{mode}") and response.strip():
                try:
                    with session_factory() as session:
                        record_id = st.session_state.get(f"training-session-{mode}")
                        record = session.get(TrainingSession, UUID(record_id)) if record_id else None
                        if record is None or record.status == "COMPLETED":
                            record = service.start_session(session, mode="CASE" if mode == "案例训练" else "ASSESSMENT", case_id=case.case_id)
                        result = service.evaluate_case(
                            session, case.case_id, response.strip(),
                            mode="CASE" if mode == "案例训练" else "ASSESSMENT",
                            training_session=record,
                        )
                        session.commit()
                        st.session_state[f"training-session-{mode}"] = str(record.id)
                except SQLAlchemyError as exc:
                    _render_database_error(exc)
                    return
                st.session_state[f"training-result-{mode}"] = result
            result = st.session_state.get(f"training-result-{mode}")
            if result:
                next_case_id = result.score.get("next_case_id")
                if mode == "能力评估" and next_case_id:
                    st.info("本步决策已记录。完成下一案例后统一生成能力结果。")
                elif mode == "案例训练":
                    st.markdown("#### Coach Feedback")
                else:
                    st.markdown("#### 能力结果")
                    st.metric("流程完成度", f"{result.score['score']} / {result.score['max_score']}")
                if mode != "能力评估" or not next_case_id:
                    st.write(result.answer.content)
                    render_ai_citations(result.answer, key=f"training-result-citations-{mode}")
                if next_case_id and st.button("继续案例", key=f"training-continue-{mode}"):
                    st.session_state[f"training-next-case-{mode}"] = next_case_id
                    st.session_state.pop(f"training-result-{mode}", None)
                    st.rerun()
        with right:
            st.markdown("#### 当前训练")
            st.write(case.category_label)
            st.markdown("**训练目标**")
            for objective in case.objectives:
                st.write(f"• {objective}")
            st.markdown("**进度**")
            progress = st.session_state.get(f"training-result-{mode}")
            st.write(f"{2 if progress and not progress.score.get('next_case_id') else 1} / 2")
            st.caption("评分以绑定已审核资料的确定性 rubric 为主；AI 只负责组织反馈语言。")
