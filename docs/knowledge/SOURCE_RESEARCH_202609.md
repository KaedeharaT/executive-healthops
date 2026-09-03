# Official Knowledge Source Research — 2026-09

Research date: 2026-09-02. Search engines were used only for discovery; each row was checked against the linked official page. `APPROVED_SOURCE` means a trustworthy governed source candidate—not automatic approval of every document. Full text is never ingested where the item-level licence is unclear.

| Source | Organization | Domain / jurisdiction | Licence / reuse finding | API | Strategy | Tier | Status |
|---|---|---|---|---|---|---|---|
| [MedlinePlus](https://medlineplus.gov/about/using/usingcontent/) | NLM/NIH | education, tests / US | Topic summaries and Medical Tests are public domain with attribution; ASHP drug and A.D.A.M. content excluded | [search](https://medlineplus.gov/about/developers/webservices/) | PUBLIC_SUMMARY | A | APPROVED_SOURCE |
| [RxNorm](https://www.nlm.nih.gov/research/umls/rxnorm/index.html) | NLM/NIH | medication terminology / US | RxNorm API vocabulary generally no licence; proprietary/UMLS source content excluded; requested attribution | [RxNav](https://lhncbc.nlm.nih.gov/RxNav/APIs/) | API_ON_DEMAND | A | APPROVED_SOURCE |
| [DailyMed](https://dailymed.nlm.nih.gov/dailymed/app-support-web-services.cfm) | NLM | official SPL / US | Versioned label source; retain label provenance and terms | REST v2 | API_ON_DEMAND | A | APPROVED_SOURCE |
| [openFDA](https://open.fda.gov/apis/) | FDA | drug/device regulatory / US | Public datasets with API disclaimer; not validated for clinical decisions | JSON API | API_ON_DEMAND | A | APPROVED_SOURCE |
| [LOINC](https://loinc.org/kb/license) | Regenstrief | lab terminology / GLOBAL | Commercial/non-commercial use allowed with mandatory notice and restrictions; no competing standard/unauthorised derivatives; third-party fields need separate rights | authenticated download/FHIR | METADATA_ONLY | B | CONDITIONAL |
| [SNOMED CT](https://www.snomed.org/get-snomed) | SNOMED International | terminology / GLOBAL | Affiliate and territory licensing applies; disabled until licence review | licensed services | LICENSE_RESTRICTED | B | CONDITIONAL |
| [WHO ICD-11](https://icd.who.int/docs/icd-api/license/) | WHO | classification / GLOBAL | CC BY-ND 3.0 IGO; no adaptation | [ICD API](https://icd.who.int/icdapi) | API_ON_DEMAND | A | CONDITIONAL |
| [WHO publications/topics](https://www.who.int/about/policies/publishing/copyright) | WHO | public health / GLOBAL | Publication-specific; common licence CC BY-NC-SA 3.0 IGO; commercial use may require permission | none general | LINK_ONLY | A | CONDITIONAL |
| [CDC](https://www.cdc.gov/other/agencymaterials.html) | CDC | public health / US | Most agency-authored text public domain; attribution/no-endorsement; third-party works excluded | selected datasets | PUBLIC_SUMMARY | A | APPROVED_SOURCE |
| [NIH](https://www.nih.gov/) | NIH | research/education / US | Government-authored text generally public domain; item-level third-party check | selected | PUBLIC_SUMMARY | A | APPROVED_SOURCE |
| [NHLBI](https://www.nhlbi.nih.gov/health) | NIH/NHLBI | BP, lipids, sleep, lung / US | Government educational content; exclude credited assets | none general | PUBLIC_SUMMARY | A | APPROVED_SOURCE |
| [NIDDK](https://www.niddk.nih.gov/health-information) | NIH/NIDDK | diabetes, kidney, liver, obesity / US | Reviewed government health information; page-date/version tracked | none general | PUBLIC_SUMMARY | A | APPROVED_SOURCE |
| [NIMH](https://www.nimh.nih.gov/health/topics) | NIH/NIMH | mental wellbeing / US | Education only; explicitly not individual medical advice | none general | PUBLIC_SUMMARY | A | APPROVED_SOURCE |
| [NIH ODS](https://ods.od.nih.gov/factsheets/list-all/) | NIH ODS | supplements / US | Government fact sheets; source-level attribution; never treatment recommendation | data files vary | PUBLIC_SUMMARY | A | APPROVED_SOURCE |
| [FDA Digital Health](https://www.fda.gov/medical-devices/digital-health-center-excellence/guidances-digital-health-content) | FDA | device/AI safety / US | Guidance metadata and versions; document-specific status/rights | none general | METADATA_ONLY | A | APPROVED_SOURCE |
| [USPSTF](https://www.uspreventiveservicestaskforce.org/uspstf/recommendation-topics/copyright-notice) | USPSTF/AHRQ | prevention / US | Unchanged reproduction allowed; profit/fee use requires written permission | app/data tools | METADATA_ONLY | A | CONDITIONAL |
| [NICE](https://www.nice.org.uk/reusing-our-content/nice-uk-open-content-licence) | NICE | guidelines / UK | UK Open Content Licence with content/territory restrictions; item review required | selected | METADATA_ONLY | B | CONDITIONAL |
| [NHS](https://www.nhs.uk/our-policies/terms-and-conditions/) | NHS | patient education / UK | Site terms and content-specific rights | syndication varies | LINK_ONLY | A | CONDITIONAL |
| [AHA](https://www.heart.org/en/about-us/statements-and-policies/copyright-permission-guidelines) | American Heart Association | cardiovascular / US | Copyrighted; reproduction generally requires permission/fees | none | METADATA_ONLY | B | METADATA_ONLY |
| [ACC](https://www.acc.org/guidelines) | American College of Cardiology | cardiovascular / US | Professional guideline metadata; rights checked per publication | none general | LINK_ONLY | B | METADATA_ONLY |
| [ADA](https://diabetes.org/about-us/policies/terms-of-use) | American Diabetes Association | diabetes / US | Personal use; electronic reproduction requires permission | none general | METADATA_ONLY | B | METADATA_ONLY |
| [Dietary Guidelines](https://www.dietaryguidelines.gov/policy-and-links) | USDA/HHS | nutrition / US | Site information public domain with attribution; protected images/assets excluded | downloads | OPEN_FULLTEXT | A | APPROVED_SOURCE |
| [Japan MHLW](https://www.mhlw.go.jp/chosakuken/) | 厚生労働省 | lifestyle/workplace / JP | Public Data Licence 1.0 unless otherwise marked; attribution required | downloads | PUBLIC_SUMMARY | A | APPROVED_SOURCE |
| [China NHC](https://www.nhc.gov.cn/) | 国家卫生健康委员会 | health policy/education / CN | 版权所有、不得非法镜像；默认只保留链接/元数据 | none general | LINK_ONLY | A | CONDITIONAL |
| [China CDC](https://www.chinacdc.cn/jkkp/) | 中国疾控中心 | public health / CN | Site copyright/disclaimer; default link/metadata pending item permission | none general | LINK_ONLY | A | CONDITIONAL |
| [Apple HealthKit](https://developer.apple.com/documentation/healthkit) | Apple | technical data definitions / GLOBAL | Developer terms; technical/product source only, never medical interpretation | SDK | LINK_ONLY | D | METADATA_ONLY |
| [NIST AI RMF](https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-ai-rmf-10) | NIST | AI safety / GLOBAL | U.S. government publication; cite NIST AI 100-1 | downloads | OPEN_FULLTEXT | A | APPROVED_SOURCE |
| [HHS HIPAA](https://www.hhs.gov/hipaa/index.html) | HHS | privacy / US | Official legal education; reference only, not compliance certification | none | PUBLIC_SUMMARY | A | APPROVED_SOURCE |
| [China PIPL](https://www.gov.cn/xinwen/2021-08/20/content_5632486.htm) | 中国政府网/全国人大 | privacy law / CN | Official legal text; metadata/link and legal review | none | LINK_ONLY | A | METADATA_ONLY |
| [Japan PPC/APPI](https://www.ppc.go.jp/en/) | Personal Information Protection Commission | privacy / JP | Official legal guidance; legal-review reference | none general | LINK_ONLY | A | METADATA_ONLY |
| [EMA](https://www.ema.europa.eu/en/about-us/legal-notice) | European Medicines Agency | medication regulatory / EU | Legal notice and document-specific rights | selected data | METADATA_ONLY | A | CONDITIONAL |
| Internal Demo SOP | Executive HealthOps | workflow / internal | Original synthetic Portfolio content, project licence | local seed | OPEN_FULLTEXT | C | APPROVED_SOURCE |
| Internal Demo Knowledge | Executive HealthOps | workflow / communication / service / AI safety | Original synthetic Portfolio content, project licence | local seed | OPEN_FULLTEXT | C | APPROVED_SOURCE |
| [UpToDate](https://www.uptodate.com/) | Wolters Kluwer | commercial clinical database | Subscription/copyrighted; no scraping, mirroring or redistribution | licensed only | DO_NOT_INGEST | D | DO_NOT_INGEST |

## Decisions

- P0 core sources are stable official/government terminology, education, regulatory and internal-governance sources. Dynamic labels and vocabularies are queried on demand rather than mirrored.
- Professional guidelines remain metadata/link or pending review unless the exact version and licence are approved. A web page being publicly readable is not full-text permission.
- China and professional-organisation content defaults to link/metadata where redistribution terms are not explicit. Unavailable pages are recorded as `UNAVAILABLE`; content is never reconstructed from search snippets.
- No external full-text corpus was downloaded or committed in this iteration.
