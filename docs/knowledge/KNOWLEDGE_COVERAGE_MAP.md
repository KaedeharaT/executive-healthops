# Knowledge Coverage Map

Coverage is measured by governed Golden Queries, not by document count.

| Domain | Product need | Primary sources/strategy | V1 | Boundary |
|---|---|---|---|---|
| A Report | tests, imaging context, follow-up concepts | MedlinePlus public summaries + internal review SOP | STRONG | no diagnosis |
| B Lab | names, units, purpose, interpretation limits | MedlinePlus Medical Tests; LOINC metadata/mapping | PARTIAL | LOINC licence/version retained |
| C Medication | normalization, official labels, warnings | RxNorm, DailyMed, openFDA on demand | PARTIAL | no prescribe/stop/change |
| D Chronic disease | BP, lipids, diabetes, obesity, kidney, lung, thyroid | CDC/NIH/NHLBI/NIDDK; WHO links | PARTIAL | education only |
| E Prevention | screening/vaccine/lifestyle metadata | USPSTF/NICE/CDC | PARTIAL | jurisdiction shown; not a rule |
| F Nutrition | food patterns and supplement safety | USDA/HHS, NIH ODS, WHO metadata | STRONG | supplements are not treatments |
| G Activity | activity and measurement education | CDC, MHLW Japan, WHO metadata | STRONG | population/jurisdiction shown |
| H Sleep | sleep education and hygiene | NHLBI/CDC | PARTIAL | no sleep-disorder diagnosis |
| I Smoking/alcohol | cessation/risk education | CDC/WHO links | PARTIAL | escalation remains human |
| J Mental wellbeing | education, stress, crisis boundary | NIMH/WHO links | PARTIAL | no psychological diagnosis |
| K Devices | BP, CGM, SpO2, Apple data definitions | FDA metadata; Apple docs link only | PARTIAL | product docs are not medical evidence |
| L Risk | source material for governed rules | guideline metadata | PARTIAL | candidate only; no auto-rule |
| M SOP | report/risk/plan/task/service/outcome/data quality | versioned Internal Demo SOP | STRONG | Portfolio SOP label required |
| N Doctor collaboration | escalation and brief requirements | Internal Demo SOP | STRONG | doctor owns medical judgement |
| O Communication | reminders, refusal, anxiety, escalation | training material | STRONG | no fear or false assurance |
| P Service | request through result | Internal Demo SOP | STRONG | operational only |
| Q Outcome | observed change and next cycle | Internal Demo SOP | STRONG | no causal claim |
| R Training | cases, rubrics, mistakes | approved SOP/training chunks | STRONG | prototype, not HR scoring |
| S Privacy/AI safety | design and training reference | NIST, FDA, HHS, CN/JP official metadata | PARTIAL | no legal-compliance claim |

## Priority

P0 core: MedlinePlus, RxNorm, DailyMed, openFDA, CDC, NIH/NHLBI/NIDDK/NIMH/ODS, FDA, USDA/HHS, MHLW, NIST and internal governed content. P1 sources (WHO, NICE, USPSTF and professional organisations) require licence, jurisdiction and version checks per item. P2 sources stay disabled until human review.
