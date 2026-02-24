from etl.text_summarizer import TextRankSummarizer

text = """
Giá vàng miếng SJC sáng nay được các doanh nghiệp niêm yết ở mức 78,5 triệu đồng/lượng mua vào và 80,5 triệu đồng/lượng bán ra, không thay đổi so với hôm qua. Tuy nhiên, giá vàng nhẫn trơn 24K lại tiếp tục lập đỉnh mới. Cụ thể, Công ty SJC niêm yết giá vàng nhẫn ở mức 76,8 - 78,2 triệu đồng/lượng (mua vào - bán ra), tăng 200.000 đồng mỗi lượng so với chốt phiên trước. Tại Bảo Tín Minh Châu, giá vàng nhẫn tròn trơn thương hiệu Vàng Rồng Thăng Long cũng được điều chỉnh tăng lên mức 77 - 78,4 triệu đồng/lượng. Đà tăng của giá vàng trong nước diễn ra trong bối cảnh giá vàng thế giới cũng đang có xu hướng đi lên mạnh mẽ. Giới chuyên gia dự báo giá vàng có thể sẽ tiếp tục biến động khó lường trong thời gian tới do những bất ổn địa chính trị. Người dân được khuyến cáo nên thận trọng khi quyết định mua thời điểm này.
"""

print("📝 TESTING TEXTRANK SUMMARIZER (EXTRACTIVE)")
print("="*50)
print(f"Bản gốc ({len(text.split())} từ):")
print(text)
print("-" * 50)

summarizer = TextRankSummarizer()
summary = summarizer.summarize(text, top_k=2)

print("\n✨ Bản Tóm Tắt (2 câu quan trọng nhất):")
print(summary)
print("="*50)
