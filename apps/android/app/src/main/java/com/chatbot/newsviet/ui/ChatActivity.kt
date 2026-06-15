package com.chatbot.newsviet.ui

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import com.chatbot.newsviet.ChatApplication
import com.chatbot.newsviet.ui.theme.NewsVietChatbotTheme

/**
 * Chat Activity — Entry Point
 * Design Pattern: MVVM (Activity chỉ khởi tạo ViewModel và gọi setContent)
 *
 * Không chứa UI logic — toàn bộ UI được khai báo trong ChatScreen composable.
 */
class ChatActivity : ComponentActivity() {

    // Inject ViewModel thông qua Factory Pattern
    private val viewModel: ChatViewModel by viewModels {
        val app = application as ChatApplication
        ChatViewModel.Factory(app.chatRepository)
    }

    /**
     * Khởi tạo màn hình hoặc ứng dụng Android và gắn các phụ thuộc cần thiết.
     */
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            NewsVietChatbotTheme {
                ChatScreen(viewModel = viewModel)
            }
        }
    }
}
