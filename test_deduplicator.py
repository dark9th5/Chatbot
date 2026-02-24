from etl.deduplicator import JaccardDeduplicator
from etl.models import Article
from datetime import datetime

t = datetime.now()

doc1 = Article(title="Bài 1", link="1", content="Hôm nay giá vàng SJC tăng mạnh lên mốc 80 triệu đồng một lượng. Người dân đổ xô đi mua vàng tích trữ.", summary="", source="test", category="test", published_date=t)
doc2 = Article(title="Bài 2", link="2", content="Theo ghi nhận hôm nay, giá vàng SJC tăng mạnh lên mốc 80 triệu đồng một lượng. Rất đông người dân đổ xô đi mua vàng để tích trữ.", summary="", source="test", category="test", published_date=t)
doc3 = Article(title="Bài 3", link="3", content="Dự báo thời tiết Hà Nội hôm nay có mưa rào và dông vài nơi, nhiệt độ giảm sâu.", summary="", source="test", category="test", published_date=t)

print("🧪 TESTING DATA DEDUPLICATION")
dedup = JaccardDeduplicator(threshold=0.6)

print(f"\n1. Xử lý bài 1: {doc1.title}")
is_dup = dedup.is_duplicate(doc1)
print(f"   -> Bị trùng lặp? {is_dup}")

print(f"\n2. Xử lý bài 2 (Copy bài 1 thêm vài chữ): {doc2.title}")
is_dup = dedup.is_duplicate(doc2)
print(f"   -> Bị trùng lặp? {is_dup}")

print(f"\n3. Xử lý bài 3 (Khác hoàn toàn): {doc3.title}")
is_dup = dedup.is_duplicate(doc3)
print(f"   -> Bị trùng lặp? {is_dup}")
