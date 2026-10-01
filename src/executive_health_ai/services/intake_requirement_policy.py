"""Versioned intake submission policy, independent of SQL nullability and risk.

Requirements govern collecting a member's statements, not medical conclusions.
Unknown is an explicit answer, never inferred absence. Optional slots do not gate
submission. AUTO_FILLED is a ready draft value; provenance distinguishes source,
existing answers and resolved human input. Medical writes keep their own gates.
"""
from datetime import date
from executive_health_ai.services.assessment_import import NEGATIVE, IDENTITY, canonical
from executive_health_ai.services.management_workflow import TABLE_FIELDS, PROFILE_FIELDS


class IntakeRequirementPolicy:
    VERSION='initial-v1'
    REQUIRED={'基础资料':{'display_name'},'个人病史':{'疾病或问题'},'过敏史':{'名称'},
        '当前用药 / 营养补充':{'名称'},'生活方式':{'睡眠','烟草','饮酒'},'会员重点关注':{'concern'}}
    NEGATIVE=NEGATIVE|{'无手术史','无住院史','无手术或住院史','无用药','未用药','不需要','没有'}

    def __init__(self,version=VERSION):
        if version!=self.VERSION:raise ValueError('初评要求版本不可用，请核对后继续。')

    def requirement(self,section,field,record):
        identity=IDENTITY.get(section)
        absent=section in TABLE_FIELDS and (str(record.get(identity,'')).strip() in self.NEGATIVE
            or str(record.get('是否存在','')).strip() in {'否','无','没有'})
        if absent and field not in {identity,'是否存在'}:return 'NOT_APPLICABLE'
        if section=='手术 / 住院史' and field=='随访内容':
            followup=str(record.get('持续随访','')).strip()
            if followup in {'否','无','不需要','没有'}:return 'NOT_APPLICABLE'
            if followup in {'是','需要','有'}:return 'REQUIRED'
        if section=='家族健康史' and field=='患病家属' and record.get('具体疾病') and not absent:return 'REQUIRED'
        # A reported surgery needs its identity, not unconditional dates/hospital
        # questions for every member who has never reported a surgery.
        if section=='手术 / 住院史' and field=='名称' and any(record.get(f) for f in ('类型','日期','机构')):return 'REQUIRED'
        return 'REQUIRED' if field in self.REQUIRED.get(section,set()) else 'OPTIONAL'

    @staticmethod
    def equivalent(section,field,value):
        value=canonical(section,field,value)
        if (section,field)==('生活方式','烟草'):
            return {'不吸烟':'不吸烟','从不吸烟':'不吸烟','无吸烟':'不吸烟','不抽烟':'不吸烟','已经戒烟':'已戒烟'}.get(value,value)
        if (section,field)==('生活方式','饮酒'):
            return {'不饮酒':'不饮酒','从不饮酒':'不饮酒','不喝酒':'不饮酒'}.get(value,value)
        return value

    def source_resolution(self,group):
        """Only mutable self-reported status with fully dated evidence can advance.
        Unknown dates, demographic changes and clinical facts remain explicit gates.
        """
        section,field=group['section'],group['field']
        rows=group['rows']
        values={self.equivalent(section,field,r.structured_data_json['value']) for r in rows}
        old=group['current']
        if len(values)==1 and (not old or self.equivalent(section,field,old) in values):
            return canonical(section,field,rows[0].structured_data_json['value']),False
        if section not in PROFILE_FIELDS or old:return None,False
        dated=[]
        for r in rows:
            raw=r.structured_data_json.get('source_date','')
            try:d=date.fromisoformat(raw)
            except (TypeError,ValueError):return None,False
            if d>date.today():return None,False
            dated.append((d,r.structured_data_json['value']))
        latest=max(d for d,_ in dated)
        current={self.equivalent(section,field,v) for d,v in dated if d==latest}
        if len(current)!=1:return None,False
        return next(v for d,v in dated if d==latest),True

    @staticmethod
    def evidence_ok(group):
        return all(r.evidence_text and str(r.structured_data_json['value']) in r.evidence_text
            and r.structured_data_json.get('source_document_id')==str(r.document_id)
            and (r.structured_data_json.get('source_location') or r.structured_data_json.get('source_locator'))
            for r in group['rows'])

    def can_prefill(self,group,value,evidence_ok):
        if not value or not evidence_ok or group['ambiguous']:return False
        if group['section']=='基础资料':
            if group['field']=='sex' and value not in {'male','female'}:return False
            if group['field']=='birth_date':
                try:
                    if not date(1900,1,1)<=date.fromisoformat(value)<=date.today():return False
                except ValueError:return False
        for r in group['rows']:
            confidence=str(r.confidence or '').upper()
            if confidence not in {'HIGH','MEDIUM'}:return False
            if r.extraction_method not in {'LLM','FIELD_MAPPING','RULE','RULE_MAPPING'}:return False
            # MEDIUM is assigned to every LLM result by the existing extractor,
            # not an uncertainty prediction. Revalidate literal evidence/identity
            # before allowing a draft prefill; never promote a diagnosis or risk.
            if any(word in str(r.structured_data_json['value']) for word in ('疑似','可能','待排','不确定')):return False
        return True
