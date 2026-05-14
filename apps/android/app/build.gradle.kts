plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.chatbot.newsviet"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.chatbot.newsviet"
        minSdk = 24
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"

        val apiBaseUrlProp = (project.findProperty("API_BASE_URL") as String?)
            ?: "http://192.168.0.104:8000/"
        val apiBaseUrl = if (apiBaseUrlProp.endsWith('/')) apiBaseUrlProp else "$apiBaseUrlProp/"
        buildConfigField("String", "API_BASE_URL", "\"$apiBaseUrl\"")

        val fallbackApiBaseUrlProp = (project.findProperty("API_FALLBACK_BASE_URL") as String?)
            ?: "http://192.168.0.104:8000/"
        val fallbackApiBaseUrl = if (fallbackApiBaseUrlProp.endsWith('/')) fallbackApiBaseUrlProp else "$fallbackApiBaseUrlProp/"
        buildConfigField("String", "API_FALLBACK_BASE_URL", "\"$fallbackApiBaseUrl\"")
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    composeOptions {
        kotlinCompilerExtensionVersion = "1.5.5"
    }
}

dependencies {
    // Compose BOM — quản lý version tập trung
    val composeBom = platform("androidx.compose:compose-bom:2024.01.00")
    implementation(composeBom)

    // Compose UI
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")

    // Pin animation-core to match BOM — prevents KeyframesSpec NoSuchMethodError
    implementation("androidx.compose.animation:animation")
    implementation("androidx.compose.animation:animation-core")

    // Compose Activity
    implementation("androidx.activity:activity-compose:1.8.2")

    // Lifecycle (ViewModel) — MVVM Pattern
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.7.0")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.7.0")

    // Retrofit — API Client
    implementation("com.squareup.retrofit2:retrofit:2.9.0")
    implementation("com.squareup.retrofit2:converter-gson:2.9.0")
    implementation("com.squareup.okhttp3:logging-interceptor:4.12.0")

    // Coroutines
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")

    // AndroidX Core
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.appcompat:appcompat:1.6.1")

    // Debug tools
    debugImplementation("androidx.compose.ui:ui-tooling")
}
