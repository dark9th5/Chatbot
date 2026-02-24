import requests
import time

API_URL = "http://localhost:8000/api/chat"

def test_cache(question: str):
    print(f"\n🔍 Testing Question: '{question}'")
    
    # Lần 1: Cache Miss (Chưa có trong cache)
    start = time.time()
    resp1 = requests.post(API_URL, json={"question": question})
    dur1 = time.time() - start
    
    if resp1.status_code == 200:
        print(f"   Attempt 1 (Expected Miss): {dur1:.4f}s")
        print(f"   Answer: {resp1.json().get('answer')[:50]}...")
    else:
        print(f"   ❌ Error: {resp1.text}")
        return

    # Lần 2: Cache Hit (Đã lưu)
    start = time.time()
    resp2 = requests.post(API_URL, json={"question": question})
    dur2 = time.time() - start
    
    if resp2.status_code == 200:
        print(f"   Attempt 2 (Expected Hit):  {dur2:.4f}s")
        print(f"   Answer: {resp2.json().get('answer')[:50]}...")
        
        # So sánh tốc độ
        speedup = dur1 / dur2 if dur2 > 0 else 0
        print(f"   🚀 Speedup: {speedup:.1f}x faster")
    else:
        print(f"   ❌ Error: {resp2.text}")

    # Lần 3: Semantic Cache Hit (Hỏi câu tương tự)
    # Ví dụ: "Giá vàng hôm nay" vs "Hôm nay giá vàng thế nào"
    # Lưu ý: Cần model embedding tốt mới bắt được semantic similarity cao > 0.9
    pass

if __name__ == "__main__":
    print("🐇 TESTING SEMANTIC CACHE")
    print("Note: First request might be slow due to model loading.")
    
    # Warm up
    requests.post(API_URL, json={"question": "Xin chào"})
    
    test_cache("Tình hình kinh tế Việt Nam 2024 thế nào?")
    test_cache("Ai là chủ tịch Vingroup?")
