"""Read-only annual portfolio; percentages represent recorded work, never health risk."""
from dataclasses import dataclass
from datetime import date, timedelta
from sqlalchemy import select
from executive_health_ai.models import HealthProgram, Patient
from executive_health_ai.services.member_management_projection import MemberManagementProjection

STAGES = ('建立基线', '持续管理', '阶段复盘', '年度复盘', '已结束')
CLOSED = {'COMPLETED', 'CANCELLED', 'CLOSED', 'REVIEWED'}


@dataclass(frozen=True)
class AnnualRow:
    member: object
    view: object
    year: int
    stage: str
    progress: str
    open_count: int
    waiting: str
    phase_end: date | None
    next_node: str
    overdue: bool
    waiting_doctor: bool
    review_due: bool
    abnormal: bool

    @property
    def id(self):
        return self.view.program.id


def project(member, view, today=None):
    today = today or date.today()
    program, phase = view.program, view.current_phase
    ended = program.status in {'COMPLETED', 'CANCELLED', 'CLOSED'}
    baseline = dict(view.milestones).get('健康基线', False)
    reviewed = {r.phase_id for r in view.reviews}
    phase_due = bool(not ended and phase and phase.id not in reviewed and phase.end_date <= today + timedelta(days=14))
    annual_due = bool(not ended and program.end_date and program.end_date <= today + timedelta(days=30))
    stage = '已结束' if ended else '建立基线' if not baseline else '年度复盘' if annual_due else '阶段复盘' if phase_due else '持续管理'
    # Unlinked legacy tasks remain visible in Member360, but cannot inflate a cycle's progress.
    tasks = [t for t in view.tasks if t.program_id == program.id and t.status != 'CANCELLED']
    phase_tasks = [t for t in tasks if phase and t.due_at and phase.start_date <= t.due_at.date() <= phase.end_date]
    if stage == '建立基线':
        count = sum(done for _, done in view.milestones)
        progress = f'{round(100 * count / len(view.milestones))}% · 入组 {count}/{len(view.milestones)}' if view.milestones else '未配置'
    elif phase and phase.status in CLOSED:
        progress = '100% · 已完成阶段'
    elif phase_tasks:
        count = sum(t.status == 'COMPLETED' for t in phase_tasks)
        progress = f'{round(100 * count / len(phase_tasks))}% · 事项 {count}/{len(phase_tasks)}'
    else:
        progress = '未配置阶段事项' if not ended else '周期已结束'
    open_tasks = [t for t in tasks if t.status not in CLOSED]
    rechecks = [r for r in view.rechecks if r.status != 'CLOSED']
    services = [r for r in view.services if r.program_id == program.id and r.status not in CLOSED]
    doctor = any(r.status == 'PENDING' for r in view.doctor_reviews) or any(r.status not in {'COMPLETED', 'WAITING_ACTIONS'} for r in view.consultations)
    waiting_member = any(t.status in {'WAITING_MEMBER', 'AWAITING_MEMBER'} for t in open_tasks)
    waiting = '等待医生' if doctor else '等待会员' if waiting_member else '—'
    overdue = not ended and (any(t.due_at and t.due_at.date() < today for t in open_tasks)
        or any(r.planned_at and r.planned_at.date() < today for r in rechecks)
        or bool(phase_due and phase.end_date < today) or bool(program.end_date and program.end_date < today))
    abnormal = program.status in {'PAUSED', 'ESCALATED_TO_MEDICAL_CARE', 'BLOCKED'}
    next_phase = next((p.title for p in view.phases if phase and p.sequence > phase.sequence), None)
    next_node = ('查看年度结果' if ended else '确认年度基线' if not baseline else '年度复盘' if annual_due
                 else '阶段复盘' if phase_due else next_phase or '核对年度安排')
    return AnnualRow(member, view, program.cycle_year or program.start_date.year, stage, progress,
                     len(open_tasks) + len(rechecks) + len(services), waiting, phase.end_date if phase else None,
                     next_node, bool(overdue), doctor, phase_due or annual_due, abnormal)


def load(session, today=None):
    projection = MemberManagementProjection()
    programs = session.execute(select(Patient, HealthProgram).join(HealthProgram, HealthProgram.patient_id == Patient.id)
                               .order_by(HealthProgram.start_date.desc(), Patient.display_name)).all()
    return [project(member, projection.member(session, member.id, program.id), today) for member, program in programs]


def summary(rows):
    count = lambda predicate: len({r.member.id for r in rows if predicate(r)})
    return [('管理中会员', count(lambda r: r.stage != '已结束')),
            ('待建立基线', count(lambda r: r.stage == '建立基线')),
            ('持续管理中', count(lambda r: r.stage == '持续管理')),
            ('即将阶段复盘', count(lambda r: r.stage == '阶段复盘' and r.phase_end and r.phase_end >= date.today())),
            ('待年度复盘', count(lambda r: r.stage == '年度复盘')),
            ('逾期 / 异常', count(lambda r: r.overdue or r.abnormal))]


def filter_rows(rows, *, year='全部', stage='全部', owner='全部', overdue='全部', doctor='全部', review='全部', status='全部', query=''):
    def flag(value, option):
        return option == '全部' or value == (option == '是')
    return [r for r in rows if (year == '全部' or r.year == int(year)) and (stage == '全部' or r.stage == stage)
            and (owner == '全部' or (r.view.owner or '待分配') == owner)
            and flag(r.overdue, overdue) and flag(r.waiting_doctor, doctor) and flag(r.review_due, review)
            and (status == '全部' or r.view.program.status == status)
            and (not query or query.casefold() in (r.member.display_name + r.view.program.main_goal).casefold())]
