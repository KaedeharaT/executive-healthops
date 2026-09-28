"""Restrained medical Soft UI tokens and shared component skins; no routing/state."""

CSS = '''<style>
:root {
 --page-bg:#eaf1f8;--surface:#edf3f9;--surface-raised:#f0f5fa;--surface-inset:#e6eef6;
 --border-soft:#d4e0ec;--shadow-light:rgba(255,255,255,.92);--shadow-dark:rgba(102,132,163,.20);
 --text-primary:#20354c;--text-secondary:#52677d;--medical-blue:#1969b4;
 --success:#26734d;--warning:#946018;--danger:#ae3939;
 --success-soft:#e5f2eb;--warning-soft:#fff2dd;--danger-soft:#faeaea;--blue-soft:#e1edf9;
 --radius-sm:12px;--radius-md:16px;--radius-lg:20px;--radius-pill:999px;
 --shadow-raised:6px 6px 16px var(--shadow-dark),-6px -6px 16px var(--shadow-light);
 --shadow-quiet:3px 3px 9px rgba(102,132,163,.13),-3px -3px 9px var(--shadow-light);
 --shadow-inset:inset 3px 3px 7px rgba(102,132,163,.17),inset -3px -3px 7px var(--shadow-light);
 --shadow-control:3px 3px 7px rgba(102,132,163,.20),-3px -3px 7px var(--shadow-light);
 --shadow-pressed:inset 2px 2px 5px rgba(53,88,126,.22),inset -2px -2px 5px rgba(255,255,255,.65);
 --shadow-primary:3px 3px 8px rgba(25,105,180,.24),-3px -3px 8px var(--shadow-light),inset 0 1px 0 rgba(255,255,255,.24);
 --shadow-primary-pressed:inset 2px 2px 5px rgba(14,52,88,.28),inset -1px -1px 4px rgba(255,255,255,.18);
 --shadow-panel:var(--shadow-raised);--motion-press:150ms;
 /* Compatibility names resolve to this one token system. */
 --canvas:var(--page-bg);--card:var(--surface-raised);--blue:var(--medical-blue);--brand-blue:var(--medical-blue);
 --ink:var(--text-primary);--text:var(--text-primary);--muted:var(--text-secondary);--line:var(--border-soft);
 --neu-well:var(--surface-inset);--neu-shadow:var(--shadow-raised);--neu-control:var(--shadow-control);
 --neu-inset:var(--shadow-inset);--neu-emphasis:var(--shadow-panel);
}
.stApp,[data-testid="stAppViewContainer"],[data-testid="stHeader"] {background:var(--page-bg)!important}
[data-testid="stSidebar"] {background:var(--surface)!important;border-right:1px solid var(--border-soft);min-width:210px!important;max-width:210px!important;box-shadow:var(--shadow-quiet)!important}
[data-testid="stSidebarUserContent"] {padding:22px 14px!important}
[data-testid="stSidebar"] h2 {font-size:14px!important;color:var(--muted)!important}
[data-testid="stSidebar"] label:has(input[type="radio"]) {padding:9px 12px;border-radius:var(--radius-sm);width:100%;margin:2px 0;background:transparent;border:0}
[data-testid="stSidebar"] label:has(input:checked) {background:var(--surface-inset)!important;color:var(--blue);font-weight:600;box-shadow:var(--shadow-inset)!important}
[data-testid="stMainBlockContainer"] {max-width:1550px!important;padding:30px 30px 55px!important}
[data-testid="stVerticalBlock"] {gap:.8rem}
[data-testid="stCaptionContainer"] p,[data-testid="stCaptionContainer"] {color:var(--text-secondary)!important;opacity:1!important}
[data-testid="stMain"] h1 {font-size:26px!important;font-weight:650!important}
[data-testid="stMain"] h2 {font-size:19px!important;margin:.25rem 0!important}
[data-testid="stMain"] h3 {font-size:16px!important}
/* PrimaryButton / SecondaryButton: press feedback without additional controls. */
[data-testid="stMain"] button,[data-testid="stSidebar"] button {border-radius:var(--radius-sm)!important;box-shadow:var(--shadow-control)!important;min-height:36px;border:1px solid var(--border-soft);background:var(--surface-raised);transition:box-shadow var(--motion-press),background var(--motion-press),transform var(--motion-press)}
[data-testid="stMain"] button[kind="primary"],[data-testid="stMain"] button[kind="primaryFormSubmit"] {background:var(--blue)!important;color:white!important;border-color:var(--blue)!important;box-shadow:var(--shadow-primary)!important}
[data-testid="stMain"] button:hover:not(:disabled) {border-color:var(--blue)!important;transform:translateY(-1px);box-shadow:var(--shadow-raised)!important}
[data-testid="stMain"] button:active:not(:disabled),[data-testid="stSidebar"] button:active:not(:disabled) {transform:translateY(0);box-shadow:var(--shadow-pressed)!important}
[data-testid="stMain"] button[kind^="primary"]:active:not(:disabled) {box-shadow:var(--shadow-primary-pressed)!important}
button:disabled {box-shadow:none!important;transform:none!important}
/* SegmentedTabs retain native radio semantics, keyboard navigation and focus. */
[data-testid="stMain"] [data-testid="stRadio"] div[role="radiogroup"][aria-orientation="horizontal"] {background:var(--surface)!important;border:0!important;border-radius:var(--radius-md)!important;padding:0!important;gap:.3rem;box-shadow:var(--shadow-quiet)}
[data-testid="stMain"] [data-testid="stRadio"] label {border-radius:var(--radius-sm)!important;min-height:40px;padding:.45rem .75rem}
[data-testid="stMain"] [data-testid="stRadio"] label:has(input:checked) {background:var(--surface-inset)!important;color:var(--blue);box-shadow:var(--shadow-inset)!important}
/* InsetInput: skin the native input shell, not every nested element. */
[data-baseweb="input"],[data-baseweb="textarea"],[data-baseweb="select"]>div,
[data-testid="stTextInputRootElement"],[data-testid="stTextArea"] textarea,
[data-testid="stSelectbox"] [role="group"],[data-testid="stNumberInputContainer"] {background:var(--surface-inset)!important;box-shadow:var(--shadow-inset)!important;border-radius:var(--radius-sm)!important;border-color:var(--border-soft)!important}
[data-testid="stMain"] input,[data-testid="stMain"] textarea {background:transparent!important;border-radius:var(--radius-sm)!important;color:var(--text-primary);box-shadow:none!important}
[data-testid="stMain"] [data-testid="stTextArea"] textarea {background:var(--surface-inset)!important;box-shadow:var(--shadow-inset)!important}
[data-testid="stSelectbox"] [role="group"] button {background:transparent!important;border-color:transparent!important;box-shadow:none!important;transform:none!important}
.st-key-intake-section-cards button {width:100%;min-height:80px!important;text-align:left;white-space:pre-line;cursor:pointer;border-radius:var(--radius-md)!important}
.st-key-intake-section-cards button:focus-visible {outline:2px solid var(--blue);outline-offset:2px}
/* Panel: only existing work surfaces get elevation. Dense rows remain flat. */
[class*="st-key-v7-main"] {background:var(--surface-raised);border:1px solid var(--border-soft);padding:20px;border-radius:var(--radius-lg);box-shadow:var(--shadow-panel)}
[class*="st-key-v7-context"] {padding:4px 0 8px 18px;border-left:1px solid var(--border-soft)}
[class*="st-key-v7-context"] .v2-summary {background:var(--surface)!important;border-radius:var(--radius-md);box-shadow:var(--shadow-quiet)!important}
.st-key-v7-context-management {background:var(--surface-raised);border:1px solid var(--border-soft);border-radius:var(--radius-lg);box-shadow:var(--shadow-panel);padding:4px 12px 8px 18px}
[class*="st-key-v2-panel"],[class*="st-key-v2-hero"] {background:var(--surface-raised)!important;box-shadow:var(--shadow-quiet)!important;border:1px solid var(--border-soft)!important;border-radius:var(--radius-lg)!important;padding:18px!important}
[data-testid="stVerticalBlockBorderWrapper"],[data-testid="stForm"] {border-radius:var(--radius-md)!important;background:var(--surface)!important;border-color:var(--border-soft)!important;box-shadow:var(--shadow-quiet)!important}
[data-testid="stForm"] [data-testid="stVerticalBlockBorderWrapper"] {box-shadow:none!important}
.st-key-intake-exception-workspace {background:var(--surface-raised)!important;border-color:var(--border-soft)!important;border-radius:var(--radius-md)!important;box-shadow:var(--shadow-quiet)!important}
.v2-summary {display:flex;gap:20px;flex-wrap:wrap;padding:10px 0!important;background:transparent!important;box-shadow:none!important;border:0!important}
.v2-summary>div {min-width:80px;background:transparent!important;box-shadow:none!important;border:0!important;padding:0 16px 0 0!important;border-radius:0!important}
.v2-summary small {color:var(--muted);font-size:12px;display:block}
.v2-summary strong {font-size:21px!important;color:var(--ink);display:block}
.care-member-header {background:var(--surface);border:0;border-bottom:1px solid var(--border-soft);border-radius:var(--radius-lg);padding:0 16px 14px;box-shadow:var(--shadow-quiet)}
.care-member-header h1 {font-size:25px!important;margin:3px 0!important}
.care-member-header .member-meta {display:flex;gap:22px;color:var(--muted);font-size:13px;flex-wrap:wrap}
.care-member-header .care-next {background:transparent;padding:6px 0 0;color:var(--text-primary)}
/* Tables and charts stay legible, with no row elevation. */
[data-testid="stDataFrame"] {border:1px solid var(--border-soft);border-radius:var(--radius-sm);box-shadow:none!important;background:var(--surface-raised)}
[data-testid="stVegaLiteChart"] {background:var(--surface-raised);border-radius:var(--radius-md);box-shadow:var(--shadow-quiet)}
.v3-comparison {background:var(--surface-raised)}
.v3-comparison th {background:var(--surface-inset)}
.v3-comparison tr:hover {background:var(--surface)}
.v2-timeline {border:0!important;border-left:2px solid var(--border-soft)!important;background:transparent!important;box-shadow:none!important;padding:8px 12px!important;margin:5px 0!important}
.v2-timeline h3 {font-size:14px!important}.v2-timeline p {font-size:13px!important}
.v2-workflow {box-shadow:none!important;background:transparent!important;padding:8px 0!important}
.v2-workflow .flow-dot {background:var(--surface-raised);box-shadow:var(--shadow-control);border-color:var(--border-soft)}
.v2-workflow .active .flow-dot {background:var(--surface-inset);color:var(--blue);border-color:var(--blue);box-shadow:var(--shadow-inset)}
.neu-intake-steps {display:flex;flex-wrap:wrap;list-style:none;padding:0;gap:8px}
.neu-intake-steps li {font-size:12px;border-bottom:2px solid var(--border-soft);padding:6px}.neu-intake-steps li.current{border-color:var(--blue);color:var(--blue)}
.neu-intake-steps small {display:block;color:var(--muted)}
/* AgentProgressPanel: the strongest work surface, with an inset progress track. */
.st-key-intake-agent-board {background:var(--surface-raised)!important;border:1px solid var(--border-soft)!important;border-top:3px solid var(--blue)!important;padding:18px!important;border-radius:var(--radius-lg)!important;box-shadow:var(--shadow-panel)!important}
.agent-progress-track {height:12px;background:var(--surface-inset);border-radius:var(--radius-pill);overflow:hidden;margin:10px 0 12px;box-shadow:var(--shadow-inset)}
.agent-progress-fill {height:100%;background:var(--blue);border-radius:var(--radius-pill)}
.agent-progress-title {font-size:22px;font-weight:700;color:var(--text-primary)}
.agent-progress-detail {color:var(--muted);margin-bottom:10px}
.agent-action-spinner {display:inline-block;width:18px;height:18px;border:2px solid var(--border-soft);border-top-color:var(--blue);border-radius:50%;animation:agent-progress-spin 1s linear infinite;margin-right:8px;vertical-align:-2px}
[data-testid="stProgressBarTrack"] {height:10px;border-radius:var(--radius-pill);background:var(--surface-inset);box-shadow:var(--shadow-inset)}
[data-testid="stProgressBarTrack"]>div {background:var(--blue);border-radius:var(--radius-pill)}
[data-testid="stExpander"] {background:var(--surface)!important;border-color:var(--border-soft)!important;border-radius:var(--radius-sm)!important;box-shadow:none}
[data-testid="stFileUploader"] {background:var(--surface-inset)!important;border-radius:var(--radius-md);box-shadow:var(--shadow-inset)}
.status-badge,.ux-badge {border-radius:var(--radius-pill);box-shadow:none;background:var(--surface-inset);color:var(--text-secondary)}
.status-badge.stable {background:var(--success-soft);color:var(--success)}
.status-badge.attention {background:var(--warning-soft);color:var(--warning)}
.status-badge.urgent {background:var(--danger-soft);color:var(--danger)}
.status-badge.action {background:var(--blue-soft);color:var(--blue)}
.st-key-v7-sidebar-user {position:fixed;bottom:16px;left:15px;width:177px;background:var(--surface);border-top:1px solid var(--border-soft);padding-top:14px}
@keyframes agent-progress-spin {to{transform:rotate(360deg)}}
@media(prefers-reduced-motion:reduce) {.agent-action-spinner{animation:none}button{transition:none!important;transform:none!important}}
@media(max-width:1000px) {[data-testid="stMainBlockContainer"]{padding:24px 16px!important}[class*="st-key-v7-context"]{padding-left:0;border-left:0}.st-key-v7-sidebar-user{position:static}}
</style>'''


def role_css(role):
    """Doctor/admin retain the same components with quieter work surface depth."""
    return CSS + ('<style>:root{--shadow-panel:var(--shadow-quiet)}</style>' if role in {'doctor', 'admin'} else '')
