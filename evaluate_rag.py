import json
import requests
import numpy as np
import time
from sklearn.metrics.pairwise import cosine_similarity
from chatbot_api.dependencies import get_embedding_service

API_URL = "http://localhost:8000/api/chat"
DATASET_PATH = "data/test_dataset.json"

class RAGEvaluator:
    def __init__(self):
        # Load embedding service để tính similarity
        self.embedding_service = get_embedding_service()

    def evaluate(self):
        print("📊 STARTING RAG EVALUATION")
        print("==================================================")
        
        with open(DATASET_PATH, 'r', encoding='utf-8') as f:
            test_cases = json.load(f)[:2]
            
        results = []
        total_time = 0
        
        for case in test_cases:
            question = case['question']
            expected = case['expected_answer']
            keywords = [k.lower() for k in case['keywords']]
            
            print(f"\n❓ Question: {question}")
            
            start = time.time()
            try:
                resp = requests.post(API_URL, json={"question": question})
                duration = time.time() - start
                total_time += duration
                
                if resp.status_code != 200:
                    print(f"   ❌ Error: API failed")
                    continue
                    
                data = resp.json()
                actual_answer = data.get('answer', '')
                sources = data.get('sources', [])
                
                # --- METRIC 1: CONTEXT PRECISION (Keyword Hit) ---
                # Kiểm tra xem từ khóa có xuất hiện trong nguồn trích dẫn không
                context_hit_score = 0
                retrieved_text = " ".join([s.get('chunk_text', '') for s in sources]).lower()
                
                hits = [k for k in keywords if k in retrieved_text]
                if keywords:
                    context_hit_score = len(hits) / len(keywords)
                
                # --- METRIC 2: ANSWER SIMILARITY (Semantic) ---
                # So sánh vector câu trả lời thực tế vs mong đợi
                vec_actual = self.embedding_service.encode_query(actual_answer)
                vec_expected = self.embedding_service.encode_query(expected)
                
                # Reshape for sklearn
                vec_actual = vec_actual.reshape(1, -1)
                vec_expected = vec_expected.reshape(1, -1)
                
                similarity = cosine_similarity(vec_actual, vec_expected)[0][0]
                
                print(f"   Answer: {actual_answer[:100]}...")
                print(f"   ⏱ Time: {duration:.2f}s")
                print(f"   🎯 Context Precision: {context_hit_score:.2f} ({len(hits)}/{len(keywords)} keywords)")
                print(f"   🧠 Semantic Similarity: {similarity:.4f}")
                
                results.append({
                    "question": question,
                    "context_score": context_hit_score,
                    "similarity_score": similarity,
                    "latency": duration
                })
                
            except Exception as e:
                print(f"   ⚠ Evaluation Error: {e}")
        
        # --- REPORT ---
        avg_context = np.mean([r['context_score'] for r in results])
        avg_sim = np.mean([r['similarity_score'] for r in results])
        avg_lat = np.mean([r['latency'] for r in results])
        
        report = f"""
📈 FINAL EVALUATION REPORT
==================================================
Total Test Cases: {len(results)}
✅ Avg Context Precision: {avg_context:.4f}
✅ Avg Answer Similarity: {avg_sim:.4f}
⚡ Avg Latency: {avg_lat:.2f}s
==================================================
"""
        print(report)
        with open("evaluation_report.txt", "w", encoding="utf-8") as f:
            f.write(report)

if __name__ == "__main__":
    evaluator = RAGEvaluator()
    evaluator.evaluate()
