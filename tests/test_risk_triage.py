from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from executive_health_ai.models import Base, Observation, Patient, RiskRule, RiskEvent
from executive_health_ai.services.risk_triage import RiskEvaluationService

def test_provider_classification_and_approved_demo_risk_flow():
    engine=create_engine("sqlite+pysqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool); Base.metadata.create_all(engine)
    with sessionmaker(bind=engine,class_=Session)() as session:
        patient=Patient(external_id="synthetic-risk",timezone="Asia/Tokyo"); session.add(patient); session.flush()
        for code,device,level in [("g","WELLNESS","GREEN"),("y","MEDICAL_MONITOR","YELLOW"),("r","MEDICAL_MONITOR","RED")]:
            session.add(RiskRule(name=code,code=code,applicable_device_class=device,canonical_code=None,risk_level=level,condition_type="SYNTHETIC_DEMO_FLAG",threshold_config={},window_config={},requires_repeated_measurement=False,requires_symptom_confirmation=False,action_type="DEMO",source_reference="DEMO",review_status="APPROVED",is_active=True))
        session.flush(); service=RiskEvaluationService()
        assert service.classify_provider("apple_health")=="WELLNESS" and service.classify_provider("mock_cgm")=="MEDICAL_MONITOR"
        assert service.evaluate_demo(session,patient.id,demo_flag=None,provider="apple_health").risk_level=="GREEN"
        assert service.evaluate_demo(session,patient.id,demo_flag="SYNTHETIC_YELLOW",provider="mock_yuwell").risk_level=="YELLOW"
        assert service.evaluate_demo(session,patient.id,demo_flag="SYNTHETIC_EMERGENCY",provider="mock_cgm").risk_level=="RED"
        assert len(session.scalars(select(RiskEvent)).all())==2
        service.evaluate_demo(session,patient.id,demo_flag="SYNTHETIC_YELLOW",provider="mock_yuwell")
        assert len(session.scalars(select(RiskEvent)).all())==2


def test_test_scoped_rule_cannot_grade_a_non_demo_uat_member():
    engine=create_engine("sqlite+pysqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool); Base.metadata.create_all(engine)
    with sessionmaker(bind=engine,class_=Session)() as session:
        member=Patient(external_id="uat-member-001",timezone="Asia/Tokyo"); session.add(member); session.flush()
        session.add(RiskRule(name="合成测试规则",code="SYNTHETIC_SCOPE_GATE",applicable_device_class="ANY",canonical_code="glucose",risk_level="YELLOW",condition_type="SYNTHETIC_TEST_THRESHOLD",threshold_config={"metric":"glucose","operator":">=","value":"1","unit":"x"},window_config={},requires_repeated_measurement=False,requires_symptom_confirmation=False,action_type="SYNTHETIC_TEST_ONLY",source_reference="SYNTHETIC TEST ONLY",review_status="APPROVED",reviewed_by="synthetic",is_active=True))
        session.flush()
        observation=Observation(patient_id=member.id,observed_at=datetime.now(timezone.utc),metric_code="glucose",value_numeric=Decimal("2"),unit="x",source="manual",quality_flag="valid")
        session.add(observation); session.flush()
        result=RiskEvaluationService().evaluate_observation(session,observation.id)
        assert result.evaluated_rule_count==0 and not result.events
