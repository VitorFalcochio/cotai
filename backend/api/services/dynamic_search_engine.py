from __future__ import annotations

import asyncio
import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote_plus, urljoin

from playwright.async_api import Browser, ElementHandle, Page, async_playwright

from ...worker.config import Settings
from ...worker.utils.logger import log_event


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def parse_price(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").strip()
    if not text:
        return None
    match = re.search(r"(\d{1,3}(?:\.\d{3})*,\d{2}|\d+(?:[.,]\d{2})?)", text)
    if not match:
        return None
    cleaned = match.group(1).replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


@dataclass(frozen=True)
class ProviderConfig:
    key: str
    name: str
    search_url_templates: tuple[str, ...]
    card_selectors: tuple[str, ...]
    title_selectors: tuple[str, ...]
    price_selectors: tuple[str, ...]
    link_selectors: tuple[str, ...]


class SearchEngine:
    """Async Playwright engine for live material searches.

    Provider selectors are resilient by design: each field accepts multiple CSS
    candidates and failures are swallowed so one broken selector does not take
    the whole search down.
    """

    PROVIDERS: tuple[ProviderConfig, ...] = (
        ProviderConfig(
            key="leroy_merlin",
            name="Leroy Merlin",
            search_url_templates=(
                "https://www.leroymerlin.com.br/busca?q={query}",
                "https://www.leroymerlin.com.br/search?term={query}",
            ),
            card_selectors=("[data-testid='product-card']", ".new-product-thumb", ".product-item", ".product-card"),
            title_selectors=(
                "[data-testid='product-title']",
                ".css-1eaoahv-ellipsis",
                ".product-item__name",
                ".product-card__name",
                "h2",
                "h3",
                "a[title]",
            ),
            price_selectors=(
                "[data-testid='price']",
                ".css-gt77zv-price-tag",
                ".price",
                ".product-price",
                ".sales-price",
                "[class*='price']",
            ),
            link_selectors=("a[href]",),
        ),
        ProviderConfig(
            key="obramax",
            name="Obramax",
            search_url_templates=("https://www.obramax.com.br/search?text={query}",),
            card_selectors=("[data-testid='product-card']", ".vtex-search-result-3-x-galleryItem", ".product-card", "article"),
            title_selectors=("[data-testid='product-title']", ".vtex-product-summary-2-x-productBrand", ".product-card__name", "h2", "h3", "a[title]"),
            price_selectors=("[data-testid='price']", ".price", ".sales-price", ".vtex-product-price-1-x-sellingPriceValue", "[class*='price']"),
            link_selectors=("a[href]",),
        ),
        ProviderConfig(
            key="telhanorte",
            name="Telhanorte",
            search_url_templates=("https://www.telhanorte.com.br/busca?q={query}",),
            card_selectors=(
                "div.vtex-product-summary-2-x-container",
                ".vtex-search-result-3-x-galleryItem",
                "[data-testid='product-card']",
                "article",
            ),
            title_selectors=(
                ".vtex-product-summary-2-x-brandName",
                ".vtex-product-summary-2-x-productBrand",
                "[data-testid='product-title']",
                "h2",
                "h3",
                "a[title]",
            ),
            price_selectors=(
                ".vtex-product-summary-2-x-sellingPrice",
                ".vtex-product-price-1-x-sellingPriceValue",
                "[data-testid='price']",
                ".price",
                ".sales-price",
                "[class*='price']",
            ),
            link_selectors=("a[href]",),
        ),
    )

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def search(self, term: str, providers: tuple[str, ...] | None = None) -> list[dict[str, Any]]:
        selected_providers = self._resolve_providers(providers)
        if not selected_providers:
            return []

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=self.settings.scraping_headless)
            try:
                results = await asyncio.gather(
                    *(self._search_provider(browser, provider, term) for provider in selected_providers),
                    return_exceptions=True,
                )
            finally:
                await browser.close()

        offers: list[dict[str, Any]] = []
        for result in results:
            if isinstance(result, Exception):
                continue
            offers.extend(result)
        return offers

    async def _search_provider(self, browser: Browser, provider: ProviderConfig, term: str) -> list[dict[str, Any]]:
        page = await browser.new_page()
        try:
            for search_url in self._candidate_search_urls(provider, term):
                await page.goto(search_url, wait_until="domcontentloaded", timeout=self.settings.scraping_timeout_ms)
                await page.wait_for_timeout(1500)
                offers = await self._extract_provider_offers(page, provider)
                if offers:
                    return offers[: self.settings.scraping_max_offers_per_store]
                json_ld_offers = await self._extract_json_ld_offers(page, provider.name)
                if json_ld_offers:
                    return json_ld_offers[: self.settings.scraping_max_offers_per_store]
            return []
        except Exception as exc:  # noqa: BLE001
            log_event(self.settings, "WARNING", "Provider scraping failed", provider=provider.name, search_term=term, error=str(exc))
            return []
        finally:
            await page.close()

    async def _extract_provider_offers(self, page: Page, provider: ProviderConfig) -> list[dict[str, Any]]:
        cards = await self._query_all(page, provider.card_selectors)
        offers: list[dict[str, Any]] = []
        for card in cards[: self.settings.scraping_max_offers_per_store * 2]:
            title = await self._safe_text(card, provider.title_selectors)
            price_text = await self._safe_text(card, provider.price_selectors)
            link = await self._safe_link(page, card, provider.link_selectors)
            price = parse_price(price_text)
            if not title or price is None:
                continue
            offers.append(
                {
                    "supplier": provider.name,
                    "product_name": title,
                    "price": price,
                    "currency": "BRL",
                    "offer_url": link,
                    "source": provider.name,
                }
            )
        return offers

    async def _extract_json_ld_offers(self, page: Page, provider_name: str) -> list[dict[str, Any]]:
        scripts = await page.locator("script[type='application/ld+json']").all_text_contents()
        offers: list[dict[str, Any]] = []
        for raw in scripts:
            for candidate in self._json_candidates(raw):
                name = candidate.get("name")
                offer = candidate.get("offers") or {}
                price = parse_price(offer.get("price"))
                link = candidate.get("url") or offer.get("url")
                if not name or price is None:
                    continue
                offers.append(
                    {
                        "supplier": provider_name,
                        "product_name": str(name).strip(),
                        "price": price,
                        "currency": str(offer.get("priceCurrency") or "BRL"),
                        "offer_url": str(link or "").strip() or page.url,
                        "source": provider_name,
                    }
                )
        return offers

    def _json_candidates(self, raw: str) -> list[dict[str, Any]]:
        try:
            payload = json.loads(raw)
        except Exception:
            return []
        if isinstance(payload, dict):
            graph = payload.get("@graph")
            if isinstance(graph, list):
                return [item for item in graph if isinstance(item, dict)]
            return [payload]
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        return []

    def _candidate_search_urls(self, provider: ProviderConfig, term: str) -> list[str]:
        query = quote_plus(term)
        return [template.format(query=query) for template in provider.search_url_templates]

    def _resolve_providers(self, providers: tuple[str, ...] | None) -> tuple[ProviderConfig, ...]:
        if not providers:
            return self.PROVIDERS
        wanted = {normalize_text(item).replace(" ", "_") for item in providers if str(item).strip()}
        selected = []
        for provider in self.PROVIDERS:
            aliases = {
                normalize_text(provider.key).replace(" ", "_"),
                normalize_text(provider.name).replace(" ", "_"),
            }
            if aliases.intersection(wanted):
                selected.append(provider)
        return tuple(selected)

    async def _query_all(self, page: Page, selectors: tuple[str, ...]) -> list[ElementHandle]:
        for selector in selectors:
            try:
                locator = page.locator(selector)
                count = await locator.count()
                if count:
                    return await locator.element_handles()
            except Exception:
                continue
        return []

    async def _safe_text(self, root: ElementHandle, selectors: tuple[str, ...]) -> str | None:
        for selector in selectors:
            try:
                locator = root.locator(selector).first
                if await locator.count():
                    text = await locator.inner_text()
                    if text and text.strip():
                        return re.sub(r"\s+", " ", text).strip()
            except Exception:
                continue
        return None

    async def _safe_link(self, page: Page, root: ElementHandle, selectors: tuple[str, ...]) -> str:
        for selector in selectors:
            try:
                locator = root.locator(selector).first
                if await locator.count():
                    href = await locator.get_attribute("href")
                    if href:
                        return urljoin(page.url, href)
            except Exception:
                continue
        return page.url
