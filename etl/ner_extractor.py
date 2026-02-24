import re
from typing import List, Dict

class NERExtractor:
    """
    Tự code module Rút trích Thực thể (Named Entity Recognition - NER) cho tiếng Việt.
    Dùng Regex và luật cơ bản thay vì Machine Learning model để tiết kiệm RAM.
    Tập trung vào:
    1. Tên người / Tên riêng (Người/Hành chính)
    2. Tổ chức / Công ty (Vingroup, FPT, Vietcombank...)
    3. Địa danh (Hà Nội, TP.HCM...)
    4. Tiền tệ (xx tỷ đồng, xx triệu USD...)
    """
    
    def __init__(self):
        # 1. Regex cho Tiền tệ (VD: 20 tỷ đồng, 15.5 triệu USD, 500 nghìn)
        self.money_pattern = re.compile(
            r'\b\d+(?:[\.,]\d+)?\s*(?:tỷ|triệu|nghìn|ngàn|trăm|đồng|usd|vnđ|vnd)\b', 
            re.IGNORECASE
        )
        
        # 2. Danh sách Tổ chức / Doanh nghiệp phổ biến (Dictionary-based)
        self.org_keywords = [
            "vingroup", "vinfast", "fpt", "viettel", "vietcombank", "bidv", 
            "vng", "masan", "thaco", "sun group", "flc", "novaland",
            "bộ công an", "chính phủ", "quoành", "vtv"
        ]
        
        # 3. Địa danh cơ bản ở VN
        self.location_keywords = [
            "hà nội", "tp.hcm", "hcm", "đà nẵng", "hải phòng", "cần thơ",
            "sài gòn", "việt nam", "mỹ", "trung quốc", "nhật bản"
        ]
        
    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """
        Phân tích văn bản và trả về Dict chứa các thực thể rút trích được.
        """
        entities = {
            "PERSON": [],
            "ORG": [],
            "LOC": [],
            "MONEY": []
        }
        
        if not text:
            return entities
            
        # 1. Extract Money
        money_matches = self.money_pattern.findall(text)
        entities["MONEY"] = list(set([m.lower() for m in money_matches]))
        
        # 2. Extract Orgs & Locs (Dictionary Lookup)
        text_lower = text.lower()
        
        for org in self.org_keywords:
            if org in text_lower:
                entities["ORG"].append(org)
                
        for loc in self.location_keywords:
            if loc in text_lower:
                entities["LOC"].append(loc)
                
        # 3. Extract Names (Heuristic: 2-4 từ viết hoa liên tiếp)
        # Bỏ qua từ đầu câu nếu có thể (khó code thuần bằng regex ngắn gọn, nên dùng regex tương đối)
        # Tìm pattern: Tên Riêng Viết Hoa (VD: Phạm Nhật Vượng, Nguyễn Đức Chung)
        name_pattern = r'\b([A-ZÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬĐEÈÉẺẼẸÊỀẾỂỄỆIÌÍỈĨỊOÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢUÙÚỦŨỤƯỪỨỬỮỰYỲÝỶỸỴ][a-zàáảãạăằắẳẵặâầấẩẫậđeèéẻẽẹêềếểễệiìíỉĩịoòóỏõọôồốổỗộơờớởỡợuùúủũụưừứửữựyỳýỷỹỵ]*\s){1,3}[A-ZÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬĐEÈÉẺẼẸÊỀẾỂỄỆIÌÍỈĨỊOÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢUÙÚỦŨỤƯỪỨỬỮỰYỲÝỶỸỴ][a-zàáảãạăằắẳẵặâầấẩẫậđeèéẻẽẹêềếểễệiìíỉĩịoòóỏõọôồốổỗộơờớởỡợuùúủũụưừứửữựyỳýỷỹỵ]*\b'
        
        names_iter = re.finditer(name_pattern, text)
        for match in names_iter:
            name = match.group().strip()
            # Lọc bỏ một số false positive nếu nó là một phần của câu (Heuristic cơ bản)
            if len(name.split()) >= 2 and len(name) > 5:
                # Tránh nhầm với những chữ viết hoa bình thường ở đầu câu (Chưa hoàn hảo 100% nhưng nhẹ RAM)
                entities["PERSON"].append(name)
                
        # Duyệt lại loại bỏ trùng gộp (Unique)
        entities["PERSON"] = list(set(entities["PERSON"]))
        
        return entities
