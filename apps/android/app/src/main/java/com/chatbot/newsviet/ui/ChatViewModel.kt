package com.chatbot.newsviet.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.chatbot.newsviet.data.model.ChatResponse
import com.chatbot.newsviet.data.repository.ChatRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.util.concurrent.atomic.AtomicLong

/**
 * Chat ViewModel — MVVM Pattern + Unidirectional Data Flow
 * Design Pattern: Observer (StateFlow thông báo Compose recompose)
 *
 * Chịu trách nhiệm:
 * - Quản lý UI State (single source of truth)
 * - Gọi Repository để gửi/nhận tin nhắn
 * - Quản lý filter state (category, date range)
 * - Expose state qua StateFlow (Compose-friendly)
 */
class ChatViewModel(
    private val repository: ChatRepository
) : ViewModel() {

    private val messageIdGenerator = AtomicLong(0)

    // ============ UI State (Single Source of Truth) ============

    private val _uiState = MutableStateFlow(ChatUiState())
    val uiState: StateFlow<ChatUiState> = _uiState.asStateFlow()

    init {
        // Load categories on initialization
        viewModelScope.launch {
            val result = repository.getCategories()
            result.onSuccess { categories ->
                _uiState.update { it.copy(availableCategories = categories) }
            }
            result.onFailure { e ->
                println("Failed to load categories: ${e.message}")
            }
        }
    }

    // ============ User Actions ============

    /**
     * Gửi câu hỏi đến chatbot với filters
     */
    fun sendMessage(question: String) {
        if (question.isBlank()) return

        val currentState = _uiState.value

        // Thêm tin nhắn user kèm theo bộ lọc
        addMessage(Message(
            id = nextMessageId(), 
            text = question, 
            isUser = true,
            categoryFilter = currentState.selectedCategory,
            fromDateFilter = currentState.fromDate,
            toDateFilter = currentState.toDate
        ))

        // Cập nhật loading state và reset filters (chỉ áp dụng cho tin nhắn hiện tại)
        _uiState.update { it.copy(
            isLoading = true, 
            error = null,
            selectedCategory = null,
            fromDate = null,
            toDate = null
        ) }

        viewModelScope.launch {
            try {
                // Sử dụng currentState để gửi API, vì _uiState đã bị reset bộ lọc
                val result = repository.sendMessage(
                    question = question,
                    category = currentState.selectedCategory,
                    fromDate = currentState.fromDate,
                    toDate = currentState.toDate
                )

                result.onSuccess { response ->
                    val botMessage = formatBotResponse(response)
                    addMessage(botMessage)
                }

                result.onFailure { _ ->
                    val errorMsg = "Kết nối máy chủ thất bại. Vui lòng thử lại sau."
                    _uiState.update { it.copy(error = errorMsg) }
                    addMessage(Message(id = nextMessageId(), text = "⚠ $errorMsg", isUser = false))
                }
            } catch (exception: Exception) {
                val errorMsg = "Có lỗi xảy ra trong quá trình xử lý yêu cầu."
                _uiState.update { it.copy(error = errorMsg) }
                addMessage(Message(id = nextMessageId(), text = "⚠ $errorMsg", isUser = false))
            }

            _uiState.update { it.copy(isLoading = false) }
        }
    }

    /**
     * Cập nhật danh mục được chọn
     */
    fun setCategory(category: String?) {
        _uiState.update { it.copy(selectedCategory = category) }
    }

    /**
     * Cập nhật ngày bắt đầu
     */
    fun setFromDate(date: LocalDate?) {
        _uiState.update { it.copy(fromDate = date) }
    }

    /**
     * Cập nhật ngày kết thúc
     */
    fun setToDate(date: LocalDate?) {
        _uiState.update { it.copy(toDate = date) }
    }

    /**
     * Reset tất cả filters
     */
    fun resetFilters() {
        _uiState.update { it.copy(
            selectedCategory = null,
            fromDate = null,
            toDate = null
        ) }
    }

    /**
     * Xóa thông báo lỗi
     */
    fun clearError() {
        _uiState.update { it.copy(error = null) }
    }

    // ============ Private Helpers ============

    private fun addMessage(message: Message) {
        _uiState.update { state ->
            state.copy(messages = state.messages + message)
        }
    }

    private fun nextMessageId(): Long = messageIdGenerator.incrementAndGet()

    private fun formatBotResponse(response: ChatResponse): Message {
        val sb = StringBuilder()

        // Câu trả lời chính (đã được format sẵn từ backend)
        val safeAnswer = response.answer.takeIf { it.isNotBlank() }
            ?: "Hiện mình chưa biết câu trả lời dựa trên dữ liệu hiện có, bạn hãy hỏi câu hỏi khác."
        sb.append(safeAnswer)

        // Độ tin cậy
        val confidenceValue = response.confidence
        val confidencePercent = (confidenceValue * 100).toInt()
        sb.append("\n\n🎯 Độ tin cậy: $confidencePercent%")

        return Message(
            id = nextMessageId(),
            text = sb.toString(),
            isUser = false,
            confidence = confidenceValue,
            sources = response.sources
        )
    }

    // ============ Factory (DI) ============

    /**
     * Factory Method — inject Repository vào ViewModel
     */
    class Factory(
        private val repository: ChatRepository
    ) : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            if (modelClass.isAssignableFrom(ChatViewModel::class.java)) {
                return ChatViewModel(repository) as T
            }
            throw IllegalArgumentException("Unknown ViewModel class")
        }
    }
}

// ============ UI State & Data Classes ============

/**
 * Immutable UI State — Single Source of Truth cho toàn bộ màn hình Chat
 * Design Pattern: Unidirectional Data Flow
 */
data class ChatUiState(
    val messages: List<Message> = emptyList(),
    val isLoading: Boolean = false,
    val error: String? = null,
    val selectedCategory: String? = null,
    val fromDate: LocalDate? = null,
    val toDate: LocalDate? = null,
    val availableCategories: List<String> = emptyList()
)

/**
 * Data class đại diện cho 1 tin nhắn
 */
data class Message(
    val id: Long,
    val text: String,
    val isUser: Boolean,
    val confidence: Double = 0.0,
    val categoryFilter: String? = null,
    val fromDateFilter: LocalDate? = null,
    val toDateFilter: LocalDate? = null,
    val sources: List<com.chatbot.newsviet.data.model.SearchResult>? = null
)
