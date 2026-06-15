package com.chatbot.newsviet.data.repository

import com.chatbot.newsviet.data.api.ChatApiService
import com.chatbot.newsviet.data.model.ChatRequest
import com.chatbot.newsviet.data.model.ChatResponse

/**
 * ChatRepository — Repository Pattern
 * Handles API communication with fallback strategy
 * Design Pattern: Repository + Result wrapper
 */
class ChatRepository(
    private val primaryService: ChatApiService,
    private val fallbackService: ChatApiService
) {

    /**
     * Gửi câu hỏi của người dùng tới máy chủ chatbot.
     */
    suspend fun sendMessage(
        question: String,
        dataSource: String,
        conversationContext: String? = null
    ): Result<ChatResponse> = try {
        val request = ChatRequest(
            question = question,
            topK = 3,
            dataSource = dataSource,
            conversationContext = conversationContext
        )

        // Try primary service
        val response = try {
            primaryService.sendMessage(request)
        } catch (e: Exception) {
            // Fallback to secondary service
            fallbackService.sendMessage(request)
        }

        Result.success(response)
    } catch (e: Exception) {
        Result.failure(e)
    }
}
