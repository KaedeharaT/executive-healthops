"""Read-only real Chromium smoke check for managed service URLs."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", action="append", required=True)
    parser.add_argument("--output", default=".runtime/background-qa/browser")
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    results = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for index, url in enumerate(args.url):
                page = browser.new_page(viewport={"width": 1440, "height": 900})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(url, wait_until="networkidle")
                page.locator('[data-testid="stAppViewContainer"]').wait_for(timeout=90000)
                page.wait_for_timeout(1000)
                page.locator('[data-testid="stStatusWidget"]').wait_for(state="hidden", timeout=90000)
                entry = page.get_by_role("button", name="进入 HealthOps 运营后台", exact=True)
                if entry.count():
                    entry.click()
                page.get_by_role("heading", name="今日工作", exact=True).wait_for(timeout=90000)
                page.locator('[data-testid="stStatusWidget"]').wait_for(state="hidden", timeout=90000)
                assert not page.locator('[data-testid="stException"]').count(), page.locator("body").inner_text()
                assert not errors, errors
                screenshot = output / f"service-{index + 1}.png"
                page.screenshot(path=str(screenshot))
                results.append(dict(url=url, browser=browser.version, heading="今日工作", errors=errors,
                                    screenshot=str(screenshot)))
                page.close()
        finally:
            browser.close()
    (output / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
