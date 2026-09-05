from levecho.universe import constituent_diff, merge_constituents, parse_constituent_tables


def test_parse_constituent_table() -> None:
    html = """
    <table>
      <tr><th>Constituent</th><th>Symbol</th><th>Sector</th></tr>
      <tr><td>Apple Inc.</td><td>AAPL</td><td>Technology</td></tr>
      <tr><td>Example Class B</td><td>EXM.B</td><td>Technology</td></tr>
    </table>
    """
    result = parse_constituent_tables(html, "sp500", "https://example.test", "2026-09-05")
    assert [item.display_symbol for item in result] == ["AAPL", "EXM.B"]
    assert result[1].provider_symbol == "EXM-B"


def test_merge_records_overlap_as_both_indices() -> None:
    sp500 = parse_constituent_tables(
        "<table><tr><th>Constituent</th><th>Symbol</th></tr><tr><td>Apple Inc.</td><td>AAPL</td></tr></table>",
        "sp500",
        "sp",
        "2026-09-05",
    )
    ndx = parse_constituent_tables(
        "<table><tr><th>Company</th><th>Ticker</th></tr><tr><td>Apple Inc.</td><td>AAPL</td></tr></table>",
        "ndx100",
        "ndx",
        "2026-09-05",
    )
    merged = merge_constituents({"sp500": sp500, "ndx100": ndx})
    assert merged[0]["indices"] == ["ndx100", "sp500"]


def test_diff_reports_added_and_removed() -> None:
    old = [{"display_symbol": "OLD", "company_name": "Old", "indices": ["sp500"], "provider_symbol": "OLD"}]
    new = [{"display_symbol": "NEW", "company_name": "New", "indices": ["ndx100"], "provider_symbol": "NEW"}]
    diff = constituent_diff(old, new)
    assert [item["display_symbol"] for item in diff["added"]] == ["NEW"]
    assert [item["display_symbol"] for item in diff["removed"]] == ["OLD"]
