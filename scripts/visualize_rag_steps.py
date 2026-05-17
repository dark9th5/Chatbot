import sys
import os
import pandas as pd
import numpy as np

# Thêm thư mục gốc vào path để import được các module trong project
sys.path.append(os.getcwd())

from pipeline.chunking_vectorizer import VietnameseTextSplitter, TextVectorizer

def visualize_rag_transformation():
    print("[INFO] Starting RAG transformation visualization...")
    
    # Khởi tạo model sớm để lấy tokenizer
    print("[INFO] Loading embedding model (bkai-foundation-models/vietnamese-bi-encoder)...")
    vectorizer = TextVectorizer()
    
    # 1. Dữ liệu đầu vào mẫu
    sample_text = (
        "Trí tuệ nhân tạo (AI) đang thay đổi cách chúng ta làm việc và sinh sống. "
        "Tại Việt Nam, nhiều doanh nghiệp đã bắt đầu ứng dụng AI vào quy trình sản xuất, giúp tối ưu hóa chi phí và tăng năng suất lao động. "
        "Chính phủ cũng đang có những chính sách hỗ trợ phát triển công nghệ cao, đặc biệt là trong lĩnh vực học máy và xử lý ngôn ngữ tự nhiên. "
        "Tuy nhiên, việc đào tạo nguồn nhân lực chất lượng cao vẫn là một thách thức lớn đối với nền kinh tế số. "
        "Chúng ta cần có lộ trình cụ thể, đầu tư mạnh mẽ vào giáo dục và hạ tầng công nghệ để bắt kịp xu hướng toàn cầu và không bị bỏ lại phía sau."
    )
    
    # Cấu hình nhỏ để dễ quan sát sự phân tách
    chunk_size = 150
    chunk_overlap = 50

    # --- SHEET 1: SENTENCES ---
    splitter = VietnameseTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    sentences = splitter._split_sentences(sample_text)
    df_sentences = pd.DataFrame([
        {"STT": i+1, "Câu văn": s, "Độ dài": len(s)} for i, s in enumerate(sentences)
    ])

    # --- SHEET 2: CHUNKS ---
    chunks = splitter.split_text(sample_text)
    chunks_data = []
    for i, chunk in enumerate(chunks):
        chunks_data.append({
            "Chunk ID": f"CHUNK_{i+1}",
            "Nội dung Chunk": chunk,
            "Độ dài": len(chunk),
            "Số câu": len(splitter._split_sentences(chunk))
        })
    df_chunks = pd.DataFrame(chunks_data)

    # --- SHEET 2.5: TOKENIZATION (INTERNAL MATH STEP) ---
    print("[INFO] Performing Tokenization...")
    tokenizer = vectorizer.model.tokenizer
    
    # Tính toán embedding trước để dùng cho các bước sau
    print("[INFO] Computing Embeddings (This takes a moment)...")
    embeddings = vectorizer.encode(chunks)

    token_data = []
    for i, chunk in enumerate(chunks):
        # Tokenize văn bản
        tokens = tokenizer.tokenize(chunk)
        token_ids = tokenizer.convert_tokens_to_ids(tokens)
        
        token_data.append({
            "Chunk ID": f"CHUNK_{i+1}",
            "Nội dung (Rút gọn)": chunk[:50] + "...",
            "Tokens (Mảnh từ)": " | ".join(tokens[:30]) + ("..." if len(tokens) > 30 else ""),
            "Token IDs (Số định danh)": " , ".join(map(str, token_ids[:30])) + ("..." if len(token_ids) > 30 else ""),
            "Tổng số Token": len(tokens)
        })
    df_tokens = pd.DataFrame(token_data)

    # --- SHEET 2.7: POOLING (BƯỚC TÍNH TOÁN TRUNG BÌNH) ---
    print("[INFO] Computing Token-level embeddings for Pooling visualization...")
    # Lấy token embeddings (vector của từng token trước khi gộp)
    # Lưu ý: encode với output_value='token_embeddings' trả về list các tensor
    token_embeddings_list = vectorizer.model.encode([chunks[0]], output_value='token_embeddings')
    token_embeddings = token_embeddings_list[0] # Lấy cho chunk đầu tiên làm mẫu
    
    tokens_sample = tokenizer.tokenize(chunks[0])
    # Giới hạn số token hiển thị để Excel không bị treo (lấy 20 token đầu)
    limit_tokens = min(20, len(tokens_sample))
    
    pooling_data = []
    for t_idx in range(limit_tokens):
        row = {
            "Token": tokens_sample[t_idx],
            "Vị trí": t_idx
        }
        # Hiển thị TẤT CẢ 768 chiều (có thể kéo ngang trong Excel để xem hết)
        for d_idx in range(len(token_embeddings[t_idx])):
            row[f"Dim_{d_idx+1}"] = float(token_embeddings[t_idx][d_idx])
        pooling_data.append(row)
    
    # Thêm dòng tính giá trị TRUNG BÌNH (Mean Pooling) - Đây là cách tính ra vector cuối
    mean_row = {
        "Token": "--- MEAN POOLING ---",
        "Vị trí": "TOTAL"
    }
    final_vector_sample = embeddings[0]
    for d_idx in range(len(final_vector_sample)):
        mean_row[f"Dim_{d_idx+1}"] = float(final_vector_sample[d_idx])
    pooling_data.append(mean_row)
    
    df_pooling = pd.DataFrame(pooling_data)

    # --- SHEET 3: VECTORS (DETAILED) ---
    print("[INFO] Finalizing vectors...")
    
    vector_data = []
    for i, vector in enumerate(embeddings):
        row = {
            "Chunk ID": f"CHUNK_{i+1}",
            "Nội dung (Rút gọn)": chunks[i][:50] + "..."
        }
        # Xuất toàn bộ 768 chiều
        for d_idx in range(len(vector)):
            row[f"Dim_{d_idx+1}"] = float(vector[d_idx])
        vector_data.append(row)
    df_vectors = pd.DataFrame(vector_data)

    # --- SHEET 3.5: NER EXTRACTION (INTERMEDIATE STEP) ---
    print("[INFO] Performing NER Extraction on chunks...")
    from etl.ner_extractor import NERExtractor
    ner_extractor = NERExtractor()
    
    ner_data = []
    for i, chunk in enumerate(chunks):
        entities = ner_extractor.extract_entities(chunk)
        # Tách các loại thực thể để hiển thị rõ (Theo cấu trúc Dict của project)
        per = entities.get("PERSON", [])
        loc = entities.get("LOC", [])
        org = entities.get("ORG", [])
        money = entities.get("MONEY", [])
        
        ner_data.append({
            "Chunk ID": f"CHUNK_{i+1}",
            "Nội dung Chunk": chunk[:100] + "...",
            "Người (PERSON)": ", ".join(per) if per else "-",
            "Địa điểm (LOC)": ", ".join(loc) if loc else "-",
            "Tổ chức (ORG)": ", ".join(org) if org else "-",
            "Tiền tệ (MONEY)": ", ".join(money) if money else "-",
            "Tổng số thực thể": len(per) + len(loc) + len(org) + len(money)
        })
    df_ner = pd.DataFrame(ner_data)

    # --- SHEET 4: QDRANT POINT (PAYLOAD + VECTOR) ---
    print("[INFO] Preparing Qdrant point structure...")
    qdrant_data = []
    for i, (chunk, vector) in enumerate(zip(chunks, embeddings)):
        metadata = {
            "article_id": 999,
            "title": "Demo RAG Visualization",
            "source": "Manual Input",
            "category": "Technology",
            "entities": ner_extractor.extract_entities(chunk),
            "content": chunk
        }
        
        qdrant_data.append({
            "Point ID": f"UUID_{i+1}",
            "Payload (Metadata JSON)": str(metadata),
            "Vector Full (768 dims)": str(vector.tolist()),
            "Final Status": "Ready to Upsert"
        })
    df_qdrant = pd.DataFrame(qdrant_data)

    # --- XUẤT RA EXCEL VỚI NHIỀU SHEET ---
    output_file = "rag_total_768_final.xlsx"
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        df_sentences.to_excel(writer, sheet_name='1. Tách Câu', index=False)
        df_chunks.to_excel(writer, sheet_name='2. Gom Chunk', index=False)
        df_tokens.to_excel(writer, sheet_name='2.5. Tokenization', index=False)
        df_pooling.to_excel(writer, sheet_name='2.7. Pooling (Tính toán)', index=False)
        df_vectors.to_excel(writer, sheet_name='3. Vector Chi Tiết', index=False)
        df_ner.to_excel(writer, sheet_name='3.5. Trích xuất NER', index=False)
        df_qdrant.to_excel(writer, sheet_name='4. Cấu trúc Qdrant', index=False)

        # Định dạng độ rộng cột (Chỉ chỉnh 2 cột đầu cho đỡ lag)
        for sheet_name in writer.sheets:
            worksheet = writer.sheets[sheet_name]
            worksheet.column_dimensions['A'].width = 20
            worksheet.column_dimensions['B'].width = 50

    print(f"\n[OK] Exported STEP-BY-STEP RAG visualization to: {os.path.abspath(output_file)}")
    print("-" * 60)
    print("Excel file structure:")
    print("1. Sheet '1. Tách Câu': individual sentences.")
    print("2. Sheet '2. Gom Chunk': sentences grouped into chunks.")
    print("3. Sheet '3. Vector Chi Tiết': embedding vector dimensions.")
    print("3.5 Sheet '3.5. Trích xuất NER': Entities extracted for filtering.")
    print("4. Sheet '4. Cấu trúc Qdrant': Final database point.")

if __name__ == "__main__":
    visualize_rag_transformation()
