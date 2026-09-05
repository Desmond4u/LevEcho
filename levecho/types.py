"""Typed records shared by data, discovery, and snapshot layers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


def yahoo_symbol(symbol: str) -> str:
    """Convert a display ticker to Yahoo Finance's common ticker spelling."""

    return str(symbol).strip().upper().replace(".", "-")


@dataclass(frozen=True)
class PriceBar:
    symbol: str
    session: date
    close: float
    dividend: float = 0.0
    split: float = 1.0
    source: str = "unknown"


@dataclass(frozen=True)
class PairConfig:
    pair_id: str
    underlying_symbol: str
    etf_symbol: str
    leverage: float
    issuer: str = ""
    reference_asset: str = ""
    source_url: str = ""
    confidence: str = "high"
    status: str = "active"

    @property
    def underlying_provider_symbol(self) -> str:
        return yahoo_symbol(self.underlying_symbol)

    @property
    def etf_provider_symbol(self) -> str:
        return yahoo_symbol(self.etf_symbol)

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "PairConfig":
        return cls(
            pair_id=str(value.get("pair_id") or value.get("id") or ""),
            underlying_symbol=str(value["underlying_symbol"]),
            etf_symbol=str(value["etf_symbol"]),
            leverage=float(value["leverage"]),
            issuer=str(value.get("issuer", "")),
            reference_asset=str(value.get("reference_asset", "")),
            source_url=str(value.get("source_url", "")),
            confidence=str(value.get("confidence", "high")),
            status=str(value.get("status", "active")),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "pair_id": self.pair_id,
            "underlying_symbol": self.underlying_symbol,
            "etf_symbol": self.etf_symbol,
            "leverage": self.leverage,
            "issuer": self.issuer,
            "reference_asset": self.reference_asset,
            "source_url": self.source_url,
            "confidence": self.confidence,
            "status": self.status,
        }
