"""Capture real Executive HealthOps Portfolio Demo pages with Playwright.

This development helper drives the live Streamlit interface using accessible
roles and visible product text.  It never creates mockups or synthesizes image
content: each PNG is a Chromium screenshot of the running local demo.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Awaitable, Callable

from playwright.async_api import Locator, Page, TimeoutError as PlaywrightTimeoutError, async_playwright


VIEWPORT = {"width": 1440, "height": 900}
WAIT_AFTER_ACTION_MS = 900
CORE_SCREENSHOTS = ("dashboard", "member_overview", "doctor_review", "timeline")
STREAMLIT_APP_ROOT = '[data-testid="stAppViewContainer"]'


@dataclass
class CaptureResult:
    status: str
    path: str | None = None
    reason: str | None = None


async def wait_for_streamlit(page: Page) -> None:
    """Wait for Streamlit to settle without relying on application CSS classes."""
    await page.wait_for_timeout(WAIT_AFTER_ACTION_MS)
    try:
        await page.get_by_text("Running...", exact=True).wait_for(state="hidden", timeout=3_000)
    except PlaywrightTimeoutError:
        pass
    await page.wait_for_timeout(450)


async def product_surface_is_ready(page: Page) -> bool:
    """Return true once Streamlit has rendered product controls, not its toolbar."""
    known_controls = (
        page.get_by_role("button", name="进入 HealthOps 运营后台", exact=True),
        page.get_by_role("radio", name="今日", exact=True),
        page.get_by_role("radio", name="成员", exact=True),
        page.get_by_role("radio", name="运营后台", exact=True),
        page.get_by_text("Executive HealthOps", exact=True),
    )
    for control in known_controls:
        if await first_visible(control) is not None:
            return True
    return False


async def open_demo_page(page: Page, demo_url: str) -> None:
    """Open a fully rendered Streamlit session, retrying the toolbar-only state once."""
    last_text = ""
    for attempt in range(2):
        if attempt == 0:
            await page.goto(demo_url, wait_until="domcontentloaded", timeout=30_000)
        else:
            await page.reload(wait_until="domcontentloaded", timeout=30_000)
        await page.locator(STREAMLIT_APP_ROOT).wait_for(state="visible", timeout=20_000)
        for _ in range(18):
            await wait_for_streamlit(page)
            if await product_surface_is_ready(page):
                return
        last_text = await dump_visible_text(page, "Streamlit did not finish rendering a product surface")
        # Streamlit's initial toolbar can briefly be the only visible UI ("Stop Deploy").
        # A single reload establishes a fresh websocket/session before the next attempt.
    raise RuntimeError(last_text)


async def dump_visible_text(page: Page, context: str) -> str:
    """Make a failed navigation actionable while avoiding a raw DOM dump."""
    try:
        text = await page.locator("body").inner_text(timeout=3_000)
    except PlaywrightTimeoutError:
        return f"{context}: page text was unavailable"
    compact = " ".join(text.split())
    return f"{context}: visible text: {compact[:1800]}"


async def first_visible(locator: Locator) -> Locator | None:
    count = await locator.count()
    for index in range(count):
        candidate = locator.nth(index)
        if await candidate.is_visible():
            return candidate
    return None


async def click_candidates(
    page: Page,
    candidates: tuple[str, ...],
    *,
    context: str,
    allow_text: bool = True,
) -> None:
    """Click the first visible product control matching Chinese or English copy."""
    for candidate in candidates:
        locators = [
            page.get_by_role("button", name=candidate, exact=True),
            page.get_by_role("link", name=candidate, exact=True),
            page.get_by_role("radio", name=candidate, exact=True),
            page.get_by_role("tab", name=candidate, exact=True),
        ]
        if allow_text:
            locators.append(page.get_by_text(candidate, exact=True))
        for locator in locators:
            visible = await first_visible(locator)
            if visible is None:
                continue
            try:
                await visible.click(timeout=3_000)
                await wait_for_streamlit(page)
                return
            except PlaywrightTimeoutError:
                continue
    raise RuntimeError(await dump_visible_text(page, f"Could not find {context}: {candidates}"))


async def ensure_operations_surface(page: Page) -> None:
    """Use the real Portfolio landing action when it is present."""
    landing = await first_visible(page.get_by_role("button", name="进入 HealthOps 运营后台", exact=True))
    if landing is not None:
        await landing.click()
        await wait_for_streamlit(page)


async def choose_workspace(page: Page, *names: str) -> None:
    await ensure_operations_surface(page)
    await click_candidates(page, tuple(names), context="workspace")


async def open_member_overview(page: Page) -> None:
    await choose_workspace(page, "成员", "Members")
    try:
        await click_candidates(page, ("查看成员", "View member"), context="member detail action", allow_text=False)
    except RuntimeError:
        await click_candidates(page, ("Demo Executive A", "查看", "View"), context="Demo Executive A")
    await wait_for_streamlit(page)
    try:
        await click_candidates(page, ("概览", "Overview"), context="member overview")
    except RuntimeError:
        # The detail view already defaults to overview in the Portfolio Demo.
        pass


async def capture(
    page: Page,
    output_dir: Path,
    name: str,
    workflow: Callable[[Page], Awaitable[None]],
    *,
    demo_url: str,
) -> CaptureResult:
    target = output_dir / f"healthops-{name.replace('_', '-')}.png"
    try:
        # Each workflow starts from a fresh real demo page to avoid state coupling.
        await open_demo_page(page, demo_url)
        await workflow(page)
        await page.screenshot(path=str(target), full_page=False)
        if not target.is_file() or target.stat().st_size < 10_000:
            raise RuntimeError("Screenshot file was missing or unexpectedly small")
        return CaptureResult(status="PASS", path=str(target.resolve()))
    except Exception as exc:  # Each page must fail independently.
        return CaptureResult(status="FAIL", reason=str(exc))


async def main_async(args: argparse.Namespace) -> dict[str, CaptureResult]:
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, CaptureResult] = {}

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(viewport=VIEWPORT, base_url=args.url)
        page = await context.new_page()

        async def dashboard(current_page: Page) -> None:
            await choose_workspace(current_page, "今日", "Today")

        async def member_overview(current_page: Page) -> None:
            await open_member_overview(current_page)

        async def doctor_review(current_page: Page) -> None:
            await choose_workspace(current_page, "医疗协同", "Medical collaboration", "Doctor review")
            try:
                await click_candidates(current_page, ("内部医生", "Doctor Review", "Internal doctor"), context="internal doctor review")
            except RuntimeError:
                pass
            try:
                await click_candidates(current_page, ("查看依据", "View evidence"), context="evidence action")
            except RuntimeError:
                # A visible doctor review is still a valid human-in-the-loop screenshot.
                pass

        async def timeline(current_page: Page) -> None:
            await open_member_overview(current_page)
            await click_candidates(current_page, ("历程", "健康历程", "Timeline", "Journey"), context="health timeline")

        async def knowledge_center(current_page: Page) -> None:
            await choose_workspace(current_page, "更多", "More")
            try:
                await click_candidates(
                    current_page,
                    ("知识库", "Knowledge Center", "Knowledge"),
                    context="knowledge center",
                    allow_text=False,
                )
            except RuntimeError:
                # The More page uses a compact card list.  Its visible action is intentionally generic.
                cards = current_page.get_by_role("button", name="查看", exact=True)
                if await cards.count() >= 2:
                    await cards.nth(1).click()
                    await wait_for_streamlit(current_page)
                else:
                    raise

        workflows: tuple[tuple[str, Callable[[Page], Awaitable[None]]], ...] = (
            ("dashboard", dashboard),
            ("member_overview", member_overview),
            ("doctor_review", doctor_review),
            ("timeline", timeline),
            ("knowledge_center", knowledge_center),
        )
        for name, workflow in workflows:
            results[name] = await capture(page, output_dir, name, workflow, demo_url=args.url)

        await context.close()
        await browser.close()
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8501", help="Running local Streamlit URL")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory for PNG files")
    parser.add_argument("--summary-json", type=Path, required=True, help="Path for machine-readable capture results")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    results = asyncio.run(main_async(args))
    args.summary_json.write_text(
        json.dumps({name: asdict(result) for name, result in results.items()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("Screenshot summary")
    labels = {
        "dashboard": "Dashboard",
        "member_overview": "Member overview",
        "doctor_review": "Doctor review",
        "timeline": "Timeline",
        "knowledge_center": "Knowledge center",
    }
    for name, label in labels.items():
        result = results[name]
        detail = result.path if result.path else result.reason
        print(f"{label}: {result.status}" + (f" — {detail}" if detail else ""))

    return 0 if all(results[name].status == "PASS" for name in CORE_SCREENSHOTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
