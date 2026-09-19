"""Central styles for role workspaces and retained detail surfaces."""

TOKENS = {"blue": "#185da8", "ink": "#20354c", "muted": "#52677d", "border": "#dce5ef", "background": "#f4f7fa", "radius": "12px", "space": "1rem"}


def role_styles(role="manager"):
    width = "1120px" if role == "member" else "1180px" if role == "doctor" else "1440px"
    return ROLE_STYLES.replace("__CONTENT_WIDTH__", width)


ROLE_STYLES = """<style>
:root {--brand-blue:#185da8;--blue:#185da8;--ink:#20354c;--muted:#52677d;--line:#dce5ef;--surface:#f4f7fa;--canvas:#f4f7fa;--card:#fff;--radius:12px;--space:1rem;--space-sm:8px;--space-md:16px;--space-lg:24px;--space-xl:32px}
.stApp,[data-testid="stAppViewContainer"] {background:var(--canvas);color:var(--ink)}
[data-testid="stMainBlockContainer"],.block-container {max-width:__CONTENT_WIDTH__!important;padding:2rem 2.1rem 4rem!important}
[data-testid="stMain"] h1 {font-size:1.9rem!important;letter-spacing:-.025em;line-height:1.3;margin:0!important;padding:.15rem 0!important}
[data-testid="stVerticalBlock"] {gap:.7rem}
[data-testid="stMain"] h2 {font-size:1.22rem!important;line-height:1.4;margin:1rem 0 .35rem!important}
[data-testid="stMain"] h3 {font-size:1.04rem!important;line-height:1.45;margin:.25rem 0!important}
[data-testid="stMain"] p {font-size:1rem;line-height:1.65}
[data-testid="stCaptionContainer"],[data-testid="stCaptionContainer"] p {color:var(--muted)!important;font-size:.81rem!important;line-height:1.55}
[data-testid="stCaption"],[data-testid="stCaption"] p {color:#52677d!important;font-size:.81rem!important;line-height:1.55}
[data-testid="stMain"] h2,[data-testid="stMain"] h3 {padding:.1rem 0!important}
[data-testid="stSidebar"] {background:#fff;border-right:1px solid var(--line)}
[data-testid="stSidebar"] [data-testid="stRadio"] label {padding:.45rem .65rem;margin:.08rem 0;min-height:40px}
[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {background:#eaf2fb;color:var(--blue);font-weight:700;box-shadow:inset 3px 0 var(--blue)}
[data-testid="stRadio"] label:focus-within,button:focus-visible,input:focus-visible,[role="combobox"]:focus-visible {outline:3px solid #327bc2!important;outline-offset:3px!important}
[data-testid="stMain"] [data-testid="stRadio"] div[role="radiogroup"] {background:transparent;border-bottom:1px solid var(--line);border-radius:0;padding:0;gap:.3rem}
[data-testid="stMain"] [data-testid="stRadio"] label {min-height:40px;padding:.45rem .75rem;border-radius:6px 6px 0 0}
[data-testid="stMain"] [data-testid="stRadio"] label:has(input:checked) {background:#eaf2fb;box-shadow:inset 0 -2px var(--blue);color:var(--blue)}
[data-testid="stDivider"] {margin:.6rem 0!important}
.stButton>button,[data-testid="stFormSubmitButton"] button {min-height:44px;border-radius:8px;font-size:.9rem;border-color:#c5d2df}
button[kind="primary"] {background:var(--blue)!important;border-color:var(--blue)!important;color:white!important}
[data-testid="stExpander"] {border:1px solid var(--line)!important;background:#fff;border-radius:10px!important;margin:.3rem 0}
[data-testid="stMetric"] {background:none;border:0;padding:.2rem 0}
[data-testid="stMetricValue"] {font-size:1.55rem!important;color:var(--ink)}
[data-testid="stDataFrame"],[data-testid="stVegaLiteChart"] {background:#fff;border-radius:8px}
[data-testid="stVerticalBlockBorderWrapper"] {border:1px solid var(--line)!important;box-shadow:none!important;background:white;border-radius:12px!important}
[class*="st-key-v2-hero"] {background:#eaf2fb;border:1px solid #c8dbed;border-radius:14px;padding:1.35rem!important}
[class*="st-key-v2-panel"],[class*="st-key-v2-context"],[class*="st-key-v2-trends"] {background:#fff;border:1px solid var(--line);border-radius:12px;padding:1.1rem!important}
[class*="st-key-v2-list"] {background:#fff;border:1px solid var(--line);border-radius:10px;padding:.3rem .65rem!important}
[class*="st-key-v2-list"] [data-testid="stButton"] button {text-align:left;justify-content:flex-start;width:100%;background:#fff;min-height:52px;white-space:pre-line;border:0;border-bottom:1px solid var(--line);border-radius:0;padding:.65rem .35rem}
[class*="st-key-v2-list"] [data-testid="stButton"] button:hover {background:#eaf2fb}
[class*="st-key-v2-panel"],[class*="st-key-v2-hero"],[class*="st-key-v2-context"] {margin-bottom:24px}
[data-testid="stCaptionContainer"] p,.ux-row small,.v2-summary small,.v2-team span {font-size:14px!important}
.v3-comparison {overflow-x:auto;margin:12px 0 20px;background:white;border-bottom:1px solid var(--line)}
.v3-comparison table {width:100%;border-collapse:collapse;font-size:14px}
.v3-comparison th {color:var(--muted);font-weight:500;text-align:left;background:#edf3f9}
.v3-comparison th,.v3-comparison td {padding:10px 12px;border-bottom:1px solid var(--line);white-space:nowrap}
.v3-comparison td:first-child {font-weight:650}.v3-comparison td:last-child {color:var(--blue)}
[data-testid="stProgress"] [role="progressbar"] {background:#d6e2ee}
.ux-eyebrow {font-size:.73rem;font-weight:650;letter-spacing:.08em;color:var(--blue);margin-bottom:.25rem}
.ux-row {padding:.75rem 0;border-bottom:1px solid var(--line);line-height:1.55;overflow-wrap:anywhere}
.ux-row b {font-size:1rem}.ux-row small,.ux-muted {color:var(--muted);font-size:.82rem}
.ux-next {border-left:3px solid var(--blue);background:#eaf2fb;padding:.7rem 1rem;margin:.4rem 0;border-radius:0 8px 8px 0;line-height:1.65}
.ux-badge {display:inline-block;background:#eaf2fb;color:#25476d;padding:.2rem .6rem;border-radius:5px;font-size:.8rem;font-weight:650}
.v2-summary {display:flex;flex-wrap:wrap;gap:0;border-top:1px solid var(--line);border-bottom:1px solid var(--line);margin:.5rem 0 1rem;background:white;border-radius:8px}
.v2-summary>div {flex:1;min-width:120px;padding:.8rem 1rem;border-right:1px solid var(--line)}
.v2-summary>div:last-child {border-right:0}.v2-summary small {display:block;color:var(--muted);font-size:.8rem}.v2-summary strong {display:block;font-size:1.02rem;margin-top:.2rem}
.v2-team {border-top:1px solid var(--line);padding:.7rem 0}.v2-team strong {display:block;font-size:.97rem}.v2-team span {color:var(--muted);font-size:.82rem}
.v2-timeline {display:grid;grid-template-columns:130px 1fr;gap:24px;padding:.8rem 0}
.v2-timeline .v2-date {color:var(--muted);font-size:.81rem;padding-top:.1rem}
.v2-timeline article {position:relative;border-left:2px solid #afc8df;padding:0 0 1rem 22px}
.v2-timeline article:before {content:'';position:absolute;left:-6px;top:4px;width:10px;height:10px;border-radius:50%;background:var(--blue)}
.v2-timeline h3 {font-size:1rem!important}.v2-timeline p {margin:.3rem 0;color:#334155}.v2-timeline small {color:var(--muted)}
.v2-workflow {display:flex;flex-wrap:wrap;gap:8px;margin:.5rem 0 1rem}
.v2-workflow span {padding:.4rem .65rem;border-bottom:2px solid #cad7e3;color:var(--muted);font-size:.83rem}
.v2-workflow .active {background:#eaf2fb;color:var(--blue);border-color:var(--blue);font-weight:700}
.empty-state {text-align:left;max-width:none;margin:.4rem 0;padding:.75rem 0;border:0;background:none}
@media(max-width:760px) {
 [data-testid="stMainBlockContainer"],.block-container {padding:1.25rem .8rem 3rem!important}
 [data-testid="stHorizontalBlock"] {flex-wrap:wrap}
 [data-testid="stColumn"] {min-width:min(100%,280px)}
 [data-testid="stMain"] h1 {font-size:1.6rem!important}
 .v2-timeline {grid-template-columns:76px 1fr;gap:10px}
 .v2-summary>div {min-width:45%}
 [class*="st-key-v2-hero"],[class*="st-key-v2-panel"] {padding:.85rem!important}
}
</style>"""

MEMBER_OVERVIEW_STYLES = """<style>
.st-key-member-health-overview {max-width:1080px;margin:0 auto}
.st-key-member-health-overview h2 {margin:0 0 8px!important}
.st-key-member-health-overview [data-testid="stVerticalBlock"] {gap:10px}
.st-key-overview-heading {margin:12px 0 8px}
.st-key-overview-heading h3 {font-size:24px!important;line-height:1.35!important}
.overview-baseline-meta {display:flex;gap:18px;flex-wrap:wrap;align-items:center;color:#52677d;font-size:14px}
.overview-baseline-meta b {color:#185da8;background:#e8f1fa;padding:3px 10px;border-radius:20px}
.overview-stages {display:grid;grid-template-columns:repeat(3,1fr);width:100%;padding:10px 0 4px;margin:0 0 16px}
.overview-stages>[role="listitem"] {position:relative;display:flex;flex-direction:column;align-items:center;gap:5px;color:#52677d;font-size:14px}
.overview-stages>[role="listitem"]:not(:last-child)::after {content:'';position:absolute;top:8px;left:calc(50% + 11px);width:calc(100% - 22px);height:2px;background:#c4d3e2}
.overview-stages .stage-dot {width:17px;height:17px;border-radius:50%;border:2px solid #91a4b8;background:white;z-index:1}
.overview-stages .done .stage-dot {background:#91a4b8}
.overview-stages .current {color:#185da8;font-weight:700}
.overview-stages .current .stage-dot {background:#185da8;border-color:#185da8;box-shadow:0 0 0 5px #e4effa}
.overview-stages small {font-size:13px}
.st-key-overview-focus {background:#fff9ed;border:1px solid #ead9b6;border-left:4px solid #b77914;border-radius:10px;padding:16px 20px;margin-bottom:24px}
.st-key-overview-focus [data-testid="stVerticalBlock"] {gap:6px}
.overview-focus-list {display:grid;grid-template-columns:1fr 1fr;gap:12px 24px}
.overview-focus-list>div {display:flex;flex-direction:column;gap:3px}
.overview-focus-list strong {font-size:16px;color:#725016}
.overview-focus-list span {font-size:14px;line-height:1.5;color:#344b63;overflow-wrap:anywhere;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.st-key-overview-trend {background:white;border:1px solid #dce5ef;border-radius:12px;padding:18px 20px;margin-bottom:24px}
.st-key-overview-trend .v3-comparison {margin:0 0 8px;border-bottom:0}
.st-key-overview-trend .v3-comparison td {padding:9px 12px}
.st-key-overview-domain-coverage {background:#fff;border:1px solid #dce5ef;border-radius:12px;padding:20px;margin-bottom:24px}
.overview-domain-list>div {display:flex;justify-content:space-between;gap:12px;padding:9px 0;border-bottom:1px solid #e4ebf2;font-size:14px}
.overview-domain-list span {color:#52677d;text-align:right}
.overview-coverage {display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:6px;margin:6px 0}
.overview-coverage>div {display:flex;flex-direction:column;gap:5px;font-size:12px;text-align:center;color:#52677d;overflow-wrap:anywhere}
.overview-coverage i {height:9px;border-radius:3px;background:#e3eaf1;border:1px solid #c3d0de}
.overview-coverage .covered i {background:#185da8;border-color:#185da8}
.overview-coverage .partial i {background:#b8cee3;border:1px dashed #4776a4}
.overview-coverage small {font-size:12px}
.st-key-overview-details {margin-bottom:24px}
@media(max-width:760px) {
 .st-key-overview-domain-coverage [data-testid="stHorizontalBlock"] {flex-direction:column}
 .st-key-overview-domain-coverage [data-testid="stColumn"] {width:100%!important;min-width:100%!important;flex:1 1 100%!important}
 .overview-focus-list {grid-template-columns:1fr}
 .st-key-overview-focus,.st-key-overview-trend,.st-key-overview-domain-coverage {padding:14px 12px}
 .overview-stages {margin-bottom:20px}
 .overview-stages strong {font-size:13px;text-align:center}
 .overview-stages small {font-size:12px}
 .overview-baseline-meta {gap:8px 12px}
}
</style>"""

LEGACY_STYLES = """
        <style>
        :root {--ink:#17243a;--muted:#607086;--faint:#8796aa;--line:#d9e2ef;--canvas:#f4f7fb;--card:#fff;--blue:#2563eb;--blue-hover:#1d4ed8;--blue-dark:#163b82;--blue-soft:#eaf1ff;--green:#287a55;--amber:#a86614;--red:#b63f46;--gray:#64748b;--radius:14px;}
        html, body, [class*="css"] {font-family:"Segoe UI","Microsoft YaHei",system-ui,sans-serif;}
        [data-testid="stAppViewContainer"] {background:var(--canvas); color:var(--ink);}
        [data-testid="stAppViewContainer"] .main .block-container {
            max-width:1260px !important; margin:0 auto; padding:2.4rem 2rem 5.5rem;
        }
        h1 {font-size:1.95rem !important; line-height:1.2; letter-spacing:-.045em; margin:0 0 .45rem !important; font-weight:720 !important; color:var(--ink);}
        h2 {font-size:1.26rem !important; line-height:1.3; letter-spacing:-.022em; margin:2.35rem 0 .55rem !important; font-weight:700 !important; color:var(--ink);}
        h3 {font-size:1rem !important; line-height:1.4; letter-spacing:-.012em; margin:.4rem 0 !important;}
        [data-testid="stCaptionContainer"] {color:var(--muted); font-size:.84rem; line-height:1.55;}
        [data-testid="stMetric"] {background:transparent; border:0; padding:.2rem 0;}
        [data-testid="stMetricLabel"] {font-size:.76rem; color:var(--muted); font-weight:600;}
        [data-testid="stMetricValue"] {font-size:1.55rem; font-weight:720; letter-spacing:-.035em; color:var(--ink);}
        [data-testid="stVerticalBlockBorderWrapper"] {border:1px solid var(--line) !important; border-radius:var(--radius) !important; box-shadow:0 2px 7px rgba(24,38,58,.035); background:var(--card);}
        [data-testid="stVerticalBlockBorderWrapper"] > div {padding:.8rem .85rem;}
        .section-frame-title {font-size:1.08rem; font-weight:720; letter-spacing:-.018em; margin:.15rem 0 .18rem; color:var(--ink);}
        [data-testid="stExpander"] {border:1px solid var(--line) !important; border-radius:12px !important; background:#fff; margin:.5rem 0;}
        [data-testid="stDivider"] {margin:1.75rem 0 !important; border-color:var(--line);}
        .stButton > button {border-radius:9px; min-height:2.35rem; font-size:.88rem; font-weight:650; border-color:#cad5e1; background:#fff; color:var(--ink);}
        .stButton > button:hover {border-color:#9eb6cf; color:var(--blue); background:#f9fbfd;}
        .stButton > button[kind="primary"] {background:var(--blue); border-color:var(--blue); color:#fff;}
        .stButton > button[kind="primary"]:hover {background:var(--blue-hover); border-color:var(--blue-hover); color:#fff;}
        [data-testid="stDataFrame"] {border:1px solid var(--line); border-radius:12px; overflow:hidden; background:#fff;}
        [data-testid="stFileUploader"] {border:1px dashed #b9c8d7; border-radius:12px; padding:.4rem; background:#fbfcfd;}
        [data-testid="stSidebar"] {background:#fff; border-right:1px solid var(--line);}
        [data-testid="stSidebar"] > div:first-child {padding:1.35rem .7rem 2rem;}
        [data-testid="stSidebar"] h2 {font-size:1.08rem !important; margin:.25rem .65rem .15rem !important;}
        [data-testid="stSidebar"] [data-testid="stRadio"] label {padding:.67rem .75rem; margin:.14rem 0; border-radius:9px; transition:background .12s ease, color .12s ease;}
        [data-testid="stSidebar"] [data-testid="stRadio"] label:hover {background:#f2f6f9;}
        [data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {background:var(--blue-soft); color:var(--blue); font-weight:700;}
        [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"][aria-orientation="horizontal"] {background:#edf1f5;padding:3px;border-radius:10px;gap:2px;}
        [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"][aria-orientation="horizontal"] label {flex:1;text-align:center;padding:.45rem .35rem;}
        [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"][aria-orientation="horizontal"] label:has(input:checked) {background:#fff;box-shadow:0 1px 3px rgba(24,38,58,.10);}
        [data-testid="stSidebar"] [data-testid="stRadio"] label > div:first-child {display:none;}
        [data-testid="stSidebar"] [data-testid="stRadio"] label > div:last-child {padding-left:0;}
        [data-testid="stRadio"] div[role="radiogroup"] {gap:.35rem;}
        [data-testid="stMain"] [data-testid="stRadio"] div[role="radiogroup"] {background:#edf1f5;padding:3px;border-radius:10px;gap:2px;}
        [data-testid="stMain"] [data-testid="stRadio"] label {border-radius:7px;padding:.38rem .7rem;margin:0;min-height:2rem;}
        [data-testid="stMain"] [data-testid="stRadio"] label > div:first-child {display:none;}
        [data-testid="stMain"] [data-testid="stRadio"] label > div:last-child {padding-left:0;}
        [data-testid="stMain"] [data-testid="stRadio"] label:has(input:checked) {background:#fff;box-shadow:0 1px 3px rgba(24,38,58,.10);color:var(--blue);font-weight:700;}
        [data-testid="stSegmentedControl"] {background:#edf1f5; border-radius:10px; padding:3px; width:100%;}
        [data-testid="stSegmentedControl"] button {border-radius:7px !important; font-size:.83rem !important; font-weight:650 !important;}
        .surface-label {font-size:.7rem; font-weight:750; color:var(--faint); letter-spacing:.08em; text-transform:uppercase; margin:.2rem .65rem .45rem;}
        .page-header {margin:0 0 1.35rem; max-width:740px;}
        .page-header .eyebrow {font-size:.71rem; font-weight:750; color:var(--blue); letter-spacing:.08em; margin-bottom:.38rem; text-transform:uppercase;}
        .page-header + h1 {margin-top:0 !important;}.page-header + h1 + [data-testid="stCaptionContainer"] {font-size:.93rem; max-width:650px; margin-bottom:1.25rem;}
        .status-strip {display:flex; gap:0; background:var(--card); border:1px solid var(--line); border-radius:12px; overflow:hidden; margin:.35rem 0 1.8rem; box-shadow:0 2px 7px rgba(24,38,58,.025);}
        .status-strip > div {flex:1; padding:.82rem .95rem; border-right:1px solid var(--line);}
        .status-strip > div:last-child {border-right:0;}
        .status-strip b {font-size:1.32rem; display:block; color:var(--ink); letter-spacing:-.03em;}
        .status-strip span {font-size:.74rem; color:var(--muted);}
        .status-strip .urgent b {color:var(--red);} .status-strip .attention b {color:var(--amber);} .status-strip .action b {color:var(--blue);} .status-strip .neutral b {color:var(--gray);}
        .section-kicker {font-size:.74rem; color:var(--muted); margin-bottom:.25rem;}
        .member-hero,.client-hero {background:var(--card); border:1px solid var(--line); border-radius:16px; padding:1.5rem 1.65rem; margin:.15rem 0 1.25rem; box-shadow:0 2px 8px rgba(24,38,58,.035);}
        .member-hero,.client-hero {border-left:4px solid var(--blue);}
        .member-hero h1,.client-hero h1 {font-size:1.78rem !important; margin:0 !important;}.member-hero p,.client-hero p{margin:.24rem 0 .65rem;color:var(--muted);}
        .hero-facts{display:flex;gap:1.5rem;flex-wrap:wrap;margin-top:1.15rem;padding-top:1rem;border-top:1px solid var(--line);}.hero-fact{min-width:100px;}.hero-fact b{display:block;font-size:1.08rem;color:var(--ink);letter-spacing:-.02em;}.hero-fact span{display:block;font-size:.74rem;color:var(--muted);margin-top:.15rem;}
        .quiet-list {list-style:none; margin:0; padding:0;}.quiet-list li {padding:.68rem 0; border-bottom:1px solid var(--line);}.quiet-list li:last-child{border-bottom:0;}
        .empty-state {text-align:center; max-width:440px; margin:1.1rem auto; padding:1.5rem; color:var(--muted); background:#fafbfd; border:1px dashed #cbd7e2; border-radius:12px;}
        .empty-state strong {display:block; color:var(--ink); font-size:1rem; margin-bottom:.35rem;}
        .summary-note {font-size:.83rem; color:var(--muted); margin:.15rem 0 .75rem;}
        .status-badge {display:inline-flex;align-items:center;border-radius:999px;padding:.24rem .58rem;font-size:.75rem;font-weight:700;line-height:1.2;background:#eef2f5;color:#516174;}.status-badge.urgent{background:#fbecec;color:#aa3838;}.status-badge.attention{background:#fff4df;color:#936019;}.status-badge.action{background:#e8f1fa;color:#205c9e;}.status-badge.stable{background:#e7f4ef;color:#266d55;}.status-badge.neutral{background:#eef2f5;color:#516174;}
        .metric-tile {padding:1rem 1.05rem;border:1px solid var(--line);border-radius:12px;background:#fff;min-height:104px;}.metric-tile .label{font-size:.78rem;font-weight:650;color:var(--muted);}.metric-tile .value{font-size:1.48rem;font-weight:720;letter-spacing:-.03em;color:var(--ink);margin:.28rem 0 .12rem;}.metric-tile .note{font-size:.76rem;color:var(--muted);}
        .entry-card {border:1px solid var(--line);border-radius:14px;background:#fff;padding:1.05rem;min-height:142px;box-shadow:0 2px 7px rgba(24,38,58,.025);}.entry-card .entry-title{font-weight:720;font-size:1rem;color:var(--ink);}.entry-card .entry-value{font-size:.8rem;color:var(--blue);font-weight:650;margin:.55rem 0 .2rem;}.entry-card .entry-copy{font-size:.8rem;line-height:1.55;color:var(--muted);}
        .work-item {border:1px solid var(--line);border-left:4px solid var(--blue);border-radius:12px;background:#fff;padding:1rem 1.05rem;margin:.55rem 0;}.work-item .work-member{font-size:.86rem;font-weight:720;color:var(--ink);}.work-item .work-title{font-size:1.02rem;font-weight:720;color:var(--ink);margin:.6rem 0;}.work-item .work-label{font-size:.73rem;font-weight:720;color:var(--muted);margin-bottom:.1rem;}.work-item .work-copy{font-size:.84rem;color:#46576b;line-height:1.45;}
        .member-card {border:1px solid var(--line);border-radius:14px;background:#fff;padding:1.1rem;min-height:255px;box-shadow:0 2px 8px rgba(24,38,58,.03);}.member-card .member-name{font-size:1.12rem;font-weight:730;color:var(--ink);}.member-card .member-meta{font-size:.8rem;color:var(--muted);margin:.24rem 0 1rem;}.member-card .member-label{font-size:.72rem;font-weight:720;color:var(--muted);margin-top:.68rem;}.member-card .member-value{font-size:.9rem;color:var(--ink);margin-top:.12rem;}
        .detail-panel {background:#fff;border:1px solid var(--line);border-radius:14px;padding:1.1rem;margin:.45rem 0;}
        .portfolio-landing {max-width:760px;margin:8vh auto 0;padding:2.1rem 2.2rem;background:#fff;border:1px solid var(--line);border-radius:18px;box-shadow:0 8px 24px rgba(24,38,58,.06);}
        .portfolio-landing .portfolio-kicker{font-size:.74rem;font-weight:760;letter-spacing:.1em;text-transform:uppercase;color:var(--blue);}.portfolio-landing h1{font-size:2.2rem !important;margin:.45rem 0 .7rem !important;}.portfolio-landing p{max-width:625px;color:var(--muted);line-height:1.75;margin:0 0 1.5rem;}
        .focus-row{display:grid;grid-template-columns:30px 1fr auto;gap:.75rem;align-items:start;padding:.8rem 0;border-bottom:1px solid var(--line);}.focus-row:last-child{border-bottom:0;}.focus-index{font-size:.75rem;font-weight:760;color:var(--blue);padding-top:.14rem;}.focus-title{font-size:.94rem;font-weight:720;color:var(--ink);}.focus-copy{font-size:.79rem;color:var(--muted);margin-top:.15rem;}.next-row{padding:.75rem 0;border-bottom:1px solid var(--line);}.next-row:last-child{border-bottom:0;}.next-date{font-size:.74rem;color:var(--blue);font-weight:720;}.timeline-preview{display:grid;grid-template-columns:92px 1fr;gap:.7rem;padding:.6rem 0;border-bottom:1px solid var(--line);}.timeline-preview:last-child{border-bottom:0;}.timeline-date{font-size:.77rem;color:var(--muted);font-weight:650;}.timeline-title{font-size:.87rem;color:var(--ink);font-weight:680;}.timeline-copy{font-size:.78rem;color:var(--muted);margin-top:.15rem;}
        @media (max-width: 900px) {[data-testid="stAppViewContainer"] .main .block-container{padding:1.35rem 1rem 3rem;} .status-strip{flex-wrap:wrap;}.status-strip > div{min-width:45%;}.member-hero,.client-hero{padding:1.2rem;}}
        </style>
        """
