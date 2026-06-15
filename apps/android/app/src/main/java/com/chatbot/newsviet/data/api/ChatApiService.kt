package com.chatbot.newsviet.data.api

import com.chatbot.newsviet.data.model.ChatRequest
import com.chatbot.newsviet.data.model.ChatResponse
import retrofit2.http.Body
import retrofit2.http.POST
import com.chatbot.newsviet.BuildConfig

/**
 * Retrofit API Service — Kết nối đến backend
 * Design Pattern: Repository Pattern + Retrofit
 */
interface ChatApiService {
    
    companion object {
        val BASE_URL: String = BuildConfig.API_BASE_URL
        val FALLBACK_BASE_URL: String = BuildConfig.API_FALLBACK_BASE_URL
    }

    /**
     * Gửi câu hỏi đến chatbot API
     *
     * Parameters:
     * - question: Câu hỏi của người dùng
     * - top_k: Số kết quả trả về
     * - data_source: Nguồn dữ liệu đang hỏi (news/documents)
     */
    @POST("api/chat")
    /**
     * Gửi câu hỏi của người dùng tới máy chủ chatbot.
     */
    suspend fun sendMessage(@Body request: ChatRequest): ChatResponse

}
