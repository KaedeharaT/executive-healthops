"""Restrained, role-aware Soft UI. Presentation only; native controls stay native."""
from html import escape

import streamlit as st


def stylesheet(role):
    shadow = {
        'member': '6px 6px 18px #20354c16, -5px -5px 14px #ffffffeb',
        'doctor': '2px 2px 6px #20354c0b, -2px -2px 6px #ffffffcc',
        'admin': '1px 2px 4px #20354c08, -1px -1px 3px #ffffff99',
    }.get(role, '5px 5px 14px #20354c12, -4px -4px 12px #ffffffd9')
    return '<style>' + CSS.replace('__ROLE_SHADOW__', shadow) + '</style>'


def archive_summary(rows):
    """A read-only scan layer; the complete actionable archive table stays below."""
    keys = {'家族健康史', '个人病史', '当前用药 / 营养补充', '过敏史', '生活方式', '环境与暴露'}
    cells = ''.join('<div><strong>'+escape(r['title'])+'</strong><span>'+escape(r['summary'])+'</span></div>'
                    for r in rows if r['key'] in keys)
    st.markdown('<div class="neu-archive-grid" aria-label="健康档案分类摘要">'+cells+'</div>', unsafe_allow_html=True)


def intake_steps(steps, selected, responses):
    """Use existing saved sections, never infer completion from step position."""
    cells = []
    for index, title in enumerate(steps):
        saved = title in responses and (title != '当前用药 / 营养补充' or '最近用药' in responses)
        state = 'current' if index == selected else 'done' if saved else 'pending'
        label = '当前填写' if index == selected else '已保存' if saved else '待填写'
        mark = '✓' if saved and index != selected else str(index+1)
        current = ' aria-current="step"' if index == selected else ''
        cells.append(f'<li class="{state}"{current}><b>{mark}</b><span>{escape(title)}<small>{label}</small></span></li>')
    st.markdown('<ol class="neu-intake-steps" aria-label="初始健康评估步骤">'+''.join(cells)+'</ol>', unsafe_allow_html=True)


CSS = r'''
:root {
 --blue:#185da8;--ink:#20354c;--muted:#52677d;--canvas:#edf2f7;
 --surface:#f5f8fc;--card:#fff;--line:#c7d4e2;--neu-well:#e9eff6;
 --neu-control-border:#7a8da2;--neu-divider:#d5dfea;--neu-radius:16px;
 --neu-shadow:__ROLE_SHADOW__;
 --neu-emphasis:6px 6px 18px #20354c16,-5px -5px 14px #ffffffeb;
 --neu-inset:inset 2px 2px 4px #20354c0d,inset -2px -2px 4px #ffffffcc;
 --neu-control:2px 2px 5px #20354c12,-2px -2px 5px #ffffffcc;
}
.stApp,[data-testid="stAppViewContainer"] {background:var(--canvas);color:var(--ink);}
[data-testid="stHeader"] {background:var(--canvas);border-bottom:1px solid var(--neu-divider);}
[data-testid="stMainBlockContainer"] {padding-top:5rem!important;}
[data-testid="stMain"] {scroll-padding-top:76px;}
[data-testid="stSidebar"] {background:var(--surface);border-right:1px solid var(--line);}
[data-testid="stSidebar"] [data-testid="stRadio"] label {border:1px solid transparent;border-radius:11px;min-height:44px;}
[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {
 background:#e2edf9;border-color:#9ab5d0;box-shadow:inset 3px 0 var(--blue),var(--neu-control);}
[data-testid="stMain"] h2 {font-size:22px!important;margin:1.2rem 0 .5rem!important;font-weight:700;}
[data-testid="stMain"] h3 {font-size:19px!important;font-weight:700;line-height:1.5;}
[data-testid="stMain"] h4 {font-size:16px!important;line-height:1.5;}
[data-testid="stMain"] p {line-height:1.6;}
[data-testid="stCaptionContainer"],[data-testid="stCaptionContainer"] p,
[data-testid="stCaption"],[data-testid="stCaption"] p {color:var(--muted)!important;font-size:14px!important;}
[data-testid="stCaptionContainer"],[data-testid="stCaption"] {opacity:1!important;}
[data-testid="stMain"] [data-testid="stAlert"] p {color:var(--ink);}
[data-testid="stMain"] [data-testid="stFileUploader"] :is(small,span) {color:var(--muted);}
[data-testid="stMain"] .overview-stages>[role="listitem"],
[data-testid="stMain"] .overview-domain-list thead th,
[data-testid="stMain"] .overview-status.neutral {color:var(--muted);}
[data-testid="stMain"] .overview-stages>.current {color:var(--blue);}
[data-testid="stMain"] [data-testid="stWidgetLabel"] p {color:var(--ink);font-size:14px;}
[data-testid="stMain"] .st-key-neu-today-summary .v2-summary {
 margin:12px 0 24px;background:var(--surface);box-shadow:var(--neu-shadow);border:1px solid var(--line);border-radius:16px;}
[data-testid="stMain"] .st-key-neu-today-summary .v2-summary strong {font-size:26px;color:var(--ink);font-variant-numeric:tabular-nums;}
[data-testid="stMain"] .st-key-neu-assistant,[data-testid="stMain"] .st-key-neu-work,
[data-testid="stMain"] .st-key-neu-archive,[data-testid="stMain"] .st-key-neu-initial-assessment,
[data-testid="stMain"] .st-key-neu-import,
[data-testid="stMain"] [class*="st-key-neu-profile-"],
[data-testid="stMain"] .st-key-health-trend-panel,
[data-testid="stMain"] .st-key-overview-heading,[data-testid="stMain"] .st-key-overview-trend,
[data-testid="stMain"] .st-key-overview-focus,[data-testid="stMain"] .st-key-overview-health-domains,
[data-testid="stMain"] .st-key-overview-data-completeness,
[data-testid="stMain"] [class*="st-key-v2-panel"],[data-testid="stMain"] [class*="st-key-v2-hero"],
[data-testid="stMain"] [class*="st-key-v2-context"],[data-testid="stMain"] [class*="st-key-v2-trends"] {
 background:var(--surface);border:1px solid var(--line)!important;border-radius:var(--neu-radius)!important;
 padding:24px!important;box-shadow:var(--neu-shadow);min-width:0;
}
[data-testid="stMain"] .st-key-neu-assistant {border-top:3px solid var(--blue)!important;box-shadow:var(--neu-emphasis);margin-bottom:24px;}
[data-testid="stMain"] .st-key-neu-assistant h3:first-child,
[data-testid="stMain"] .st-key-neu-work h3:first-child {margin-top:0!important;}
[data-testid="stMain"] .st-key-neu-assistant .v2-summary,
[data-testid="stMain"] .st-key-neu-initial-assessment .v2-summary {background:transparent;box-shadow:none;border-radius:0;border:0;border-bottom:1px solid var(--neu-divider);}
[data-testid="stMain"] .v2-summary {border-color:var(--neu-divider);border-radius:11px;}
[data-testid="stMain"] .v2-summary>div {border-color:var(--neu-divider);padding:12px 16px;min-width:0;overflow-wrap:anywhere;}
[data-testid="stMain"] .v2-summary small {color:var(--muted);font-size:14px;}
[data-testid="stMain"] .v2-summary strong {font-variant-numeric:tabular-nums;font-size:16px;}
[data-testid="stMain"] div[class*="st-key-assistant-card-"] {
 background:#f9fbfd;border:1px solid var(--line);border-left:3px solid var(--blue);border-radius:12px;box-shadow:var(--neu-control);}
[data-testid="stMain"] .st-key-assistant-recent {border-top:1px solid var(--neu-divider);padding-top:12px;}
[data-testid="stMain"] .st-key-assistant-recent button {box-shadow:none;}
[data-testid="stMain"] .st-key-assistant-recent {overflow-x:auto;max-width:100%;padding-bottom:8px;}
[data-testid="stMain"] .st-key-assistant-recent [class*="st-key-completed-row-"],
[data-testid="stMain"] .st-key-assistant-recent .st-key-completed-header {min-width:960px;}
[data-testid="stMain"] .assistant-history-cell {white-space:normal;overflow:visible;text-overflow:clip;overflow-wrap:anywhere;}
[data-testid="stMain"] .assistant-history-head {color:var(--muted);font-size:13px;}
[data-testid="stMain"] .care-member-header {
 background:var(--surface);border:1px solid var(--line);border-left:4px solid var(--blue);border-radius:16px;
 padding:20px 24px;box-shadow:var(--neu-shadow);margin:4px 0 12px;overflow-wrap:anywhere;
}
[data-testid="stMain"] .care-member-header .care-name {gap:12px 24px;flex-wrap:wrap;}
[data-testid="stMain"] .care-member-header .care-name h1 {font-size:26px!important;}
[data-testid="stMain"] .care-member-header small {font-size:13px;color:var(--muted);}
[data-testid="stMain"] .care-focus {border-top:1px solid var(--neu-divider);padding:12px 0 8px;margin-top:10px;gap:10px 24px;}
[data-testid="stMain"] .care-next {background:#e5eef8;border-radius:8px;padding:10px 12px;}
[data-testid="stMain"] [data-testid="stRadio"] div[role="radiogroup"]:has(input[type="radio"]) {
 border:1px solid var(--line);border-radius:12px;padding:4px;gap:4px;background:var(--neu-well);box-shadow:var(--neu-inset);flex-wrap:wrap;
}
[data-testid="stMain"] [data-testid="stRadio"] label {border:1px solid transparent;border-radius:9px;min-height:44px;padding:8px 12px;}
[data-testid="stMain"] [data-testid="stRadio"] label:has(input:checked) {
 background:#f8fbff;color:var(--blue);font-weight:700;border-color:#a4bad1;box-shadow:inset 0 -3px var(--blue),var(--neu-control);
}
[data-testid="stMain"] [data-testid="stTabs"] [role="tablist"] {gap:4px;background:var(--neu-well);padding:5px;border:1px solid var(--line);border-radius:12px;box-shadow:var(--neu-inset);}
[data-testid="stMain"] [role="tab"] {min-height:44px;border-radius:9px;padding:8px 14px;}
[data-testid="stMain"] [role="tab"][aria-selected="true"] {background:#f8fbff;color:var(--blue);font-weight:700;box-shadow:var(--neu-control);}
[data-testid="stMain"] [data-testid="stButtonGroup"] {background:var(--neu-well);border-radius:12px;padding:4px;}
[data-testid="stMain"] [data-testid="stButtonGroup"] button {border-radius:9px!important;min-height:40px;box-shadow:none;color:var(--muted);}
[data-testid="stMain"] [data-testid="stButtonGroup"] button[aria-pressed="true"] {background:#f8fbff;color:var(--blue);border-color:var(--blue);box-shadow:var(--neu-control);font-weight:700;}
[data-testid="stMain"] .stButton>button,[data-testid="stFormSubmitButton"] button,
[data-testid="stDownloadButton"] button,[data-testid="stPopover"]>button {
 border:1px solid var(--neu-control-border);border-radius:11px;min-height:44px;background:var(--surface);color:var(--ink);box-shadow:var(--neu-control);
 transition:background-color 150ms ease,border-color 150ms ease,box-shadow 150ms ease;
}
[data-testid="stMain"] button[kind="primary"],button[kind="primaryFormSubmit"] {
 background:var(--blue)!important;border-color:var(--blue)!important;color:#fff!important;box-shadow:2px 3px 7px #185da82b,inset 1px 1px 0 #ffffff26;
}
[data-testid="stMain"] button:hover:not(:disabled) {border-color:var(--blue);}
[data-testid="stMain"] button:active:not(:disabled) {box-shadow:var(--neu-inset);}
[data-testid="stMain"] button:disabled {opacity:1!important;background:var(--neu-well)!important;color:var(--muted)!important;border-color:#a9b7c6!important;box-shadow:none;}
[data-testid="stMain"] [data-baseweb="input"],
[data-testid="stMain"] [data-baseweb="textarea"],
[data-testid="stMain"] [data-testid="stTextInputRootElement"],
[data-testid="stMain"] [data-testid="stTextAreaRootElement"],
[data-testid="stMain"] [data-testid="stNumberInputContainer"],
[data-testid="stMain"] [data-testid="stSelectbox"] [role="group"],
[data-testid="stMain"] [data-testid="stMultiSelect"] [role="group"],
[data-testid="stMain"] [data-baseweb="select"]>div {
 background:var(--neu-well);border:1px solid var(--neu-control-border);border-radius:11px;box-shadow:var(--neu-inset);min-height:44px;
}
[data-testid="stMain"] input,[data-testid="stMain"] textarea {color:var(--ink);font-size:16px;min-width:0;}
[data-testid="stMain"] input::placeholder,[data-testid="stMain"] textarea::placeholder {color:var(--muted);opacity:1;}
[data-testid="stMain"] [data-baseweb="input"]:focus-within,
[data-testid="stMain"] [data-baseweb="textarea"]:focus-within,
[data-testid="stMain"] [data-testid="stTextInputRootElement"]:focus-within,
[data-testid="stMain"] [data-testid="stTextAreaRootElement"]:focus-within,
[data-testid="stMain"] [data-testid="stNumberInputContainer"]:focus-within,
[data-testid="stMain"] [data-testid="stSelectbox"] [role="group"]:focus-within,
[data-testid="stMain"] [data-baseweb="select"]:focus-within {outline:3px solid var(--blue);outline-offset:3px;}
[data-testid="stMain"] [aria-invalid="true"] {border:2px solid #a53030!important;}
:is(button,a,input,textarea,select,summary,[tabindex],[role="tab"],[role="checkbox"]):focus-visible {
 outline:3px solid #185da8!important;outline-offset:3px!important;
}
[data-testid="stRadio"] label:focus-within,[data-testid="stCheckbox"] label:focus-within {outline:3px solid #185da8!important;outline-offset:3px!important;}
[data-testid="stMain"] [data-testid="stForm"] {background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:24px;box-shadow:var(--neu-shadow);}
[data-testid="stMain"] [data-testid="stExpander"] {background:var(--surface);border-color:var(--line)!important;border-radius:11px!important;}
[data-testid="stMain"] [data-testid="stDataFrame"] {background:#fff;border:1px solid var(--line);border-radius:10px;box-shadow:none;max-width:100%;}
[data-testid="stMain"] [data-testid="stVegaLiteChart"],
[data-testid="stMain"] [data-testid="stVegaLiteChart"] svg,
[data-testid="stMain"] [data-testid="stVegaLiteChart"] canvas {background:#fff;box-shadow:none;}
[data-testid="stMain"] table {color:var(--ink);font-variant-numeric:tabular-nums;box-shadow:none;}
[data-testid="stMain"] th {background:#e9eff6;color:var(--muted);font-weight:600;}
[data-testid="stMain"] td {border-color:var(--neu-divider);}
[data-testid="stMain"] .st-key-health-trend-filters {background:var(--neu-well);border:1px solid var(--neu-divider);border-radius:12px;box-shadow:none;}
[data-testid="stMain"] .st-key-health-trend-summary .v2-summary {background:transparent;box-shadow:none;}
[data-testid="stMain"] .trend-metadata {color:var(--muted);}
[data-testid="stMain"] .st-key-board-header,[data-testid="stMain"] .st-key-board-routing,
[data-testid="stMain"] .st-key-board-activity,[data-testid="stMain"] .st-key-board-timeline,
[data-testid="stMain"] .st-key-board-humans,[data-testid="stMain"] .st-key-board-findings,
[data-testid="stMain"] .st-key-board-risk,[data-testid="stMain"] .st-key-board-exit {
 background:var(--surface);border:1px solid var(--line)!important;border-radius:16px;padding:24px!important;box-shadow:var(--neu-shadow);
}
[data-testid="stMain"] .st-key-board-header {border-top:3px solid var(--blue)!important;}
[data-testid="stMain"] .board-current {background:#e3edf8;border-radius:10px;border-left:3px solid var(--blue);padding:16px;}
[data-testid="stMain"] .board-current strong {color:var(--blue);}
[data-testid="stMain"] .board-current p,[data-testid="stMain"] .route-line span,
[data-testid="stMain"] .care-history time,[data-testid="stMain"] .care-history .next {color:var(--muted);}
[data-testid="stMain"] .care-history li {padding-top:8px;padding-bottom:8px;}
[data-testid="stMain"] .route-line {gap:12px;flex-wrap:wrap;}
[data-testid="stMain"] .v2-workflow {background:var(--neu-well);border:1px solid var(--line);border-radius:14px;padding:16px 8px!important;row-gap:16px;}
[data-testid="stMain"] .v2-workflow .flow-dot {background:var(--neu-well);box-shadow:var(--neu-inset);color:var(--muted);border-color:var(--neu-control-border);width:34px;height:34px;line-height:30px;}
[data-testid="stMain"] .v2-workflow .active .flow-dot {color:#fff;background:var(--blue);border-color:var(--blue);box-shadow:var(--neu-control);}
[data-testid="stMain"] .v2-workflow .done .flow-dot {color:#226548;background:#e7f3ec;border-color:#579774;box-shadow:none;}
[data-testid="stMain"] .v2-workflow .flow-step:before {top:16px;border-color:#a6b9cc;}
.neu-archive-grid {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;margin:8px 0 16px;}
.neu-profile-legend {display:flex;flex-wrap:wrap;gap:8px;margin:8px 0;}
.neu-profile-legend span {padding:6px 10px;border:1px solid var(--line);border-radius:8px;font-size:13px;color:var(--blue);background:#e5eef8;}
.neu-profile-legend .same {color:#226548;background:#e7f3ec;}
.neu-profile-legend .conflict {color:#914d17;background:#fff0e1;}
.neu-profile-legend .uncertain {color:#795514;background:#fff3d6;}
.neu-archive-grid>div {border:1px solid var(--line);border-radius:12px;background:var(--surface);box-shadow:var(--neu-control);padding:16px;}
.neu-archive-grid strong,.neu-archive-grid span {display:block;font-size:14px;line-height:1.6;overflow-wrap:anywhere;}
.neu-archive-grid span {color:var(--muted);margin-top:8px;}
.neu-intake-steps {list-style:none;display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px;margin:8px 0 16px;padding:12px;background:var(--neu-well);border:1px solid var(--line);border-radius:14px;}
.neu-intake-steps li {display:flex;align-items:flex-start;gap:8px;padding:10px 8px;min-width:0;font-size:13px;color:var(--muted);border:1px solid transparent;border-radius:10px;}
.neu-intake-steps li b {flex:0 0 24px;height:24px;line-height:24px;text-align:center;border-radius:50%;background:var(--neu-well);box-shadow:var(--neu-inset);}
.neu-intake-steps li span {overflow-wrap:anywhere;}
.neu-intake-steps small {display:block;font-size:12px;margin-top:4px;}
.neu-intake-steps .current {background:#f8fbff;border-color:#8baed1;box-shadow:var(--neu-control);color:var(--blue);font-weight:700;}
.neu-intake-steps .current b {color:#fff;background:var(--blue);box-shadow:none;}
.neu-intake-steps .done b {color:#226548;background:#e7f3ec;box-shadow:none;}
[data-testid="stMain"] .ux-badge,[data-testid="stMain"] .status-badge,[data-testid="stMain"] .overview-status {border-radius:8px;box-shadow:none;}
[data-testid="stMain"] .status-badge.attention {color:#795514;background:#fff3d6;}
[data-testid="stMain"] .status-badge.urgent {color:#a53030;background:#fcecec;}
[data-testid="stMain"] .status-badge.stable {color:#226548;background:#e7f3ec;}
[data-testid="stMain"] .st-key-neu-import [role="radiogroup"] {display:grid!important;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px!important;}
[data-testid="stMain"] .st-key-neu-import [data-testid="stRadio"] label {padding:16px;}
@media(max-width:1100px) {.neu-intake-steps {grid-template-columns:repeat(4,minmax(0,1fr));}}
@media(max-width:760px) {
 [data-testid="stMainBlockContainer"] {padding:4.75rem .9rem 3rem!important;}
 [data-testid="stMain"] .care-member-header {padding:16px;}
 [data-testid="stMain"] .st-key-neu-assistant,[data-testid="stMain"] .st-key-neu-work,
 [data-testid="stMain"] .st-key-neu-archive,[data-testid="stMain"] .st-key-neu-initial-assessment,
 [data-testid="stMain"] .st-key-neu-import,[data-testid="stMain"] .st-key-health-trend-panel,
 [data-testid="stMain"] [class*="st-key-board-"],[data-testid="stMain"] [data-testid="stForm"] {padding:16px!important;}
 [data-testid="stMain"] .v2-summary {flex-wrap:wrap;}
 [data-testid="stMain"] .v2-summary>div {flex:1 1 45%;padding:10px;}
 .neu-archive-grid,.neu-intake-steps {grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;}
 [data-testid="stMain"] .st-key-neu-import [role="radiogroup"] {grid-template-columns:1fr;}
 [data-testid="stMain"] .care-focus {display:block;}
 [data-testid="stMain"] .care-focus span {display:block;margin:8px 0;}
 [data-testid="stMain"] .v2-workflow .flow-step {min-width:95px;}
}
@media(prefers-reduced-motion:reduce) {
 *,*::before,*::after {animation-duration:.01ms!important;animation-iteration-count:1!important;transition:none!important;scroll-behavior:auto!important;}
}
@media(forced-colors:active) {
 button,input,textarea,[role="tab"],[role="radio"] {border:1px solid ButtonText!important;}
 :focus-visible {outline:3px solid Highlight!important;}
}
'''
