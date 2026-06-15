package com.chatbot.newsviet.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.chatbot.newsviet.data.model.ChatResponse
import com.chatbot.newsviet.data.model.SearchResult
import com.chatbot.newsviet.data.repository.ChatRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.util.concurrent.atomic.AtomicLong

enum class ChatDataSource(
    val apiValue: String,
    val label: String,
    val inputHint: String
) {
    NEWS(
        apiValue = "news",
        label = "Tin tức",
        inputHint = "Hỏi gì đó về tin tức..."
    )
}

/**
 * Chat ViewModel — quản lý lịch sử chat cho tin tức.
 */
class ChatViewModel(
    private val repository: ChatRepository
) : ViewModel() {

    private val messageIdGenerator = AtomicLong(0)
    private val messageHistoryBySource = mutableMapOf(
        ChatDataSource.NEWS to emptyList<Message>()
    )
    private val pendingClarificationBySource = mutableMapOf<ChatDataSource, PendingClarification?>(
        ChatDataSource.NEWS to null
    )

    private val _uiState = MutableStateFlow(ChatUiState())
    val uiState: StateFlow<ChatUiState> = _uiState.asStateFlow()

    /**
     * Đổi nguồn dữ liệu đang được chọn trên giao diện chat.
     */
    fun setDataSource(source: ChatDataSource) {
        if (_uiState.value.selectedSource == source) return

        _uiState.update {
            it.copy(
                selectedSource = source,
                messages = messageHistoryBySource[source].orEmpty(),
                error = null
            )
        }
    }

    /**
     * Xóa lịch sử hội thoại hiện tại và đưa khung chat về trạng thái ban đầu.
     */
    fun resetChat() {
        val source = _uiState.value.selectedSource
        messageHistoryBySource[source] = emptyList()
        pendingClarificationBySource[source] = null
        _uiState.update { it.copy(messages = emptyList(), error = null) }
    }

    /**
     * Gửi câu hỏi của người dùng tới máy chủ chatbot.
     */
    fun sendMessage(question: String) {
        if (question.isBlank()) return

        val source = _uiState.value.selectedSource
        val pendingContext = pendingClarificationBySource[source]
        val conversationContext = pendingContext?.question

        addMessage(
            source = source,
            message = Message(
                id = nextMessageId(),
                text = question,
                isUser = true
            )
        )

        _uiState.update { it.copy(isLoading = true, error = null) }

        viewModelScope.launch {
            try {
                val result = repository.sendMessage(
                    question = question,
                    dataSource = source.apiValue,
                    conversationContext = conversationContext
                )

                result.onSuccess { response ->
                    pendingClarificationBySource[source] = if (response.needsClarification) {
                        PendingClarification(question = question)
                    } else {
                        null
                    }
                    addMessage(source = source, message = formatBotResponse(response))
                }

                result.onFailure {
                    val errorMsg = "Kết nối máy chủ thất bại. Vui lòng thử lại sau."
                    updateErrorForSource(source, errorMsg)
                    addMessage(
                        source = source,
                        message = Message(
                            id = nextMessageId(),
                            text = "⚠ $errorMsg",
                            isUser = false
                        )
                    )
                }
            } catch (_: Exception) {
                val errorMsg = "Có lỗi xảy ra trong quá trình xử lý yêu cầu."
                updateErrorForSource(source, errorMsg)
                addMessage(
                    source = source,
                    message = Message(
                        id = nextMessageId(),
                        text = "⚠ $errorMsg",
                        isUser = false
                    )
                )
            }

            _uiState.update { state ->
                if (state.selectedSource == source) {
                    state.copy(isLoading = false)
                } else {
                    state
                }
            }
        }
    }

    /**
     * Xóa thông báo lỗi đang hiển thị trên giao diện.
     */
    fun clearError() {
        _uiState.update { it.copy(error = null) }
    }

    /**
     * Cập nhật lỗi cho đúng nguồn dữ liệu đang sử dụng.
     */
    private fun updateErrorForSource(source: ChatDataSource, error: String) {
        _uiState.update { state ->
            if (state.selectedSource == source) {
                state.copy(error = error)
            } else {
                state
            }
        }
    }

    /**
     * Thêm một tin nhắn mới vào lịch sử hội thoại.
     */
    private fun addMessage(source: ChatDataSource, message: Message) {
        val updatedHistory = messageHistoryBySource[source].orEmpty() + message
        messageHistoryBySource[source] = updatedHistory

        _uiState.update { state ->
            if (state.selectedSource == source) {
                state.copy(messages = updatedHistory)
            } else {
                state
            }
        }
    }

    /**
     * Sinh mã định danh tăng dần cho tin nhắn mới.
     */
    private fun nextMessageId(): Long = messageIdGenerator.incrementAndGet()

    /**
     * Chuyển phản hồi API thành tin nhắn hiển thị trên giao diện.
     */
    private fun formatBotResponse(response: ChatResponse): Message {
        val safeAnswer = response.answer.takeIf { it.isNotBlank() }
            ?: "Hiện mình chưa biết câu trả lời dựa trên dữ liệu hiện có, bạn hãy hỏi câu hỏi khác."

        return Message(
            id = nextMessageId(),
            text = safeAnswer,
            isUser = false,
            sources = response.sources
        )
    }

    class Factory(
        private val repository: ChatRepository
    ) : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        /**
         * Mô tả chức năng của hàm trong luồng xử lý Android.
         */
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            if (modelClass.isAssignableFrom(ChatViewModel::class.java)) {
                return ChatViewModel(repository) as T
            }
            throw IllegalArgumentException("Unknown ViewModel class")
        }
    }
}

data class ChatUiState(
    val messages: List<Message> = emptyList(),
    val isLoading: Boolean = false,
    val error: String? = null,
    val selectedSource: ChatDataSource = ChatDataSource.NEWS
)

data class Message(
    val id: Long,
    val text: String,
    val isUser: Boolean,
    val sources: List<SearchResult>? = null
)

private data class PendingClarification(
    val question: String
)
