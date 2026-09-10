"""Bilingual Streamlit UI for the one-session price calculator."""

from pathlib import Path

import pandas as pd
import streamlit as st

from levecho.io import load_json
from levecho.model import ModelInputError, daily_return, price_from_return, solve_etf_price, solve_stock_price
from levecho.ui_text import format_updated_at, price_input_spec, translate

ROOT = Path(__file__).resolve().parent
SNAPSHOT_PATH = ROOT / "data/latest.json"

st.set_page_config(page_title="LevEcho", page_icon="↗", layout="centered")


def _seed_query_state() -> None:
    """Deep-link language and theme from the URL on a fresh session."""
    if st.query_params.get("lang") in ("zh", "en"):
        st.session_state.setdefault("language", st.query_params["lang"])
    if st.query_params.get("theme") in ("light", "dark"):
        st.session_state.setdefault("theme", st.query_params["theme"])


_seed_query_state()

with st.container(key="topbar"):
    header, languages, appearance = st.columns([3, 1.5, 1.5])
with languages:
    language = st.selectbox("🌐 语言 / Language", ["zh", "en"],
                            format_func=lambda value: "中文" if value == "zh" else "English",
                            key="language")


def t(key: str) -> str:
    return translate(key, language)


with appearance:
    theme = st.selectbox(t("appearance"), ["light", "dark"], key="theme",
                         format_func=lambda value: t(value))

# Design tokens: bg_top, bg_bottom, card, field, text, muted, accent, accent2,
# border, shadow, accent_soft, topbar_bg, pos, neg
palette = (
    ("#0b1122", "#0d1528", "#151d34", "#1b2442", "#e9eefb", "#8e9cbd",
     "#7d9bff", "#35d6e4", "#263254",
     "0 1px 2px rgba(0,0,0,.45), 0 14px 34px rgba(0,0,0,.38)",
     "rgba(125,155,255,.14)", "rgba(11,17,34,.72)", "#3ddc97", "#ff7a7a")
    if theme == "dark" else
    ("#f7f8fc", "#eef2f9", "#ffffff", "#f3f5fb", "#17203a", "#5d6b85",
     "#2c53f0", "#1fb6cc", "#e3e8f3",
     "0 1px 2px rgba(23,32,58,.05), 0 10px 30px rgba(23,32,58,.07)",
     "rgba(44,83,240,.09)", "rgba(247,248,252,.78)", "#0c9d70", "#e0484d")
)
bg_top, bg_bottom, card, field, text, muted, accent, accent2, border, shadow, accent_soft, topbar_bg, pos, neg = palette
st.markdown(f"""
<style>
.stApp {{
    background: linear-gradient(180deg, {bg_top} 0%, {bg_bottom} 100%) fixed;
    color: {text}; color-scheme: {theme};
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI",
                 Roboto, "Helvetica Neue", Arial, "PingFang SC",
                 "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
}}
.block-container {{max-width: 1040px; padding-top: 4.4rem; padding-bottom: 3rem;}}
[data-testid="stHeader"] {{background: transparent;}}
h1 {{letter-spacing: -.045em; font-weight: 750;}}
h3 {{letter-spacing: -.02em; position: relative; padding-left: 14px;}}
h3::before {{
    content: ""; position: absolute; left: 0; top: .3em; width: 4px; height: .95em;
    border-radius: 2px; background: linear-gradient(180deg, {accent}, {accent2});
}}
h1, h2, label, [data-testid="stWidgetLabel"],
[data-testid="stMarkdownContainer"], [data-testid="stMetricLabel"] {{color: {text};}}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] * {{color: {muted} !important; font-size: .82rem; letter-spacing: .01em;}}

/* Sticky frosted topbar */
.st-key-topbar {{
    position: sticky; top: 0; z-index: 200; margin: 0 -1rem; padding: .55rem 1rem;
    background: {topbar_bg}; backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
    border-bottom: 1px solid {border};
}}
.st-key-topbar [data-baseweb="select"] > div {{
    background: {card}; border: 1px solid {border}; border-radius: 999px;
    min-height: 38px; font-size: .85rem;
}}

/* Cards */
.st-key-selection, .st-key-input_card, .st-key-result_card, .st-key-data_card,
.st-key-history_card, .st-key-compare_card {{
    background: {card}; border: 1px solid {border}; border-color: {border} !important;
    border-radius: 20px; box-shadow: {shadow};
}}
.st-key-result_card {{position: relative; overflow: hidden;}}
.st-key-result_card::before {{
    content: ""; position: absolute; inset: 0 0 auto 0; height: 3px;
    background: linear-gradient(90deg, {accent}, {accent2});
}}
.st-key-result_card::after {{
    content: ""; position: absolute; inset: 0 0 auto 0; height: 180px; pointer-events: none;
    background: radial-gradient(60% 100% at 50% 0%, {accent_soft}, transparent 75%);
}}
.st-key-result_card [data-testid="stMetricValue"] {{
    font-size: clamp(2.4rem, 4.5vw, 3.3rem); font-weight: 700; letter-spacing: -.02em;
    background: linear-gradient(90deg, {accent}, {accent2});
    -webkit-background-clip: text; background-clip: text;
    -webkit-text-fill-color: transparent; color: {accent};
    font-variant-numeric: tabular-nums;
}}
.delta {{font-weight: 700; font-size: 1.05rem; font-variant-numeric: tabular-nums;}}
.delta.up {{color: {pos};}}
.delta.down {{color: {neg};}}
.delta-label {{color: {muted}; font-weight: 500;}}

/* Product chips */
.chip {{
    display: inline-flex; align-items: center; padding: .38rem .85rem; margin: 0 .5rem .8rem 0;
    border-radius: 999px; background: {field}; color: {muted};
    border: 1px solid {border}; font-size: .85rem; font-weight: 600; letter-spacing: .01em;
}}
.chip-accent {{background: {accent_soft}; color: {accent}; border-color: transparent; font-size: .9rem;}}

/* Inputs, selects, quick buttons */
[data-baseweb="select"] > div, [data-baseweb="input"], [data-baseweb="base-input"],
input, [data-testid="stNumberInput"] button {{background: {field} !important; color: {text} !important;}}
[data-baseweb="select"] > div, [data-baseweb="input"] {{border-radius: 12px;}}
[data-baseweb="input"]:focus-within {{border-color: {accent}; box-shadow: 0 0 0 3px {accent_soft};}}
[data-baseweb="select"] svg {{fill: {text};}}
[data-baseweb="popover"], [data-baseweb="popover"] ul,
[data-baseweb="popover"] li {{background: {card}; color: {text}; border-radius: 12px;}}
[data-baseweb="popover"] li:hover, [role="option"][aria-selected="true"] {{background: {field};}}
.st-key-shortcuts button {{
    background: {field}; color: {text}; border: 1px solid {border}; border-radius: 12px;
    min-height: 42px; font-weight: 600; font-variant-numeric: tabular-nums;
    transition: border-color .15s ease, transform .15s ease, background .15s ease, color .15s ease;
}}
.st-key-shortcuts button:hover {{
    border-color: {accent}; color: {accent}; background: {accent_soft}; transform: translateY(-1px);
}}

/* Metrics, tables, expanders */
[data-testid="stMetricValue"], [data-testid="stMetricValue"] * {{color: {accent} !important; font-variant-numeric: tabular-nums;}}
[data-testid="stMetricLabel"] {{font-size: .78rem; letter-spacing: .02em;}}
.st-key-data_card [data-testid="stText"] {{color: {text}; font-variant-numeric: tabular-nums;}}
[data-testid="stTable"] {{font-variant-numeric: tabular-nums; overflow-x: auto;}}
[data-testid="stTable"] th {{
    color: {muted} !important; font-size: .72rem; text-transform: uppercase;
    letter-spacing: .08em; border-color: {border};
}}
[data-testid="stTable"] td {{color: {text}; border-color: {border};}}
[data-testid="stTable"] tbody tr:hover td {{background: {accent_soft};}}
[data-testid="stExpander"] details {{background: {card}; border: 1px solid {border}; border-radius: 16px;}}
[data-testid="stExpander"] summary {{color: {text}; font-weight: 600;}}
[data-testid="stExpander"] summary:hover {{color: {accent};}}
[data-testid="stAlert"] [data-testid="stMarkdownContainer"] {{color: inherit;}}
@media (max-width: 640px) {{
    .block-container {{padding: 3.6rem 1rem 2rem;}}
    h1 {{font-size: 2rem !important; padding-bottom: .2rem !important;}}
    h3 {{font-size: 1.2rem !important;}}
    .st-key-topbar [data-testid="stHorizontalBlock"] {{flex-wrap: wrap; gap: .65rem;}}
    .st-key-topbar [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{min-width: 0 !important; flex: 1 1 calc(50% - .65rem) !important; width: calc(50% - .65rem) !important;}}
    .st-key-topbar [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child {{flex-basis: 100% !important; width: 100% !important;}}
    .st-key-shortcuts [data-testid="stHorizontalBlock"] {{flex-wrap: nowrap; gap: .3rem;}}
    .st-key-shortcuts [data-testid="stColumn"] {{min-width: 0 !important; flex: 1 1 0 !important; width: 0 !important;}}
    .st-key-shortcuts button {{width: 100%; padding: .25rem .1rem;}}
    .st-key-shortcuts button p {{font-size: .8rem; white-space: nowrap;}}
    [data-baseweb="input"] input {{font-size: 16px;}}
    [data-baseweb="select"] > div {{min-height: 44px;}}
    .st-key-result_card [data-testid="stMetricValue"] {{font-size: 2.4rem;}}
}}
</style>
""", unsafe_allow_html=True)


with header:
    st.title("LevEcho")
    st.caption(t("subtitle"))

st.caption(t("universe"))

snapshot = load_json(SNAPSHOT_PATH, default={}) or {}
pairs = [item for item in snapshot.get("pairs", []) if item.get("status", "active") == "active"]
if not pairs:
    st.info(t("empty"))
    st.caption(t("notice"))
    st.stop()

pair_by_id = {p["pair_id"]: p for p in pairs}
stocks = sorted({p["underlying_symbol"] for p in pairs})
if st.query_params.get("pair") in pair_by_id:
    st.session_state.setdefault("pair", st.query_params["pair"])
if st.session_state.get("pair") not in pair_by_id:
    st.session_state["pair"] = pairs[0]["pair_id"]
st.session_state["stock"] = pair_by_id[st.session_state["pair"]]["underlying_symbol"]


def select_stock() -> None:
    selected = st.session_state["stock"]
    if pair_by_id[st.session_state["pair"]]["underlying_symbol"] != selected:
        st.session_state["pair"] = next(p["pair_id"] for p in pairs if p["underlying_symbol"] == selected)


def select_etf() -> None:
    st.session_state["stock"] = pair_by_id[st.session_state["pair"]]["underlying_symbol"]


with st.container(border=True, key="selection"):
    stock_col, etf_col = st.columns(2)
    stock_col.selectbox(t("stock"), stocks, key="stock", on_change=select_stock)
    etf_col.selectbox(t("etf"), sorted(pair_by_id, key=lambda value: pair_by_id[value]["etf_symbol"]),
                      key="pair", on_change=select_etf,
                      format_func=lambda value: (
                          f"{pair_by_id[value]['etf_symbol']} · {pair_by_id[value]['leverage']:+g}x"
                          f" · {pair_by_id[value]['underlying_symbol']}"
                      ))
    st.caption(t("selection_hint") + " " + t("coverage"))
pair_id = st.session_state["pair"]
pair = pair_by_id[pair_id]
symbol = pair["underlying_symbol"]
base_date = pair.get("calculation_base_session", pair["as_of_session"])
stock_base = float(pair.get("calculation_base_stock_close", pair["latest_stock_close"]))
etf_base = float(pair.get("calculation_base_etf_close", pair["latest_etf_close"]))

chips = f'<span class="chip chip-accent">{pair["leverage"]:+g}× · {t("daily_target")}</span>'
chips += f'<span class="chip">{pair["etf_symbol"]}</span>'
if pair.get("issuer"):
    chips += f'<span class="chip">{pair["issuer"]}</span>'
st.markdown(chips, unsafe_allow_html=True)
st.caption(t("snapshot"))
left, right = st.columns(2)
with left, st.container(border=True, key="input_card"):
    st.subheader(t("input"))
    mode = st.radio(t("direction"), ["stock", "etf"], horizontal=True, key="direction",
                    index=["stock", "etf"].index(st.session_state.get("direction", "stock")),
                    format_func=lambda value: t("forward" if value == "stock" else "reverse"))
    forward = mode == "stock"
    input_symbol = symbol if forward else pair["etf_symbol"]
    output_symbol = pair["etf_symbol"] if forward else symbol
    input_base, output_base = (stock_base, etf_base) if forward else (etf_base, stock_base)
    input_kind = st.radio(t("input_kind"), ["price", "return"], horizontal=True,
                          key="input_kind",
                          index=["price", "return"].index(st.session_state.get("input_kind", "price")),
                          format_func=lambda value: t(f"by_{value}"))
    # Store values separately from widget state so switching pairs/directions preserves scenarios.
    scenario = f"{pair_id}:{mode}"
    saved = st.session_state.setdefault("prices", {})
    saved_returns = st.session_state.setdefault("returns", {})
    widget_key = f"{input_kind}:{scenario}"
    input_error = None
    if input_kind == "price":
        if widget_key not in st.session_state:
            st.session_state[widget_key] = saved.get(scenario, input_base)
        current_price = st.session_state[widget_key]
        step, price_format = price_input_spec(input_base if current_price is None else current_price)
        # Return-based scenarios may produce a positive price below the usual quote increment.
        minimum = min(0.0001, current_price) if current_price is not None and current_price > 0 else 0.0001
        price = st.number_input(f"{input_symbol} · {t('input')} (USD)", min_value=minimum,
                                value=None, step=step, format=price_format, key=widget_key,
                                help=t("precision"))
        saved[scenario] = price
        try:
            saved_returns[scenario] = daily_return(input_base, price) * 100
        except ModelInputError:
            saved_returns[scenario] = None
    else:
        if widget_key not in st.session_state:
            st.session_state[widget_key] = saved_returns.get(scenario, 0.0)
        return_percent = st.number_input(f"{input_symbol} · {t('input_return')} (%)",
                                         value=None, step=0.1, format="%.2f", key=widget_key,
                                         help=t("return_help"))
        saved_returns[scenario] = return_percent
        try:
            if return_percent is None:
                raise ModelInputError("return input is empty")
            price = price_from_return(input_base, return_percent / 100)
        except ModelInputError:
            price = None
            input_error = t("return_error")
        saved[scenario] = price
        if price is not None:
            st.caption(f"{t('converted_price')} · {input_symbol} {price:,.4f} USD")

    def apply_scenario(change: float) -> None:
        value = price_from_return(input_base, change)
        st.session_state[widget_key] = value if input_kind == "price" else change * 100
        saved[scenario] = value
        saved_returns[scenario] = change * 100

    st.caption(t("quick"))
    with st.container(key="shortcuts"):
        for column, change in zip(st.columns(5), [-.05, -.01, 0, .01, .05]):
            column.button(t("reset") if change == 0 else f"{change:+.0%}",
                          key=f"quick:{change}", on_click=apply_scenario, args=(change,),
                          use_container_width=True)
    st.caption(f"{t('reference')} · {symbol} {stock_base:,.4f} USD / {pair['etf_symbol']} {etf_base:,.4f} USD")
with right, st.container(border=True, key="result_card"):
    st.subheader(t("result"))
    try:
        solver = solve_etf_price if forward else solve_stock_price
        result = solver(stock_base, etf_base, pair["leverage"], price)
        st.metric(f"{output_symbol} · USD", f"${result:,.4f}")
        change_percent = (result / output_base - 1) * 100
        delta_class = "delta up" if change_percent >= 0 else "delta down"
        st.markdown(f'<span class="{delta_class}">{change_percent:+.2f}%</span>'
                    f' <span class="delta-label">· {t("change")}</span>', unsafe_allow_html=True)
    except ModelInputError:
        st.error(input_error or t("error"))
    st.caption(t("hint"))

with st.container(border=True, key="data_card"):
    dates = st.columns(2)
    for column, label, value in (
        (dates[0], "date", base_date),
        (dates[1], "session", pair["as_of_session"]),
    ):
        column.caption(t(label))
        column.text(value)
    metadata = st.columns(2)
    metadata[0].caption(t("updated"))
    metadata[0].text(format_updated_at(snapshot.get("published_at"), language))
    metadata[1].caption(t("source"))
    metadata[1].text(pair.get("source") or t("unknown"))
    st.caption(f"{t('status')} · {snapshot.get('source_status') or t('unknown')}")
if pair.get("warnings"):
    st.caption(t("warnings"))
    for warning in pair["warnings"]:
        st.warning(warning)

st.subheader(t("history"))
st.caption(f"{pair['base_session']} → {pair['as_of_session']}")
with st.container(border=True, key="history_card"):
    for column, label, field in zip(st.columns(3), ["stock_return", "etf_return", "ideal"],
                                     ["stock_return", "etf_return", "ideal_etf_return"]):
        column.metric(t(label), f"{pair[field] * 100:+.2f}%")
    st.caption(f"{t('deviation')} · {pair['tracking_error'] * 100:+.4f} {t('pp')}")
    st.table(pd.DataFrame({"": [symbol, pair["etf_symbol"]],
              pair["base_session"]: [f"${pair['base_stock_close']:,.4f}", f"${pair['base_etf_close']:,.4f}"],
              pair["as_of_session"]: [f"${pair['latest_stock_close']:,.4f}", f"${pair['latest_etf_close']:,.4f}"]}).set_index(""))

peers = [item for item in pairs if item["underlying_symbol"] == symbol]
if len(peers) > 1:
    st.subheader(f"{t('compare')} · {symbol}")
    st.caption(t("compare_help"))
    with st.container(border=True, key="compare_card"):
        rows = []
        for item in sorted(peers, key=lambda value: (abs(float(value.get("tracking_error") or 0.0)), value["etf_symbol"])):
            row = {
                t("col_etf"): ("● " if item["pair_id"] == pair_id else "") + item["etf_symbol"],
                t("col_leverage"): f"{item['leverage']:+g}x",
                t("col_issuer"): item.get("issuer") or t("unknown"),
                t("col_deviation"): f"{float(item.get('tracking_error') or 0.0) * 100:+.2f}",
            }
            if forward and price is not None:
                try:
                    theoretical = solve_etf_price(
                        float(item.get("calculation_base_stock_close", item["latest_stock_close"])),
                        float(item.get("calculation_base_etf_close", item["latest_etf_close"])),
                        item["leverage"],
                        price,
                    )
                    row[t("col_theoretical")] = f"${theoretical:,.4f}"
                except ModelInputError:
                    row[t("col_theoretical")] = "—"
            rows.append(row)
        columns = [t("col_etf"), t("col_leverage"), t("col_issuer")]
        if forward and price is not None:
            columns.insert(3, t("col_theoretical"))
        columns.append(t("col_deviation"))
        st.table(pd.DataFrame(rows, columns=columns))
with st.expander(t("details")):
    st.latex(r"E = E_0[1 + L(S/S_0 - 1)]")
    st.latex(r"S = S_0[1 + (E/E_0 - 1)/L]")
    st.write(t("formula_help"))
st.caption(t("notice"))
# Keep the URL shareable: reflect the current selection, language and theme.
st.query_params["pair"] = pair_id
st.query_params["lang"] = language
st.query_params["theme"] = theme
