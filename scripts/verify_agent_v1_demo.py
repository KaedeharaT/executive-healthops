"""Read-only persistence checks after the real-browser synthetic walkthrough."""
import json
import sqlite3
from pathlib import Path


def rows(connection, table):
    return connection.execute(f'SELECT * FROM {table} ORDER BY id').fetchall()


with sqlite3.connect('.runtime/agent-v1.db') as db, sqlite3.connect('.runtime/workbench-v4.db') as original:
    goal_id = Path('.runtime/agent-v1-goal.txt').read_text().strip()
    goal = db.execute('SELECT id,status,context_json,source_id FROM agent_goals WHERE id=?', (goal_id.replace('-', ''),)).fetchone()
    context = json.loads(goal[2])
    assert goal[1] == 'COMPLETED' and context['manager_confirmed'] and context['actions_confirmed']
    assert context['next_node']['owner'] and context['next_node']['due']
    assert db.execute('SELECT COUNT(*) FROM agent_goals WHERE source_id=?', (goal[3],)).fetchone()[0] == 1
    assert db.execute('SELECT status FROM doctor_reviews WHERE id=?', (context['review_id'].replace('-', ''),)).fetchone()[0] == 'CONFIRMED'
    mapping = {'tasks': 'tasks', 'rechecks': 'recheck_plans', 'followups': 'follow_ups', 'services': 'service_requests', 'logs': 'management_logs'}
    counts = {}
    for key, table in mapping.items():
        identities = context['created'][key]
        assert len(set(identities)) == len(identities)
        for identity in identities:
            assert db.execute(f'SELECT COUNT(*) FROM {table} WHERE id=?', (identity.replace('-', ''),)).fetchone()[0] == 1
        counts[key] = len(identities)
    assert counts == {'tasks': 3, 'rechecks': 1, 'followups': 1, 'services': 0, 'logs': 1}
    for identity in context['created']['tasks']:
        owner, due = db.execute('SELECT assignee,due_at FROM tasks WHERE id=?', (identity.replace('-', ''),)).fetchone()
        assert owner and due
    baseline_preserved = rows(db, 'health_assessments') == rows(original, 'health_assessments')
    rules_preserved = rows(db, 'risk_rules') == rows(original, 'risk_rules')
    assert baseline_preserved and rules_preserved
    result = {'original_goal_completed': True, 'duplicate_goals': 0, 'created': counts,
              'owners_and_dates': True, 'baseline_unchanged': baseline_preserved,
              'risk_rules_unchanged': rules_preserved, 'model_status': context['llm_status'],
              'next_node': context['next_node'], 'synthetic_data_only': True}
    Path('docs/images/agent-v1/persistence-results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))
