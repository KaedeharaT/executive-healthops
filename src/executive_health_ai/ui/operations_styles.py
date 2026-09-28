"""Clean healthcare workspace surfaces; presentation only."""
CSS = '''<style>
:root {--canvas:#f3f6fa;--surface:#fff;--card:#fff;--blue:#1969b4;--brand-blue:#1969b4;--ink:#20354c;--text:#20354c;--muted:#617387;--line:#dde5ee;--neu-well:#edf2f7;--neu-shadow:none;--neu-control:none;--neu-inset:none;--neu-emphasis:0 2px 8px #20354c0a}
.stApp,[data-testid="stAppViewContainer"] {background:var(--canvas)!important}
[data-testid="stSidebar"] {background:#fff!important;border-right:1px solid var(--line);min-width:210px!important;max-width:210px!important;box-shadow:none!important}
[data-testid="stSidebarUserContent"] {padding:22px 14px!important}
[data-testid="stSidebar"] h2 {font-size:14px!important;color:var(--muted)!important}
[data-testid="stSidebar"] label:has(input[type="radio"]) {padding:9px 12px;border-radius:6px;width:100%;margin:2px 0}
[data-testid="stSidebar"] label:has(input:checked) {background:#e9f2fc;color:#1969b4;font-weight:600}
[data-testid="stMainBlockContainer"] {max-width:1550px!important;padding:30px 30px 55px!important}
[data-testid="stVerticalBlock"] {gap:.8rem}
[data-testid="stCaptionContainer"] p,[data-testid="stCaptionContainer"] {color:#53677d!important;opacity:1!important}
.neu-intake-steps {display:flex;flex-wrap:wrap;list-style:none;padding:0;gap:8px}
.neu-intake-steps li {font-size:12px;border-bottom:2px solid #dbe4ed;padding:6px}.neu-intake-steps li.current{border-color:#1969b4;color:#1969b4}
.neu-intake-steps small {display:block;color:#53677d}
[data-testid="stMain"] h1 {font-size:26px!important;font-weight:650!important}
[data-testid="stMain"] h2 {font-size:19px!important;margin:.25rem 0!important}
[data-testid="stMain"] h3 {font-size:16px!important}
[data-testid="stMain"] button {border-radius:6px!important;box-shadow:none!important;min-height:36px;border:1px solid #d6e0eb;background:#fff}
[data-testid="stMain"] button[kind="primary"], [data-testid="stMain"] button[kind="primaryFormSubmit"] {background:#1969b4!important;color:#fff!important;border-color:#1969b4!important}
[data-testid="stMain"] button:hover {border-color:#1969b4!important;background:#edf5ff}
[data-testid="stMain"] input,[data-testid="stMain"] textarea,[data-baseweb="select"]>div {box-shadow:none!important;background:#fff!important;border-radius:6px!important}
[data-testid="stDataFrame"] {border:1px solid var(--line);border-radius:6px;box-shadow:none!important;background:#fff}
[data-testid="stVerticalBlockBorderWrapper"] {border-radius:8px!important;box-shadow:none!important;background:#fff}
[class*="st-key-v7-main"] {background:#fff;border:1px solid var(--line);padding:20px;border-radius:8px}
[class*="st-key-v7-context"] {padding:4px 0 8px 18px;border-left:1px solid var(--line)}
[class*="st-key-v2-panel"],[class*="st-key-v2-hero"] {background:#fff!important;box-shadow:none!important;border:1px solid var(--line)!important;border-radius:8px!important;padding:18px!important}
.v2-summary {display:flex;gap:20px;flex-wrap:wrap;padding:10px 0!important;background:transparent!important;box-shadow:none!important;border:0!important}
.v2-summary>div {min-width:80px;background:transparent!important;box-shadow:none!important;border:0!important;padding:0 16px 0 0!important;border-radius:0!important}
.v2-summary small {color:var(--muted);font-size:12px;display:block}
.v2-summary strong {font-size:21px!important;color:var(--ink);display:block}
.care-member-header {background:transparent;border:0;border-bottom:1px solid var(--line);border-radius:0;padding:0 0 14px}
.care-member-header h1 {font-size:25px!important;margin:3px 0!important}
.care-member-header .member-meta {display:flex;gap:22px;color:var(--muted);font-size:13px;flex-wrap:wrap}
.care-member-header .care-next {background:transparent;padding:6px 0 0;color:#334b63}
.v2-workflow {box-shadow:none!important;background:transparent!important;padding:8px 0!important}
.v2-timeline {border:0!important;border-left:2px solid #d8e5f0!important;background:transparent!important;box-shadow:none!important;padding:8px 12px!important;margin:5px 0!important}
.v2-timeline h3 {font-size:14px!important}.v2-timeline p {font-size:13px!important}
.st-key-intake-agent-board {background:#fff!important;border:1px solid var(--line)!important;border-top:3px solid #1969b4!important;padding:18px!important;border-radius:8px!important;box-shadow:none!important}
.st-key-v7-sidebar-user {position:fixed;bottom:16px;left:15px;width:177px;background:#fff;border-top:1px solid var(--line);padding-top:14px}
@media(max-width:1000px) {[data-testid="stMainBlockContainer"]{padding:24px 16px!important}[class*="st-key-v7-context"]{padding-left:0;border-left:0}.st-key-v7-sidebar-user{position:static}}
</style>'''
