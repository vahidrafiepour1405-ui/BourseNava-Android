plugins { id("com.android.application"); id("org.jetbrains.kotlin.android") }

android {
    namespace = "ir.boursenava.app"
    compileSdk = 35
    defaultConfig { applicationId = "ir.boursenava.app"; minSdk = 26; targetSdk = 35; versionCode = 1; versionName = "1.0.0" }
}