"""Index constituent retrieval and approved-universe diffing."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from io import StringIO
from typing import Any, Iterable

import pandas as pd
import requests

from .types import yahoo_symbol


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


class UniverseSourceError(RuntimeError):
    """Raised when an official constituent source cannot be parsed."""


@dataclass(frozen=True)
class Constituent:
    display_symbol: str
    provider_symbol: str
    company_name: str
    indices: tuple[str, ...]
    source_asof: str
    source_url: str

    def to_mapping(self) -> dict[str, Any]:
        return {
            "display_symbol": self.display_symbol,
            "provider_symbol": self.provider_symbol,
            "company_name": self.company_name,
            "indices": list(self.indices),
            "source_asof": self.source_asof,
            "source_url": self.source_url,
            "active": True,
        }


def _flatten_columns(columns: Iterable[object]) -> list[str]:
    flattened: list[str] = []
    for column in columns:
        if isinstance(column, tuple):
            pieces = [str(piece).strip() for piece in column if str(piece).strip().lower() != "nan"]
            flattened.append(" ".join(pieces))
        else:
            flattened.append(str(column).strip())
    return flattened


def _column_index(columns: Iterable[str], keywords: Iterable[str]) -> int | None:
    lowered = [column.lower() for column in columns]
    for keyword in keywords:
        for index, column in enumerate(lowered):
            if keyword in column:
                return index
    return None


def _clean_symbol(value: object) -> str:
    text = str(value).strip().upper().replace("−", "-")
    text = re.sub(r"\s+", "", text)
    return text


def _clean_name(value: object) -> str:
    text = re.sub(r"\s+", " ", str(value).strip())
    return "" if text.lower() == "nan" else text


def parse_constituent_tables(html: str, index_id: str, source_url: str, source_asof: str) -> list[Constituent]:
    try:
        tables = pd.read_html(StringIO(html))
    except (ValueError, ImportError) as exc:
        raise UniverseSourceError(f"unable to read tables from {source_url}: {exc}") from exc

    for table in tables:
        table = table.copy()
        table.columns = _flatten_columns(table.columns)
        symbol_index = _column_index(table.columns, ("symbol", "ticker"))
        name_index = _column_index(table.columns, ("constituent", "company", "security", "name"))
        if symbol_index is None or name_index is None:
            continue

        rows: list[Constituent] = []
        for _, row in table.iterrows():
            symbol = _clean_symbol(row.iloc[symbol_index])
            name = _clean_name(row.iloc[name_index])
            if not symbol or not name or symbol.lower() == "nan":
                continue
            if not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-]{0,9}", symbol):
                continue
            rows.append(
                Constituent(
                    display_symbol=symbol,
                    provider_symbol=yahoo_symbol(symbol),
                    company_name=name,
                    indices=(index_id,),
                    source_asof=source_asof,
                    source_url=source_url,
                )
            )
        if rows:
            return rows
    raise UniverseSourceError(f"no constituent table found at {source_url}")


def _jsonld_item_lists(value: object) -> Iterable[list[dict[str, Any]]]:
    if isinstance(value, dict):
        elements = value.get("itemListElement")
        if isinstance(elements, list):
            yield [item for item in elements if isinstance(item, dict)]
        for child in value.values():
            yield from _jsonld_item_lists(child)
    elif isinstance(value, list):
        for child in value:
            yield from _jsonld_item_lists(child)


def parse_constituent_jsonld(html: str, index_id: str, source_url: str, source_asof: str) -> list[Constituent]:
    scripts = re.findall(
        r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    for script in scripts:
        try:
            payload = json.loads(script.strip())
        except json.JSONDecodeError:
            continue
        for elements in _jsonld_item_lists(payload):
            rows: list[Constituent] = []
            for item in elements:
                symbol = _clean_symbol(item.get("description", ""))
                name = _clean_name(item.get("name", ""))
                if not symbol or not name:
                    continue
                if not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-]{0,9}", symbol):
                    continue
                rows.append(
                    Constituent(
                        display_symbol=symbol,
                        provider_symbol=yahoo_symbol(symbol),
                        company_name=name,
                        indices=(index_id,),
                        source_asof=source_asof,
                        source_url=source_url,
                    )
                )
            if rows:
                return rows
    raise UniverseSourceError(f"no constituent JSON-LD found at {source_url}")


def parse_constituent_content(html: str, index_id: str, source_url: str, source_asof: str) -> list[Constituent]:
    try:
        return parse_constituent_tables(html, index_id, source_url, source_asof)
    except UniverseSourceError as table_error:
        try:
            return parse_constituent_jsonld(html, index_id, source_url, source_asof)
        except UniverseSourceError as json_error:
            raise UniverseSourceError(f"{table_error}; {json_error}") from json_error


def fetch_index_constituents(
    index_id: str,
    urls: Iterable[str],
    source_asof: str,
    session: requests.Session | None = None,
) -> tuple[list[Constituent], str]:
    client = session or requests.Session()
    errors: list[str] = []
    for url in urls:
        try:
            response = client.get(
                url,
                timeout=30,
                headers=DEFAULT_HEADERS,
            )
            response.raise_for_status()
            constituents = parse_constituent_content(response.text, index_id, url, source_asof)
            return constituents, url
        except Exception as exc:  # noqa: BLE001 - try the next official URL
            errors.append(f"{url}: {type(exc).__name__}: {exc}")
    raise UniverseSourceError("; ".join(errors))


def merge_constituents(groups: dict[str, Iterable[Constituent]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for index_id, constituents in groups.items():
        for item in constituents:
            key = item.display_symbol
            current = merged.setdefault(
                key,
                {
                    "display_symbol": item.display_symbol,
                    "provider_symbol": item.provider_symbol,
                    "company_name": item.company_name,
                    "indices": set(),
                    "source_asof": item.source_asof,
                    "source_urls": set(),
                    "active": True,
                },
            )
            current["indices"].add(index_id)
            current["source_urls"].add(item.source_url)
            if len(item.company_name) > len(current["company_name"]):
                current["company_name"] = item.company_name
            current["source_asof"] = max(current["source_asof"], item.source_asof)

    result: list[dict[str, Any]] = []
    for item in merged.values():
        item["indices"] = sorted(item["indices"])
        item["source_urls"] = sorted(item["source_urls"])
        result.append(item)
    return sorted(result, key=lambda value: value["display_symbol"])


def constituent_diff(old: Iterable[dict[str, Any]], new: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    old_map = {str(item["display_symbol"]): item for item in old}
    new_map = {str(item["display_symbol"]): item for item in new}
    added = [new_map[key] for key in sorted(new_map.keys() - old_map.keys())]
    removed = [old_map[key] for key in sorted(old_map.keys() - new_map.keys())]
    changed = [
        {"before": old_map[key], "after": new_map[key]}
        for key in sorted(old_map.keys() & new_map.keys())
        if {
            "company_name": old_map[key].get("company_name"),
            "indices": old_map[key].get("indices"),
            "provider_symbol": old_map[key].get("provider_symbol"),
            "source_urls": old_map[key].get("source_urls"),
        }
        != {
            "company_name": new_map[key].get("company_name"),
            "indices": new_map[key].get("indices"),
            "provider_symbol": new_map[key].get("provider_symbol"),
            "source_urls": new_map[key].get("source_urls"),
        }
    ]
    return {"added": added, "removed": removed, "changed": changed}


def render_constituent_diff(diff: dict[str, list[dict[str, Any]]], source_asof: str) -> str:
    lines = ["# Index constituent change report", "", f"Source as of: `{source_asof}`", ""]
    for label, title in (("added", "Added"), ("removed", "Removed"), ("changed", "Changed")):
        entries = diff[label]
        lines.extend([f"## {title} ({len(entries)})", ""])
        if not entries:
            lines.extend(["None", ""])
            continue
        for entry in entries:
            if label == "changed":
                lines.append(f"- `{entry['after']['display_symbol']}`: metadata changed")
            else:
                lines.append(f"- `{entry['display_symbol']}` — {entry.get('company_name', '')}")
        lines.append("")
    return "\n".join(lines)
