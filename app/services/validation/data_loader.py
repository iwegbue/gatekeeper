"""
Data Loader — fetches OHLCV bars from yfinance and persists them to the DB.

Uses asyncio.to_thread so yfinance's synchronous calls don't block the event loop.
Returns a data_snapshot_id UUID that groups a set of bars fetched together.
"""

import asyncio
import logging
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# ── Symbol mapping ─────────────────────────────────────────────────────────────

YFINANCE_SYMBOL_MAP: dict[str, str] = {
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "USDJPY=X",
    "AUDUSD": "AUDUSD=X",
    "USDCAD": "USDCAD=X",
    "USDCHF": "USDCHF=X",
    "NZDUSD": "NZDUSD=X",
    "XAUUSD": "GC=F",
    "GOLD": "GC=F",
    "NQ": "NQ=F",
    "ES": "ES=F",
    "SPX": "^GSPC",
    "US30": "YM=F",
    "DAX": "^GDAXI",
    "FTSE": "^FTSE",
    "XAGUSD": "SI=F",
    "SILVER": "SI=F",
    "OIL": "CL=F",
    "USOIL": "CL=F",
}

# yfinance caps 1h data to 730 days (as of 2024)
TIMEFRAME_TO_YF_INTERVAL: dict[str, str] = {
    "1d": "1d",
    "4h": "1h",   # We fetch 1h and resample to 4h
    "1h": "1h",
    "15m": "15m",
}

YF_1H_MAX_DAYS = 730  # yfinance caps hourly data at ~730 days


class DataLoaderError(Exception):
    """Raised when we cannot fetch usable market data."""


# ── Sync fetch (runs in thread) ────────────────────────────────────────────────


def _fetch_ohlc_sync(yf_symbol: str, yf_interval: str, start: date, end: date) -> list[dict]:
    """
    Synchronous yfinance fetch. Returns a list of bar dicts with plain Python types.
    Must run in a thread (asyncio.to_thread).
    """
    import yfinance as yf  # imported here to avoid top-level import cost

    ticker = yf.Ticker(yf_symbol)
    df = ticker.history(
        start=start.isoformat(),
        end=end.isoformat(),
        interval=yf_interval,
        auto_adjust=True,
        prepost=False,
    )

    if df is None or df.empty:
        return []

    bars: list[dict] = []
    for ts, row in df.iterrows():
        # Convert pandas Timestamp → UTC-aware datetime
        if hasattr(ts, "to_pydatetime"):
            dt = ts.to_pydatetime()
        else:
            dt = datetime.fromisoformat(str(ts))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)

        volume = float(row.get("Volume", 0)) if row.get("Volume") is not None else None

        bars.append({
            "ts": dt,
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
            "volume": volume,
        })

    return bars


def _resample_to_4h(bars_1h: list[dict]) -> list[dict]:
    """
    Resample 1h bars into 4h bars using pure Python bucketing.
    Each 4h bucket starts at UTC hours 0, 4, 8, 12, 16, 20.
    Incomplete buckets (< 4 bars) are discarded.
    """
    if not bars_1h:
        return []

    from collections import defaultdict

    buckets: dict[datetime, list[dict]] = defaultdict(list)

    for bar in bars_1h:
        ts = bar["ts"]
        bucket_hour = (ts.hour // 4) * 4
        bucket_ts = ts.replace(hour=bucket_hour, minute=0, second=0, microsecond=0)
        buckets[bucket_ts].append(bar)

    result: list[dict] = []
    for bucket_ts in sorted(buckets):
        bucket_bars = buckets[bucket_ts]
        if len(bucket_bars) < 4:
            # Incomplete bucket — skip
            continue
        result.append({
            "ts": bucket_ts,
            "open": bucket_bars[0]["open"],
            "high": max(b["high"] for b in bucket_bars),
            "low": min(b["low"] for b in bucket_bars),
            "close": bucket_bars[-1]["close"],
            "volume": sum(b["volume"] or 0.0 for b in bucket_bars) or None,
        })

    return result


# ── Async public API ──────────────────────────────────────────────────────────


async def fetch_and_store_ohlc(
    db: AsyncSession,
    symbol: str,
    timeframe: str,
    start_date: date,
    end_date: date,
) -> uuid.UUID:
    """
    Fetch OHLCV bars for `symbol` / `timeframe` from yfinance and persist them to the DB.
    Returns the data_snapshot_id UUID that identifies this batch of bars.
    Raises DataLoaderError if no data was returned.
    """
    from app.models.ohlc_bar import OhlcBar  # local import to avoid circular refs

    symbol_upper = symbol.upper()
    yf_symbol = YFINANCE_SYMBOL_MAP.get(symbol_upper, symbol_upper)
    yf_interval = TIMEFRAME_TO_YF_INTERVAL.get(timeframe, timeframe)
    needs_resample = timeframe == "4h"

    # Warn if 1h range exceeds yfinance cap
    days_requested = (end_date - start_date).days
    if yf_interval == "1h" and days_requested > YF_1H_MAX_DAYS:
        logger.warning(
            "Requested %d days of 1h data for %s but yfinance caps at %d days. "
            "Data coverage may be incomplete.",
            days_requested, symbol, YF_1H_MAX_DAYS,
        )

    logger.info("Fetching %s/%s (%s → %s) from yfinance…", symbol, timeframe, start_date, end_date)

    bars = await asyncio.to_thread(_fetch_ohlc_sync, yf_symbol, yf_interval, start_date, end_date)

    if not bars:
        raise DataLoaderError(
            f"yfinance returned 0 bars for {symbol}/{timeframe} "
            f"({start_date} → {end_date}). "
            "Check that the symbol is supported and the date range is valid."
        )

    if needs_resample:
        bars = _resample_to_4h(bars)
        if not bars:
            raise DataLoaderError(
                f"4h resampling of {symbol} produced 0 complete buckets. "
                "Try a wider date range."
            )

    # Coverage check
    _check_coverage(bars, start_date, end_date, symbol, timeframe)

    snapshot_id = uuid.uuid4()
    db_bars = [
        OhlcBar(
            id=uuid.uuid4(),
            symbol=symbol_upper,
            timeframe=timeframe,
            ts=b["ts"],
            open=b["open"],
            high=b["high"],
            low=b["low"],
            close=b["close"],
            volume=b["volume"],
            data_snapshot_id=snapshot_id,
        )
        for b in bars
    ]
    db.add_all(db_bars)
    await db.flush()

    logger.info("Stored %d bars for %s/%s (snapshot %s)", len(bars), symbol, timeframe, snapshot_id)
    return snapshot_id


async def load_bars_for_snapshot(db: AsyncSession, data_snapshot_id: uuid.UUID) -> list[dict]:
    """
    Load all bars for a given snapshot, ordered by timestamp ascending.
    Returns plain dicts (not ORM objects) for use in the pure-Python replay engine.
    """
    from app.models.ohlc_bar import OhlcBar  # local import

    result = await db.execute(
        select(OhlcBar)
        .where(OhlcBar.data_snapshot_id == data_snapshot_id)
        .order_by(OhlcBar.ts.asc())
    )
    rows = result.scalars().all()
    return [
        {
            "ts": row.ts,
            "open": float(row.open),
            "high": float(row.high),
            "low": float(row.low),
            "close": float(row.close),
            "volume": float(row.volume) if row.volume is not None else None,
        }
        for row in rows
    ]


# ── Private helpers ────────────────────────────────────────────────────────────


def _check_coverage(bars: list[dict], start_date: date, end_date: date, symbol: str, timeframe: str) -> None:
    """Log a warning if coverage is significantly below expectation."""
    days_requested = max((end_date - start_date).days, 1)

    # Rough expected bar counts per day (excluding weekends/holidays)
    expected_bars_per_day = {
        "1d": 1,
        "4h": 6,
        "1h": 24,
        "15m": 96,
    }
    bars_per_day = expected_bars_per_day.get(timeframe, 1)
    # Assume ~70% trading days (accounts for weekends, holidays, FX closes)
    expected_total = int(days_requested * bars_per_day * 0.70)

    if expected_total > 0 and len(bars) < expected_total * 0.80:
        logger.warning(
            "Coverage warning: expected ~%d bars for %s/%s but got %d (%.0f%%). "
            "Data may be sparse for this symbol/period.",
            expected_total, symbol, timeframe, len(bars),
            100 * len(bars) / expected_total,
        )
