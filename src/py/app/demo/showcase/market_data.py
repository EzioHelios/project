"""Audited public market observations bundled with the showcase tenant.

The snapshots below are transcribed from the linked official publications. They
are deliberately static so installing the demo is reproducible and does not
depend on network availability. Budget and stress-test prices belong in carbon
cost scenarios, never in this market-observation catalog.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class PublicMarketQuoteSpec:
    """One source-preserving public market observation."""

    instrument_code: str
    trade_date: date
    close_price: Decimal
    volume: Decimal | None
    turnover: Decimal | None
    source_name: str
    source_version: str
    source_url: str
    published_at: datetime
    open_price: Decimal | None = None
    high_price: Decimal | None = None
    low_price: Decimal | None = None


CEA_MONTHLY_SOURCE = "上海环境能源交易所全国碳市场月度行情数据"
CEA_MONTHLY_METRIC = "monthly-ohlc-v1"
CCER_MONTHLY_SOURCE = "全国温室气体自愿减排交易系统月度成交数据"
CCER_MONTHLY_METRIC = "monthly-average-v1"
CCER_DAILY_URL = "https://www.ccer.com.cn/wcm/ccer/html/2502sjcx/index.html"
GREEN_CERTIFICATE_MONTHLY_SOURCE = "国家能源局全国绿证交易数据(2025年电量)"
GREEN_CERTIFICATE_MONTHLY_METRIC = "monthly-average-vintage-2025-v1"


def _published(year: int, month: int, day: int) -> datetime:
    """Represent an official China publication date at 17:00 Asia/Shanghai."""
    return datetime(year, month, day, 9, tzinfo=UTC)


PUBLIC_MARKET_QUOTES: tuple[PublicMarketQuoteSpec, ...] = (
    # CEA: official month-end/latest observations represented as a monthly
    # market snapshot for bid-demo charting. OHLC is the listed-agreement price.
    PublicMarketQuoteSpec(
        "CEA-NATIONAL",
        date(2026, 1, 30),
        Decimal("79.00"),
        Decimal(100100),
        Decimal("8047900.00"),
        CEA_MONTHLY_SOURCE,
        CEA_MONTHLY_METRIC,
        "https://overview.cneeex.com/c/2026-01-30/497355.shtml",
        _published(2026, 1, 30),
        Decimal("79.00"),
        Decimal("79.00"),
        Decimal("79.00"),
    ),
    PublicMarketQuoteSpec(
        "CEA-NATIONAL",
        date(2026, 2, 27),
        Decimal("80.50"),
        Decimal(107901),
        Decimal("8506030.50"),
        CEA_MONTHLY_SOURCE,
        CEA_MONTHLY_METRIC,
        "https://overview.cneeex.com/c/2026-02-27/497401.shtml",
        _published(2026, 2, 27),
        Decimal("80.50"),
        Decimal("80.50"),
        Decimal("80.50"),
    ),
    PublicMarketQuoteSpec(
        "CEA-NATIONAL",
        date(2026, 3, 31),
        Decimal("79.54"),
        Decimal(27800),
        Decimal("2211200.00"),
        CEA_MONTHLY_SOURCE,
        CEA_MONTHLY_METRIC,
        "https://overview.cneeex.com/c/2026-03-31/497493.shtml",
        _published(2026, 3, 31),
        Decimal("79.80"),
        Decimal("79.80"),
        Decimal("79.50"),
    ),
    PublicMarketQuoteSpec(
        "CEA-NATIONAL",
        date(2026, 4, 30),
        Decimal("79.50"),
        Decimal(232000),
        Decimal("18194500.00"),
        CEA_MONTHLY_SOURCE,
        CEA_MONTHLY_METRIC,
        "https://overview.cneeex.com/c/2026-04-30/497562.shtml",
        _published(2026, 4, 30),
        Decimal("79.50"),
        Decimal("80.00"),
        Decimal("79.30"),
    ),
    PublicMarketQuoteSpec(
        "CEA-NATIONAL",
        date(2026, 5, 29),
        Decimal("80.77"),
        Decimal(941184),
        Decimal("74444567.35"),
        CEA_MONTHLY_SOURCE,
        CEA_MONTHLY_METRIC,
        "https://overview.cneeex.com/c/2026-05-29/497617.shtml",
        _published(2026, 5, 29),
        Decimal("80.30"),
        Decimal("83.00"),
        Decimal("80.30"),
    ),
    PublicMarketQuoteSpec(
        "CEA-NATIONAL",
        date(2026, 6, 30),
        Decimal("83.34"),
        Decimal(169500),
        Decimal("14126800.00"),
        CEA_MONTHLY_SOURCE,
        CEA_MONTHLY_METRIC,
        "https://overview.cneeex.com/c/2026-06-30/497696.shtml",
        _published(2026, 6, 30),
        Decimal("83.15"),
        Decimal("83.60"),
        Decimal("83.00"),
    ),
    PublicMarketQuoteSpec(
        "CEA-NATIONAL",
        date(2026, 7, 31),
        Decimal("98.59"),
        Decimal(1251806),
        Decimal("109770473.40"),
        CEA_MONTHLY_SOURCE,
        CEA_MONTHLY_METRIC,
        "https://overview.cneeex.com/c/2026-07-31/498094.shtml",
        _published(2026, 7, 31),
        Decimal("97.50"),
        Decimal("99.50"),
        Decimal("97.50"),
    ),
    PublicMarketQuoteSpec(
        "CEA-NATIONAL",
        date(2026, 8, 14),
        Decimal("98.21"),
        Decimal(724197),
        Decimal("68962438.00"),
        CEA_MONTHLY_SOURCE,
        CEA_MONTHLY_METRIC,
        "https://overview.cneeex.com/c/2026-08-14/498134.shtml",
        _published(2026, 8, 14),
        Decimal("98.80"),
        Decimal("98.80"),
        Decimal("98.00"),
    ),
    # CCER: the source reports an average price, not an OHLC close.
    PublicMarketQuoteSpec(
        "CCER-NATIONAL",
        date(2026, 1, 30),
        Decimal("84.00"),
        Decimal(10000),
        Decimal("840000.00"),
        CCER_MONTHLY_SOURCE,
        CCER_MONTHLY_METRIC,
        CCER_DAILY_URL,
        _published(2026, 1, 30),
    ),
    PublicMarketQuoteSpec(
        "CCER-NATIONAL",
        date(2026, 2, 27),
        Decimal("87.22"),
        Decimal(244),
        Decimal("21280.50"),
        CCER_MONTHLY_SOURCE,
        CCER_MONTHLY_METRIC,
        CCER_DAILY_URL,
        _published(2026, 2, 27),
    ),
    PublicMarketQuoteSpec(
        "CCER-NATIONAL",
        date(2026, 3, 31),
        Decimal("84.60"),
        Decimal(100000),
        Decimal("8460000.00"),
        CCER_MONTHLY_SOURCE,
        CCER_MONTHLY_METRIC,
        CCER_DAILY_URL,
        _published(2026, 3, 31),
    ),
    PublicMarketQuoteSpec(
        "CCER-NATIONAL",
        date(2026, 4, 30),
        Decimal("84.23"),
        Decimal(118100),
        Decimal("9947197.00"),
        CCER_MONTHLY_SOURCE,
        CCER_MONTHLY_METRIC,
        CCER_DAILY_URL,
        _published(2026, 4, 30),
    ),
    PublicMarketQuoteSpec(
        "CCER-NATIONAL",
        date(2026, 5, 29),
        Decimal("83.54"),
        Decimal(30042),
        Decimal("2509636.27"),
        CCER_MONTHLY_SOURCE,
        CCER_MONTHLY_METRIC,
        CCER_DAILY_URL,
        _published(2026, 5, 29),
    ),
    PublicMarketQuoteSpec(
        "CCER-NATIONAL",
        date(2026, 6, 30),
        Decimal("83.36"),
        Decimal(70000),
        Decimal("5835500.00"),
        CCER_MONTHLY_SOURCE,
        CCER_MONTHLY_METRIC,
        CCER_DAILY_URL,
        _published(2026, 6, 30),
    ),
    PublicMarketQuoteSpec(
        "CCER-NATIONAL",
        date(2026, 7, 31),
        Decimal("94.92"),
        Decimal(367751),
        Decimal("34906700.94"),
        CCER_MONTHLY_SOURCE,
        CCER_MONTHLY_METRIC,
        CCER_DAILY_URL,
        _published(2026, 7, 31),
    ),
    PublicMarketQuoteSpec(
        "CCER-NATIONAL",
        date(2026, 8, 21),
        Decimal("96.34"),
        Decimal(184148),
        Decimal("17739930.00"),
        CCER_MONTHLY_SOURCE,
        CCER_MONTHLY_METRIC,
        CCER_DAILY_URL,
        _published(2026, 8, 21),
    ),
    # Green certificates: official monthly standalone-trade average for power
    # generated in 2025. Volume is the same-vintage standalone-trade volume.
    PublicMarketQuoteSpec(
        "GREEN-CERTIFICATE-CN",
        date(2026, 1, 31),
        Decimal("5.51"),
        Decimal(61880000),
        None,
        GREEN_CERTIFICATE_MONTHLY_SOURCE,
        GREEN_CERTIFICATE_MONTHLY_METRIC,
        "https://www.nea.gov.cn/20260305/f7d78bfc2f0f4566b56260a1b2bea008/c.html",
        _published(2026, 2, 14),
    ),
    PublicMarketQuoteSpec(
        "GREEN-CERTIFICATE-CN",
        date(2026, 2, 28),
        Decimal("5.90"),
        Decimal(38310000),
        None,
        GREEN_CERTIFICATE_MONTHLY_SOURCE,
        GREEN_CERTIFICATE_MONTHLY_METRIC,
        "https://www.nea.gov.cn/20260319/2710b019b1d84563a80f9a0b7da1fb8b/c.html",
        _published(2026, 3, 19),
    ),
    PublicMarketQuoteSpec(
        "GREEN-CERTIFICATE-CN",
        date(2026, 3, 31),
        Decimal("5.95"),
        Decimal(22280000),
        None,
        GREEN_CERTIFICATE_MONTHLY_SOURCE,
        GREEN_CERTIFICATE_MONTHLY_METRIC,
        "https://www.nea.gov.cn/20260424/73af87686f2a4a088bb6075d57452717/c.html",
        _published(2026, 4, 24),
    ),
    PublicMarketQuoteSpec(
        "GREEN-CERTIFICATE-CN",
        date(2026, 4, 30),
        Decimal("4.63"),
        Decimal(35120000),
        None,
        GREEN_CERTIFICATE_MONTHLY_SOURCE,
        GREEN_CERTIFICATE_MONTHLY_METRIC,
        "https://www.nea.gov.cn/20260602/a7e494c0ee274b839b9febc63b74d861/c.html",
        _published(2026, 6, 2),
    ),
    PublicMarketQuoteSpec(
        "GREEN-CERTIFICATE-CN",
        date(2026, 5, 31),
        Decimal("4.31"),
        Decimal(18190000),
        None,
        GREEN_CERTIFICATE_MONTHLY_SOURCE,
        GREEN_CERTIFICATE_MONTHLY_METRIC,
        "https://obor.nea.gov.cn/detail/22979.html",
        _published(2026, 7, 7),
    ),
    PublicMarketQuoteSpec(
        "GREEN-CERTIFICATE-CN",
        date(2026, 6, 30),
        Decimal("4.05"),
        Decimal(28160000),
        None,
        GREEN_CERTIFICATE_MONTHLY_SOURCE,
        GREEN_CERTIFICATE_MONTHLY_METRIC,
        "https://www.nea.gov.cn/20260724/d35b8a39fb724572b3d3ce3cbed9d4e9/c.html",
        _published(2026, 7, 24),
    ),
)
