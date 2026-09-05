from pathlib import Path
from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app.py"


@pytest.fixture
def page():
    pair = dict(pair_id="test", underlying_symbol="TEST", etf_symbol="TETF", leverage=2,
                base_session="2026-09-03", as_of_session="2026-09-04",
                base_stock_close=99, base_etf_close=9, latest_stock_close=100,
                latest_etf_close=10, stock_return=.01, etf_return=.02,
                ideal_etf_return=.02, tracking_error=0, source="fixture", warnings=["Source warning"])
    with patch("levecho.io.load_json", return_value={"pairs": [pair], "published_at": "2026-09-05T20:22:35Z"}):
        yield AppTest.from_file(str(APP)).run()


def test_language_preserves_input_and_calculation(page):
    page.number_input[0].set_value(110).run()
    assert page.metric[0].value == "$12.0000"
    page.selectbox(key="language").select("en").run()
    assert not page.exception
    assert page.number_input[0].value == 110
    assert page.metric[0].value == "$12.0000"
    assert page.subheader[0].value == "Hypothetical price"
    assert page.warning[0].value == "Source warning"
    page.selectbox(key="language").select("zh").run()
    assert page.number_input[0].value == 110


def test_reverse_and_domain_error(page):
    page.radio[0].set_value("etf").run()
    page.number_input[0].set_value(12).run()
    assert page.metric[0].value == "$110.0000"
    page.radio[0].set_value("stock").run()
    page.number_input[0].set_value(40).run()
    assert page.error
    assert not page.exception
    page.selectbox(key="language").select("en").run()
    assert "Unable to calculate" in page.error[0].value


def test_empty_snapshot():
    with patch("levecho.io.load_json", return_value={}):
        page = AppTest.from_file(str(APP)).run()
        page.selectbox(key="language").select("en").run()
    assert not page.exception
    assert "No price data" in page.info[0].value


def test_theme_preserves_scenario(page):
    page.number_input[0].set_value(110).run()
    page.selectbox(key="theme").select("dark").run()
    assert not page.exception
    assert page.number_input[0].value == 110
    assert page.metric[0].value == "$12.0000"
    assert "#0e1726" in page.markdown[0].value
    assert "🌐" in page.selectbox(key="language").label
    page.selectbox(key="language").select("en").run()
    assert page.selectbox(key="theme").value == "dark"
    page.selectbox(key="theme").select("light").run()
    assert page.number_input[0].value == 110
    assert "#f5f7fb" in page.markdown[0].value


def test_select_from_either_side():
    base = dict(leverage=2, base_session="2026-09-03", as_of_session="2026-09-04",
                base_stock_close=99, base_etf_close=9, latest_stock_close=100,
                latest_etf_close=10, stock_return=.01, etf_return=.02,
                ideal_etf_return=.02, tracking_error=0, warnings=[])
    pairs = [dict(base, pair_id=key, underlying_symbol=stock, etf_symbol=etf)
             for key, stock, etf in [("a", "AAA", "AAA2"), ("b", "BBB", "BBB2"),
                                      ("c", "BBB", "BBB3")]]
    with patch("levecho.io.load_json", return_value={"pairs": pairs}):
        page = AppTest.from_file(str(APP)).run()
        page.number_input[0].set_value(110).run()
        page.selectbox(key="pair").select("c").run()
        assert page.selectbox(key="stock").value == "BBB"
        assert page.selectbox(key="pair").value == "c"
        assert "BBB3" in page.metric[0].label
        page.selectbox(key="language").select("en").run()
        assert page.selectbox(key="pair").value == "c"
        page.selectbox(key="stock").select("AAA").run()
        assert page.selectbox(key="pair").value == "a"
        assert page.number_input[0].value == 110
        page.selectbox(key="stock").select("BBB").run()
        assert page.selectbox(key="pair").value == "b"
        assert not page.exception


def test_update_time_follows_language(page):
    assert "2026-09-06 04:22:35" in [item.value for item in page.text]
    assert any("GMT+8" in item.value for item in page.caption)
    page.selectbox(key="language").select("en").run()
    assert "2026-09-05 15:22:35" in [item.value for item in page.text]
    assert any("EST (GMT−5)" in item.value for item in page.caption)
    assert not page.exception


def test_quick_scenarios_and_precision(page):
    assert page.number_input[0].proto.format == "%.2f"
    assert page.number_input[0].step == .01
    page.button(key="quick:0.05").click().run()
    assert not any("Session State" in item.value for item in page.warning)
    assert page.number_input[0].value == 105
    assert page.metric[0].value == "$11.0000"
    page.button(key="quick:0").click().run()
    assert page.number_input[0].value == 100
    page.radio[0].set_value("etf").run()
    page.button(key="quick:-0.05").click().run()
    assert page.number_input[0].value == 9.5
    assert page.metric[0].value == "$97.5000"
    page.number_input[0].set_value(.9999).run()
    assert page.number_input[0].proto.format == "%.4f"
    assert page.number_input[0].step == .0001
    page.number_input[0].set_value(1).run()
    assert page.number_input[0].proto.format == "%.2f"
    assert not page.exception


def test_universe_label_in_both_languages(page):
    assert any("纳斯达克100 ∪ 标普500" in item.value for item in page.caption)
    page.selectbox(key="language").select("en").run()
    assert any("Nasdaq-100 ∪ S&P 500" in item.value for item in page.caption)


def test_cleared_price_can_be_reset(page):
    page.number_input[0].set_value(None).run()
    assert not page.exception
    assert page.error
    page.button(key="quick:0").click().run()
    assert page.number_input[0].value == 100
    assert not page.error
