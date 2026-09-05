"""Create a reviewable report for ETF metadata and mapping changes."""

from __future__ import annotations

import argparse
from pathlib import Path

from levecho.discovery import discover_candidates, match_candidates, merge_approved_pairs
from levecho.io import load_json, utc_now_iso, write_json


ROOT = Path(__file__).resolve().parents[1]


def _render_report(
    approved: list[dict],
    pending: list[dict],
    errors: list[str],
    updated_at: str,
) -> str:
    lines = ["# ETF mapping review", "", f"Generated at: `{updated_at}`", ""]
    lines.extend([f"Approved active pairs in proposal: **{len(approved)}**", ""])
    lines.extend([f"Pending records: **{len(pending)}**", ""])
    if errors:
        lines.extend(["## Source errors", ""])
        lines.extend(f"- {error}" for error in errors)
        lines.append("")
    lines.extend(["## Pending changes", ""])
    if not pending:
        lines.append("None")
    else:
        for item in pending:
            ticker = item.get("ticker", "unknown")
            reason = item.get("reason", "review required")
            lines.append(f"- `{ticker}` — {reason}")
    lines.extend(
        [
            "",
            "Review issuer references and leverage before applying any pending mapping to `data/approved_pairs.json`.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--universe", default=str(ROOT / "data/approved_universe.json"))
    parser.add_argument("--approved", default=str(ROOT / "data/approved_pairs.json"))
    parser.add_argument("--proposal", default=str(ROOT / "data/approved_pairs_proposal.json"))
    parser.add_argument("--pending", default=str(ROOT / "data/pending_pairs.json"))
    parser.add_argument("--sources", default=str(ROOT / "config/issuer_sources.json"))
    parser.add_argument("--report", default=str(ROOT / "reports/etf_pair_review.md"))
    args = parser.parse_args()

    universe_payload = load_json(args.universe, default={}) or {}
    existing_payload = load_json(args.approved, default={}) or {}
    existing_pending_payload = load_json(args.pending, default={}) or {}
    source_configs = load_json(args.sources, default=[]) or []
    universe = universe_payload.get("constituents", [])
    existing = existing_payload.get("pairs", [])
    candidates, source_errors = discover_candidates(source_configs)
    discovered, pending = match_candidates(candidates, universe)
    proposed, changed_pending = merge_approved_pairs(existing, discovered)
    pending.extend(changed_pending)
    updated_at = utc_now_iso()

    same_pairs = proposed == existing_payload.get("pairs", [])
    same_pending = pending == existing_pending_payload.get("candidates", [])
    same_errors = source_errors == existing_pending_payload.get("source_errors", [])
    if same_pairs and same_pending and same_errors and Path(args.proposal).exists() and Path(args.report).exists():
        print(f"No ETF mapping changes detected (approved={len(proposed)} pending={len(pending)}).")
        return 0

    write_json(
        args.proposal,
        {
            "model_version": "1.0",
            "updated_at": updated_at,
            "source_errors": source_errors,
            "pairs": proposed,
        },
    )
    write_json(
        args.pending,
        {
            "model_version": "1.0",
            "updated_at": updated_at,
            "source_errors": source_errors,
            "candidates": pending,
        },
    )
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_render_report(proposed, pending, source_errors, updated_at), encoding="utf-8")
    print(f"proposed={len(proposed)} pending={len(pending)} source_errors={len(source_errors)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
