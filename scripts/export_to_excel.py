import os
import pandas as pd
from qdrant_client import QdrantClient
from dotenv import load_dotenv

def export_qdrant_to_excel(output_file="qdrant_report.xlsx", limit=100):
    """
    Xuất dữ liệu từ Qdrant Local ra file Excel để báo cáo.
    """
    load_dotenv()
    
    # Kết nối Qdrant Local (đường dẫn mặc định của bạn)
    persist_path = "data/qdrant_db"
    if not os.path.exists(persist_path):
        print(f"[LOI] Khong tim thay du lieu Qdrant tai: {persist_path}")
        return

    print(f"[INFO] Dang ket noi toi Qdrant tai {persist_path}...")
    client = QdrantClient(path=persist_path)
    collection_name = "news_articles"

    # Lấy dữ liệu
    print(f"[INFO] Dang lay {limit} mau du lieu tu collection '{collection_name}'...")
    result = client.scroll(
        collection_name=collection_name,
        limit=limit,
        with_payload=True,
        with_vectors=True
    )

    points = result[0]
    if not points:
        print("[!] Khong co du lieu trong Qdrant!")
        return

    data_rows = []
    for point in points:
        payload = point.payload or {}
        vector = point.vector
        
        # Rút gọn vector để hiển thị trong Excel (lấy 10 số đầu và 10 số cuối)
        vector_str = f"[{', '.join(map(lambda x: f'{x:.4f}', vector[:10]))}, ..., {', '.join(map(lambda x: f'{x:.4f}', vector[-10:]))}]"
        
        data_rows.append({
            "ID": point.id,
            "Tiêu đề": payload.get("title", "N/A"),
            "Nguồn": payload.get("source", "N/A"),
            "Danh mục": payload.get("category", "N/A"),
            "Ngày đăng": payload.get("published_date", "N/A"),
            "Nội dung Chunk": payload.get("content", ""),
            "Vector (Rút gọn)": vector_str,
            "Độ dài Vector": len(vector)
        })

    # Tạo DataFrame và xuất Excel
    df = pd.DataFrame(data_rows)
    df.to_excel(output_file, index=False)
    
    print(f"[OK] Da xuat du lieu thanh cong ra file: {os.path.abspath(output_file)}")
    print(f"[INFO] Tong so dong: {len(df)}")

if __name__ == "__main__":
    # Bạn có thể thay đổi limit=None nếu muốn xuất toàn bộ (nhưng sẽ hơi lâu nếu dữ liệu lớn)
    export_qdrant_to_excel(limit=100)
