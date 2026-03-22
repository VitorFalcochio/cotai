from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Variavel obrigatoria ausente: {name}")
    return value


def main() -> int:
    frontend_url = os.getenv("COTAI_E2E_FRONTEND_URL", "http://127.0.0.1:5500/frontend/pages").rstrip("/")
    email = require_env("COTAI_E2E_EMAIL")
    password = require_env("COTAI_E2E_PASSWORD")
    quote_message = os.getenv(
        "COTAI_E2E_QUOTE_MESSAGE",
        "Preciso de 12 sacos de cimento cp-ii 50kg para entrega amanha em Rio Preto.",
    ).strip()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(f"{frontend_url}/login.html", wait_until="networkidle")
            page.fill("#email", email)
            page.fill("#password", password)
            page.click("#loginSubmit")
            page.wait_for_url("**/dashboard.html", timeout=20000)

            page.goto(f"{frontend_url}/new-request.html", wait_until="networkidle")
            page.fill("#chatComposerInput", quote_message)
            page.click("#chatComposerSubmit")
            page.wait_for_selector("#chatConfirmButton:not(.hidden)", timeout=20000)
            page.click("#chatConfirmButton")

            request_badge = page.locator("#chatRequestCode")
            request_badge.wait_for(timeout=20000)

            deadline = time.time() + 20
            request_code = ""
            while time.time() < deadline:
                candidate = request_badge.inner_text().strip()
                if candidate and candidate != "Aguardando":
                    request_code = candidate
                    break
                time.sleep(0.5)

            if not request_code:
                raise RuntimeError("O fluxo nao exibiu request_code apos a confirmacao.")

            page.goto(f"{frontend_url}/requests.html", wait_until="networkidle")
            page.wait_for_selector("#requestsTableBody tr", timeout=20000)
            table_text = page.locator("#requestsTableBody").inner_text()
            if request_code not in table_text:
                raise RuntimeError(f"O pedido {request_code} nao apareceu na tela de pedidos.")

            print(f"SMOKE E2E OK: {request_code}")
            return 0
        except PlaywrightTimeoutError as exc:
            print(f"SMOKE E2E TIMEOUT: {exc}", file=sys.stderr)
            return 2
        finally:
            browser.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"SMOKE E2E FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
