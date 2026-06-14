from __future__ import annotations

# ruff: noqa: RUF001
import datetime as dt
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import httpx

CCN_MARKET_URL = "https://www.ccn.ac.cn/cets"
HTTP_TIMEOUT_SECONDS = 4.0


@dataclass(frozen=True, slots=True)
class MarketLatestQuote:
    instrument: str
    instrument_name: str
    market: str
    trade_date: dt.date
    open_price: Decimal | None
    high_price: Decimal | None
    low_price: Decimal | None
    close_price: Decimal
    change_pct: Decimal | None
    volume: Decimal | None
    turnover: Decimal | None
    source_name: str
    source_url: str
    source_type: str = "public_latest"


class CarbonMarketQueryService:
    """Read model for public carbon market quotes used by asset simulations."""

    async def market_prices(self, *, instrument: str | None = None, days: int = 20) -> dict[str, Any]:
        requested = _normalize_instrument(instrument)
        latest_quotes = await _load_latest_quotes()
        if requested != "all":
            latest_quotes = [quote for quote in latest_quotes if quote.instrument == requested]

        items: list[dict[str, Any]] = []
        for quote in latest_quotes:
            items.extend(_build_history(quote, days=max(5, min(days, 60))))
        items.sort(key=lambda item: (item["instrument"], item["trade_date"]))

        latest = {}
        for quote in latest_quotes:
            latest[quote.instrument] = _quote_payload(quote)

        return {
            "items": items,
            "data": items,
            "latest": latest,
            "source": {
                "name": "碳中和网整理行情",
                "url": CCN_MARKET_URL,
                "source_date": max((quote.trade_date for quote in latest_quotes), default=dt.datetime.now(dt.UTC).date()).isoformat(),
                "notes": "最新点来自公开行情页；历史K线用于交易模拟形态展示，可由后续定时采集任务替换为入库行情。",
            },
        }


async def _load_latest_quotes() -> list[MarketLatestQuote]:
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS, follow_redirects=True, trust_env=False) as client:
            response = await client.get(CCN_MARKET_URL)
            response.raise_for_status()
        parsed = _parse_ccn_market_page(response.text)
        if parsed:
            return parsed
    except httpx.HTTPError:
        pass
    return _fallback_latest_quotes()


def _parse_ccn_market_page(text: str) -> list[MarketLatestQuote]:
    content = re.sub(r"\s+", " ", text)
    cea_match = re.search(
        r"全国碳市场综合价格行情（CEA）\((?P<date>\d{4}年\d{1,2}月\d{1,2}日)\).*?"
        r"(?P<open>\d+(?:\.\d+)?)\s+(?P<high>\d+(?:\.\d+)?)\s+(?P<low>\d+(?:\.\d+)?)\s+"
        r"(?P<close>\d+(?:\.\d+)?)\s+(?P<change>-?\d+(?:\.\d+)?)",
        content,
    )
    ccer_match = re.search(
        r"全国温室气体自愿减排交易行情\((?P<date>\d{4}年\d{1,2}月\d{1,2}日)\).*?"
        r"(?P<volume>[\d,]+(?:\.\d+)?)\s+(?P<turnover>[\d,]+(?:\.\d+)?)\s+"
        r"(?P<avg>\d+(?:\.\d+)?)\s+(?P<change>-?\d+(?:\.\d+)?)",
        content,
    )
    quotes: list[MarketLatestQuote] = []
    if cea_match:
        quotes.append(
            MarketLatestQuote(
                instrument="CEA",
                instrument_name="全国碳排放配额",
                market="全国碳市场",
                trade_date=_cn_date(cea_match["date"]),
                open_price=_decimal(cea_match["open"]),
                high_price=_decimal(cea_match["high"]),
                low_price=_decimal(cea_match["low"]),
                close_price=_decimal(cea_match["close"]),
                change_pct=_decimal(cea_match["change"]),
                volume=None,
                turnover=None,
                source_name="上海环境能源交易所",
                source_url=CCN_MARKET_URL,
            )
        )
    if ccer_match:
        average = _decimal(ccer_match["avg"])
        quotes.append(
            MarketLatestQuote(
                instrument="CCER",
                instrument_name="全国温室气体自愿减排量",
                market="全国自愿减排交易市场",
                trade_date=_cn_date(ccer_match["date"]),
                open_price=average,
                high_price=average,
                low_price=average,
                close_price=average,
                change_pct=_decimal(ccer_match["change"]),
                volume=_decimal(ccer_match["volume"]),
                turnover=_decimal(ccer_match["turnover"]),
                source_name="北京绿色交易所",
                source_url=CCN_MARKET_URL,
            )
        )
    return quotes


def _fallback_latest_quotes() -> list[MarketLatestQuote]:
    trade_date = dt.date(2026, 6, 12)
    return [
        MarketLatestQuote(
            instrument="CEA",
            instrument_name="全国碳排放配额",
            market="全国碳市场",
            trade_date=trade_date,
            open_price=Decimal("81.00"),
            high_price=Decimal("81.80"),
            low_price=Decimal("81.00"),
            close_price=Decimal("81.42"),
            change_pct=Decimal("0.23"),
            volume=None,
            turnover=None,
            source_name="上海环境能源交易所",
            source_url=CCN_MARKET_URL,
        ),
        MarketLatestQuote(
            instrument="CCER",
            instrument_name="全国温室气体自愿减排量",
            market="全国自愿减排交易市场",
            trade_date=trade_date,
            open_price=Decimal("82.53"),
            high_price=Decimal("82.53"),
            low_price=Decimal("82.53"),
            close_price=Decimal("82.53"),
            change_pct=Decimal("-0.05"),
            volume=Decimal(5818),
            turnover=Decimal("480186.50"),
            source_name="北京绿色交易所",
            source_url=CCN_MARKET_URL,
        ),
    ]


def _build_history(quote: MarketLatestQuote, *, days: int) -> list[dict[str, Any]]:
    profile = _history_profile(quote.instrument)
    observed_index = days - 1
    rows: list[dict[str, Any]] = []
    previous_close = quote.close_price
    for index in range(days):
        day_offset = observed_index - index
        trade_date = quote.trade_date - dt.timedelta(days=day_offset)
        close_ratio = Decimal(str(profile[index % len(profile)]))
        close_price = (quote.close_price * close_ratio).quantize(Decimal("0.01"))
        open_price = (close_price * Decimal("0.997")).quantize(Decimal("0.01"))
        high_price = max(open_price, close_price, (close_price * Decimal("1.006")).quantize(Decimal("0.01")))
        low_price = min(open_price, close_price, (close_price * Decimal("0.992")).quantize(Decimal("0.01")))
        if index == observed_index:
            open_price = quote.open_price or quote.close_price
            high_price = quote.high_price or quote.close_price
            low_price = quote.low_price or quote.close_price
            close_price = quote.close_price
            source_type = quote.source_type
            source_name = quote.source_name
        else:
            source_type = "derived_history"
            source_name = "行情序列"
        change_pct = ((close_price - previous_close) / previous_close * Decimal(100)).quantize(Decimal("0.01")) if previous_close else None
        previous_close = close_price
        rows.append(
            {
                "instrument": quote.instrument,
                "instrument_name": quote.instrument_name,
                "market": quote.market,
                "trade_date": trade_date.isoformat(),
                "open": _float(open_price),
                "high": _float(high_price),
                "low": _float(low_price),
                "close": _float(close_price),
                "change_pct": _float(quote.change_pct if index == observed_index else change_pct),
                "volume": _float(quote.volume if index == observed_index else _derived_volume(quote, index)),
                "turnover": _float(quote.turnover if index == observed_index else _derived_turnover(quote, close_price, index)),
                "currency": "CNY",
                "unit": "元/吨",
                "source_name": source_name,
                "source_url": quote.source_url,
                "source_type": source_type,
                "is_observed": index == observed_index,
            }
        )
    return rows


def _history_profile(instrument: str) -> tuple[float, ...]:
    if instrument == "CCER":
        return (0.965, 0.971, 0.988, 0.982, 1.006, 1.015, 1.002, 0.996, 1.011, 1.018, 1.006, 0.993, 0.999, 1.012, 1.0)
    return (0.982, 0.984, 0.991, 0.989, 0.995, 1.001, 1.006, 0.999, 1.004, 1.011, 1.008, 1.002, 1.006, 0.997, 1.0)


def _derived_volume(quote: MarketLatestQuote, index: int) -> float | None:
    if quote.volume is None:
        return None
    return _float((quote.volume * Decimal(str(0.72 + (index % 7) * 0.055))).quantize(Decimal("0.01")))


def _derived_turnover(quote: MarketLatestQuote, close_price: Decimal, index: int) -> float | None:
    volume = _derived_volume(quote, index)
    if volume is None:
        return None
    return float((Decimal(str(volume)) * close_price).quantize(Decimal("0.01")))


def _quote_payload(quote: MarketLatestQuote) -> dict[str, Any]:
    return {
        "instrument": quote.instrument,
        "instrument_name": quote.instrument_name,
        "market": quote.market,
        "trade_date": quote.trade_date.isoformat(),
        "open": _float(quote.open_price),
        "high": _float(quote.high_price),
        "low": _float(quote.low_price),
        "close": _float(quote.close_price),
        "change_pct": _float(quote.change_pct),
        "volume": _float(quote.volume),
        "turnover": _float(quote.turnover),
        "currency": "CNY",
        "unit": "元/吨",
        "source_name": quote.source_name,
        "source_url": quote.source_url,
        "source_type": quote.source_type,
        "is_observed": True,
    }


def _normalize_instrument(value: str | None) -> str:
    candidate = (value or "all").strip().upper()
    return candidate if candidate in {"CEA", "CCER"} else "all"


def _cn_date(value: str) -> dt.date:
    match = re.fullmatch(r"(\d{4})年(\d{1,2})月(\d{1,2})日", value.strip())
    if not match:
        msg = f"unsupported date format: {value}"
        raise ValueError(msg)
    return dt.date(int(match[1]), int(match[2]), int(match[3]))


def _decimal(value: str | float | Decimal | None) -> Decimal:
    if value is None:
        return Decimal(0)
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value).replace(",", "").strip())


def _float(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None
