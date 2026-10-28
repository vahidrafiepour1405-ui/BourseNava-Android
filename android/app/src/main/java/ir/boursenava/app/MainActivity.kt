package ir.boursenava.app

import android.app.Activity
import android.os.Bundle
import android.graphics.Color
import android.view.Gravity
import android.view.ViewGroup
import android.widget.*
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.text.DecimalFormat
import kotlin.concurrent.thread

class MainActivity : Activity() {
    private val base = "https://cdn.tsetmc.com/api"
    private val symbols = listOf("فملی", "وبملت", "شپنا", "شبندر", "شتران")
    private lateinit var status: TextView
    private lateinit var list: LinearLayout
    private lateinit var refresh: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(20, 26, 20, 14)
            setBackgroundColor(Color.rgb(7, 18, 33))
            layoutDirection = ViewGroup.LAYOUT_DIRECTION_RTL
        }
        root.addView(TextView(this).apply {
            text = "بورس‌نوا"
            textSize = 30f
            setTextColor(Color.rgb(242, 190, 75))
            gravity = Gravity.RIGHT
        })
        root.addView(TextView(this).apply {
            text = "قیمت‌های بازار به‌صورت آنلاین از منبع TSETMC دریافت می‌شوند."
            textSize = 14f
            setTextColor(Color.LTGRAY)
            gravity = Gravity.RIGHT
            setPadding(0, 8, 0, 12)
        })
        status = TextView(this).apply {
            text = "آماده بررسی اتصال…"
            textSize = 14f
            setTextColor(Color.rgb(0, 207, 151))
            gravity = Gravity.RIGHT
            setPadding(0, 8, 0, 12)
        }
        root.addView(status)
        refresh = Button(this).apply {
            text = "به‌روزرسانی قیمت‌ها"
            setOnClickListener { load() }
        }
        root.addView(refresh)
        val scroll = ScrollView(this)
        list = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        scroll.addView(list)
        root.addView(scroll, LinearLayout.LayoutParams(-1, 0, 1f))
        setContentView(root)
        load()
    }

    private fun request(path: String): JSONObject {
        val conn = (URL("$"+"base/$"+"path").openConnection() as HttpURLConnection).apply {
            connectTimeout = 10000
            readTimeout = 12000
            requestMethod = "GET"
            setRequestProperty("User-Agent", "Mozilla/5.0 BourseNava Android")
            setRequestProperty("Accept", "application/json")
            setRequestProperty("Referer", "https://www.tsetmc.com/")
        }
        try {
            val code = conn.responseCode
            val stream = if (code in 200..299) conn.inputStream else conn.errorStream
            val body = stream.bufferedReader().use { it.readText() }
            if (code !in 200..299) throw IllegalStateException("HTTP $"+"code")
            return JSONObject(body)
        } finally {
            conn.disconnect()
        }
    }

    private fun num(obj: JSONObject, vararg keys: String): Double? {
        for (key in keys) {
            val value = obj.opt(key)
            val parsed = when (value) {
                is Number -> value.toDouble()
                is String -> value.toDoubleOrNull()
                else -> null
            }
            if (parsed != null && parsed > 0) return parsed
        }
        return null
    }

    private fun load() {
        refresh.isEnabled = false
        status.text = "در حال بررسی منبع و دریافت قیمت‌ها…"
        list.removeAllViews()
        thread {
            var good = 0
            val rows = mutableListOf<Pair<String, String>>()
            for (symbol in symbols) {
                try {
                    val encoded = URLEncoder.encode(symbol, "UTF-8")
                    val search = request("Instrument/GetInstrumentSearch/$"+"encoded")
                    val results = search.optJSONArray("instrumentSearch") ?: JSONArray()
                    var match: JSONObject? = null
                    for (i in 0 until results.length()) {
                        val item = results.optJSONObject(i) ?: continue
                        if (item.optString("lVal18AFC").trim() == symbol) {
                            match = item
                            break
                        }
                    }
                    if (match == null && results.length() > 0) match = results.optJSONObject(0)
                    val code = match?.opt("insCode")?.toString()
                    if (code.isNullOrBlank()) {
                        rows.add(symbol to "اطلاعات این نماد فعلاً از منبع دریافت نشد.")
                        continue
                    }
                    val closing = request("ClosingPrice/GetClosingPriceInfo/$"+"code")
                    val quote = closing.optJSONObject("closingPriceInfo") ?: closing
                    val last = num(quote, "pDrCotVal", "pl", "lastPrice")
                    val close = num(quote, "pClosing", "pc", "closingPrice")
                    val prev = num(quote, "priceYesterday", "py", "yesterdayPrice")
                    val volume = num(quote, "qTotTran5J", "zTotTran", "volume")
                    val price = last ?: close
                    if (price == null) {
                        rows.add(symbol to "قیمت معتبر در پاسخ منبع موجود نبود.")
                        continue
                    }
                    good++
                    val change = if (prev != null) " | تغییر: " + DecimalFormat("0.00").format((price / prev - 1) * 100) + "٪" else ""
                    val volumeText = volume?.let { " | حجم: " + DecimalFormat("#,###").format(it) } ?: ""
                    val detail = "آخرین قیمت: " + DecimalFormat("#,###").format(price) + " ریال" + change + volumeText + "\nمنبع: TSETMC API\nوضعیت: قیمت دریافت شد؛ سیگنال تأییدشده در این نسخه فعال نیست."
                    rows.add(symbol to detail)
                } catch (e: Exception) {
                    rows.add(symbol to "دریافت اطلاعات از منبع آنلاین ناموفق بود؛ برای تازه‌سازی دوباره تلاش کن.")
                }
            }
            runOnUiThread {
                status.text = if (good == symbols.size) "وضعیت: دریافت قیمت برای همه نمادها موفق بود" else if (good > 0) "وضعیت: داده جزئی ($"+"good از $"+"{symbols.size} نماد)" else "وضعیت: منبع در دسترس نیست؛ بعداً دوباره امتحان کن"
                status.setTextColor(if (good > 0) Color.rgb(0, 207, 151) else Color.rgb(255, 170, 90))
                rows.forEach { (title, detail) -> addCard(title, detail) }
                refresh.isEnabled = true
            }
        }
    }

    private fun addCard(title: String, detail: String) {
        val card = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(16, 14, 16, 14)
            setBackgroundColor(Color.rgb(16, 34, 54))
            layoutDirection = ViewGroup.LAYOUT_DIRECTION_RTL
        }
        card.addView(TextView(this).apply {
            text = title
            textSize = 19f
            setTextColor(Color.rgb(242, 190, 75))
            gravity = Gravity.RIGHT
        })
        card.addView(TextView(this).apply {
            text = detail
            textSize = 14f
            setTextColor(Color.WHITE)
            gravity = Gravity.RIGHT
            setPadding(0, 8, 0, 0)
        })
        val p = LinearLayout.LayoutParams(-1, -2)
        p.setMargins(0, 8, 0, 8)
        list.addView(card, p)
    }
}
