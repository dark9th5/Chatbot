import requests
import time

API_URL = "http://localhost:8000/api/chat"

def test_expansion(question: str):
    print(f"\n🔍 Testing Question (Short): '{question}'")
    
    start = time.time()
    resp = requests.post(API_URL, json={"question": question})
    dur = time.time() - start
    
    if resp.status_code == 200:
        print(f"   Response Time: {dur:.4f}s")
        data = resp.json()
        print(f"   Answer: {data.get('answer')[:100]}...")
        print(f"   Confidence: {data.get('confidence')}")
        
        print("\n👉 CHECK SERVER TERMINAL logs to see expanded query:")
        print("   [Query Expansion] '...' -> '...'")
    else:
        print(f"   ❌ Error: {resp.text}")

if __name__ == "__main__":
    print("🧠 TESTING QUERY EXPANSION")
    
    # Warm up
    requests.post(API_URL, json={"question": "Hello"})
    
    # Câu hỏi quá ngắn, cần expand
    test_expansion("Dân trí thế nào") 
    test_expansion("vàng hôm nay")
