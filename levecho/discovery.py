"""Discover and validate single-stock daily leveraged ETF candidates."""

from __future__ import annotations

import re
from dataclasses import dataclass
from io import BytesIO
from io import StringIO
from typing import Any, Iterable

import pandas as pd
import pypdf
import requests

from .types import PairConfig, yahoo_symbol


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

SUPPORTED_LEVERAGE = frozenset({-3.0, -2.0, 2.0, 3.0})


@dataclass(frozen=True)
class ETFCandidate:
    ticker: str
    fund_name: str
    reference_symbol: str
    reference_text: str
    leverage: float | None
    issuer: str
    source_url: str
    confidence: str
    single_stock: bool
    reason: str = ""

    def to_mapping(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "fund_name": self.fund_name,
            "reference_symbol": self.reference_symbol,
            "reference_text": self.reference_text,
            "leverage": self.leverage,
            "issuer": self.issuer,
            "source_url": self.source_url,
            "confidence": self.confidence,
            "single_stock": self.single_stock,
            "reason": self.reason,
        }


class DiscoverySourceError(RuntimeError):
    """Raised when an issuer catalog cannot be parsed."""


def _flatten_columns(columns: Iterable[object]) -> list[str]:
    result: list[str] = []
    for column in columns:
        if isinstance(column, tuple):
            result.append(
                " ".join(str(part).strip() for part in column if str(part).lower() != "nan").strip()
            )
        else:
            result.append(str(column).strip())
    return result


def _column_index(columns: list[str], keywords: Iterable[str]) -> int | None:
    lowered = [column.lower() for column in columns]
    for keyword in keywords:
        for index, column in enumerate(lowered):
            if keyword in column:
                return index
    return None


def parse_leverage(value: object) -> float | None:
    text = str(value).strip().upper().replace("−", "-")
    percentage = re.search(r"(?P<number>[+-]?\d+(?:\.\d+)?)\s*%", text)
    if percentage:
        return float(percentage.group("number")) / 100.0
    multiple = re.search(r"(?P<number>[+-]?\d+(?:\.\d+)?)\s*X", text)
    if multiple:
        return float(multiple.group("number"))
    return None


def _clean_ticker(value: object) -> str:
    match = re.search(r"\b([A-Z][A-Z0-9.\-]{0,9})\b", str(value).upper())
    return match.group(1) if match else ""


def _extract_reference_symbol(text: str) -> str:
    upper = text.upper()
    exchange_match = re.search(
        r"\b(?:NASDAQ|NYSE|NYSE ARCA|AMEX|CBOE|BZX|OTC)\s*:\s*([A-Z][A-Z0-9.\-]{0,9})\b",
        upper,
    )
    if exchange_match:
        return exchange_match.group(1)
    parenthetical = re.findall(r"\(([A-Z][A-Z0-9.\-]{0,9})\)", upper)
    for token in parenthetical:
        if token not in {"ETF", "ETP", "USD", "NAV", "ADR"}:
            return token
    return ""


def _is_single_stock(reference_text: str, fund_name: str, reference_symbol: str) -> bool:
    text = f"{reference_text} {fund_name}".upper()
    disallowed = ("INDEX", "SECTOR", "TOP 5", "BASKET", "BITCOIN", "CRYPTO", "FUTURE", "COMMODITY")
    if any(term in text for term in disallowed):
        return False
    return bool(reference_symbol) and any(
        term in text for term in ("COMMON SHARE", "COMMON STOCK", "CORPORATION", "INC.")
    )


def parse_issuer_tables(html: str, issuer: str, source_url: str) -> list[ETFCandidate]:
    try:
        tables = pd.read_html(StringIO(html))
    except (ValueError, ImportError) as exc:
        raise DiscoverySourceError(f"unable to read issuer tables from {source_url}: {exc}") from exc

    for table in tables:
        table = table.copy()
        table.columns = _flatten_columns(table.columns)
        ticker_index = _column_index(table.columns, ("ticker", "symbol"))
        leverage_index = _column_index(table.columns, ("daily target", "target", "leverage", "multiple"))
        reference_index = _column_index(table.columns, ("index/benchmark", "benchmark", "underlying", "reference"))
        name_index = _column_index(table.columns, ("fund name", "etf", "name"))
        if ticker_index is None or leverage_index is None:
            continue
        if reference_index is None:
            reference_index = name_index
        if name_index is None:
            name_index = ticker_index

        candidates: list[ETFCandidate] = []
        for _, row in table.iterrows():
            ticker = _clean_ticker(row.iloc[ticker_index])
            fund_name = str(row.iloc[name_index]).strip()
            reference_text = "" if reference_index is None else str(row.iloc[reference_index]).strip()
            if not ticker or not fund_name:
                continue
            leverage = parse_leverage(row.iloc[leverage_index])
            reference_symbol = _extract_reference_symbol(reference_text)
            if not reference_symbol:
                reference_symbol = _extract_reference_symbol(fund_name)
            explicit_reference = bool(_extract_reference_symbol(reference_text))
            single_stock = _is_single_stock(reference_text, fund_name, reference_symbol)
            confidence = "high" if explicit_reference and leverage is not None and single_stock else "low"
            reason = "" if confidence == "high" else "reference asset, target, or single-stock status needs review"
            candidates.append(
                ETFCandidate(
                    ticker=ticker,
                    fund_name=fund_name,
                    reference_symbol=reference_symbol,
                    reference_text=reference_text,
                    leverage=leverage,
                    issuer=issuer,
                    source_url=source_url,
                    confidence=confidence,
                    single_stock=single_stock,
                    reason=reason,
                )
            )
        if candidates:
            return candidates
    raise DiscoverySourceError(f"no ETF table found at {source_url}")


def parse_issuer_pdf_text(text: str, issuer: str, source_url: str) -> list[ETFCandidate]:
    """Parse the compact issuer PDF layout used by single-stock ETF lists."""

    current_reference = ""
    candidates: list[ETFCandidate] = []
    for raw_line in text.splitlines():
        line = " ".join(raw_line.split())
        if not line:
            continue
        reference_symbol = _extract_reference_symbol(line)
        if reference_symbol and "|" not in line:
            current_reference = reference_symbol
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 3:
            continue
        ticker = _clean_ticker(parts[0])
        fund_name = parts[1]
        leverage = parse_leverage(parts[2])
        if not ticker or not fund_name or leverage is None or not current_reference:
            continue
        candidates.append(
            ETFCandidate(
                ticker=ticker,
                fund_name=fund_name,
                reference_symbol=current_reference,
                reference_text=f"common shares ({current_reference})",
                leverage=leverage,
                issuer=issuer,
                source_url=source_url,
                confidence="high",
                single_stock=True,
            )
        )
    if not candidates:
        raise DiscoverySourceError(f"no single-stock ETF rows found in {source_url}")
    return candidates


def parse_issuer_pdf(content: bytes, issuer: str, source_url: str) -> list[ETFCandidate]:
    try:
        reader = pypdf.PdfReader(BytesIO(content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:  # noqa: BLE001 - report source parsing failure to the caller
        raise DiscoverySourceError(f"unable to extract PDF text from {source_url}: {exc}") from exc
    return parse_issuer_pdf_text(text, issuer, source_url)


def discover_candidates(
    source_configs: Iterable[dict[str, Any]],
    session: requests.Session | None = None,
) -> tuple[list[ETFCandidate], list[str]]:
    client = session or requests.Session()
    candidates: dict[str, ETFCandidate] = {}
    errors: list[str] = []
    for source in source_configs:
        issuer = str(source["issuer"])
        for url in source.get("urls", []):
            try:
                response = client.get(
                    url,
                    timeout=30,
                    headers=DEFAULT_HEADERS,
                )
                response.raise_for_status()
                if str(url).lower().split("?")[0].endswith(".pdf"):
                    parsed = parse_issuer_pdf(response.content, issuer, url)
                else:
                    parsed = parse_issuer_tables(response.text, issuer, url)
                for candidate in parsed:
                    current = candidates.get(candidate.ticker)
                    if current is None or (candidate.confidence == "high" and current.confidence != "high"):
                        candidates[candidate.ticker] = candidate
                break
            except Exception as exc:  # noqa: BLE001 - try next official source URL
                errors.append(f"{issuer} {url}: {type(exc).__name__}: {exc}")
    return sorted(candidates.values(), key=lambda item: item.ticker), errors


def _pair_id(underlying: str, etf: str) -> str:
    return f"{underlying.lower().replace('.', '-')}-{etf.lower()}"


def match_candidates(
    candidates: Iterable[ETFCandidate],
    universe: Iterable[dict[str, Any]],
) -> tuple[list[PairConfig], list[dict[str, Any]]]:
    universe_map = {
        yahoo_symbol(str(item["display_symbol"])): item
        for item in universe
        if item.get("active", True)
    }
    approved: list[PairConfig] = []
    pending: list[dict[str, Any]] = []
    for candidate in candidates:
        normalized_reference = yahoo_symbol(candidate.reference_symbol) if candidate.reference_symbol else ""
        stock = universe_map.get(normalized_reference)
        base_record = candidate.to_mapping()
        if stock is None:
            continue
        if candidate.leverage not in SUPPORTED_LEVERAGE:
            base_record["status"] = "pending_review"
            base_record["reason"] = "unsupported leverage; v1 supports signed 2x and 3x only"
            pending.append(base_record)
            continue
        if not candidate.single_stock:
            base_record["status"] = "pending_review"
            base_record["reason"] = "not confirmed as a single-stock daily product"
            pending.append(base_record)
            continue
        if candidate.confidence != "high":
            base_record["status"] = "pending_review"
            pending.append(base_record)
            continue
        approved.append(
            PairConfig(
                pair_id=_pair_id(stock["display_symbol"], candidate.ticker),
                underlying_symbol=stock["display_symbol"],
                etf_symbol=candidate.ticker,
                leverage=float(candidate.leverage),
                issuer=candidate.issuer,
                reference_asset=candidate.reference_symbol,
                source_url=candidate.source_url,
                confidence=candidate.confidence,
                status="active",
            )
        )
    return approved, pending


def merge_approved_pairs(
    existing: Iterable[dict[str, Any]],
    discovered: Iterable[PairConfig],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Add high-confidence new products while keeping changed products pending."""

    current = {str(item.get("etf_symbol")): dict(item) for item in existing}
    pending: list[dict[str, Any]] = []
    for pair in discovered:
        mapping = pair.to_mapping()
        old = current.get(pair.etf_symbol)
        if old is None:
            current[pair.etf_symbol] = mapping
            continue
        comparable = (old.get("underlying_symbol"), float(old.get("leverage", 0)))
        proposed = (pair.underlying_symbol, float(pair.leverage))
        if comparable != proposed:
            pending.append(
                {
                    "ticker": pair.etf_symbol,
                    "status": "pending_review",
                    "reason": "reference asset or leverage changed",
                    "existing": old,
                    "proposed": mapping,
                }
            )
    return sorted(current.values(), key=lambda item: str(item["pair_id"])), pending
