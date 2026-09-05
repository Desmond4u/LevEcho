"""Fetch current index constituents and produce a reviewable diff."""

from __future__ import annotations

import argparse
from pathlib import Path

from levecho.io import load_json, utc_now_iso, write_json
from levecho.universe import (
    constituent_diff,
    fetch_index_constituents,
    merge_constituents,
    render_constituent_diff,
)


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", default=str(ROOT / "config/index_sources.json"))
    parser.add_argument("--approved", default=str(ROOT / "data/approved_universe.json"))
    parser.add_argument("--candidate", default=str(ROOT / "data/universe_candidate.json"))
    parser.add_argument("--report", default=str(ROOT / "reports/universe_diff.md"))
    parser.add_argument(
        "--write-approved-proposal",
        action="store_true",
        help="also write the proposed approved file; intended for a review PR",
    )
    args = parser.parse_args()

    source_configs = load_json(args.sources, default={})
    source_asof = utc_now_iso()[:10]
    groups = {}
    source_urls = {}
    for index_id, config in source_configs.items():
        constituents, source_url = fetch_index_constituents(index_id, config["urls"], source_asof)
        groups[index_id] = constituents
        source_urls[index_id] = source_url

    merged = merge_constituents(groups)
    approved = load_json(args.approved, default={})
    old = approved.get("constituents", [])
    diff = constituent_diff(old, merged)
    candidate = {
        "model_version": "1.0",
        "source_status": "success",
        "source_asof": source_asof,
        "updated_at": utc_now_iso(),
        "source_urls": source_urls,
        "constituents": merged,
        "diff": diff,
    }
    write_json(args.candidate, candidate)
    if args.write_approved_proposal:
        write_json(
            args.approved,
            {
                "model_version": "1.0",
                "source_status": "approved",
                "source_asof": source_asof,
                "updated_at": utc_now_iso(),
                "source_urls": source_urls,
                "constituents": merged,
                "diff_summary": {key: len(value) for key, value in diff.items()},
            },
        )
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_constituent_diff(diff, source_asof), encoding="utf-8")
    print(
        f"candidate={len(merged)} added={len(diff['added'])} "
        f"removed={len(diff['removed'])} changed={len(diff['changed'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
