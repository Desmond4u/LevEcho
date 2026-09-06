"""Discover and validate single-stock daily leveraged ETF candidates."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from io import BytesIO
from io import StringIO
from typing import Any, Iterable

import pandas as pd
import pypdf
import requests
from bs4 import BeautifulSoup

from .types import PairConfig, yahoo_symbol


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

SUPPORTED_LEVERAGE = frozenset({-3.0, -2.0, -1.0, 1.0, 2.0, 3.0})

_REFERENCE_NAME_ALIASES = {
    "ALPHABET": "GOOG",
    "APPLE": "AAPL",
    "COINBASE": "COIN",
    "CIRCLE": "CRCL",
    "GOOGLE": "GOOG",
    "MICROSOFT": "MSFT",
    "MICROSTRATEGY": "MSTR",
    "NVIDIA": "NVDA",
    "NETFLIX": "NFLX",
    "ROBINHOOD": "HOOD",
    "SANDISK": "SNDK",
    "SPACEX": "SPCX",
    "STRATEGY": "MSTR",
    "SUPER MICRO": "SMCI",
    "SUPER MICRO COMPUTER": "SMCI",
    "TESLA": "TSLA",
}


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


def _fetch_source(client: requests.Session, url: str) -> tuple[bytes, str]:
    """Fetch a public catalog, using curl when Python TLS cannot negotiate it."""

    try:
        response = client.get(url, timeout=30, headers=DEFAULT_HEADERS)
        response.raise_for_status()
        return response.content, response.text
    except Exception as request_error:  # noqa: BLE001 - try the transport fallback
        try:
            result = subprocess.run(
                [
                    "curl",
                    "--fail",
                    "--silent",
                    "--show-error",
                    "--location",
                    "--max-time",
                    "30",
                    "--user-agent",
                    DEFAULT_HEADERS["User-Agent"],
                    url,
                ],
                check=True,
                capture_output=True,
                timeout=40,
            )
        except Exception as curl_error:  # noqa: BLE001 - report both transport failures
            raise DiscoverySourceError(
                f"requests failed ({type(request_error).__name__}: {request_error}); "
                f"curl failed ({type(curl_error).__name__}: {curl_error})"
            ) from request_error
        content = result.stdout
        return content, content.decode("utf-8", errors="replace")


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
    numeric = re.fullmatch(r"[+-]?\d+(?:\.\d+)?", text)
    if numeric:
        return float(numeric.group(0))
    return None


def _clean_ticker(value: object) -> str:
    match = re.search(r"\b([A-Z][A-Z0-9.\-]{0,9})\b", str(value).upper())
    return match.group(1) if match else ""


def _extract_reference_symbol(text: str) -> str:
    upper = text.upper().strip()
    direct = re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,9}", upper)
    if direct and direct.group(0) not in {"ETF", "ETP", "USD", "NAV", "ADR"}:
        return direct.group(0)
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


def _extract_directional_reference_symbol(text: str) -> str:
    """Extract the asset named after Long/Short/Inverse in a fund name."""

    upper = " ".join(text.upper().split())
    match = re.search(
        r"\b(?:LONG|SHORT|INVERSE|BEAR|BULL)\s+(.+?)(?:\s+DAILY\b|\s+ETF\b|\s+\()",
        upper,
    )
    if not match:
        return ""
    target = match.group(1).strip(" -")
    if target in _REFERENCE_NAME_ALIASES:
        return _REFERENCE_NAME_ALIASES[target]
    return _extract_reference_symbol(target)


def _signed_leverage(value: object, *contexts: object) -> float | None:
    leverage = parse_leverage(value)
    if leverage is None:
        return None
    context = " ".join(str(item).upper() for item in contexts)
    if any(term in context for term in ("SHORT", "INVERSE", "BEAR")):
        return -abs(leverage)
    if any(term in context for term in ("LONG", "BULL")):
        return abs(leverage)
    return leverage


def _issuer_status_reason(text: str) -> str:
    upper = text.upper()
    if any(term in upper for term in ("DELIST", "CLOSING", "CLOSED", "LIQUIDAT", "TERMINAT")):
        return "issuer marks product as delisting, closing, or terminating"
    return ""


def _is_single_stock(reference_text: str, fund_name: str, reference_symbol: str) -> bool:
    text = f"{reference_text} {fund_name}".upper()
    disallowed = ("INDEX", "SECTOR", "TOP 5", "BASKET", "BITCOIN", "CRYPTO", "FUTURE", "COMMODITY")
    if any(term in text for term in disallowed):
        return False
    if not reference_symbol:
        return False
    return (
        reference_text.strip().upper() == reference_symbol.upper()
        or any(term in text for term in ("COMMON SHARE", "COMMON STOCK", "CORPORATION", "INC."))
        or "EXPOSURE TO" in text
        or bool(re.search(r"\([A-Z][A-Z0-9.\-]{0,9}\)", reference_text.upper()))
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
        leverage_index = _column_index(
            table.columns,
            ("daily objective", "daily target", "target", "leverage", "multiple"),
        )
        reference_index = _column_index(table.columns, ("index/benchmark", "benchmark", "underlying", "reference"))
        exposure_index = _column_index(table.columns, ("exposure", "direction"))
        reset_index = _column_index(table.columns, ("reset period", "reset frequency", "frequency"))
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
            if reset_index is not None:
                reset_period = str(row.iloc[reset_index]).strip().upper()
                if reset_period not in {"", "NAN"} and "DAILY" not in reset_period:
                    continue
            exposure = "" if exposure_index is None else str(row.iloc[exposure_index]).strip()
            leverage = _signed_leverage(row.iloc[leverage_index], exposure, fund_name)
            reference_symbol = _extract_reference_symbol(reference_text)
            if not reference_symbol:
                reference_symbol = _extract_reference_symbol(fund_name)
            if not reference_symbol:
                reference_symbol = _extract_directional_reference_symbol(fund_name)
            explicit_reference = bool(_extract_reference_symbol(reference_text))
            single_stock = _is_single_stock(reference_text, fund_name, reference_symbol)
            confidence = "high" if explicit_reference and leverage is not None and single_stock else "low"
            reason = "" if confidence == "high" else "reference asset, target, or single-stock status needs review"
            status_reason = _issuer_status_reason(f"{fund_name} {reference_text}")
            if status_reason:
                confidence = "low"
                reason = status_reason
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


def _card_text(card: Any, selector: str) -> str:
    node = card.select_one(selector)
    return "" if node is None else " ".join(node.get_text(" ", strip=True).split())


def parse_graniteshares_cards(html: str, issuer: str, source_url: str) -> list[ETFCandidate]:
    """Parse the data attributes used by GraniteShares' leveraged ETF catalog."""

    soup = BeautifulSoup(html, "html.parser")
    candidates: list[ETFCandidate] = []
    for ticker_node in soup.select(".etf-table-cell--ticker__symbol"):
        ticker_cell = ticker_node.find_parent("span", class_=re.compile(r"etf-table-cell--ticker"))
        if ticker_cell is None or ticker_cell.get("data-type") != "leveraged":
            continue
        product_id = ticker_cell.get("data-id")
        name_cell = soup.find(
            "span",
            class_=re.compile(r"etf-table-cell--name\b"),
            attrs={"data-id": product_id},
        )
        if name_cell is None:
            continue
        ticker = _clean_ticker(ticker_node.get_text(" ", strip=True))
        title_node = name_cell.select_one(".etf-table-cell--name-title")
        fund_name = "" if title_node is None else " ".join(title_node.get_text(" ", strip=True).split())
        reference_text = _card_text(name_cell, ".etf-table-cell--name-description")
        if not reference_text:
            reference_text = str(ticker_cell.get("data-underlying", "")).strip()
        reference_symbol = _extract_reference_symbol(reference_text)
        if not reference_symbol:
            reference_symbol = _extract_directional_reference_symbol(fund_name)
        leverage = _signed_leverage(ticker_cell.get("data-leverage"), fund_name, reference_text)
        single_stock = _is_single_stock(reference_text, fund_name, reference_symbol)
        status_reason = _issuer_status_reason(f"{fund_name} {reference_text}")
        confidence = "high" if reference_symbol and leverage is not None and single_stock else "low"
        reason = "" if confidence == "high" else "reference asset, target, or single-stock status needs review"
        if status_reason:
            confidence = "low"
            reason = status_reason
        if ticker:
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
    if not candidates:
        raise DiscoverySourceError(f"no GraniteShares leveraged ETF cards found at {source_url}")
    return candidates


def parse_trex_page(html: str, issuer: str, source_url: str) -> list[ETFCandidate]:
    """Parse the T-REX single-stock rows from the REX/Tuttle catalog."""

    soup = BeautifulSoup(html, "html.parser")
    candidates: list[ETFCandidate] = []
    seen: set[str] = set()
    for item in soup.select(".table3_item"):
        columns = item.select(".table3_column")
        if len(columns) < 2:
            continue
        ticker = _clean_ticker(columns[0].get_text(" ", strip=True))
        fund_name = " ".join(columns[1].get_text(" ", strip=True).split())
        upper_name = fund_name.upper()
        if not ticker or ticker in seen or "T-REX" not in upper_name or "DAILY" not in upper_name:
            continue
        seen.add(ticker)
        reference_symbol = _extract_directional_reference_symbol(fund_name)
        reference_text = f"common shares ({reference_symbol})" if reference_symbol else fund_name
        leverage = _signed_leverage(parse_leverage(fund_name), fund_name)
        single_stock = _is_single_stock(reference_text, fund_name, reference_symbol)
        confidence = "high" if reference_symbol and leverage is not None and single_stock else "low"
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
    if not candidates:
        raise DiscoverySourceError(f"no T-REX daily ETF rows found at {source_url}")
    return candidates


def _js_field(block: str, field: str) -> str:
    match = re.search(rf"\b{re.escape(field)}\s*:\s*(['\"])(.*?)\1", block, re.DOTALL)
    return "" if match is None else match.group(2).strip()


def parse_leverage_shares_page(html: str, issuer: str, source_url: str) -> list[ETFCandidate]:
    """Parse Leverage Shares' embedded productsData catalog."""

    soup = BeautifulSoup(html, "html.parser")
    script = next((node.get_text() for node in soup.find_all("script") if "window.productsData" in node.get_text()), "")
    blocks = re.findall(r"\{\s*name:.*?\}", script, flags=re.DOTALL)
    candidates: list[ETFCandidate] = []
    for block in blocks:
        ticker = _clean_ticker(_js_field(block, "ticker"))
        category = _js_field(block, "category").upper()
        fund_name = _js_field(block, "fund") or _js_field(block, "name")
        reference_text = _js_field(block, "category2")
        if not ticker or category not in {"LEVERAGED", "INVERSE"} or not fund_name:
            continue
        reference_symbol = _extract_reference_symbol(reference_text)
        leverage = _signed_leverage(_js_field(block, "leverage_factor"), fund_name)
        single_stock = _is_single_stock(reference_text, fund_name, reference_symbol)
        confidence = "high" if reference_symbol and leverage is not None and single_stock else "low"
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
    if not candidates:
        raise DiscoverySourceError(f"no Leverage Shares products found at {source_url}")
    return candidates


def parse_defiance_cards(html: str, issuer: str, source_url: str) -> list[ETFCandidate]:
    """Parse Defiance prospectus cards for current daily single-stock products."""

    soup = BeautifulSoup(html, "html.parser")
    candidates: list[ETFCandidate] = []
    for card in soup.select(".pros-card"):
        ticker = _clean_ticker(_card_text(card, ".pros-card-ticker"))
        fund_name = _card_text(card, ".pros-card-name")
        upper_name = fund_name.upper()
        if (
            not ticker
            or not fund_name
            or "DAILY" not in upper_name
            or not any(term in upper_name for term in ("LONG", "SHORT", "INVERSE"))
            or parse_leverage(fund_name) is None
        ):
            continue
        reference_symbol = _extract_directional_reference_symbol(fund_name)
        reference_text = f"common shares ({reference_symbol})" if reference_symbol else fund_name
        leverage = _signed_leverage(parse_leverage(fund_name), fund_name)
        single_stock = _is_single_stock(reference_text, fund_name, reference_symbol)
        confidence = "high" if reference_symbol and leverage is not None and single_stock else "low"
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
    if not candidates:
        raise DiscoverySourceError(f"no Defiance daily leveraged ETF cards found at {source_url}")
    return candidates


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
                content, text = _fetch_source(client, url)
                parser = str(source.get("parser", "table"))
                if str(url).lower().split("?")[0].endswith(".pdf"):
                    parsed = parse_issuer_pdf(content, issuer, url)
                elif parser == "graniteshares_cards":
                    parsed = parse_graniteshares_cards(text, issuer, url)
                elif parser == "trex_page":
                    parsed = parse_trex_page(text, issuer, url)
                elif parser == "leverage_shares_page":
                    parsed = parse_leverage_shares_page(text, issuer, url)
                elif parser == "defiance_cards":
                    parsed = parse_defiance_cards(text, issuer, url)
                else:
                    parsed = parse_issuer_tables(text, issuer, url)
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
            base_record["reason"] = "unsupported leverage; v1 supports signed 1x, 2x, and 3x only"
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
