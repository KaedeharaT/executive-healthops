"""Central Chinese display dictionary; internal contracts remain English."""
from __future__ import annotations
from datetime import datetime
from executive_health_ai.blood_pressure import TOKYO_TIMEZONE

STATUS = {"NEW":"新建","AI_SCREENED":"规则筛查完成","WAITING_MANAGER_REVIEW":"待健康管理师核实","MANAGER_CONFIRMED":"管理师已确认","WAITING_DOCTOR_REVIEW":"待医生复核","IN_FOLLOW_UP":"随访中","CLOSED":"已关闭","OPEN":"待处理","ACTIVE":"进行中","INACTIVE":"未启用","PENDING":"等待处理","PENDING_REVIEW":"待审核","NEEDS_MANUAL_REVIEW":"需要人工核对","IN_PROGRESS":"进行中","REQUESTED":"已申请","REVIEWING":"审核中","APPROVED":"已批准","SCHEDULED":"已安排","WAITING_FEEDBACK":"等待反馈","DECLINED":"未批准","COMPLETED":"已完成","CANCELLED":"已取消","OVERDUE":"已逾期","CONFIRMED":"已确认","ASSESSMENT":"健康评估","90_DAY_PROGRAM":"90天健康管理","STABILIZATION":"稳定管理","ANNUAL_MANAGEMENT":"年度健康管理","FAMILY_EXTENSION":"家庭健康管理","PLANNED":"待开始","PAUSED":"已暂停","NEEDS_REASSESSMENT":"待重新评估","ESCALATED_TO_MEDICAL_CARE":"已升级医疗处理","ADJUSTED":"已调整","RESOLVED":"已处理","IMPROVED":"已改善","STABLE":"基本稳定","WORSENED":"出现恶化","INSUFFICIENT_DATA":"数据不足","NEEDS_MEDICAL_REVIEW":"需要医生复核","NEEDS_REVIEW":"等待人工确认","INCOMPLETE":"原文需要人工核对","EVIDENCE_MISMATCH":"证据与提取内容不一致","AMBIGUOUS":"内容存在歧义","SUCCESS":"成功","PARTIAL_SUCCESS":"部分成功","FAILED":"失败","UNMATCHED":"未匹配成员","VALID":"有效","SUSPECT":"待核实","INVALID":"无效","DUPLICATE":"重复","MANUALLY_CORRECTED":"已人工修正","WAITING_REVIEW":"等待人工复核"}
PRIORITY={"CRITICAL":"紧急","HIGH":"高","MEDIUM":"中","LOW":"低","OVERDUE":"已逾期"}
PROVIDER={"apple_health":"Apple Health","mock_yuwell":"演示血压设备","mock_oura":"演示健康设备（Oura）","mock_cgm":"演示连续血糖设备","glucose_meter_interface":"血糖仪","manual":"手工录入","report":"体检报告","csv":"导入数据文件","excel":"导入数据文件","pdf":"健康报告文件","json":"设备数据接口"}
OBSERVATION={"systolic_bp":"收缩压","diastolic_bp":"舒张压","blood_pressure":"血压","heart_rate":"心率","resting_heart_rate":"静息心率","hrv":"心率变异性","glucose":"血糖","blood_glucose":"血糖","cgm_glucose":"动态血糖","weight":"体重","height":"身高","bmi":"体重指数","waist":"腰围","body_fat":"体脂率","sleep_duration":"睡眠时长","deep_sleep_duration":"深度睡眠","light_sleep_duration":"浅睡","rem_sleep_duration":"REM 睡眠","awake_duration":"清醒时间","sleep_score":"睡眠评分","steps":"步数","exercise_minutes":"运动时长","active_calories":"活动消耗","spo2":"血氧饱和度","hba1c":"糖化血红蛋白","ldl_c":"低密度脂蛋白胆固醇","hdl_c":"高密度脂蛋白胆固醇","triglycerides":"甘油三酯","alt":"ALT","ast":"AST"}
BARRIER={"TRAVEL":"出差","WORK_PRESSURE":"工作压力","SOCIAL_DINING":"应酬较多","POOR_SLEEP":"睡眠不足","TOO_DIFFICULT":"当前任务难度过高","FORGOT":"遗忘","LOW_MOTIVATION":"执行动力不足","SIDE_EFFECT_CONCERN":"担心药物或干预副作用","FAMILY_REASON":"家庭原因","SCHEDULE_CONFLICT":"时间冲突","OTHER":"其他"}
TYPE={"alert":"健康异常","problem":"健康问题","task":"执行任务","follow_up":"随访","observation":"健康数据","doctor_review":"医生复核","management_plan":"管理方案","audit":"操作记录","program_review":"阶段复盘","execution_risk":"执行风险","outcome":"阶段效果评估"}
PROGRAM_TYPE={"NINETY_DAY":"90天健康管理","STABILIZATION":"稳定管理","ANNUAL":"年度健康管理"}
PROGRAM_PHASE={"STARTUP":"启动与基线建立","EXECUTION":"执行与调整","STABILIZATION":"稳定与适应","REASSESSMENT":"阶段复评","ONGOING":"持续管理"}
RISK_LEVEL={"GREEN":"低风险","YELLOW":"中风险","RED":"高风险","UNKNOWN":"暂无正式风险评估","NEEDS_REVIEW":"等待人工确认"}
DEVICE_CLASS={"WELLNESS":"日常健康设备","MEDICAL_MONITOR":"医疗监测设备","UNKNOWN":"待确认设备类型"}
KNOWLEDGE_CATEGORY={"PATIENT_EDUCATION":"疾病与健康教育","MEDICATION":"药物","LAB_TEST":"检查与化验","DISEASE_CLASSIFICATION":"标准术语","INTERNAL_SOP":"内部SOP","COMMUNICATION":"成员沟通","AI_SAFETY":"AI安全边界","PRIVACY":"隐私与数据边界","RISK_RULE_EVIDENCE":"风险规则依据（仅参考）","CLINICAL_GUIDELINE":"医疗指南","TEXTBOOK_REFERENCE":"教材与参考书","CHRONIC_RISK":"慢病与风险","MANAGEMENT_PROGRAM":"管理方案","SERVICE_SOP":"服务SOP","DATA_DEVICE":"数据与设备","SAFETY_COMPLIANCE":"医疗边界与合规"}
KNOWLEDGE_REVIEW_STATUS={"DRAFT":"草稿","PENDING_REVIEW":"待审核","APPROVED":"已批准","REJECTED":"未通过","ARCHIVED":"已归档"}
def status(value: str|None)->str:return STATUS.get(value or "", "待确认" if value else "未记录")
def priority(value: str|None)->str:return PRIORITY.get(value or "", "一般")
def provider(value: str|None)->str:return PROVIDER.get(value or "", "健康数据来源")
def observation(value: str|None)->str:return OBSERVATION.get(value or "", "健康数据")
def barrier(value: str|None)->str:return BARRIER.get(value or "", "其他原因")
def type_label(value: str|None)->str:return TYPE.get(value or "", "健康记录")
def program_type(value: str|None)->str:return PROGRAM_TYPE.get(value or "", "健康管理计划")
def program_phase(value: str|None)->str:return PROGRAM_PHASE.get(value or "", "待确认阶段")
def risk_level(value: str|None)->str:return RISK_LEVEL.get(value or "", "暂无正式风险评估")
def device_class(value: str|None)->str:return DEVICE_CLASS.get(value or "", "待确认设备类型")
def knowledge_category(value: str|None)->str:return KNOWLEDGE_CATEGORY.get(value or "", "其他资料")
def knowledge_review_status(value: str|None)->str:return KNOWLEDGE_REVIEW_STATUS.get(value or "", "待确认")
def display_datetime(value: datetime|None)->str:
    if value is None:
        return "未记录"
    if value.tzinfo is None:
        value = value.replace(tzinfo=TOKYO_TIMEZONE)
    return value.astimezone(TOKYO_TIMEZONE).strftime("%Y-%m-%d %H:%M")
