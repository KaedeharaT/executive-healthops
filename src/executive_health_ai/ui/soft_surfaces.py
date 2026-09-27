"""HealthOps shared surface hierarchy; presentation only, no business decisions."""

SURFACES = r'''
:root {
 --canvas:#dce5ef;--surface:#eaf0f6;--card:#f7faff;--neu-well:#dce6f0;
 --ink:#18334e;--muted:#405b74;--line:#b7c8d9;--neu-divider:#b7c8d9;
 --blue:#185da8;--neu-control-border:#748ba2;--neu-radius:18px;
 --neu-shadow:__SURFACE_SHADOW__;--neu-emphasis:var(--neu-shadow);
 --neu-inset:inset 4px 4px 8px #a9bacc80,inset -4px -4px 8px #ffffffd9;
 --neu-control:4px 4px 8px #adbdcf99,-4px -4px 8px #ffffffeb;
}
.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"] {background:var(--canvas)!important;}
[data-testid="stHeader"] {background:var(--canvas)!important;border-bottom:0!important;}
[data-testid="stMainBlockContainer"] {padding:4.6rem 2rem 3rem!important;max-width:1680px;}
[data-testid="stSidebar"] {background:#d5e1ed!important;border-right:1px solid #a8bdd0;box-shadow:4px 0 14px #b0bfd14d;}
[data-testid="stSidebar"] [data-testid="stRadio"] label {padding:10px 14px;margin-bottom:5px;}
[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {background:#f4f8fc;box-shadow:var(--neu-control);border:1px solid #9eb5cb;}
[data-testid="stMain"] [class*="st-key-soft-page-header-"] {padding:20px 24px;border-left:5px solid var(--blue);background:var(--surface);border-radius:16px;box-shadow:var(--neu-shadow);margin-bottom:16px;}
[data-testid="stMain"] [class*="st-key-soft-page-header-"] h1 {font-size:28px!important;line-height:1.25;padding:0 0 8px!important;}
[data-testid="stMain"] .st-key-neu-today-summary {background:var(--surface);border:1px solid var(--line);border-radius:18px;padding:18px;box-shadow:var(--neu-shadow);margin-bottom:24px;}
[data-testid="stMain"] .st-key-neu-today-summary [class*="st-key-soft-page-header-"] {background:var(--blue);border:0;box-shadow:none;margin:0;padding:22px 18px;}
[data-testid="stMain"] .st-key-neu-today-summary [class*="st-key-soft-page-header-"] :is(h1,p) {color:#fff!important;}
[data-testid="stMain"] .st-key-neu-today-summary .v2-summary {margin:0!important;border:1px solid #c0cedd;background:var(--neu-well);box-shadow:var(--neu-inset);padding:10px;border-radius:14px;}
[data-testid="stMain"] .st-key-neu-today-summary .v2-summary>div {padding:10px 12px;}
[data-testid="stMain"] .st-key-neu-today-summary .v2-summary strong {font-size:32px;line-height:1.3;color:var(--blue);}
[data-testid="stMain"] :is(.st-key-neu-assistant,.st-key-neu-work) {padding:24px!important;border:1px solid var(--line)!important;margin-bottom:24px;}
[data-testid="stMain"] .st-key-soft-assistant-status {background:var(--neu-well);padding:16px 20px;border-radius:14px;box-shadow:var(--neu-inset);border:1px solid var(--line);}
[data-testid="stMain"] .st-key-soft-assistant-status h3 {font-size:22px!important;margin:0!important;}
[data-testid="stMain"] .st-key-soft-assistant-status .v2-summary {border:0;margin:4px 0 0!important;}
[data-testid="stMain"] .st-key-soft-assistant-status .v2-summary>div {border-right:1px solid #b2c4d6;padding:8px 12px;}
[data-testid="stMain"] .st-key-soft-assistant-status .v2-summary strong {font-size:25px;color:var(--blue);}
[data-testid="stMain"] div[class*="st-key-assistant-card-"] {background:var(--card)!important;border:1px solid var(--line)!important;border-left:5px solid var(--blue)!important;box-shadow:var(--neu-control);padding:20px!important;}
[data-testid="stMain"] .st-key-assistant-recent {background:#f8fafc;border-radius:10px;padding:12px;border:1px solid var(--line);}
[data-testid="stMain"] :is([class*="st-key-soft-filter-"],.st-key-health-trend-filters) {background:var(--neu-well)!important;box-shadow:var(--neu-inset)!important;border:1px solid var(--line);border-radius:14px;padding:18px!important;margin-bottom:12px;}
[data-testid="stMain"] .care-member-header {padding:18px!important;background:var(--surface)!important;border:1px solid var(--line)!important;box-shadow:var(--neu-shadow);border-radius:18px;margin:8px 0 16px;}
.soft-profile-top {display:grid;grid-template-columns:1.1fr 1.8fr;gap:24px;align-items:center;}
[data-testid="stMain"] .care-member-header .care-name {display:flex;align-items:center;flex-wrap:nowrap;gap:16px;}
.soft-profile-mark {display:grid;place-items:center;flex:0 0 56px;height:56px;border-radius:16px;background:var(--blue);color:#fff;font-size:28px;font-weight:700;box-shadow:3px 3px 8px #9bafc5,-3px -3px 8px #fff;}
.soft-profile-meta {display:grid;grid-template-columns:1.7fr 1fr .8fr;background:var(--neu-well);box-shadow:var(--neu-inset);border:1px solid var(--line);border-radius:12px;padding:16px 8px;}
.soft-profile-meta>div {padding:0 12px;border-right:1px solid #adbed0;}
.soft-profile-meta>div:last-child {border:0;}
.soft-profile-meta small,.soft-profile-meta strong {display:block;}
.soft-profile-meta strong {font-size:14px;margin-top:4px;}
[data-testid="stMain"] .care-focus {display:grid;grid-template-columns:1fr 2fr;gap:16px;padding:12px 0;margin-top:12px;border-top:1px solid var(--line);}
.care-focus>span {display:block;padding:0 16px;border-left:3px solid #89a6c3;}
.care-focus>span>b {display:block;color:var(--muted);font-size:13px;margin-bottom:6px;}
.care-focus>span>span {display:block;color:var(--ink);font-size:15px;line-height:1.6;}
[data-testid="stMain"] .care-next {display:flex;gap:20px;align-items:center;background:#d9e8f6;border:1px solid #a8bfd7;border-radius:12px;padding:10px 16px;}
.care-next>b {flex:0 0 auto;color:var(--blue);}
.care-next>span {line-height:1.6;}
[data-testid="stMain"] .st-key-soft-member-navigation {padding:8px;background:var(--neu-well);box-shadow:var(--neu-inset);border:1px solid #aabed2;border-radius:16px;margin-bottom:18px;}
[data-testid="stMain"] :is(.st-key-soft-member-navigation,.st-key-member-health-tabs) [data-testid="stElementContainer"]:has(>[data-testid="stRadio"]) {width:100%!important;}
[data-testid="stMain"] .st-key-soft-member-navigation [role="radiogroup"] {display:grid!important;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px!important;background:none!important;border:0!important;box-shadow:none!important;padding:0!important;}
[data-testid="stMain"] .st-key-soft-member-navigation [data-testid="stRadio"] label {flex:1;justify-content:center;min-height:48px;padding:12px 20px;border-radius:12px;}
[data-testid="stMain"] .st-key-soft-member-navigation label:has(input:checked) {background:var(--card)!important;border:1px solid #92aecb!important;box-shadow:var(--neu-control)!important;color:var(--blue);}
[data-testid="stMain"] :is(.st-key-soft-member-navigation,.st-key-member-health-tabs) [data-testid="stRadioOption"]>div>div>div:not([data-testid]) {display:none;}
[data-testid="stMain"] :is(.st-key-soft-member-navigation,.st-key-member-health-tabs) [data-testid="stRadioOption"]>div {width:100%;}
[data-testid="stMain"] :is(.st-key-soft-member-navigation,.st-key-member-health-tabs) [data-testid="stRadioOption"] p {white-space:nowrap;text-align:center;}
[data-testid="stMain"] :is(.st-key-soft-member-navigation,.st-key-member-health-tabs) [data-testid="stRadioOption"]>div>div {justify-content:center;}
[data-testid="stMain"] .st-key-member-health-tabs [role="radiogroup"] {display:grid!important;grid-template-columns:repeat(4,minmax(0,1fr));padding:8px!important;background:var(--neu-well)!important;box-shadow:var(--neu-inset);border-radius:14px;}
[data-testid="stMain"] .st-key-member-health-tabs [data-testid="stRadioOption"]:has(input:checked) {background:var(--card)!important;box-shadow:var(--neu-control)!important;border:1px solid #92aecb;}
[data-testid="stMain"] :is(.st-key-soft-archive-summary,.st-key-soft-archive-details,.st-key-soft-intake-header,.st-key-soft-intake-progress,.st-key-soft-board-next) {background:var(--surface);border:1px solid var(--line);border-radius:18px;padding:24px;box-shadow:var(--neu-shadow);margin-bottom:20px;}
[data-testid="stMain"] .st-key-neu-initial-assessment {border-left:6px solid var(--blue)!important;}
[data-testid="stMain"] .neu-archive-grid {grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;margin-top:18px;}
[data-testid="stMain"] .neu-archive-grid>div {background:var(--card);padding:18px;border-radius:14px;}
.soft-archive-title {display:flex;gap:12px;align-items:center;}
.soft-archive-title i {display:grid;place-items:center;width:36px;height:36px;flex:0 0 36px;border-radius:10px;box-shadow:var(--neu-inset);background:var(--neu-well);color:var(--blue);}
.soft-archive-title svg {width:23px;height:23px;}
.soft-archive-state {display:block;margin:16px 0 8px;font-size:17px;color:var(--blue);}
[data-testid="stMain"] .neu-archive-grid span {font-size:13px;}
[data-testid="stMain"] .st-key-health-trend-panel {border-radius:18px!important;padding:26px!important;border:1px solid var(--line)!important;}
[data-testid="stMain"] .st-key-health-trend-panel h3 {font-size:25px!important;}
[data-testid="stMain"] .st-key-health-trend-summary {background:var(--card);border:1px solid var(--line);border-radius:14px;box-shadow:var(--neu-control);padding:8px 0;}
[data-testid="stMain"] .st-key-health-trend-summary .v2-summary {border:0;margin:0;}
[data-testid="stMain"] .st-key-health-trend-summary .v2-summary strong {font-size:22px;color:var(--blue);}
[data-testid="stMain"] .st-key-health-trend-chart {background:#fff;border:1px solid var(--line);border-radius:14px;padding:20px!important;}
[data-testid="stMain"] .st-key-health-trend-metadata {background:var(--neu-well);border-radius:12px;padding:16px!important;}
[data-testid="stMain"] .st-key-board-header {border-top:0!important;border-left:6px solid var(--blue)!important;}
[data-testid="stMain"] .st-key-board-header h2 {font-size:27px!important;margin-top:0!important;}
[data-testid="stMain"] .st-key-board-header .v2-summary {background:var(--neu-well);border-radius:12px;box-shadow:var(--neu-inset);padding:8px;margin-top:10px;}
[data-testid="stMain"] .board-current {display:flex;align-items:center;justify-content:space-between;gap:20px;padding:16px 20px;background:#d6e6f6;border:1px solid #a1bbd6;border-radius:12px;}
[data-testid="stMain"] .board-current p {margin:0;}
[data-testid="stMain"] .st-key-soft-board-process {background:var(--surface);border:1px solid var(--line);border-radius:18px;padding:18px;box-shadow:var(--neu-shadow);margin:10px 0 24px;}
[data-testid="stMain"] .st-key-soft-board-process .v2-workflow {border:0;padding:8px!important;box-shadow:none;background:transparent;gap:12px;}
[data-testid="stMain"] .st-key-soft-board-process .flow-step {background:var(--neu-well);box-shadow:var(--neu-inset);border:1px solid var(--line);border-radius:14px;padding:16px 8px;min-height:112px;}
[data-testid="stMain"] .st-key-soft-board-process .flow-step.active {background:var(--card);box-shadow:var(--neu-control);border-color:var(--blue);}
[data-testid="stMain"] .st-key-soft-board-process .flow-step.done {background:#e1efe7;}
[data-testid="stMain"] .st-key-soft-board-process .flow-step:before {display:none;}
[data-testid="stMain"] .st-key-soft-board-process .flow-dot {width:38px;height:38px;line-height:34px;}
[data-testid="stMain"] :is(.st-key-board-activity,.st-key-board-routing,.st-key-board-findings,.st-key-board-risk,.st-key-board-humans,.st-key-board-timeline,.st-key-soft-board-next,.st-key-board-exit,.st-key-board-support) {border-top:4px solid #a4bad0!important;background:var(--surface);box-shadow:var(--neu-shadow);border-radius:18px;padding:24px!important;}
[data-testid="stMain"] .st-key-board-activity {border-top-color:var(--blue)!important;}
[data-testid="stMain"] .st-key-board-routing {border-top-color:#6285a8!important;}
[data-testid="stMain"] .st-key-board-first,[data-testid="stMain"] .st-key-board-clinical,[data-testid="stMain"] .st-key-board-history {margin-bottom:24px;}
[data-testid="stMain"] .route-line {background:#f5f8fb;}
[data-testid="stMain"] .st-key-soft-intake-progress {background:var(--neu-well);box-shadow:var(--neu-inset);}
[data-testid="stMain"] .neu-intake-steps {display:grid!important;width:100%!important;background:transparent;border:0;padding:8px 0;gap:12px;}
[data-testid="stMain"] .neu-intake-steps li {border:1px solid #b4c7da;background:var(--neu-well);box-shadow:var(--neu-inset);padding:12px;}
[data-testid="stMain"] .neu-intake-steps .current {background:var(--blue);color:#fff;border-color:var(--blue);box-shadow:var(--neu-control);}
[data-testid="stMain"] .neu-intake-steps .current b {background:#fff;color:var(--blue);}
[data-testid="stMain"] .neu-intake-steps .done {background:#e1efe7;color:#226548;box-shadow:none;}
[data-testid="stMain"] .st-key-soft-intake-actions {background:var(--neu-well);padding:18px;border-radius:12px;border:1px solid var(--line);}
[data-testid="stMain"] [data-testid="stDivider"] {margin:12px 0!important;}
[data-testid="stMain"] div[class*="st-key-assistant-card-"] [data-testid="stVerticalBlock"] {gap:10px;}
[data-testid="stMain"] [data-testid="stForm"] {border-top:5px solid var(--blue);padding:28px;}
[data-testid="stMain"] :is(.stButton>button,[data-testid="stFormSubmitButton"] button,[data-testid="stDownloadButton"] button) {border-radius:12px;box-shadow:var(--neu-control);padding:10px 18px;min-height:44px;}
[data-testid="stMain"] button[kind="primary"],[data-testid="stMain"] button[kind="primaryFormSubmit"] {background:#185da8!important;box-shadow:4px 4px 8px #a2b5cb,inset 1px 1px 1px #ffffff66!important;border:1px solid #114d8d!important;}
[data-testid="stMain"] button:hover:not(:disabled) {box-shadow:2px 2px 4px #a2b5cb,-2px -2px 4px #fff;}
[data-testid="stMain"] button[kind="primary"]:hover:not(:disabled),[data-testid="stMain"] button[kind="primaryFormSubmit"]:hover:not(:disabled) {background:#124f91!important;box-shadow:2px 2px 5px #9aafc8,inset 1px 1px 1px #ffffff66!important;}
[data-testid="stMain"] button:active:not(:disabled) {box-shadow:var(--neu-inset)!important;}
[data-testid="stMain"] button[kind="primary"]:active:not(:disabled),[data-testid="stMain"] button[kind="primaryFormSubmit"]:active:not(:disabled) {box-shadow:inset 3px 3px 6px #0b3c73,inset -2px -2px 5px #4680b8!important;}
[data-testid="stMain"] button:disabled {background:var(--neu-well)!important;color:var(--muted)!important;box-shadow:none!important;border-color:#a9b7c6!important;}
[data-testid="stMain"] .st-key-assistant-recent button {box-shadow:none!important;min-height:32px!important;padding:4px 8px!important;}
[data-testid="stMain"] [data-testid="stButtonGroup"] {padding:6px;box-shadow:var(--neu-inset);border:1px solid var(--line);}
[data-testid="stMain"] [data-testid="stButtonGroup"] button[aria-pressed="true"] {box-shadow:var(--neu-control);background:var(--card);}
@media(max-width:1100px) {.soft-profile-top{grid-template-columns:1fr;}.neu-archive-grid{grid-template-columns:repeat(3,minmax(0,1fr))!important;}}
@media(max-width:760px) {
 [data-testid="stMainBlockContainer"]{padding:4.5rem 1rem 2rem!important;}
 .soft-profile-meta{grid-template-columns:1fr;gap:12px;}.soft-profile-meta>div{border:0;}
 [data-testid="stMain"] .care-focus{grid-template-columns:1fr;}.care-next{flex-wrap:wrap;}
 [data-testid="stMain"] .st-key-soft-member-navigation [role="radiogroup"]{grid-template-columns:repeat(3,minmax(0,1fr));}
 [data-testid="stMain"] .st-key-member-health-tabs [role="radiogroup"]{grid-template-columns:repeat(2,minmax(0,1fr));}
 [data-testid="stMain"] .st-key-soft-member-navigation [data-testid="stRadio"] label{flex:1 1 28%;padding:10px;}
 [data-testid="stMain"] .neu-archive-grid{grid-template-columns:repeat(2,minmax(0,1fr))!important;}
 [data-testid="stMain"] .board-current{display:block;}
 [data-testid="stMain"] .st-key-soft-board-process .flow-step{min-width:105px;}
 [data-testid="stMain"] :is(.st-key-neu-assistant,.st-key-neu-work,.st-key-soft-archive-summary,.st-key-soft-archive-details,.st-key-soft-intake-header,.st-key-soft-intake-progress){padding:16px!important;}
}
'''
