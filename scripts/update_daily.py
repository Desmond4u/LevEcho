"""Discover approved pairs, fetch EOD data, and publish an atomic snapshot."""

from __future__ import annotations

import argparse
from pathlib import Path

from levecho.data import FallbackProvider, NasdaqProvider, YFinanceProvider
from levecho.discovery import discover_candidates, match_candidates, merge_approved_pairs
from levecho.io import load_json, utc_now_iso, write_json
from levecho.pipeline import SnapshotBuildError, build_snapshot
from levecho.types import PairConfig


ROOT = Path(__file__).resolve().parents[1]


def _load_pairs(path: str) -> list[PairConfig]:
    payload = load_json(path, default={}) or {}
    return [PairConfig.from_mapping(item) for item in payload.get("pairs", [])]


def _refresh_pairs(universe_path: str, pairs_path: str, pending_path: str, sources_path: str) -> list[PairConfig]:
    universe_payload = load_json(universe_path, default={}) or {}
    universe = universe_payload.get("constituents", [])
    existing_payload = load_json(pairs_path, default={}) or {}
    existing = existing_payload.get("pairs", [])
    source_configs = load_json(sources_path, default=[]) or []

    if not universe or not source_configs:
        return [PairConfig.from_mapping(item) for item in existing if item.get("status", "active") == "active"]

    candidates, discovery_errors = discover_candidates(source_configs)
    discovered, pending = match_candidates(candidates, universe)
    merged, changed_pending = merge_approved_pairs(existing, discovered)
    pending.extend(changed_pending)
    pending_payload = {
        "model_version": "1.0",
        "updated_at": utc_now_iso(),
        "source_errors": discovery_errors,
        "candidates": pending,
    }
    write_json(pending_path, pending_payload)
    write_json(
        pairs_path,
        {
            "model_version": "1.0",
            "updated_at": utc_now_iso(),
            "pairs": merged,
        },
    )
    return [PairConfig.from_mapping(item) for item in merged if item.get("status", "active") == "active"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--universe", default=str(ROOT / "data/approved_universe.json"))
    parser.add_argument("--pairs", default=str(ROOT / "data/approved_pairs.json"))
    parser.add_argument("--pending", default=str(ROOT / "data/pending_pairs.json"))
    parser.add_argument("--sources", default=str(ROOT / "config/issuer_sources.json"))
    parser.add_argument("--output", default=str(ROOT / "data/latest.json"))
    args = parser.parse_args()

    pairs = _refresh_pairs(args.universe, args.pairs, args.pending, args.sources)
    if not pairs:
        print("No active pairs are configured; leaving the existing latest snapshot unchanged.")
        return 0

    symbols = []
    for pair in pairs:
        symbols.extend((pair.underlying_provider_symbol, pair.etf_provider_symbol))
    provider = FallbackProvider(NasdaqProvider(), YFinanceProvider())
    fetched = provider.fetch(symbols, lookback_days=15)
    try:
        snapshot = build_snapshot(pairs, fetched)
    except SnapshotBuildError as exc:
        print(f"Snapshot was not published: {exc}")
        return 2
    write_json(args.output, snapshot)
    print(f"Published {len(snapshot['pairs'])} pairs for {snapshot['as_of_session']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
