package com.chatbot.newsviet.data.model

import com.google.gson.annotations.SerializedName
import java.time.LocalDate

/**
 * ChatRequest — DTO gửi đến API
 */
data class ChatRequest(
    val question: String,
    @SerializedName("top_k")
    val topK: Int = 3,
    @SerializedName("data_source")
    val dataSource: String = "news",
    @SerializedName("conversation_context")
    val conversationContext: String? = null
)

/**
 * SearchResult — Một kết quả tìm kiếm
 */
data class SearchResult(
    @SerializedName("chunk_text")
    val chunkText: String,
    @SerializedName("similarity_score")
    val similarityScore: Float,
    @SerializedName("vector_score")
    val vectorScore: Float? = null,
    @SerializedName("keyword_score")
    val keywordScore: Float? = null,
    @SerializedName("article_title")
    val articleTitle: String,
    @SerializedName("article_source")
    val articleSource: String,
    @SerializedName("article_link")
    val articleLink: String = "",
    @SerializedName("published_date")
    val publishedDate: String? = null
)

/**
 * ChatResponse — Response từ API
 */
data class ChatResponse(
    val question: String,
    val answer: String,
    val sources: List<SearchResult>,
    @SerializedName("total_chunks_searched")
    val totalChunksSearched: Int,
    @SerializedName("needs_clarification")
    val needsClarification: Boolean = false
)

