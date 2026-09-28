"""Reproducible source inventory; runtime visibility is recorded separately by Chromium."""
import ast,csv,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/ui-dedup-audit'
KINDS={'button','link_button','page_link','radio','selectbox','multiselect','checkbox','toggle',
       'form_submit_button','download_button','file_uploader','tabs','expander','popover','data_table',
       'dataframe','action_button','primary_action','detail_button','filter_bar','segmented_control'}

def inventory():
    result=[]
    for path in [ROOT/'streamlit_app.py',*sorted((ROOT/'src/executive_health_ai/ui').rglob('*.py'))]:
        source=path.read_text(encoding='utf-8-sig');tree=ast.parse(source);parents={child:node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
        for node in ast.walk(tree):
            if not isinstance(node,ast.Call):continue
            kind=node.func.attr if isinstance(node.func,ast.Attribute) else node.func.id if isinstance(node.func,ast.Name) else ''
            if kind not in KINDS:continue
            if kind=='dataframe' and not any(k.arg=='on_select' for k in node.keywords):continue
            if kind=='data_table' and any(k.arg=='selectable' and isinstance(k.value,ast.Constant) and k.value.value is False for k in node.keywords):continue
            owner=node
            while owner in parents and not isinstance(owner,(ast.FunctionDef,ast.AsyncFunctionDef)):owner=parents[owner]
            function=owner.name if isinstance(owner,(ast.FunctionDef,ast.AsyncFunctionDef)) else '<module>'
            kw={k.arg:ast.unparse(k.value) for k in node.keywords if k.arg}
            action=[]
            for call in ast.walk(owner):
                if isinstance(call,ast.Call):
                    name=ast.unparse(call.func)
                    if any(t in name for t in ('navigation','open_','session_state','submit','complete','approve','confirm','archive','commit','render_')):
                        action.append(ast.unparse(call))
            result.append({'page_source':path.relative_to(ROOT).as_posix(),'renderer':function,'line':node.lineno,'kind':kind,
                'label':ast.unparse(node.args[0]) if node.args else kw.get('label',''),
                'callback':kw.get('on_click',kw.get('on_change',kw.get('on_select',''))),
                'key':kw.get('key',''),'options':ast.unparse(node.args[1]) if kind in {'radio','selectbox','multiselect'} and len(node.args)>1 else '',
                'context_args':kw.get('args','')+' '+kw.get('kwargs',''),
                'enclosing_navigation_and_commands':' | '.join(dict.fromkeys(action)),
                'side_effect_review':'包含提交动作，请结合分支核对' if any('commit(' in x for x in action) else '导航/筛选/选择/展示；见回调',
                'navigation_only':kind in {'tabs','expander','popover','page_link','link_button','radio','selectbox','data_table','dataframe'}})
    return sorted(result,key=lambda r:(r['page_source'],r['line']))

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--name',default='controls-after');args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True);rows=inventory()
    with (OUT/(args.name+'.csv')).open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
    print(json.dumps({'source_control_definitions':len(rows),'files':len({r['page_source'] for r in rows})}))
