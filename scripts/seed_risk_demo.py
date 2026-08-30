"""Seed approved DEMO ONLY workflow rules, never clinical production rules."""
from sqlalchemy import select
from executive_health_ai.database import SessionLocal
from executive_health_ai.models import EmergencyContact, Patient, RiskRule
from executive_health_ai.services.risk_triage import RiskEvaluationService

RULES=[("DEMO_WELLNESS_GREEN","稳定日常健康趋势（演示）","WELLNESS","GREEN","CONTINUE_MONITORING"),("DEMO_MEDICAL_YELLOW","医疗监测趋势需要人工核实（演示）","MEDICAL_MONITOR","YELLOW","MANAGER_REVIEW"),("DEMO_SYNTHETIC_RED","合成紧急风险流程（演示）","MEDICAL_MONITOR","RED","EMERGENCY_ACTION")]
with SessionLocal() as session:
    for code,name,device,level,action in RULES:
        if not session.scalar(select(RiskRule).where(RiskRule.code==code)):
            session.add(RiskRule(name=name,code=code,applicable_device_class=device,canonical_code=None,risk_level=level,condition_type="SYNTHETIC_DEMO_FLAG",threshold_config={},window_config={},requires_repeated_measurement=False,requires_symptom_confirmation=False,action_type=action,source_reference="DEMO WORKFLOW RULE：仅用于工作流验证，不作为医疗判断依据。",review_status="APPROVED",reviewed_by="演示审核",is_active=True))
    member=session.scalar(select(Patient).where(Patient.external_id=="demo-executive-001"))
    if member and not session.scalar(select(EmergencyContact).where(EmergencyContact.patient_id==member.id)):
        session.add(EmergencyContact(patient_id=member.id,name="演示紧急联系人",relationship="家庭联系人",phone="00000000000",is_primary=True,consent_status="DEMO_ONLY"))
    if member:
        RiskEvaluationService().evaluate_demo(session,member.id,demo_flag="SYNTHETIC_YELLOW",provider="mock_yuwell",canonical_code="systolic_bp")
        RiskEvaluationService().evaluate_demo(session,member.id,demo_flag="SYNTHETIC_EMERGENCY",provider="mock_cgm",canonical_code="glucose")
    session.commit()
print("Synthetic risk rules seeded.")
