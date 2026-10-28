package ir.boursenava.app

import android.app.Activity
import android.os.Bundle
import android.graphics.Color
import android.view.Gravity
import android.view.ViewGroup
import android.widget.*
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import kotlin.concurrent.thread

class MainActivity : Activity() {
    private val apiBase = "https://boursenava-api.onrender.com"
    private lateinit var status: TextView
    private lateinit var list: LinearLayout
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val root = LinearLayout(this).apply { orientation=LinearLayout.VERTICAL; setPadding(24,28,24,16); setBackgroundColor(Color.rgb(7,18,33)); layoutDirection=ViewGroup.LAYOUT_DIRECTION_RTL }
        root.addView(TextView(this).apply { text="بورس‌نوا"; textSize=28f; setTextColor(Color.WHITE); gravity=Gravity.RIGHT })
        root.addView(TextView(this).apply { text="تحلیل مشروط بورس ایران؛ بدون داده معتبر، بدون سیگنال ساختگی"; textSize=14f; setTextColor(Color.LTGRAY); gravity=Gravity.RIGHT; setPadding(0,8,0,14) })
        status=TextView(this).apply { text="وضعیت داده: هنوز بررسی نشده"; textSize=14f; setTextColor(Color.rgb(0,207,151)); gravity=Gravity.RIGHT; setPadding(0,8,0,12) }; root.addView(status)
        root.addView(Button(this).apply { text="بررسی دوباره"; setOnClickListener { load() } })
        val scroll=ScrollView(this); list=LinearLayout(this).apply { orientation=LinearLayout.VERTICAL }; scroll.addView(list); root.addView(scroll, LinearLayout.LayoutParams(-1,0,1f)); setContentView(root); load()
    }
    private fun load() {
        status.text="در حال دریافت وضعیت از سرور…"; list.removeAllViews()
        thread {
            try {
                val url=URL("$apiBase/api/signals?symbols="+URLEncoder.encode("فملی,وبملت,شپنا,شبندر,شتران", "UTF-8"))
                val c=(url.openConnection() as HttpURLConnection).apply { connectTimeout=10000; readTimeout=15000; requestMethod="GET" }
                val code=c.responseCode; val body=(if(code in 200..299)c.inputStream else c.errorStream).bufferedReader().use{it.readText()}; c.disconnect()
                val json=JSONObject(body)
                runOnUiThread {
                    status.text="منبع: ${json.optString("source","نامشخص")} | وضعیت: ${json.optString("status","نامشخص")}"
                    val arr=json.optJSONArray("signals")
                    if(arr==null || arr.length()==0) addCard("فعلاً سیگنال معتبر نداریم", json.optString("message","داده کافی برای اعلام ورود و خروج موجود نیست."))
                    else for(i in 0 until arr.length()) { val o=arr.getJSONObject(i); addCard(o.optString("symbol"), o.toString(2)) }
                }
            } catch(e:Exception) { runOnUiThread { status.text="اتصال به بک‌اند برقرار نشد"; addCard("داده در دسترس نیست", "آدرس API هنوز باید پس از استقرار بک‌اند تنظیم شود. برای جلوگیری از قیمت و سیگنال ساختگی، معامله‌ای پیشنهاد نمی‌شود.") } }
        }
    }
    private fun addCard(title:String, detail:String) { val t=TextView(this).apply { text="$title\n$detail"; textSize=15f; setTextColor(Color.WHITE); setPadding(16,18,16,18); setBackgroundColor(Color.rgb(16,34,54)); layoutDirection=ViewGroup.LAYOUT_DIRECTION_RTL }; val p=LinearLayout.LayoutParams(-1,-2); p.setMargins(0,8,0,8); list.addView(t,p) }
}