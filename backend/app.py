from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import httpx

app = FastAPI(title="BourseNava API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["GET"], allow_headers=["*"])
BASE = "https://cdn.tsetmc.com/api"
HEADERS = {"User-Agent": "Mozilla/5.0 BourseNava/0.1 read-only"}

@app.get("/health")
def health():
    return {"status": "ok", "service": "boursenava-api", "time_utc": datetime.now(timezone.utc).isoformat()}

@app.get("/api/status")
def status():
    return {"status": "INSUFFICIENT_DATA", "source": "TSETMC REST API", "note": "اتصال زنده و ساختار پاسخ هنوز در این استقرار تأیید نشده است.", "checked_at_utc": datetime.now(timezone.utc).isoformat()}

@app.get("/api/signals")
async def signals(symbols: str = "فملی,وبملت,شپنا,شبندر,شتران"):
    # Fail closed: no guessed quotes or fabricated trading levels.
    return {"source": "TSETMC REST API", "status": "INSUFFICIENT_DATA", "generated_at_utc": datetime.now(timezone.utc).isoformat(), "signals": [], "message": "تا زمان تأیید داده معتبر و کافی، نقطه ورود/خروج تولید نمی‌شود.", "requested_symbols": [s.strip() for s in symbols.split(",") if s.strip()]}
