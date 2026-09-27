# HealthOps Neumorphism Design System

Revision 2 — visually distinct surfaces. Supersedes the first redesign's visual
acceptance. Implementation: `ui/soft_surfaces.py`, shared by the existing Streamlit UI.

## Authority and verified sources

Read: `D:/executive_health_ai/.agents/skills/ui-ux-pro-max/SKILL.md`.
Local CLI: `.agents/skills/ui-ux-pro-max/scripts/search.py`.
Queries executed: healthcare SaaS (`--design-system`); neumorphism, soft UI,
enterprise dashboard (`--domain style`); health management dashboard, medical
operations (`--domain product`); accessible dashboard contrast, data table
(`--domain ux`); health charts (`--domain chart`).

Verified matches: `styles.csv` Neumorphism, Soft UI Evolution, Data-Dense
Dashboard; `products.csv` Medical Clinic, Healthcare App, Patient Portal / Health
Records; `ux-guidelines.csv` Color Contrast, Contrast Readability, Table Handling.
The broad health management query returned LMS and incident products: rejected;
retry `healthcare patient records` returned Healthcare App / Patient Portal.
The broad chart query returned distribution/radar: rejected; retry `health time
series trend` returned Trend Over Time. Preserve existing clinical chart semantics.
The generator's landing-page hero/testimonial pattern is inapplicable to the
operations application: rejected. No new marketing content or external fonts.

## Direction and boundaries

Restrained Neumorphism / Soft UI for an existing Streamlit healthcare SaaS.
Professional, calm, compact. Existing medical blue remains `#185da8`.
User constraints override dataset suggestions for pastel colors, borderless
surfaces and framework examples. Keep visible borders and native Streamlit
controls; no React, Tailwind app, platform migration or clinical behavior changes.

Records → table; trends → chart; logs → timeline; stages → stepper;
priorities → summary; prose → detail. Never turn table rows, every metric,
labels or small utility buttons into elevated cards. Do not remove any action.

## Tokens

| Role | Value | Use |
|---|---|---|
| App background | `#dce5ef` | Clearly visible cool gray-blue canvas |
| Surface 1 | `#eaf0f6` | Major business panels |
| Surface 2 / raised | `#f7faff` | Active flows, selected tabs, chart summary |
| Data surface | `#ffffff` | Tables, charts, readable form contents |
| Recessed surface | `#dce6f0` | Input wells, filter bars, segmented navigation |
| Ink | `#18334e` | Headings, values, body |
| Native table ink | `#06182b` | Native canvas headers apply a 60% tint; this darker seed preserves ≥4.5:1 header contrast |
| Secondary ink | `#405b74` | Hints, labels; maintain 4.5:1 |
| Medical blue | `#185da8` | Primary CTA, current state |
| Control border | `#748ba2` | Operable boundaries, combined with explicit focus |
| Panel border / divider | `#b7c8d9` | Section boundary, with spacing and heading |
| Completed | `#226548` / `#e7f3ec` | Text/check + green |
| Confirm | `#795514` / `#fff3d6` | Text + amber |
| Doctor judgment | `#914d17` / `#fff0e1` | Text + orange |
| Escalation | `#a53030` / `#fcecec` | True escalation only, never every abnormal value |
| No data / not started | `#405b74` / `#dce6f0` | Explicit state text |

Raised shadow: `8px 8px 18px #afbdcd80, -7px -7px 18px #ffffffcc`.
Doctor raised shadow: `4px 4px 10px #b8c6d559, -4px -4px 10px #ffffffb3`.
Admin raised shadow: `2px 2px 6px #b8c6d540, -2px -2px 6px #ffffff99`.
Inset shadow: `inset 4px 4px 8px #a9bacc80, inset -4px -4px 8px #ffffffd9`.
Control shadow: `4px 4px 8px #adbdcf99, -4px -4px 8px #ffffffeb`.
Primary button: `#185da8`; hover `#124f91`; pressed shadow
`inset 3px 3px 6px #0b3c73, inset -2px -2px 5px #4680b8`.
No glows, black heavy shadows, decorative gradients or hover movement.

Radii: main 18px, input 11px, button 12px, badge 8px, navigation track 16px.
Spacing: 4, 8, 12, 16, 24, 32px. Main panel padding 24px (16px narrow).
Main section separation 24–32px; internal field gaps 8–16px.
Typography: system sans, Segoe UI / Microsoft YaHei / PingFang SC; local fallbacks.
Page heading 28–30px/1.3, section 20–22px/1.4, subsection 16–18px/1.5;
body/input 16px/1.6; dense table/help 14px/1.55; badge ≥12px.
Numeric data uses tabular figures. Essential values wrap; no new line clamps.

## Components

| Component | Contract |
|---|---|
| Buttons | Primary blue with white label and subtle paired shadow; secondary light raised surface; tertiary table/list actions flat. ≥44px height. Pressed inset; no translate/scale. |
| Inputs | Visible border and shallow inset; keep labels, help, validation, names, values and native semantics. Focus 3px blue outline with 3px offset. |
| Cards | Elevate only main business areas, identity, assistant, initial assessment, major summaries. Internal sections use rule/heading/padding. |
| Tables | White flat data surface, tinted headers, readable grid and text; original sort/select/export behavior retained. Local horizontal scroll on narrow screens. No row shadow or row cards. |
| Tabs | Full-width inset track; five equal Member360 segments; current segment is raised. Decorative radio circles are visually replaced by the selected surface, while native inputs, labels, keyboard behavior and selected semantics remain. Narrow screens wrap all segments. |
| Stepper | Current blue outline/fill plus explicit current text; completed green/check only when existing state says complete; future neutral inset. Preserve every stage and navigation. |
| Timeline | A continuous rule, markers and text. No raised container per record. Preserve dates, owners and details. |
| Charts | One outer trend panel, internal filters / summary / chart / metadata separated by rules. Clean white SVG/canvas; no shadow on chart marks. Keep axes, unit, time, baseline/current and data alternatives. |
| Badges | Flat tint, 8px corner; full text plus optional existing glyph; never color-only meaning. |
| Hover | Border/background emphasis with 150ms color/shadow transition. No shifting geometry. |
| Focus | Visible outline on keyboard interactive elements, including links, tabs, radios, checkboxes and summary. Do not clip. |
| Disabled | Native disabled semantics, readable `#405b74` on `#dce6f0`; no blanket opacity. |

## Page composition

- Today: title and five-count summary share a two-column header surface;
  prominent assistant panel contains an inset status strip and active
  flows; recent completion remains compact rows; work filters and original table
  share one clear main panel, with an inset filter bar. Active flow source/current
  state and completed work use columns; next action is below a divider.
- Assistant board: distinct header, six-step progress, current work, routing,
  findings, formal Risk, human timeline, next step and outcome. Existing clinical
  responsibility and entry/wait/resume/exit are untouched.
- Member360: identity/name at left; year/owner/stage in an inset metadata area;
  member concern and professional focus form distinct columns; next action gets
  a full-width band. Every original value and all five navigation options remain.
- Archive: initial assessment main panel; read-only category grid adds at-a-glance
  summaries in seven categories including surgery, with a consistent line icon,
  recorded count/state and explanatory subtitle. The full interactive table remains.
  Import uses the existing three type choices with clear descriptions.
- Wizard: one stepper and one form panel. All eleven steps, table editors,
  fields, validation, save/back/submit and assessment review remain.
- Member: softer major surfaces; preserve health, plan, action and owner content.
- Doctor: low relief, high contrast, evidence/table/chart first.
- Admin: lowest relief; dense table/status/log/integration surfaces.

## Accessibility and acceptance

Measure normal text ≥4.5:1, meaningful controls/focus ≥3:1. Preserve keyboard
navigation, visible labels and native semantics; color never carries state alone.
Honor `prefers-reduced-motion` and forced colors. No hidden controls to make a
small screen fit. Check 1366×768, 1440×900, 1920×1080, and existing 390px narrow
viewport. Tables may scroll inside their existing container, page may not overflow.
Baseline + final full pytest; AST inventory must lose zero original UI calls;
protected business/Agent/model/migration/chart file hashes must remain unchanged.
Real Chromium journeys and matched screenshots use a synthetic database copy.

Revision 2 acceptance additionally requires manually opening side-by-side images
at 50% scale. Pixel differences only quantify changed area; they never decide
visual quality. Capture both original → 3b78204 (prior work audit) and
3b78204 → revised (current work). Match database hash, role, route, viewport and
scroll offsets. A stale running service must be detected and reloaded before
claiming the user's existing URL displays the revised interface.
