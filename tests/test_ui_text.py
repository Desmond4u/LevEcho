import pytest

from levecho.ui_text import format_updated_at


@pytest.mark.parametrize("value,language,expected", [
    ("2026-09-05T20:22:35Z", "zh", "2026-09-06 04:22:35"),
    ("2026-09-05T02:22:35Z", "en", "2026-09-04 21:22:35"),
    ("2026-01-05T02:22:35Z", "en", "2026-01-04 21:22:35"),
    ("2026-09-05T10:22:35+08:00", "en", "2026-09-04 21:22:35"),
    ("2026-09-05T10:22:35.123+08:00", "zh", "2026-09-05 10:22:35"),
])
def test_localized_timestamp(value, language, expected):
    assert format_updated_at(value, language) == expected


@pytest.mark.parametrize("value", [None, "", "bad", "2026-09-05T10:22:35", 123])
def test_unusable_timestamp_is_unknown(value):
    assert format_updated_at(value, "zh") == "未知"
    assert format_updated_at(value, "en") == "Unknown"


@pytest.mark.parametrize("price,step,display", [
    (1740, .01, "1740.00"), (1, .01, "1.00"),
    (.9999, .0001, "0.9999"), (.0001, .0001, "0.0001"),
])
def test_quote_display(price, step, display):
    from levecho.ui_text import price_input_spec
    actual_step, fmt = price_input_spec(price)
    assert actual_step == step
    assert fmt % price == display
