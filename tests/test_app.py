from pathlib import Path
from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app.py"


@pytest.fixture
def sample_pair():
    return dict(pair_id="test", underlying_symbol="TEST", etf_symbol="TETF", leverage=2,
                base_session="2026-09-03", as_of_session="2026-09-04",
                base_stock_close=99, base_etf_close=9, latest_stock_close=100,
                latest_etf_close=10, stock_return=.01, etf_return=.02,
                ideal_etf_return=.02, tracking_error=0, source="fixture", warnings=["Source warning"])


@pytest.fixture
def page(sample_pair):
    with patch("levecho.io.load_json", return_value={"pairs": [sample_pair], "published_at": "2026-09-05T20:22:35Z"}):
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
        page.radio(key="input_kind").set_value("return").run()
        assert page.number_input[0].value == 0
        page.number_input[0].set_value(7).run()
        page.selectbox(key="pair").select("a").run()
        assert page.number_input[0].value == pytest.approx(10)
        page.selectbox(key="pair").select("b").run()
        assert page.number_input[0].value == 7
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


@pytest.mark.parametrize("direction,return_percent,expected", [
    ("stock", 10, "$12.0000"), ("etf", 20, "$110.0000"),
])
def test_return_inputs_in_both_directions(page, direction, return_percent, expected):
    page.radio(key="direction").set_value(direction).run()
    page.radio(key="input_kind").set_value("return").run()
    page.number_input[0].set_value(return_percent).run()
    assert page.metric[0].value == expected
    assert any("对应假设价格" in item.value for item in page.caption)
    page.selectbox(key="language").select("en").run()
    page.selectbox(key="theme").select("dark").run()
    assert page.number_input[0].value == return_percent
    assert page.metric[0].value == expected
    assert "Hypothetical return (%)" in page.number_input[0].label
    assert any("Implied input price" in item.value for item in page.caption)
    assert not page.exception


def test_price_and_return_switches_keep_the_scenario(page):
    page.number_input[0].set_value(110).run()
    page.radio(key="input_kind").set_value("return").run()
    assert page.number_input[0].value == pytest.approx(10)
    page.number_input[0].set_value(12.345678).run()
    page.radio(key="input_kind").set_value("price").run()
    assert page.number_input[0].value == pytest.approx(112.345678)
    page.radio(key="input_kind").set_value("return").run()
    assert page.number_input[0].value == pytest.approx(12.345678)
    page.button(key="quick:0.05").click().run()
    assert page.number_input[0].value == 5
    assert page.metric[0].value == "$11.0000"
    page.radio(key="direction").set_value("etf").run()
    assert page.number_input[0].value == 0
    page.button(key="quick:-0.05").click().run()
    assert page.number_input[0].value == -5
    assert page.metric[0].value == "$97.5000"
    page.radio(key="direction").set_value("stock").run()
    assert page.number_input[0].value == 5
    page.button(key="quick:0").click().run()
    assert page.metric[0].value == "$10.0000"
    assert not any("Session State" in item.value for item in page.warning)
    assert not page.exception


@pytest.mark.parametrize("invalid_return", [None, -100, -101])
def test_invalid_return_is_localized_and_resettable(page, invalid_return):
    page.radio(key="input_kind").set_value("return").run()
    page.number_input[0].set_value(invalid_return).run()
    assert "−100%" in page.error[0].value
    assert not page.exception
    page.selectbox(key="language").select("en").run()
    assert "Enter a valid return" in page.error[0].value
    assert not any("Implied input price" in item.value for item in page.caption)
    page.button(key="quick:0").click().run()
    assert page.number_input[0].value == 0
    assert not page.error


def test_valid_return_outside_leveraged_model_domain(page):
    page.radio(key="input_kind").set_value("return").run()
    page.number_input[0].set_value(-60).run()
    assert "无法计算" in page.error[0].value
    assert all(item.label != "TETF · USD" for item in page.metric)
    assert not page.exception


@pytest.mark.parametrize("leverage,direction,return_percent,expected", [
    (-2, "stock", 10, "$8.0000"), (-3, "etf", 30, "$90.0000"),
    (3, "stock", 10, "$13.0000"),
])
def test_return_input_supports_signed_leverage(sample_pair, leverage, direction, return_percent, expected):
    pair = dict(sample_pair, leverage=leverage)
    with patch("levecho.io.load_json", return_value={"pairs": [pair]}):
        page = AppTest.from_file(str(APP)).run()
        page.radio(key="direction").set_value(direction).run()
        page.radio(key="input_kind").set_value("return").run()
        page.number_input[0].set_value(return_percent).run()
        assert page.metric[0].value == expected
        assert not page.exception
