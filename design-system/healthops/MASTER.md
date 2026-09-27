# HealthOps Neumorphism Design System

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
| Canvas | `#edf2f7` | Cool medical gray-blue, never full-screen white |
| Main surface | `#f5f8fc` | Major panels |
| Data surface | `#ffffff` | Tables, charts, readable form contents |
| Recessed surface | `#e9eff6` | Input wells and segmented control tracks |
| Ink | `#20354c` | Headings, values, body |
| Native table ink | `#06182b` | Native canvas headers apply a 60% tint; this darker seed preserves ≥4.5:1 header contrast |
| Secondary ink | `#52677d` | Hints, labels; maintain 4.5:1 |
| Medical blue | `#185da8` | Primary CTA, current state |
| Control border | `#7a8da2` | Operable boundaries, ≥3:1 on light surfaces |
| Panel border | `#c7d4e2` | Section boundary, with spacing and heading |
| Divider | `#d5dfea` | Internal grouping |
| Completed | `#226548` / `#e7f3ec` | Text/check + green |
| Confirm | `#795514` / `#fff3d6` | Text + amber |
| Doctor judgment | `#914d17` / `#fff0e1` | Text + orange |
| Escalation | `#a53030` / `#fcecec` | True escalation only, never every abnormal value |
| No data / not started | `#52677d` / `#e9eff6` | Explicit state text |

Shadow main: `5px 5px 14px #20354c12, -4px -4px 12px #ffffffd9`.
Shadow emphasis: `6px 6px 18px #20354c16, -5px -5px 14px #ffffffeb`.
Shadow inset: `inset 2px 2px 4px #20354c0d, inset -2px -2px 4px #ffffffcc`.
Shadow controls: `2px 2px 5px #20354c12, -2px -2px 5px #ffffffcc`.
No glows, black heavy shadows, decorative gradients or hover movement.

Radii: main 16px, form/input/button 11px, badge 8px, track 12px.
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
| Tabs | Recessed segmented track; selected blue-tinted raised item, strong label and blue bottom indicator. Wrap without hiding any tab. Native radio/tab semantics and keyboard behavior. |
| Stepper | Current blue outline/fill plus explicit current text; completed green/check only when existing state says complete; future neutral inset. Preserve every stage and navigation. |
| Timeline | A continuous rule, markers and text. No raised container per record. Preserve dates, owners and details. |
| Charts | One outer trend panel, internal filters / summary / chart / metadata separated by rules. Clean white SVG/canvas; no shadow on chart marks. Keep axes, unit, time, baseline/current and data alternatives. |
| Badges | Flat tint, 8px corner; full text plus optional existing glyph; never color-only meaning. |
| Hover | Border/background emphasis with 150ms color/shadow transition. No shifting geometry. |
| Focus | Visible outline on keyboard interactive elements, including links, tabs, radios, checkboxes and summary. Do not clip. |
| Disabled | Native disabled semantics, readable `#52677d` on `#e9eff6`; no blanket opacity. |

## Page composition

- Today: light summary; prominent assistant panel containing counts + active
  flows; recent completion remains compact rows; work filters and original table
  share one clear main panel.
- Assistant board: distinct header, six-step progress, current work, routing,
  findings, formal Risk, human timeline, next step and outcome. Existing clinical
  responsibility and entry/wait/resume/exit are untouched.
- Member360: unified identity panel retains member, year, owner, stage, concern,
  professional focus, next action and updated timestamp. Original five tabs.
- Archive: initial assessment main panel; read-only category grid adds at-a-glance
  summaries, while the original complete interactive table remains available.
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
