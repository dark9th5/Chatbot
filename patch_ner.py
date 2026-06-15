import os
import re

file_path = "d:\\App Android\\DoAn_CT060122\\etl\\ner_extractor.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Check if RELATION_ELIGIBLE_TYPES is already there
if "RELATION_ELIGIBLE_TYPES" in content:
    print("Already patched")
    exit(0)

# We will inject the methods before analyze_query
inject_marker = "    def analyze_query("

methods = """
    # === CHUẨN QUỐC TẾ: Chỉ Named Entity thực sự mới được làm subject/object ===
    RELATION_ELIGIBLE_TYPES = {
        "PERSON", "ORG", "LOC", "EVENT", "PRODUCT", "LAW", "FACILITY",
        "SPORT_TEAM", "DISEASE", "AWARD", "WORK_OF_ART", "VEHICLE",
        "NATIONALITY", "CRYPTO", "INDEX", "TOPIC", "JOB",
    }

    def extract_relations(
        self,
        text: str,
        entities_dict: dict | None = None,
    ) -> list:
        \"\"\"
        Trích xuất quan hệ giữa các thực thể theo chuẩn quốc tế.
        CHỈ cho phép Named Entity thực sự (PERSON, ORG, LOC, EVENT...)
        làm subject/object.
        \"\"\"
        relations = []
        entities_dict = entities_dict or self.extract_entities(text)

        flat_entities = []
        for e_type, values in entities_dict.items():
            if e_type not in self.RELATION_ELIGIBLE_TYPES:
                continue
            for val in values:
                for match in re.finditer(re.escape(val), text, re.IGNORECASE):
                    flat_entities.append({
                        "type": e_type,
                        "value": val,
                        "start": match.start(),
                        "end": match.end()
                    })

        flat_entities.sort(key=lambda x: x['start'])

        relation_rules = {
            ("PERSON", "ORG"): "LÀ_THÀNH_VIÊN_CỦA",
            ("ORG", "PERSON"): "CÓ_THÀNH_VIÊN",
            ("PERSON", "JOB"): "ĐẢM_NHẬN_CHỨC_VỤ",
            ("JOB", "PERSON"): "LÀ_CHỨC_VỤ_CỦA",
            ("PERSON", "LOC"): "XUẤT_HIỆN_TẠI",
            ("PERSON", "EVENT"): "THAM_GIA_SỰ_KIỆN",
            ("PERSON", "AWARD"): "NHẬN_GIẢI_THƯỞNG",
            ("PERSON", "PRODUCT"): "SỬ_DỤNG_SẢN_PHẨM",
            ("PERSON", "LAW"): "LIÊN_QUAN_PHÁP_LUẬT",
            ("PERSON", "DISEASE"): "MẮC_BỆNH",
            ("PERSON", "MONEY"): "LIÊN_QUAN_TÀI_CHÍNH",
            ("PERSON", "NATIONALITY"): "CÓ_QUỐC_TỊCH",
            ("ORG", "LOC"): "CÓ_TRỤ_SỞ_TẠI",
            ("ORG", "PRODUCT"): "SẢN_XUẤT_SẢN_PHẨM",
            ("ORG", "ORG"): "HỢP_TÁC_VỚI",
            ("ORG", "EVENT"): "TỔ_CHỨC_SỰ_KIỆN",
            ("ORG", "MONEY"): "CÓ_VỐN_ĐẦU_TƯ",
            ("ORG", "LAW"): "TUÂN_THỦ_PHÁP_LUẬT",
            ("ORG", "AWARD"): "NHẬN_GIẢI_THƯỞNG",
            ("ORG", "DISEASE"): "LIÊN_QUAN_DỊCH_BỆNH",
            ("ORG", "INDEX"): "THUỘC_CHỈ_SỐ",
            ("LOC", "LOC"): "THUỘC_ĐỊA_PHẬN",
            ("LOC", "EVENT"): "DIỄN_RA_TẠI",
            ("LOC", "ORG"): "LÀ_NƠI_ĐẶT_TRỤ_SỞ",
            ("PRODUCT", "ORG"): "ĐƯỢC_SẢN_XUẤT_BỞI",
            ("PRODUCT", "MONEY"): "CÓ_GIÁ_BÁN",
            ("EVENT", "LOC"): "TỔ_CHỨC_TẠI",
            ("EVENT", "ORG"): "DO_TỔ_CHỨC_ĐỨNG_RA",
            ("EVENT", "PERSON"): "CÓ_SỰ_THAM_GIA_CỦA",
            ("LAW", "ORG"): "DO_BAN_HÀNH",
            ("LAW", "PERSON"): "ÁP_DỤNG_CHO",
        }

        context_relation_map = [
            (re.compile(r"\\b(?:bổ nhiệm|được bầu|được chọn|bầu làm)\\b", re.IGNORECASE), "ĐƯỢC_BỔ_NHIỆM_VÀO"),
            (re.compile(r"\\b(?:từ chức|rời bỏ|từ bỏ|thôi giữ)\\b", re.IGNORECASE), "RỜI_KHỎI"),
            (re.compile(r"\\b(?:mua lại|thâu tóm|sáp nhập|hợp nhất)\\b", re.IGNORECASE), "MUA_LẠI"),
            (re.compile(r"\\b(?:đầu tư vào|rót vốn|cam kết đầu tư)\\b", re.IGNORECASE), "ĐẦU_TƯ_VÀO"),
            (re.compile(r"\\b(?:khởi tố|bắt giữ|điều tra|xét xử|kết án)\\b", re.IGNORECASE), "BỊ_XỬ_LÝ_PHÁP_LUẬT"),
            (re.compile(r"\\b(?:ký kết|ký hợp đồng|ký biên bản|ký thỏa thuận)\\b", re.IGNORECASE), "KÝ_KẾT_VỚI"),
            (re.compile(r"\\b(?:ra mắt|phát hành|công bố|giới thiệu)\\b", re.IGNORECASE), "RA_MẮT_SẢN_PHẨM"),
            (re.compile(r"\\b(?:thi đấu|đối đầu|gặp gỡ|đấu với)\\b", re.IGNORECASE), "THI_ĐẤU_VỚI"),
            (re.compile(r"\\b(?:thắng|chiến thắng|đánh bại|vượt qua)\\b", re.IGNORECASE), "THẮNG"),
            (re.compile(r"\\b(?:thua|thất bại|bị loại)\\b", re.IGNORECASE), "THUA"),
            (re.compile(r"\\b(?:hợp tác|liên kết|liên minh|kết hợp)\\b", re.IGNORECASE), "HỢP_TÁC_VỚI"),
            (re.compile(r"\\b(?:phê duyệt|thông qua|chấp thuận|ban hành)\\b", re.IGNORECASE), "PHÊ_DUYỆT"),
            (re.compile(r"\\b(?:sinh tại|quê ở|sinh ra tại|xuất thân từ)\\b", re.IGNORECASE), "SINH_TẠI"),
        ]

        actions = []
        if "ACTION" in entities_dict:
            for val in entities_dict["ACTION"]:
                for match in re.finditer(re.escape(val), text, re.IGNORECASE):
                    actions.append({
                        "value": val,
                        "start": match.start(),
                        "end": match.end()
                    })
        actions.sort(key=lambda x: x['start'])

        for i in range(len(flat_entities)):
            for j in range(i + 1, min(i + 5, len(flat_entities))):
                e1 = flat_entities[i]
                e2 = flat_entities[j]

                if e1['value'] == e2['value']:
                    continue

                ctx_start = max(0, e1['start'] - 10)
                ctx_end = min(len(text), e2['end'] + 10)
                pair_context = text[ctx_start:ctx_end]

                distance = e2['start'] - e1['end']
                if 0 <= distance <= 120:
                    found_ctx_rel = None
                    for ctx_pat, ctx_rel_name in context_relation_map:
                        if ctx_pat.search(pair_context):
                            found_ctx_rel = ctx_rel_name
                            break

                    found_action = None
                    for act in actions:
                        if e1['end'] <= act['start'] and act['end'] <= e2['start']:
                            found_action = act['value'].upper()
                            break
                        elif e2['end'] <= act['start'] and act['end'] <= e1['start']:
                            found_action = act['value'].upper()
                            break

                    rel_name = found_ctx_rel or found_action
                    if not rel_name:
                        rel_name = relation_rules.get((e1['type'], e2['type']))
                    if not rel_name:
                        rel_name = relation_rules.get((e2['type'], e1['type']))

                    if rel_name:
                        subject = e1
                        obj = e2

                        if not found_ctx_rel and not found_action and relation_rules.get((e2['type'], e1['type'])) == rel_name and relation_rules.get((e1['type'], e2['type'])) != rel_name:
                            subject = e2
                            obj = e1

                        rel = {
                            "subject": subject['value'].title(),
                            "subject_type": subject['type'],
                            "relation": rel_name.replace(" ", "_"),
                            "object": obj['value'].title(),
                            "object_type": obj['type']
                        }
                        if rel not in relations:
                            relations.append(rel)
        return relations

    def extract_attributes(
        self,
        text: str,
        entities_dict: dict | None = None,
    ) -> list:
        \"\"\"
        Trích xuất thuộc tính của thực thể (Attribute Extraction).
        CẬP NHẬT: Gắn điều kiện kiểu logic, giảm window size.
        \"\"\"
        attributes = []
        entities_dict = entities_dict or self.extract_entities(text)

        flat_entities = []
        for e_type, values in entities_dict.items():
            if e_type not in self.RELATION_ELIGIBLE_TYPES:
                continue
            for val in values:
                for match in re.finditer(re.escape(val), text, re.IGNORECASE):
                    flat_entities.append({
                        "type": e_type,
                        "value": val,
                        "start": match.start(),
                        "end": match.end()
                    })
        flat_entities.sort(key=lambda x: x['start'])

        # Mapping rules to enforce strict logic for attribute association
        ATTR_ALLOWED_TYPES = {
            "TUỔI": {"PERSON"},
            "CHỨC_VỤ": {"PERSON"},
            "NHÂN_SỰ": {"ORG", "FACILITY"},
            "HÀNH_ĐỘNG": {"PERSON", "ORG", "SPORT_TEAM"},
            "XU_HƯỚNG": {"INDEX", "TOPIC", "PRODUCT", "ORG", "CRYPTO"},
            "GIÁ_TRỊ": {"ORG", "PRODUCT", "INDEX", "TOPIC", "EVENT"},
            "BIẾN_ĐỘNG": {"ORG", "PRODUCT", "INDEX", "TOPIC", "CRYPTO"},
            "XẾP_HẠNG": {"PERSON", "ORG", "PRODUCT", "SPORT_TEAM", "LOC"},
            "QUỐC_TỊCH": {"PERSON", "PRODUCT", "ORG"},
            "TRẠNG_THÁI": {"PERSON", "ORG", "LOC", "FACILITY", "DISEASE", "PRODUCT", "EVENT"}
        }

        VI_UPPER = "A-ZÀÁẢÃẠÂẦẤẨẪẬĂẰẮẲẴẶĐÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴ"
        VI_LOWER = "a-zàáảãạâầấẩẫậăằắẳẵặđèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵ"

        structural_attr_patterns = [
            (re.compile(rf"\\b([{VI_UPPER}][{VI_LOWER}]+(?:\\s+[{VI_UPPER}][{VI_LOWER}]+){{0,4}})\\s*,?\\s*(\\d{{2,3}})\\s*tuổi\\b"), "TUỔI", 2),
            (re.compile(rf"\\b([{VI_UPPER}][{VI_LOWER}]+(?:\\s+[{VI_UPPER}][{VI_LOWER}]+){{0,4}})\\s*,\\s*([\\w\\s]{{4,40}})(?=,|\\.|;)"), "CHỨC_VỤ", 2),
            (re.compile(rf"\\b(tổng thống|thủ tướng|bộ trưởng|thứ trưởng|đại sứ|tổng giám đốc|giám đốc|phó chủ tịch|chủ tịch|đại tướng|thượng tướng|trung tướng|thiếu tướng|đội trưởng|đội phó|huấn luyện viên|hlv)\\s+(?:[{VI_UPPER}][{VI_LOWER}]+(?:\\s+[{VI_UPPER}][{VI_LOWER}]+){{1,4}})\\b", re.IGNORECASE), "CHỨC_VỤ", 1),
            (re.compile(r"\\b(\\d+(?:[,.]\\d+)?\\s*(?:tỷ|triệu|nghìn)\\s*(?:đồng|usd|vnd)?)\\b", re.IGNORECASE), "GIÁ_TRỊ", 0),
            (re.compile(r"\\b(\\d+(?:[,.]\\d+)?\\s*(?:nhân viên|lao động|người lao động|cán bộ|công nhân))", re.IGNORECASE), "NHÂN_SỰ", 0),
            (re.compile(r"\\b(tăng|giảm|tăng trưởng|sụt giảm)\\s*(\\d+(?:[,.]\\d+)?\\s*%)\\b", re.IGNORECASE), "BIẾN_ĐỘNG", 0),
            (re.compile(r"\\b(?:xếp hạng|đứng thứ|hạng)\\s*(\\d+|nhất|nhì|ba)\\b", re.IGNORECASE), "XẾP_HẠNG", 0),
            (re.compile(r"\\b(người|có quốc tịch|đến từ|xuất xứ từ)\\s+([A-ZĐÀÁẢÃẠ][\\w\\s]{2,20})\\b"), "QUỐC_TỊCH", 2),
        ]

        attrs_signals = []
        for a_type in ["TREND", "STATE", "ACTION"]:
            if a_type in entities_dict:
                for val in entities_dict[a_type]:
                    for match in re.finditer(re.escape(val), text, re.IGNORECASE):
                        attrs_signals.append({
                            "type": a_type,
                            "value": val,
                            "start": match.start(),
                            "end": match.end()
                        })

        for sig in attrs_signals:
            attr_key = "XU_HƯỚNG" if sig['type'] == "TREND" else ("HÀNH_ĐỘNG" if sig['type'] == "ACTION" else "TRẠNG_THÁI")
            allowed_types = ATTR_ALLOWED_TYPES.get(attr_key, self.RELATION_ELIGIBLE_TYPES)
            
            best_ent = None
            best_dist = 200
            sig_mid = (sig['start'] + sig['end']) // 2
            
            for ent in flat_entities:
                if ent['type'] not in allowed_types:
                    continue
                dist = abs(((ent['start'] + ent['end']) // 2) - sig_mid)
                if dist < best_dist:
                    start_idx = min(ent['end'], sig['start'])
                    end_idx = max(ent['start'], sig['end'])
                    between = text[start_idx:end_idx]
                    if not re.search(r'[.!?\\n]{2,}', between):
                        best_dist = dist
                        best_ent = ent

            if best_ent and best_dist < 50:
                attributes.append({
                    "entity": best_ent['value'].title(),
                    "entity_type": best_ent['type'],
                    "attribute_key": attr_key,
                    "attribute_value": sig['value'].upper()
                })

        for pattern, attr_key, group_idx in structural_attr_patterns:
            allowed_types = ATTR_ALLOWED_TYPES.get(attr_key, self.RELATION_ELIGIBLE_TYPES)
            for match in pattern.finditer(text):
                val = match.group(group_idx) if group_idx > 0 else match.group(0)
                val_norm = val.strip()
                if not val_norm or len(val_norm) < 2:
                    continue
                match_mid = (match.start() + match.end()) // 2
                best_ent = None
                best_dist = 200
                for ent in flat_entities:
                    if ent['type'] not in allowed_types:
                        continue
                    dist = abs(((ent['start'] + ent['end']) // 2) - match_mid)
                    if dist < best_dist:
                        best_dist = dist
                        best_ent = ent
                if best_ent and best_dist < 60:
                    attributes.append({
                        "entity": best_ent['value'].title(),
                        "entity_type": best_ent['type'],
                        "attribute_key": attr_key,
                        "attribute_value": val_norm.upper()
                    })

        unique_attrs = []
        seen = set()
        for a in attributes:
            k = (a['entity'], a['attribute_key'], a['attribute_value'])
            if k not in seen:
                seen.add(k)
                unique_attrs.append(a)

        return unique_attrs

"""

content = content.replace(inject_marker, methods + inject_marker)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Patched successfully")
