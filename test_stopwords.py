from nlp_processor import clean_query

queries = [
    "Làm ơn cho tôi hỏi giá vàng hôm nay là bao nhiêu vậy nhỉ?",
    "thông tin chi tiết về doanh thu của vingroup thế nào",
    "có phải ông phạm nhật vượng đã mua thêm máy bay mới nhất hay không"
]

print("🧹 KIỂM THỬ BỘ LỌC STOPWORDS")
for q in queries:
    print(f"\n❓ Gốc: {q}")
    cleaned = clean_query(q)
    print(f"✅ Sạch: {cleaned}")
