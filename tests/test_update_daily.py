from levecho.data import FetchResult
from scripts.update_daily import _print_fetch_errors


def test_print_fetch_errors_lists_symbols_and_caps_count(capsys) -> None:
    errors = {f"S{index:02d}": "boom" for index in range(12)}
    _print_fetch_errors(FetchResult(errors=errors))
    out = capsys.readouterr().out
    assert "Provider errors for 12 symbol(s):" in out
    assert out.count(": boom") == 10
    assert "... and 2 more" in out


def test_print_fetch_errors_truncates_long_messages(capsys) -> None:
    _print_fetch_errors(FetchResult(errors={"AAA": "x" * 500}))
    out = capsys.readouterr().out
    assert len(out) < 300
    assert out.rstrip().endswith("...")


def test_print_fetch_errors_is_silent_without_errors(capsys) -> None:
    _print_fetch_errors(FetchResult())
    assert capsys.readouterr().out == ""
