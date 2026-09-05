from levecho.discovery import (
    ETFCandidate,
    SUPPORTED_LEVERAGE,
    match_candidates,
    merge_approved_pairs,
    parse_defiance_cards,
    parse_graniteshares_cards,
    parse_issuer_pdf_text,
    parse_issuer_tables,
    parse_leverage_shares_page,
    parse_trex_page,
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


def test_parse_bare_reference_and_short_direction() -> None:
    html = """
    <table>
      <tr><th>Ticker</th><th>Fund Name</th><th>Reference Security</th><th>Target</th><th>Exposure</th><th>Reset Period</th></tr>
      <tr><td>SNXX</td><td>Tradr 2X Long SNDK Daily ETF</td><td>SNDK</td><td>2X</td><td>Long</td><td>Daily</td></tr>
      <tr><td>SNDQ</td><td>Tradr 2X Short SNDK Daily ETF</td><td>SNDK</td><td>2X</td><td>Short</td><td>Daily</td></tr>
      <tr><td>OLDX</td><td>Weekly SNDK ETF</td><td>SNDK</td><td>2X</td><td>Long</td><td>Weekly</td></tr>
    </table>
    """
    result = parse_issuer_tables(html, "Tradr", "https://example.test/etfs")
    assert [(item.ticker, item.reference_symbol, item.leverage) for item in result] == [
        ("SNXX", "SNDK", 2),
        ("SNDQ", "SNDK", -2),
    ]
    assert all(item.confidence == "high" and item.single_stock for item in result)


def test_parse_graniteshares_cards() -> None:
    html = """
    <span data-id="1" data-type="leveraged" data-underlying="NVIDIA Corp" data-leverage="2"
          class="etf-table-cell etf-table-cell--ticker">
      <span class="etf-table-cell--ticker__symbol">NVDL</span>
    </span>
    <span data-id="1" data-type="leveraged" data-underlying="NVIDIA Corp" data-leverage="2"
          class="etf-table-cell etf-table-cell--name">
      <span class="etf-table-cell--name-title">GraniteShares 2x Long NVDA Daily ETF</span>
      <span class="etf-table-cell--name-description">2x long exposure to NVIDIA Corp (NVDA)</span>
    </span>
    """
    result = parse_graniteshares_cards(html, "GraniteShares", "https://example.test/etfs")
    assert result[0].reference_symbol == "NVDA"
    assert result[0].leverage == 2
    assert result[0].confidence == "high"


def test_parse_trex_and_defiance_directional_names() -> None:
    trex_html = """
    <div class="table3_item">
      <div class="table3_column">SNDU</div>
      <div class="table3_column">T-REX 2X Long SNDK Daily Target ETF</div>
    </div>
    <div class="table3_item">
      <div class="table3_column">AAPX</div>
      <div class="table3_column">T-REX 2X Long Apple Daily Target ETF</div>
    </div>
    """
    trex = parse_trex_page(trex_html, "T-REX", "https://example.test/etfs")
    assert [(item.ticker, item.reference_symbol, item.leverage) for item in trex] == [
        ("SNDU", "SNDK", 2),
        ("AAPX", "AAPL", 2),
    ]

    defiance_html = """
    <div class="pros-card">
      <p class="pros-card-ticker">NVDX</p>
      <p class="pros-card-name">Defiance Daily Target 2X Long NVDA ETF</p>
    </div>
    """
    defiance = parse_defiance_cards(defiance_html, "Defiance", "https://example.test/prospectuses")
    assert defiance[0].reference_symbol == "NVDA"
    assert defiance[0].leverage == 2
    assert defiance[0].confidence == "high"


def test_parse_leverage_shares_embedded_catalog() -> None:
    html = """
    <script>
    window.productsData = [
      { name: "2x Long SNDK Daily ETF", ticker: 'SNDG', leverage_factor: '2',
        fund: "2x Long SNDK Daily ETF", category: "Leveraged", category2: "SNDK" },
      { name: "2x Short SNDK Daily ETF", ticker: 'SNDZ', leverage_factor: '-2',
        fund: "2x Short SNDK Daily ETF", category: "Inverse", category2: "SNDK" }
    ];
    </script>
    """
    result = parse_leverage_shares_page(html, "Leverage Shares", "https://example.test/all-etfs")
    assert [(item.ticker, item.reference_symbol, item.leverage) for item in result] == [
        ("SNDG", "SNDK", 2),
        ("SNDZ", "SNDK", -2),
    ]


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
