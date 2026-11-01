"""Browser smoke test for the public registration -> workspace -> logout journey.

Run against a started Compose stack with:
  pip install -r qa/requirements-e2e.txt
  playwright install chromium
  BASE_URL=http://127.0.0.1:8080 pytest -q qa/e2e
"""

from __future__ import annotations

import os
import re
from uuid import uuid4

from playwright.sync_api import Page, expect, sync_playwright

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8080").rstrip("/")


def test_register_open_workspace_and_sign_out() -> None:
    unique = uuid4().hex[:12]
    email = f"phase12-{unique}@example.test"

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page: Page = browser.new_page(viewport={"width": 1440, "height": 960})
        try:
            page.goto(f"{BASE_URL}/register", wait_until="networkidle")
            expect(page.get_by_role("heading", name="Create your workspace")).to_be_visible()
            page.get_by_label("Full name").fill("Phase Twelve Test Owner")
            page.get_by_label("Work email").fill(email)
            page.get_by_label("Organization name").fill(f"Phase Twelve Workspace {unique}")
            page.get_by_label("Password").fill("phase-twelve-test-password-2026")
            page.get_by_role("button", name="Create account and workspace").click()

            expect(page).to_have_url(re.compile(r".*/app/?$"), timeout=20_000)
            expect(page.get_by_role("heading", name="Dashboard")).to_be_visible(timeout=20_000)
            navigation = page.get_by_role("navigation", name="Main navigation")
            expect(navigation.get_by_role("link", name="Import orders")).to_be_visible()
            expect(navigation.get_by_role("link", name="Export orders")).to_be_visible()
            expect(navigation.get_by_role("link", name="Reports")).to_be_visible()

            page.get_by_role("button", name="Sign out").click()
            expect(page).to_have_url(re.compile(r".*/login$"), timeout=10_000)
            expect(page.get_by_role("heading", name="Welcome back")).to_be_visible()
        finally:
            browser.close()
