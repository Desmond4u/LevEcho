"""Localized copy for the calculator interface."""

from datetime import datetime, timedelta, timezone


TEXT = {
    "universe": ("股票池：纳斯达克100 ∪ 标普500成分股", "Universe: Nasdaq-100 ∪ S&P 500 constituents"),
    "coverage": ("仅展示已有可用杠杆 ETF 配对的成分股。", "Only constituents with available leveraged ETF pairs are shown."),
    "daily_target": ("每日目标", "Daily target"),
    "quick": ("快捷情景 · 相对输入侧基准价", "Quick scenarios · vs. input reference close"),
    "reset": ("基准", "Base"),
    "precision": ("输入按常规报价精度显示：≥ $1 为两位，< $1 为四位。基准价与理论计算保留原始精度。", "Input display uses standard quote precision: 2 decimals at $1 or above, 4 below $1. Reference prices and theoretical calculations retain full precision."),
    "appearance": ("外观", "Appearance"),
    "light": ("☀️ 日间", "☀️ Light"),
    "dark": ("🌙 夜间", "🌙 Dark"),
    "selection_hint": ("股票与 ETF 可双向选择、自动关联。", "Select a stock or ETF; the other selection updates automatically."),
    "subtitle": ("单股票杠杆 ETF · 单日理论价格", "Single-stock leveraged ETFs · One-day theoretical prices"),
    "language": ("语言", "Language"),
    "stock": ("选择股票", "Select stock"),
    "etf": ("选择 ETF", "Select ETF"),
    "direction": ("计算方向", "Calculation direction"),
    "forward": ("股票 → ETF", "Stock → ETF"),
    "reverse": ("ETF → 股票", "ETF → Stock"),
    "input": ("假设价格", "Hypothetical price"),
    "input_kind": ("输入方式", "Input type"),
    "by_price": ("按价格", "Price"),
    "by_return": ("按涨跌幅", "Return (%)"),
    "input_return": ("假设涨跌幅", "Hypothetical return"),
    "return_help": ("相对输入侧基准价的单日涨跌幅。输入 10 表示上涨 10%，−5 表示下跌 5%。", "One-day return relative to the input reference close. Enter 10 for a 10% rise, or −5 for a 5% fall."),
    "converted_price": ("对应假设价格", "Implied input price"),
    "return_error": ("请输入有效的涨跌幅，且必须大于 −100%；折算价格须为有限正数。", "Enter a valid return above −100%. The implied input price must be finite and positive."),
    "result": ("理论价格", "Theoretical price"),
    "change": ("相对基准", "vs. reference"),
    "reference": ("价格基准", "Reference close"),
    "date": ("价格基准日", "Reference date"),
    "session": ("数据交易日", "Data session"),
    "updated": ("更新时间 · 北京时间（GMT+8）", "Updated · EST (GMT−5)"),
    "source": ("数据源", "Source"),
    "status": ("来源状态", "Source status"),
    "unknown": ("未知", "Unknown"),
    "snapshot": ("收盘快照 · 非实时", "Closing snapshot · Not live"),
    "hint": ("输入价格用于基准日之后目标交易日的单日假设计算。", "Use a hypothetical price for the target trading session after the reference date."),
    "empty": ("暂无可用行情，等待数据更新后即可使用。", "No price data available yet. Please check back after the next data update."),
    "history": ("最近两个共同交易日表现", "Performance between the latest two common sessions"),
    "stock_return": ("股票实际涨跌", "Stock return"),
    "etf_return": ("ETF 实际涨跌", "ETF return"),
    "ideal": ("理想 ETF 涨跌", "Ideal ETF return"),
    "deviation": ("实际与理想 ETF 收益偏差", "Actual minus ideal ETF return"),
    "pp": ("个百分点", "percentage points"),
    "details": ("计算公式与模型说明", "Formula & assumptions"),
    "notice": ("单日理论值，仅供参考。实际价格可能受到费用、融资成本、跟踪误差、买卖价差、分红、拆分及市场价与 NAV 偏差影响。本工具不提供实时行情、NAV 估值或交易建议。", "One-day theoretical values for reference only. Fees, financing costs, tracking error, bid–ask spreads, distributions, splits and market price/NAV differences may affect actual prices. This tool does not provide live quotes, NAV valuations or trading advice."),
    "formula_help": ("S₀ 为股票基准价，E₀ 为 ETF 基准价，L 为有符号日目标倍数。模型仅用于单日，不适用于跨日累计收益。历史区间取双方最近两个共同行情日期，并已按 NYSE 交易日历确认相邻；公司行为字段缺失不代表已确认无公司行为。", "S₀ is the stock reference price, E₀ the ETF reference price, and L the signed daily leverage. The model applies to one session, not cumulative multi-day returns. Historical dates are the latest two common quote dates, verified as consecutive NYSE sessions. Missing corporate-action fields do not confirm the absence of corporate actions."),
    "error": ("无法计算：请检查价格与基准数据。输入必须是有限正数，且计算结果必须大于零；当前假设可能超出单日线性模型的有效范围。", "Unable to calculate. Check the input and reference data: prices must be finite and positive, and the theoretical result must exceed zero. This scenario may be outside the one-day linear model’s valid range."),
    "warnings": ("数据警告（来源原文）", "Data warnings (source text)"),
}


def translate(key: str, language: str) -> str:
    return TEXT[key][1 if language == "en" else 0]


def format_updated_at(value: object, language: str) -> str:
    """Display an aware snapshot timestamp in the requested fixed-offset zone."""
    if not isinstance(value, str):
        return translate("unknown", language)
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            return translate("unknown", language)
        # EST is deliberately fixed at UTC-5, including during US daylight saving time.
        zone = timezone(timedelta(hours=-5 if language == "en" else 8))
        return timestamp.astimezone(zone).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, OverflowError):
        return translate("unknown", language)


def price_input_spec(price: float) -> tuple[float, str]:
    """Standard NMS quote display as of 2026-09; not an execution-price validator.

    SEC Rule 612 FAQ: https://www.sec.gov/divisions/marketreg/subpenny612faq.htm
    Half-cent rollout deferred to November 2027: SEC Release 34-105656.
    """
    return (0.01, "%.2f") if price >= 1 else (0.0001, "%.4f")
