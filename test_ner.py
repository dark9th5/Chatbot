from etl.ner_extractor import NERExtractor

text = "Tỷ phú Phạm Nhật Vượng chủ tịch Vingroup vừa công bố đầu tư 20 tỷ đồng vào dự án công nghệ trí tuệ nhân tạo ở TP.HCM."

ner = NERExtractor()
entities = ner.extract_entities(text)
print("Text:", text)
print("Entities:", entities)
