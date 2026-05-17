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
    val category: String? = null,
    @SerializedName("from_date")
    val fromDate: String? = null,  // Format: YYYY-MM-DD
    @SerializedName("to_date")
    val toDate: String? = null     // Format: YYYY-MM-DD
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
    val articleLink: String = ""
)

/**
 * ChatResponse — Response từ API
 */
data class ChatResponse(
    val question: String,
    val answer: String,
    val confidence: Double,
    val sources: List<SearchResult>,
    @SerializedName("total_chunks_searched")
    val totalChunksSearched: Int
)

/**
 * CategoriesResponse — Danh sách danh mục từ server
 */
data class CategoriesResponse(
    val categories: List<String>,
    val count: Int
)
