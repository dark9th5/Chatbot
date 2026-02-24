package com.chatbot.newsviet.ui

import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.chatbot.newsviet.ui.theme.*

/**
 * ChatScreen — Composable chính
 * Design Pattern: State Hoisting + Unidirectional Data Flow
 *
 * Screen chỉ nhận ViewModel, sub-composables nhận data + lambda.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(viewModel: ChatViewModel) {
    val uiState by viewModel.uiState.collectAsState()
    var inputText by remember { mutableStateOf("") }
    val listState = rememberLazyListState()

    // Auto-scroll khi có tin nhắn mới
    LaunchedEffect(uiState.messages.size) {
        if (uiState.messages.isNotEmpty()) {
            listState.animateScrollToItem(uiState.messages.size - 1)
        }
    }

    // Snackbar
    val snackbarHostState = remember { SnackbarHostState() }
    LaunchedEffect(uiState.error) {
        uiState.error?.let { msg ->
            snackbarHostState.showSnackbar(msg)
            viewModel.clearError()
        }
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        topBar = { ChatTopBar() },
        bottomBar = {
            ChatInputBar(
                inputText = inputText,
                isLoading = uiState.isLoading,
                onTextChange = { inputText = it },
                onSend = {
                    if (inputText.isNotBlank()) {
                        viewModel.sendMessage(inputText.trim())
                        inputText = ""
                    }
                }
            )
        },
        containerColor = Background
    ) { paddingValues ->
        if (uiState.messages.isEmpty()) {
            WelcomeScreen(
                modifier = Modifier.padding(paddingValues),
                onSuggestionClick = { suggestion ->
                    if (!uiState.isLoading) {
                        viewModel.sendMessage(suggestion)
                    }
                }
            )
        } else {
            LazyColumn(
                state = listState,
                modifier = Modifier
                    .fillMaxSize()
                    .padding(paddingValues),
                contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                items(uiState.messages, key = { it.id }) { message ->
                    AnimatedVisibility(
                        visible = true,
                        enter = slideInVertically(initialOffsetY = { 50 }) + fadeIn()
                    ) {
                        MessageBubble(message = message)
                    }
                }

                if (uiState.isLoading) {
                    item { TypingIndicator() }
                }
            }
        }
    }
}

// ============ Top Bar ============

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatTopBar() {
    TopAppBar(
        title = {
            Row(verticalAlignment = Alignment.CenterVertically) {
                // Avatar Bot
                Box(
                    modifier = Modifier
                        .size(40.dp)
                        .clip(CircleShape)
                        .background(
                            Brush.linearGradient(listOf(Primary, Secondary))
                        ),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(
                        imageVector = Icons.Default.AutoAwesome,
                        contentDescription = null,
                        tint = Color.White,
                        modifier = Modifier.size(22.dp)
                    )
                }
                Spacer(modifier = Modifier.width(12.dp))
                Column {
                    Text(
                        "Chatbot tin tức Việt Nam",
                        fontWeight = FontWeight.Bold,
                        fontSize = 17.sp,
                        color = TextOnPrimary
                    )
                    Text(
                        "● Đang hoạt động",
                        fontSize = 11.sp,
                        color = Success,
                        fontWeight = FontWeight.Medium
                    )
                }
            }
        },
        colors = TopAppBarDefaults.topAppBarColors(
            containerColor = PrimaryDark
        )
    )
}

// ============ Message Bubble ============

@Composable
fun MessageBubble(message: Message) {
    val isUser = message.isUser

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(
                start = if (isUser) 48.dp else 0.dp,
                end = if (isUser) 0.dp else 48.dp
            ),
        horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start
    ) {
        if (isUser) {
            // USER: Gradient bubble
            Box(
                modifier = Modifier
                    .shadow(
                        elevation = 4.dp,
                        shape = RoundedCornerShape(20.dp, 20.dp, 4.dp, 20.dp)
                    )
                    .clip(RoundedCornerShape(20.dp, 20.dp, 4.dp, 20.dp))
                    .background(
                        Brush.linearGradient(listOf(UserBubbleStart, UserBubbleEnd))
                    )
            ) {
                Text(
                    text = message.text,
                    modifier = Modifier.padding(14.dp),
                    color = TextOnPrimary,
                    fontSize = 15.sp,
                    lineHeight = 22.sp
                )
            }
        } else {
            // BOT: White card with subtle border
            Surface(
                shape = RoundedCornerShape(4.dp, 20.dp, 20.dp, 20.dp),
                color = BotBubble,
                tonalElevation = 1.dp,
                shadowElevation = 2.dp,
                border = androidx.compose.foundation.BorderStroke(
                    0.5.dp, BotBubbleBorder
                )
            ) {
                Column(modifier = Modifier.padding(14.dp)) {
                    Text(
                        text = message.text,
                        color = TextPrimary,
                        fontSize = 15.sp,
                        lineHeight = 22.sp
                    )

                    // Confidence badge
                    if (message.confidence > 0) {
                        Spacer(modifier = Modifier.height(8.dp))
                        val pct = (message.confidence * 100).toInt()
                        val badgeColor = when {
                            pct >= 70 -> Success
                            pct >= 40 -> Accent
                            else -> Error
                        }
                        Surface(
                            shape = RoundedCornerShape(12.dp),
                            color = badgeColor.copy(alpha = 0.12f)
                        ) {
                            Text(
                                text = "🎯 $pct%",
                                modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
                                color = badgeColor,
                                fontSize = 12.sp,
                                fontWeight = FontWeight.SemiBold
                            )
                        }
                    }
                }
            }
        }
    }
}

// ============ Input Bar ============

@Composable
fun ChatInputBar(
    inputText: String,
    isLoading: Boolean,
    onTextChange: (String) -> Unit,
    onSend: () -> Unit
) {
    Surface(
        tonalElevation = 3.dp,
        shadowElevation = 8.dp,
        color = SurfaceLight
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 10.dp),
            verticalAlignment = Alignment.Bottom
        ) {
            OutlinedTextField(
                value = inputText,
                onValueChange = onTextChange,
                modifier = Modifier.weight(1f),
                placeholder = {
                    Text("Hỏi gì đó về tin tức...", color = TextMuted)
                },
                shape = RoundedCornerShape(24.dp),
                maxLines = 4,
                enabled = !isLoading,
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = Primary,
                    unfocusedBorderColor = Divider,
                    focusedContainerColor = SurfaceDim,
                    unfocusedContainerColor = SurfaceDim
                )
            )

            Spacer(modifier = Modifier.width(10.dp))

            // Send Button — Gradient
            val canSend = !isLoading && inputText.isNotBlank()
            Box(
                modifier = Modifier
                    .size(50.dp)
                    .clip(CircleShape)
                    .background(
                        if (canSend) Brush.linearGradient(listOf(Primary, Secondary))
                        else Brush.linearGradient(listOf(Divider, Divider))
                    ),
                contentAlignment = Alignment.Center
            ) {
                IconButton(
                    onClick = onSend,
                    enabled = canSend,
                    modifier = Modifier.size(50.dp)
                ) {
                    if (isLoading) {
                        // Custom rotation animation — avoids Material3 keyframes API crash
                        val infiniteTransition = rememberInfiniteTransition(label = "loading")
                        val rotation by infiniteTransition.animateFloat(
                            initialValue = 0f,
                            targetValue = 360f,
                            animationSpec = infiniteRepeatable(
                                animation = tween(durationMillis = 1000, easing = LinearEasing),
                                repeatMode = RepeatMode.Restart
                            ),
                            label = "rotate"
                        )
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.Send,
                            contentDescription = "Đang gửi",
                            tint = TextOnPrimary,
                            modifier = Modifier
                                .size(22.dp)
                                .graphicsLayer { rotationZ = rotation }
                        )
                    } else {
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.Send,
                            contentDescription = "Gửi",
                            tint = if (canSend) TextOnPrimary else TextMuted,
                            modifier = Modifier.size(22.dp)
                        )
                    }
                }
            }
        }
    }
}

// ============ Welcome Screen ============

@Composable
fun WelcomeScreen(
    modifier: Modifier = Modifier,
    onSuggestionClick: (String) -> Unit
) {
    Box(
        modifier = modifier.fillMaxSize(),
        contentAlignment = Alignment.Center
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            modifier = Modifier.padding(32.dp)
        ) {
            // Animated bot icon
            Box(
                modifier = Modifier
                    .size(80.dp)
                    .clip(CircleShape)
                    .background(
                        Brush.linearGradient(listOf(Primary, Secondary))
                    ),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = Icons.Default.AutoAwesome,
                    contentDescription = null,
                    tint = Color.White,
                    modifier = Modifier.size(40.dp)
                )
            }

            Spacer(modifier = Modifier.height(24.dp))

            Text(
                "Xin chào! 👋",
                fontWeight = FontWeight.ExtraBold,
                fontSize = 26.sp,
                color = TextPrimary
            )

            Spacer(modifier = Modifier.height(8.dp))

            Text(
                "Tôi là Chatbot tin tức Việt Nam\nHỏi tôi bất cứ gì về tin tức!",
                fontSize = 15.sp,
                color = TextSecondary,
                textAlign = TextAlign.Center,
                lineHeight = 24.sp
            )

            Spacer(modifier = Modifier.height(32.dp))

            // Suggestion chips
            val suggestions = listOf(
                "Thời tiết Hà Nội",
                "Giá vàng hôm nay",
                "Kết quả trận bóng hôm nay"
            )
            suggestions.forEach { text ->
                SuggestionChip(
                    onClick = { onSuggestionClick(text) },
                    label = {
                        Text(text, fontWeight = FontWeight.Medium)
                    },
                    modifier = Modifier.padding(vertical = 4.dp),
                    border = SuggestionChipDefaults.suggestionChipBorder(
                        borderColor = PrimaryLight
                    ),
                    colors = SuggestionChipDefaults.suggestionChipColors(
                        containerColor = PrimaryContainer.copy(alpha = 0.5f),
                        labelColor = Primary
                    )
                )
            }
        }
    }
}

// ============ Typing Indicator ============

@Composable
fun TypingIndicator() {
    val infiniteTransition = rememberInfiniteTransition(label = "typing")

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(end = 48.dp),
        horizontalArrangement = Arrangement.Start
    ) {
        Surface(
            shape = RoundedCornerShape(4.dp, 20.dp, 20.dp, 20.dp),
            color = BotBubble,
            border = androidx.compose.foundation.BorderStroke(0.5.dp, BotBubbleBorder),
            shadowElevation = 2.dp
        ) {
            Row(
                modifier = Modifier.padding(horizontal = 18.dp, vertical = 14.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                repeat(3) { index ->
                    val alpha by infiniteTransition.animateFloat(
                        initialValue = 0.3f,
                        targetValue = 1f,
                        animationSpec = infiniteRepeatable(
                            animation = tween(600, delayMillis = index * 200),
                            repeatMode = RepeatMode.Reverse
                        ),
                        label = "dot$index"
                    )
                    Box(
                        modifier = Modifier
                            .size(8.dp)
                            .clip(CircleShape)
                            .background(Primary.copy(alpha = alpha))
                    )
                }
                Spacer(modifier = Modifier.width(6.dp))
                Text(
                    "Đang tìm kiếm...",
                    fontSize = 13.sp,
                    color = TextMuted,
                    fontWeight = FontWeight.Medium
                )
            }
        }
    }
}
