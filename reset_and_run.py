import pymysql
import os
import shutil
from db_config import MYSQL_CONFIG

def reset_database():
    print("🧹 BẮT ĐẦU XÓA DATA CŨ...")
    
    # 1. Xóa MySQL articles
    print("1. Đang dọn dẹp MySQL (Bảng articles)...")
    try:
        conn = pymysql.connect(**MYSQL_CONFIG, cursorclass=pymysql.cursors.DictCursor)
        cursor = conn.cursor()
        cursor.execute("TRUNCATE TABLE articles")
        conn.commit()
        conn.close()
        print("   -> Đã xóa toàn bộ bài báo trong MySQL.")
    except Exception as e:
        print(f"   -> Lỗi MySQL: {e}")

    # 2. Xóa Qdrant Local Vector DB (Bằng cách xóa folder)
    print("2. Đang dọn dẹp Qdrant Vector Data...")
    qdrant_path = os.path.join(os.path.dirname(__file__), "data", "qdrant_db")
    try:
        if os.path.exists(qdrant_path):
            shutil.rmtree(qdrant_path)
            print(f"   -> Đã xóa folder {qdrant_path}.")
        else:
            print("   -> Folder Qdrant trống.")
    except Exception as e:
        print(f"   -> Lỗi xóa Qdrant: {e}")

    print("✅ ĐÃ DỌN DẸP XONG. HỆ THỐNG SẴN SÀNG CHO DATA MỚI!\n")

if __name__ == "__main__":
    reset_database()
    
    # Kích hoạt luôn việc Crawl
    print("🚀 ĐANG KIẾN TẠO LẠI DATA BẰNG PIPELINE MỚI...")
    from main_etl import main as crawl_main
    crawl_main()
    
    print("\n🚀 ĐANG CHUNKING & VECTOR HÓA BẰNG THUẬT TOÁN MỚI...")
    from chunking_vectorizer import process_all_articles
    process_all_articles(incremental=False)
    
    print("\n🎉 HOÀN TẤT TOÀN BỘ QUÁ TRÌNH RESET & UPDATE!")
