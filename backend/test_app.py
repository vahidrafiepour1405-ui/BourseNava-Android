import app


def test_as_number_preserves_zero_volume():
    assert app.as_number("0") == 0.0


def test_as_number_rejects_invalid_values():
    assert app.as_number("N/A") is None
    assert app.as_number(None) is None


def test_rows_from_payload_reads_tsetmc_style_object():
    payload = {"data": [{"symbol": "فملی", "lastPrice": "1200"}]}
    rows = app.rows_from_payload(payload)
    assert len(rows) == 1
    assert rows[0]["symbol"] == "فملی"


def test_quote_uses_real_price_and_zero_volume():
    result = app.quote_from_row("فملی", {
        "symbol": "فملی",
        "lastPrice": "1200",
        "volume": "0",
        "source": "TSETMC_CDN",
    })
    assert result["status"] == "LIVE"
    assert result["last_price"] == 1200.0
    assert result["volume"] == 0.0
    assert result["source"] == "TSETMC_CDN"
    assert result["signal"] == "WAIT"


def test_quote_rejects_missing_price():
    result = app.quote_from_row("وبملت", {
        "symbol": "وبملت",
        "volume": "100",
        "source": "TSETMC_CDN",
    })
    assert result["status"] == "INSUFFICIENT_DATA"
    assert "last_price" not in result


def test_health_response_is_stable():
    result = app.health()
    assert result["status"] == "ok"
    assert result["service"] == "boursenava-api"
    assert "time_utc" in result
