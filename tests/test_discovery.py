from levecho.discovery import (
    ETFCandidate,
    SUPPORTED_LEVERAGE,
    match_candidates,
    merge_approved_pairs,
    parse_issuer_pdf_text,
    parse_issuer_tables,
)
from levecho.types import PairConfig


def test_parse_explicit_single_stock_target() -> None:
    html = """
    <table>
      <tr><th>Ticker</th><th>Fund Name</th><th>Index/Benchmark</th><th>Daily Target</th></tr>
      <tr><td>ABCU</td><td>Daily ABC Bull 2X ETF</td><td>Common shares of ABC Corp. (NASDAQ: ABC)</td><td>200%</td></tr>
    </table>
    """
    result = parse_issuer_tables(html, "Test Issuer", "https://example.test")
    assert result[0].reference_symbol == "ABC"
    assert result[0].leverage == 2
    assert result[0].confidence == "high"
    assert result[0].single_stock is True


def test_match_requires_supported_high_confidence_pair() -> None:
    candidate = ETFCandidate(
        ticker="ABCU",
        fund_name="Daily ABC Bull 2X ETF",
        reference_symbol="ABC",
        reference_text="Common shares of ABC Corp. (NASDAQ: ABC)",
        leverage=2,
        issuer="Test Issuer",
        source_url="https://example.test",
        confidence="high",
        single_stock=True,
    )
    approved, pending = match_candidates(
        [candidate],
        [{"display_symbol": "ABC", "active": True}],
    )
    assert approved[0].etf_symbol == "ABCU"
    assert not pending
    assert SUPPORTED_LEVERAGE == frozenset({-3.0, -2.0, 2.0, 3.0})


def test_parse_single_stock_pdf_text() -> None:
    text = """
    Apple Inc. (NASDAQ: AAPL)
    AAPU | Daily AAPL Bull 2X Shares | 200%
    AAPD | Daily AAPL Bear 2X Shares | -200%
    """
    result = parse_issuer_pdf_text(text, "Test Issuer", "https://example.test/list.pdf")
    assert [(item.ticker, item.reference_symbol, item.leverage) for item in result] == [
        ("AAPU", "AAPL", 2),
        ("AAPD", "AAPL", -2),
    ]


def test_changed_existing_pair_is_pending() -> None:
    discovered = PairConfig(
        pair_id="abc-abcu",
        underlying_symbol="ABC",
        etf_symbol="ABCU",
        leverage=3,
    )
    approved, pending = merge_approved_pairs(
        [{"pair_id": "abc-abcu", "underlying_symbol": "ABC", "etf_symbol": "ABCU", "leverage": 2}],
        [discovered],
    )
    assert approved[0]["leverage"] == 2
    assert pending[0]["reason"] == "reference asset or leverage changed"
