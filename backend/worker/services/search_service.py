from __future__ import annotations

import csv
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

import requests

from ..config import Settings
from ..utils.retry import retry_call


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", (text or "").strip().lower())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


class SearchService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session = requests.Session()

    def close(self) -> None:
        self.session.close()

    def _supabase_headers(self) -> dict[str, str]:
        return {
            "apikey": self.settings.supabase_service_role_key,
            "Authorization": f"Bearer {self.settings.supabase_service_role_key}",
            "Content-Type": "application/json",
            "Accept-Profile": self.settings.supabase_schema,
        }

    def _load_catalog_file(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []

        if path.suffix.lower() == ".json":
            with path.open("r", encoding="utf-8-sig") as handle:
                payload = json.load(handle)
            return [row for row in payload if isinstance(row, dict)] if isinstance(payload, list) else []

        if path.suffix.lower() == ".csv":
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                return [dict(row) for row in csv.DictReader(handle)]

        return []

    def load_catalog(self) -> list[dict[str, Any]]:
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        json_rows = self._load_catalog_file(self.settings.catalog_json)
        if json_rows:
            return json_rows
        return self._load_catalog_file(self.settings.catalog_csv)

    def search_supplier_snapshots(self, item_name: str, limit: int = 3) -> list[dict[str, Any]]:
        if not self.settings.supabase_url or not self.settings.supabase_service_role_key:
            return []

        normalized_name = normalize_text(item_name)
        if not normalized_name:
            return []

        try:
            response = self.session.get(
                f"{self.settings.supabase_url}/rest/v1/supplier_price_snapshots",
                params={
                    "select": "*",
                    "normalized_item_name": f"eq.{normalized_name}",
                    "order": "captured_at.desc",
                    "limit": max(limit * 3, 8),
                },
                headers=self._supabase_headers(),
                timeout=self.settings.request_timeout_seconds,
            )
            response.raise_for_status()
            rows = response.json()
            if not isinstance(rows, list):
                return []
        except Exception:
            return []

        offers: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            offers.append(
                {
                    "title": str(row.get("title") or row.get("item_name") or "").strip(),
                    "price": to_float(row.get("unit_price") or row.get("price")),
                    "supplier": str(row.get("supplier_name") or "Fornecedor").strip(),
                    "link": str(row.get("result_url") or "").strip(),
                    "source": str(row.get("provider") or row.get("source_name") or "snapshot").strip(),
                    "delivery_days": row.get("delivery_days"),
                    "delivery_label": str(row.get("delivery_label") or "").strip() or None,
                    "captured_at": row.get("captured_at"),
                }
            )
        return self._dedupe_offers(offers, limit)

    def _catalog_score(self, item_name: str, catalog_name: str) -> int:
        item_norm = normalize_text(item_name)
        catalog_norm = normalize_text(catalog_name)
        if not item_norm or not catalog_norm:
            return 0

        score = 0
        if item_norm in catalog_norm or catalog_norm in item_norm:
            score += 3
        item_tokens = {tok for tok in re.findall(r"[a-z0-9]+", item_norm) if len(tok) > 2}
        catalog_tokens = {tok for tok in re.findall(r"[a-z0-9]+", catalog_norm) if len(tok) > 2}
        score += len(item_tokens.intersection(catalog_tokens))
        return score

    def search_catalog(self, item_name: str, limit: int = 3) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        for row in self.load_catalog():
            catalog_name = str(row.get("name") or row.get("titulo") or "").strip()
            if not catalog_name:
                continue
            score = self._catalog_score(item_name, catalog_name)
            if score <= 0:
                continue
            candidates.append(
                {
                    "title": catalog_name,
                    "price": to_float(row.get("price") or row.get("preco")),
                    "supplier": str(row.get("supplier") or row.get("fornecedor") or "Fornecedor local").strip(),
                    "link": str(row.get("link") or "").strip(),
                    "source": "catalog",
                    "score": score,
                }
            )

        candidates.sort(key=lambda item: (-item["score"], item["price"] if item["price"] is not None else float("inf")))
        return candidates[:limit]

    def _dedupe_offers(self, offers: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
        deduped: list[dict[str, Any]] = []
        seen: set[tuple[str, str, float | None]] = set()
        for offer in offers:
            key = (
                normalize_text(str(offer.get("title") or "")),
                normalize_text(str(offer.get("supplier") or "")),
                to_float(offer.get("price")),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(offer)
        deduped.sort(key=lambda item: item["price"] if item["price"] is not None else float("inf"))
        return deduped[:limit]

    def search_mercado_livre(self, query: str, limit: int = 3) -> list[dict[str, Any]]:
        url = f"https://api.mercadolibre.com/sites/{self.settings.mercado_livre_site}/search"

        def do_request() -> list[dict[str, Any]]:
            response = self.session.get(
                url,
                params={"q": query, "limit": max(limit * 2, 8)},
                timeout=self.settings.request_timeout_seconds,
            )
            response.raise_for_status()
            results = response.json().get("results", [])
            offers = []
            for item in results:
                if not isinstance(item, dict):
                    continue
                offers.append(
                    {
                        "title": str(item.get("title") or "").strip(),
                        "price": to_float(item.get("price")),
                        "supplier": "Mercado Livre",
                        "link": str(item.get("permalink") or "").strip(),
                        "source": "mercado_livre",
                    }
                )
            offers.sort(key=lambda item: item["price"] if item["price"] is not None else float("inf"))
            return offers[:limit]

        return retry_call(
            do_request,
            attempts=self.settings.retry_attempts,
            backoff_seconds=self.settings.retry_backoff_seconds,
            max_backoff_seconds=max(self.settings.retry_backoff_seconds, self.settings.request_timeout_seconds),
        )

    def suggest_search_term(self, item_name: str) -> str:
        normalized = re.sub(r"\([^\)]*\)", "", item_name or "")
        normalized = re.sub(r"\b\d+[\.,]?\d*\s*(kg|g|l|m2|m3|m|mm|cm|saco|sacos|un|barras?)\b", "", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"\s+", " ", normalized).strip(" -")
        words = normalized.split()
        if len(words) >= 3:
            return " ".join(words[:3])
        return normalized or item_name

    def quote_item(self, item_name: str) -> tuple[list[dict[str, Any]], str]:
        offers = self.search_supplier_snapshots(item_name, limit=5)
        sources = {"snapshot"} if offers else set()

        catalog_offers = self.search_catalog(item_name, limit=5)
        if catalog_offers:
            offers.extend(catalog_offers)
            sources.add("catalog")

        suggestion = self.suggest_search_term(item_name)
        try:
            mercado_offers = self.search_mercado_livre(suggestion or item_name, limit=5)
            if mercado_offers:
                offers.extend(mercado_offers)
                sources.add("mercado_livre")
        except Exception:
            pass

        deduped = self._dedupe_offers(offers, limit=5)
        if deduped:
            return deduped, "+".join(sorted(sources))
        return [], "unavailable"
