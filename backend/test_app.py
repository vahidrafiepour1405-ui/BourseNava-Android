import asyncio
from unittest.mock import AsyncMock

import pytest

import app


def test_number_preserves_zero_volume():
    assert app.number({"qTotTran5J": "0"}, "qTotTran5J") == 0.0


def test_number_skips_invalid_values():
    assert app.number({"a": "N/A", "b": "123"}, "a", "b") == 123.0


@pytest.mark.asyncio
async def test_invalid_symbol_does_not_call_source():
    client = AsyncMock()
    result = await app.quote_for_symbol(client, "فملی/بد")
    assert result["status"] == "INSUFFICIENT_DATA"
    client.get.assert_not_called()


@pytest.mark.asyncio
async def test_symbol_search_does_not_return_another_company(monkeypatch):
    async def fake_get_json(client, path):
        return {"instrumentSearch": [
            {"lVal18AFC": "نماددیگر", "insCode": "123"}
        ]}
    monkeypatch.setattr(app, "get_json", fake_get_json)
    result = await app.quote_for_symbol(object(), "فملی")
    assert result["status"] == "INSUFFICIENT_DATA"
    assert result["symbol"] == "فملی"


@pytest.mark.asyncio
async def test_quote_uses_zero_volume_and_exact_symbol(monkeypatch):
    async def fake_get_json(client, path):
        if path.startswith("Instrument/"):
            return {"instrumentSearch": [
                {"lVal18AFC": "فملی", "lVal30": "ملی", "insCode": "987"}
            ]}
        return {"closingPriceInfo": {
            "pDrCotVal": "1200", "pClosing": "1190",
            "priceYesterday": "1000", "qTotTran5J": "0"
        }}
    monkeypatch.setattr(app, "get_json", fake_get_json)
    result = await app.quote_for_symbol(object(), "فملی")
    assert result["status"] == "LIVE"
    assert result["last_price_rial"] == 1200.0
    assert result["volume"] == 0.0
    assert result["change_percent"] == 20.0
    assert result["signal"] == "WAIT"


def test_health_response_is_stable():
    result = app.health()
    assert result["status"] == "ok"
    assert result["service"] == "boursenava-api"
    assert "time_utc" in result
