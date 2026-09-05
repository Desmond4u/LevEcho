"""Streamlit UI for the LevEcho one-session price calculator."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from levecho.io import load_json
from levecho.model import ModelInputError, solve_etf_price, solve_stock_price


ROOT = Path(__file__).resolve().parent
SNAPSHOT_PATH = ROOT / "data/latest.json"


def _pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def _percentage_points(value: float) -> str:
    return f"{value * 100:.2f} 个百分点"


st.set_page_config(page_title="LevEcho", page_icon="📈", layout="centered")
st.title("LevEcho：杠杆 ETF 理论价格计算器")
st.caption("以最近共同交易日收盘价为基准，计算下一目标交易日的单日理论价格")

snapshot = load_json(SNAPSHOT_PATH, default={}) or {}
if snapshot.get("published_at"):
    st.caption(
        f"快照发布时间：{snapshot['published_at']} · 状态：{snapshot.get('source_status', 'unknown')}"
    )
pairs = [item for item in snapshot.get("pairs", []) if item.get("status", "active") == "active"]

if not pairs:
    st.info("当前还没有可用的行情快照。请先运行每日更新任务并确认 approved universe / ETF 配置。")
    st.markdown(
        """
        本页面只读取 `data/latest.json`，不会在访问者打开页面时请求行情接口。
        当前模型仅针对一个交易日，结果会受到费用、融资成本、跟踪误差、分红、拆分和市场价/NAV偏差影响。
        """
    )
    st.stop()

pair_by_id = {item["pair_id"]: item for item in pairs}
pair_id = st.selectbox(
    "选择股票—ETF配对",
    options=list(pair_by_id),
    format_func=lambda value: (
        f"{pair_by_id[value]['underlying_symbol']} ↔ {pair_by_id[value]['etf_symbol']} "
        f"({pair_by_id[value]['leverage']:+g}x)"
    ),
)
pair = pair_by_id[pair_id]
calculation_base_session = pair.get("calculation_base_session", pair["as_of_session"])
calculation_base_stock_close = float(
    pair.get("calculation_base_stock_close", pair["latest_stock_close"])
)
calculation_base_etf_close = float(
    pair.get("calculation_base_etf_close", pair["latest_etf_close"])
)

st.caption(
    f"价格基准日：{calculation_base_session}（上一共同交易日收盘） · "
    f"历史表现区间：{pair['base_session']} → {pair['as_of_session']} · "
    f"数据源：{pair.get('source', 'unknown')}"
)

st.info(
    "输入价格按价格基准日之后的目标交易日假设价格处理。页面只读取已发布的收盘快照，"
    "不会请求实时行情。"
)

if pair.get("warnings"):
    for warning in pair["warnings"]:
        st.warning(warning)

input_mode = st.radio("输入哪一边的价格？", ["股票价格", "ETF价格"], horizontal=True)
if input_mode == "股票价格":
    input_price = st.number_input(
        f"{pair['underlying_symbol']} 假设价格",
        min_value=0.0001,
        value=calculation_base_stock_close,
        step=0.01,
        format="%.6f",
    )
    try:
        result = solve_etf_price(
            calculation_base_stock_close,
            calculation_base_etf_close,
            pair["leverage"],
            input_price,
        )
        st.metric(f"{pair['etf_symbol']} 理论价格", f"${result:,.4f}")
    except ModelInputError as exc:
        st.error(str(exc))
else:
    input_price = st.number_input(
        f"{pair['etf_symbol']} 假设价格",
        min_value=0.0001,
        value=calculation_base_etf_close,
        step=0.01,
        format="%.6f",
    )
    try:
        result = solve_stock_price(
            calculation_base_stock_close,
            calculation_base_etf_close,
            pair["leverage"],
            input_price,
        )
        st.metric(f"{pair['underlying_symbol']} 理论价格", f"${result:,.4f}")
    except ModelInputError as exc:
        st.error(str(exc))

st.subheader("价格基准与最近两个共同交易日收盘价")
st.table(
    {
        "": [pair["underlying_symbol"], pair["etf_symbol"]],
        f"历史起点 {pair['base_session']}": [pair["base_stock_close"], pair["base_etf_close"]],
        f"价格基准 {calculation_base_session}": [
            calculation_base_stock_close,
            calculation_base_etf_close,
        ],
    }
)

st.subheader("上一交易日实际表现（参考）")
col1, col2, col3 = st.columns(3)
col1.metric("股票实际涨跌", _pct(pair["stock_return"]))
col2.metric("ETF实际涨跌", _pct(pair["etf_return"]))
col3.metric("理想 ETF 涨跌", _pct(pair["ideal_etf_return"]))
st.caption(
    "实际 ETF 与理想杠杆收益偏差："
    f"{_percentage_points(pair['tracking_error'])}"
)

st.warning(
    "本结果是下一目标交易日的单日理论值，不是实时行情、NAV估值或交易建议。杠杆 ETF 的费用、融资成本、"
    "跟踪误差、买卖价差、分红/拆分及市场价与 NAV 偏差均可能导致实际价格不同。"
)
