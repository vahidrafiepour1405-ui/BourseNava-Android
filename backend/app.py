from datetime import datetime, timezone
from typing import Any
import asyncio
import re

import httpx
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="BourseNava API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

BASE = "https://cdn.tsetmc.com/api"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; BourseNava/1.0; read-only)",
    "Accept": "application/json,text/plain,*/*",
    "Referer": "https://www.tsetmc.com/",
}
DEFAULT_SYMBOLS = ["فملی", "وبملت", "شپنا", "شبندر", "شتران"]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def number(obj: dict, *keys: str):
    for key in keys:
        value = obj.get(key)
        if value is not None:
            try:
                n = float(value)
                if n > 0:
                    return n
            except (TypeError, ValueError):
                continue
    return None


async def get_json(client: httpx.AsyncClient, path: str) -> Any:
    response = await client.get(f"{BASE}/{path.lstrip('/')}")
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, (dict, list)):
        raise ValueError("Unexpected API response")
    return data


async def quote_for_symbol(client: httpx.AsyncClient, symbol: str) -> dict:
    safe_symbol = symbol.strip()[:32]
    if not safe_symbol or not re.fullmatch(r"[\u0600-\u06FFa-zA-Z0-9_]+", safe_symbol):
        return {"symbol": safe_symbol, "status": "INSUFFICIENT_DATA", "message": "نام نماد نامعتبر است."}

    search_data = await get_json(client, f"Instrument/GetInstrumentSearch/{safe_symbol}")
    results = search_data.get("instrumentSearch", []) if isinstance(search_data, dict) else []
    if isinstance(results, dict):
        results = results.get("instrumentSearch", [])
    if not isinstance(results, list):
        results = []
    match = next(
        (item for item in results if isinstance(item, dict) and
         str(item.get("lVal18AFC", "")).strip() == safe_symbol),
        None,
    )
    if match is None and results:
        match = next((item for item in results if isinstance(item, dict)), None)
    if not match:
        return {"symbol": safe_symbol, "status": "INSUFFICIENT_DATA", "message": "نماد در پاسخ منبع پیدا نشد."}

    ins_code = match.get("insCode") or match.get("insCode2") or match.get("insCode3")
    if not ins_code:
        return {"symbol": safe_symbol, "status": "INSUFFICIENT_DATA", "message": "شناسه نماد از منبع دریافت نشد."}

    raw = await get_json(client, f"ClosingPrice/GetClosingPriceInfo/{ins_code}")
    quote = raw.get("closingPriceInfo", {}) if isinstance(raw, dict) else {}
    if not isinstance(quote, dict) or not quote:
        return {"symbol": safe_symbol, "status": "INSUFFICIENT_DATA", "message": "اطلاعات قیمت در پاسخ منبع موجود نیست."}

    last = number(quote, "pDrCotVal", "pl", "lastPrice")
    close = number(quote, "pClosing", "pc", "closingPrice")
    prev = number(quote, "priceYesterday", "py", "yesterdayPrice")
    volume = number(quote, "qTotTran5J", "zTotTran", "volume")
    if last is None and close is None:
        return {"symbol": safe_symbol, "status": "INSUFFICIENT_DATA", "message": "قیمت معتبر از منبع دریافت نشد."}

    price = last or close
    change_pct = round(((price / prev) - 1) * 100, 2) if prev else None
    return {
        "symbol": str(match.get("lVal18AFC") or safe_symbol),
        "name": match.get("lVal30"),
        "ins_code": str(ins_code),
        "status": "LIVE",
        "source": "TSETMC REST API (read-only)",
        "last_price_rial": price,
        "closing_price_rial": close,
        "previous_close_rial": prev,
        "change_percent": change_pct,
        "volume": volume,
        "data_checked_at_utc": now_utc(),
        "analysis": "قیمت دریافت شده است؛ برای پیشنهاد ورود/خروج، داده تاریخی کافی و آزمون‌شده لازم است.",
        "signal": "WAIT",
    }


@app.get("/health")
def health():
    return {"status": "ok", "service": "boursenava-api", "time_utc": now_utc()}


@app.get("/api/status")
async def status():
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=10.0, follow_redirects=True) as client:
            data = await get_json(client, "Instrument/GetInstrumentSearch/%D9%81%D9%85%D9%84%DB%8C")
        rows = data.get("instrumentSearch", []) if isinstance(data, dict) else []
        reachable = isinstance(rows, list) and len(rows) > 0
        return {
            "status": "LIVE" if reachable else "INSUFFICIENT_DATA",
            "source": "TSETMC REST API",
            "reachable": reachable,
            "checked_at_utc": now_utc(),
            "note": "وضعیت دسترسی منبع؛ زنده بودن قیمت هر نماد جداگانه بررسی می‌شود.",
        }
    except Exception as exc:
        return {
            "status": "OFFLINE",
            "source": "TSETMC REST API",
            "reachable": False,
            "checked_at_utc": now_utc(),
            "error_type": type(exc).__name__,
            "note": "منبع بازار از سرور قابل دریافت نیست؛ داده ساختگی نمایش داده نمی‌شود.",
        }


@app.get("/api/signals")
async def signals(symbols: str = Query(",".join(DEFAULT_SYMBOLS), max_length=500)):
    requested = list(dict.fromkeys(s.strip() for s in symbols.split(",") if s.strip()))[:20]
    if not requested:
        requested = DEFAULT_SYMBOLS
    results = []
    failures = 0
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=12.0, follow_redirects=True) as client:
            for symbol in requested:
                try:
                    results.append(await quote_for_symbol(client, symbol))
                except Exception as exc:
                    failures += 1
                    results.append({
                        "symbol": symbol,
                        "status": "OFFLINE",
                        "signal": "WAIT",
                        "message": "داده معتبر این نماد دریافت نشد؛ از اعلام قیمت یا سیگنال حدسی خودداری شد.",
                        "error_type": type(exc).__name__,
                    })
                await asyncio.sleep(0.15)
    except Exception as exc:
        return {
            "source": "TSETMC REST API",
            "status": "OFFLINE",
            "generated_at_utc": now_utc(),
            "signals": [],
            "message": "اتصال به منبع بازار برقرار نشد؛ هیچ داده یا سیگنال ساختگی تولید نشده است.",
            "error_type": type(exc).__name__,
        }

    live_count = sum(1 for item in results if item.get("status") == "LIVE")
    overall = "LIVE" if live_count == len(results) and results else (
        "PARTIAL" if live_count else ("OFFLINE" if failures else "INSUFFICIENT_DATA")
    )
    return {
        "source": "TSETMC REST API (read-only)",
        "status": overall,
        "generated_at_utc": now_utc(),
        "live_count": live_count,
        "requested_count": len(results),
        "signals": results,
        "message": "قیمت‌های دریافتی، داده بازار هستند نه توصیه خرید یا فروش. فعلاً سیگنال ورود/خروج تأییدشده تولید نمی‌شود.",
    }
