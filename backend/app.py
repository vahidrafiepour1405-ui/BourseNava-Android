from datetime import datetime, timezone
from typing import Any
import os
import re

import httpx
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="BourseNava API", version="1.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

MAJID_BASE = "https://api.majidapi.ir/bourse"
DEFAULT_SYMBOLS = ["فملی", "وبملت", "شپنا", "شبندر", "شتران"]
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; BourseNava/1.1; read-only)",
    "Accept": "application/json,text/plain,*/*",
}
SYMBOL_KEYS = ("symbol", "ticker", "namad", "lVal18AFC", "نماد", "نام نماد")
PRICE_KEYS = (
    "lastPrice", "last_price", "last", "price", "close", "closingPrice",
    "pClosing", "pDrCotVal", "closing_price", "قیمت", "قیمت پایانی",
    "آخرین قیمت", "آخرین",
)
VOLUME_KEYS = ("volume", "tradeVolume", "qTotTran5J", "حجم", "حجم معاملات")


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def as_number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        # API may return comma-separated Persian-market numbers.
        value = str(value).replace(",", "").replace("٬", "").strip()
        n = float(value)
        return n if n >= 0 else None
    except (TypeError, ValueError):
        return None


def rows_from_payload(payload: Any) -> list:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in ("data", "result", "stocks", "items", "results", "list", "تعداد"):
            value = payload.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
            if isinstance(value, dict):
                nested = rows_from_payload(value)
                if nested:
                    return nested
        # Some APIs return one stock object directly.
        if any(k in payload for k in SYMBOL_KEYS):
            return [payload]
    return []


def first_value(row: dict, keys: tuple):
    for key in keys:
        if row.get(key) not in (None, ""):
            return row.get(key)
    # Case-insensitive fallback for English field names.
    lowered = {str(k).lower(): v for k, v in row.items()}
    for key in keys:
        value = lowered.get(key.lower())
        if value not in (None, ""):
            return value
    return None


def find_row(rows: list, symbol: str):
    for row in rows:
        raw = first_value(row, SYMBOL_KEYS)
        if raw is not None and str(raw).strip() == symbol:
            return row
    return None


async def majid_get(client: httpx.AsyncClient, action: str, **params):
    token = os.getenv("MAJIDAPI_TOKEN", "").strip()
    if not token:
        raise RuntimeError("MAJIDAPI_TOKEN is not configured")
    query = {"action": action, "token": token}
    query.update(params)
    response = await client.get(MAJID_BASE, params=query)
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict) and (
        payload.get("success") is False or payload.get("status") in ("error", "failed")
    ):
        raise ValueError("MajidAPI returned an error response")
    return payload


async def load_market(client: httpx.AsyncClient):
    # The documented stocks action contains the market symbol list and quote fields.
    payload = await majid_get(client, "stocks")
    rows = rows_from_payload(payload)
    if not rows:
        # Try the provider's documented last-trading-day action as a compatible fallback.
        payload = await majid_get(client, "lastTradingDay")
        rows = rows_from_payload(payload)
    if not rows:
        raise ValueError("MajidAPI response contained no recognizable stock rows")
    return rows


def quote_from_row(symbol: str, row: dict) -> dict:
    price = as_number(first_value(row, PRICE_KEYS))
    volume = as_number(first_value(row, VOLUME_KEYS))
    if price is None:
        return {
            "symbol": symbol,
            "status": "INSUFFICIENT_DATA",
            "source": "MajidAPI",
            "message": "نماد پیدا شد اما فیلد قیمت قابل تشخیص در پاسخ منبع وجود ندارد.",
        }
    return {
        "symbol": symbol,
        "status": "LIVE",
        "source": "MajidAPI",
        "last_price": price,
        "volume": volume,
        "data_checked_at_utc": now_utc(),
        "signal": "WAIT",
        "analysis": "قیمت از منبع دریافت شده؛ برای سیگنال خرید یا فروش، داده تاریخی و معیارهای تأییدشده لازم است.",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "boursenava-api",
        "time_utc": now_utc(),
        "market_source": "MajidAPI",
    }


@app.get("/api/status")
async def status():
    if not os.getenv("MAJIDAPI_TOKEN", "").strip():
        return {
            "status": "OFFLINE",
            "source": "MajidAPI",
            "reachable": False,
            "checked_at_utc": now_utc(),
            "note": "توکن در تنظیمات سرور تعریف نشده است.",
        }
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=15.0, follow_redirects=True) as client:
            rows = await load_market(client)
        return {
            "status": "LIVE",
            "source": "MajidAPI",
            "reachable": True,
            "rows_received": len(rows),
            "checked_at_utc": now_utc(),
            "note": "پاسخ بازار از API دریافت شد؛ زنده بودن قیمت هر نماد جداگانه بررسی می‌شود.",
        }
    except httpx.HTTPStatusError as exc:
        return {
            "status": "OFFLINE",
            "source": "MajidAPI",
            "reachable": False,
            "http_status": exc.response.status_code,
            "checked_at_utc": now_utc(),
            "note": "API درخواست را نپذیرفت؛ توکن، دسترسی یا وضعیت سرویس باید بررسی شود.",
        }
    except Exception as exc:
        return {
            "status": "OFFLINE",
            "source": "MajidAPI",
            "reachable": False,
            "error_type": type(exc).__name__,
            "checked_at_utc": now_utc(),
            "note": "داده معتبر از API دریافت نشد؛ هیچ قیمت ساختگی نمایش داده نمی‌شود.",
        }


@app.get("/api/signals")
async def signals(symbols: str = Query(",".join(DEFAULT_SYMBOLS), max_length=500)):
    requested = list(dict.fromkeys(s.strip() for s in symbols.split(",") if s.strip()))[:20]
    if not requested:
        requested = DEFAULT_SYMBOLS
    if any(not re.fullmatch(r"[\u0600-\u06FFa-zA-Z0-9_]+", s) for s in requested):
        return {"source": "MajidAPI", "status": "INSUFFICIENT_DATA", "signals": [], "message": "نام نماد نامعتبر است."}
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=20.0, follow_redirects=True) as client:
            rows = await load_market(client)
        results = []
        for symbol in requested:
            row = find_row(rows, symbol)
            if row is None:
                results.append({
                    "symbol": symbol,
                    "status": "INSUFFICIENT_DATA",
                    "source": "MajidAPI",
                    "signal": "WAIT",
                    "message": "نماد در پاسخ منبع پیدا نشد؛ قیمت حدس زده نمی‌شود.",
                })
            else:
                results.append(quote_from_row(symbol, row))
        live_count = sum(1 for item in results if item["status"] == "LIVE")
        overall = "LIVE" if live_count == len(results) else ("PARTIAL" if live_count else "INSUFFICIENT_DATA")
        return {
            "source": "MajidAPI",
            "status": overall,
            "generated_at_utc": now_utc(),
            "live_count": live_count,
            "requested_count": len(results),
            "signals": results,
            "message": "قیمت‌ها در صورت دریافت از منبع نمایش داده می‌شوند؛ این نسخه هنوز سیگنال خرید/فروش تأییدشده تولید نمی‌کند.",
        }
    except httpx.HTTPStatusError as exc:
        return {
            "source": "MajidAPI",
            "status": "OFFLINE",
            "generated_at_utc": now_utc(),
            "signals": [],
            "message": "API درخواست را نپذیرفت؛ قیمت یا سیگنال ساختگی تولید نشده است.",
            "http_status": exc.response.status_code,
        }
    except Exception as exc:
        return {
            "source": "MajidAPI",
            "status": "OFFLINE",
            "generated_at_utc": now_utc(),
            "signals": [],
            "message": "داده معتبر از API دریافت نشد؛ هیچ قیمت یا سیگنال ساختگی تولید نشده است.",
            "error_type": type(exc).__name__,
        }
