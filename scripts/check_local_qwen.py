"""Synthetic-only verification for the optional local Qwen report fallback."""

from __future__ import annotations

import sys
import time
from uuid import uuid4

from executive_health_ai.llm.prompts.health_report import FINDING_EXTRACTION_SYSTEM_PROMPT, finding_extraction_prompt
from executive_health_ai.llm.qwen_client import LocalQwenClient, LocalQwenUnavailable
from executive_health_ai.services.report_parsing import ExtractedPage, ReportSemanticFallback


SYNTHETIC_CT_TEXT = "胸部CT检查结论：左肺下叶见少许条索影。双肺可见多个小结节。建议约3个月后复查胸部CT。"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    client = LocalQwenClient()
    health = client.health_check()
    print(f"Ollama ............ {'OK' if health.available else 'FAIL'}")
    print(f"Model {health.model} .. {'OK' if health.available else 'FAIL'}")
    if not health.available:
        print(f"Reason ............ {health.reason or 'unavailable'}")
        return 1
    started = time.perf_counter()
    try:
        payload = client.generate_structured(
            task="report_semantic_fallback",
            system_prompt=FINDING_EXTRACTION_SYSTEM_PROMPT,
            user_prompt=finding_extraction_prompt(SYNTHETIC_CT_TEXT),
            document_id="synthetic-qwen-health-check",
            page=1,
        )
    except LocalQwenUnavailable as error:
        print("Health client ..... FAIL")
        print(f"Reason ............ {error}")
        return 1
    if not isinstance(payload, dict):
        print("Structured JSON ... FAIL")
        return 1
    print("Health client ..... OK")
    print("Structured JSON ... OK")
    result = ReportSemanticFallback(client=client).extract(
        pages=[ExtractedPage(1, SYNTHETIC_CT_TEXT)], existing=[], document_id=uuid4()
    )
    types = {draft.candidate_type for draft in result.drafts}
    valid = result.used and {"FINDING", "FOLLOWUP"}.issubset(types) and all(draft.evidence_text for draft in result.drafts)
    print(f"Semantic fallback . {'OK' if valid else 'FAIL'}")
    print(f"Latency ........... {time.perf_counter() - started:.1f}s")
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
