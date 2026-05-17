package com.chatbot.newsviet.data.repository

import com.chatbot.newsviet.data.api.ChatApiService
import com.chatbot.newsviet.data.model.ChatRequest
import com.chatbot.newsviet.data.model.ChatResponse
import java.time.LocalDate

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
     * Gửi tin nhắn với hỗ trợ lọc
     *
     * Parameters:
     * - question: Câu hỏi từ user
     * - category: Danh mục (optional)
     * - fromDate: Ngày bắt đầu (optional)
     * - toDate: Ngày kết thúc (optional)
     *
     * Returns:
     * - Result<ChatResponse>: Success hoặc Failure
     */
    suspend fun sendMessage(
        question: String,
        category: String? = null,
        fromDate: LocalDate? = null,
        toDate: LocalDate? = null
    ): Result<ChatResponse> = try {
        // Convert LocalDate to YYYY-MM-DD string
        val fromDateStr = fromDate?.toString()
        val toDateStr = toDate?.toString()
        
        // Build request
        val request = ChatRequest(
            question = question,
            topK = 3,
            category = category,
            fromDate = fromDateStr,
            toDate = toDateStr
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

    /**
     * Lấy danh sách danh mục từ server
     */
    suspend fun getCategories(): Result<List<String>> = try {
        val response = try {
            primaryService.getCategories()
        } catch (e: Exception) {
            fallbackService.getCategories()
        }
        Result.success(response.categories)
    } catch (e: Exception) {
        Result.failure(e)
    }
}
