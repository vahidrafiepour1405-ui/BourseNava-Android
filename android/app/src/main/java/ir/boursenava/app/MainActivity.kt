package ir.boursenava.app

import android.app.Activity
import android.os.Bundle
import android.graphics.Color
import android.view.Gravity
import android.view.ViewGroup
import android.widget.*
import java.net.HttpURLConnection
import java.net.URL
import java.text.DecimalFormat
import kotlin.concurrent.thread

class MainActivity : Activity() {
    private data class Quote(val symbol: String, val name: String, val last: String, val close: String, val change: String, val volume: String)
    private val marketUrl = "https://old.tsetmc.com/tsev2/data/MarketWatchInit.aspx?h=0&r=0"
    private lateinit var status: TextView
    private lateinit var list: LinearLayout
    private lateinit var refresh: Button
    private lateinit var search: EditText
    private var allQuotes: List<Quote> = emptyList()
    private val fmt = DecimalFormat("#,###")

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(18, 22, 18, 12)
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
            text = "دیده‌بان بازار ایران • جست‌وجو میان نمادهای دریافتی از TSETMC"
            textSize = 14f
            setTextColor(Color.LTGRAY)
            gravity = Gravity.RIGHT
            setPadding(0, 7, 0, 10)
        })
        status = TextView(this).apply {
            text = "برای دریافت فهرست بازار در حال اتصال…"
            textSize = 14f
            setTextColor(Color.rgb(255, 190, 70))
            gravity = Gravity.RIGHT
            setPadding(0, 6, 0, 8)
        }
        root.addView(status)
        search = EditText(this).apply {
            hint = "جست‌وجوی نماد یا نام شرکت، مثلاً فملی"
            textSize = 15f
            singleLine = true
            setTextColor(Color.WHITE)
            setHintTextColor(Color.LTGRAY)
            setPadding(12, 4, 12, 4)
            setBackgroundColor(Color.rgb(24, 43, 63))
        }
        root.addView(search, LinearLayout.LayoutParams(-1, -2))
        search.addTextChangedListener(object : android.text.TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) { render(s?.toString().orEmpty()) }
            override fun afterTextChanged(s: android.text.Editable?) {}
        })
        refresh = Button(this).apply {
            text = "دریافت / به‌روزرسانی کل بازار"
            setOnClickListener { loadMarket() }
        }
        root.addView(refresh)
        val scroll = ScrollView(this)
        list = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        scroll.addView(list)
        root.addView(scroll, LinearLayout.LayoutParams(-1, 0, 1f))
        setContentView(root)
        loadMarket()
    }

    private fun fetchText(url: String): String {
        val conn = (URL(url).openConnection() as HttpURLConnection).apply {
            connectTimeout = 15000
            readTimeout = 25000
            requestMethod = "GET"
            setRequestProperty("User-Agent", "Mozilla/5.0 (Linux; Android 16) AppleWebKit/537.36 Chrome/130 Mobile Safari/537.36")
            setRequestProperty("Accept", "*/*")
            setRequestProperty("Referer", "https://www.tsetmc.com/")
        }
        try {
            val code = conn.responseCode
            val stream = if (code in 200..299) conn.inputStream else conn.errorStream
            val body = stream.bufferedReader(Charsets.UTF_8).use { it.readText() }
            if (code !in 200..299) throw IllegalStateException("HTTP " + code)
            return body
        } finally { conn.disconnect() }
    }

    private fun parseMarket(body: String): List<Quote> {
        val sections = body.split("@")
        if (sections.size < 3) throw IllegalStateException("ساختار پاسخ بازار شناخته نشد")
        val parsed = sections[2].split(';').mapNotNull { row ->
            val c = row.trim().split(',')
            if (c.size < 14) return@mapNotNull null
            val symbol = c[2].trim()
            if (symbol.isBlank()) return@mapNotNull null
            val name = c[3].trim()
            val last = c[7].toDoubleOrNull()
            val close = c[6].toDoubleOrNull()
            val yesterday = c[13].toDoubleOrNull()
            if (last == null && close == null) return@mapNotNull null
            val price = last ?: close!!
            val pct = if (yesterday != null && yesterday > 0) String.format(java.util.Locale.US, "%.2f", (price / yesterday - 1.0) * 100.0) + "%" else "—"
            val volume = c.getOrNull(9)?.toDoubleOrNull()?.let { fmt.format(it) } ?: "—"
            Quote(symbol, name, last?.let { fmt.format(it) } ?: "—", close?.let { fmt.format(it) } ?: "—", pct, volume)
        }
        return parsed.distinctBy { it.symbol }.sortedBy { it.symbol }
    }

    private fun loadMarket() {
        refresh.isEnabled = false
        status.text = "در حال دریافت فهرست بازار از TSETMC…"
        list.removeAllViews()
        thread {
            try {
                val data = parseMarket(fetchText(marketUrl))
                runOnUiThread {
                    allQuotes = data
                    status.text = if (data.isNotEmpty()) "دریافت موفق: " + data.size + " نماد/ابزار از منبع بازار • برای جست‌وجو تایپ کن" else "منبع پاسخ داد اما داده قابل‌استفاده نداشت."
                    status.setTextColor(if (data.isNotEmpty()) Color.rgb(0, 207, 151) else Color.rgb(255, 170, 90))
                    render(search.text.toString())
                    refresh.isEnabled = true
                }
            } catch (e: Exception) {
                runOnUiThread {
                    allQuotes = emptyList()
                    status.text = "اتصال زنده برقرار نشد (" + e.javaClass.simpleName + "). داده ساختگی نمایش داده نمی‌شود؛ دوباره تلاش کن."
                    status.setTextColor(Color.rgb(255, 170, 90))
                    list.removeAllViews()
                    refresh.isEnabled = true
                }
            }
        }
    }

    private fun render(query: String) {
        if (!::list.isInitialized) return
        list.removeAllViews()
        if (allQuotes.isEmpty()) return
        val q = query.trim()
        val matched = if (q.isEmpty()) allQuotes.take(100) else allQuotes.filter {
            it.symbol.contains(q, ignoreCase = true) || it.name.contains(q, ignoreCase = true)
        }.take(250)
        if (q.isEmpty()) {
            list.addView(TextView(this).apply {
                text = "۱۰۰ ردیف اول نمایش داده می‌شود؛ برای یافتن هر نماد، نام آن را در کادر بالا وارد کن. فهرست کامل برای جست‌وجو در حافظه است."
                setTextColor(Color.LTGRAY)
                textSize = 12f
                gravity = Gravity.RIGHT
                setPadding(4, 8, 4, 8)
            })
        }
        if (matched.isEmpty()) {
            list.addView(TextView(this).apply {
                text = "نمادی با این عبارت در داده دریافتی پیدا نشد."
                setTextColor(Color.WHITE)
                gravity = Gravity.RIGHT
                setPadding(8, 18, 8, 18)
            })
        } else matched.forEach { addCard(it) }
    }

    private fun addCard(q: Quote) {
        val card = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(14, 12, 14, 12)
            setBackgroundColor(Color.rgb(16, 34, 54))
            layoutDirection = ViewGroup.LAYOUT_DIRECTION_RTL
        }
        card.addView(TextView(this).apply {
            text = if (q.name.isBlank()) q.symbol else q.symbol + " • " + q.name
            textSize = 17f
            setTextColor(Color.rgb(242, 190, 75))
            gravity = Gravity.RIGHT
        })
        card.addView(TextView(this).apply {
            text = "آخرین معامله: " + q.last + " ریال\nپایانی: " + q.close + " ریال  |  تغییر آخرین قیمت نسبت به دیروز: " + q.change + "\nحجم: " + q.volume + "\nمنبع: TSETMC MarketWatch • قیمت بازار، نه سیگنال خرید/فروش"
            textSize = 13f
            setTextColor(Color.WHITE)
            gravity = Gravity.RIGHT
            setPadding(0, 7, 0, 0)
        })
        val p = LinearLayout.LayoutParams(-1, -2)
        p.setMargins(0, 6, 0, 6)
        list.addView(card, p)
    }
}
