package com.chatbot.newsviet

import android.app.Application
import com.chatbot.newsviet.data.api.ChatApiService
import com.chatbot.newsviet.data.repository.ChatRepository
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

/**
 * Application class — Dependency Injection thủ công
 * Design Pattern: Singleton (Application instance duy nhất)
 *
 * Khởi tạo Retrofit, ApiService, Repository một lần duy nhất.
 * Các Activity/ViewModel truy cập qua: (application as ChatApplication).chatRepository
 */
class ChatApplication : Application() {

    lateinit var chatRepository: ChatRepository
        private set

    override fun onCreate() {
        super.onCreate()

        // Logging Interceptor (debug)
        val loggingInterceptor = HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.BODY
        }

        // OkHttp Client
        val httpClient = OkHttpClient.Builder()
            .addInterceptor { chain ->
                val req = chain.request().newBuilder()
                    .addHeader("ngrok-skip-browser-warning", "true")
                    .build()
                chain.proceed(req)
            }
            .addInterceptor(loggingInterceptor)
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(60, TimeUnit.SECONDS)    // Model AI cần thời gian xử lý
            .writeTimeout(30, TimeUnit.SECONDS)
            .build()

        // API Services (primary + fallback)
        val primaryApiService = createApiService(
            baseUrl = ChatApiService.BASE_URL,
            httpClient = httpClient
        )
        val fallbackApiService = createApiService(
            baseUrl = ChatApiService.FALLBACK_BASE_URL,
            httpClient = httpClient
        )

        // Repository (Singleton trong Application scope)
        chatRepository = ChatRepository(primaryApiService, fallbackApiService)
    }

    private fun createApiService(baseUrl: String, httpClient: OkHttpClient): ChatApiService {
        val retrofit = Retrofit.Builder()
            .baseUrl(baseUrl)
            .client(httpClient)
            .addConverterFactory(GsonConverterFactory.create())
            .build()

        return retrofit.create(ChatApiService::class.java)
    }
}
