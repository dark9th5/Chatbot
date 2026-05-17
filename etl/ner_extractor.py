from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Dict, Iterable, List, Set


VI_UPPER = "A-ZÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬĐEÈÉẺẼẸÊỀẾỂỄỆIÌÍỈĨỊOÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢUÙÚỦŨỤƯỪỨỬỮỰYỲÝỶỸỴ"
VI_LOWER = "a-zàáảãạăằắẳẵặâầấẩẫậđeèéẻẽẹêềếểễệiìíỉĩịoòóỏõọôồốổỗộơờớởỡợuùúủũụưừứửữựyỳýỷỹỵ"


def _terms(blob: str) -> Set[str]:
    return {item.strip() for item in blob.split("|") if item.strip()}


def _normalize_for_match(value: str) -> str:
    value = unicodedata.normalize("NFC", value).casefold()
    value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


class NERExtractor:
    """
    Bộ rút trích thực thể tiếng Việt tất định cho miền tin tức.

    Hỗ trợ 27 loại thực thể:
    PERSON, ORG, LOC, MONEY, DATE, TIME, JOB, EVENT, PRODUCT, LAW,
    PERCENT, PHONE, EMAIL, URL, AGE, TEMPERATURE, QUANTITY, SCORE,
    FACILITY, VEHICLE, AWARD, DISEASE, SPORT_TEAM, WORK_OF_ART,
    LANGUAGE, NATIONALITY, CRYPTO.

    Thiết kế theo 3 lớp:
    1. Regex cho các mẫu có cấu trúc rõ ràng.
    2. Từ điển MaxMatch cho thực thể tên riêng.
    3. Tùy chọn nạp thêm data/ner_lexicons.json để mở rộng tới hàng chục nghìn mục
       mà không cần sửa code.
    """

    TYPE_ORDER = [
        "PERSON",
        "ORG",
        "LOC",
        "MONEY",
        "DATE",
        "TIME",
        "JOB",
        "EVENT",
        "PRODUCT",
        "LAW",
        "PERCENT",
        "PHONE",
        "EMAIL",
        "URL",
        "AGE",
        "TEMPERATURE",
        "QUANTITY",
        "SCORE",
        "FACILITY",
        "VEHICLE",
        "AWARD",
        "DISEASE",
        "SPORT_TEAM",
        "WORK_OF_ART",
        "LANGUAGE",
        "NATIONALITY",
        "CRYPTO",
    ]

    def __init__(self):
        self.money_pattern = re.compile(
            r"\b\d+(?:[\.,]\d+)?\s*(?:nghìn|ngàn|triệu|tỷ|nghìn tỷ|"
            r"đồng|vnđ|vnd|usd|đô la|đô la mỹ|euro|eur|bảng anh|gbp|"
            r"nhân dân tệ|cny|yên|jpy|won|krw|baht|thb)\b",
            re.IGNORECASE,
        )
        self.date_pattern = re.compile(
            r"\b(?:ngày\s+)?(?:0?[1-9]|[12][0-9]|3[01])/(?:0?[1-9]|1[012])(?:/\d{2,4})?\b"
            r"|\b(?:0?[1-9]|[12][0-9]|3[01])-(?:0?[1-9]|1[012])-\d{2,4}\b"
            r"|\b(?:tháng\s+)?(?:0?[1-9]|1[012])\s+năm\s+\d{4}\b"
            r"|\bquý\s+[ivx1-4]+\s*(?:năm\s+)?\d{4}\b"
            r"|\b(?:hôm nay|hôm qua|ngày mai|sáng nay|chiều nay|tối nay|"
            r"tuần này|tuần trước|tuần sau|tháng này|tháng trước|tháng sau|"
            r"năm nay|năm ngoái|đầu năm|cuối năm)\b",
            re.IGNORECASE,
        )
        self.time_pattern = re.compile(
            r"\b(?:[01]?\d|2[0-3])[:h](?:[0-5]\d)\b"
            r"|\b(?:[01]?\d|2[0-3])\s*giờ(?:\s*(?:[0-5]\d)\s*phút)?\b"
            r"|\b(?:sáng|trưa|chiều|tối|đêm|rạng sáng)\b",
            re.IGNORECASE,
        )
        self.percent_pattern = re.compile(
            r"\b\d+(?:[\.,]\d+)?\s*(?:%|phần trăm)(?=\s|$|[.,;:!?])",
            re.IGNORECASE,
        )
        self.phone_pattern = re.compile(
            r"(?<!\d)(?:\+84|0)\s*(?:\d[\s.-]?){8,10}\d(?!\d)"
        )
        self.email_pattern = re.compile(
            r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"
        )
        self.url_pattern = re.compile(
            r"\b(?:https?://|www\.)[^\s<>()]+\b",
            re.IGNORECASE,
        )
        self.age_pattern = re.compile(
            r"\b\d{1,3}\s*(?:tuổi|năm tuổi)\b",
            re.IGNORECASE,
        )
        self.temperature_pattern = re.compile(
            r"\b-?\d+(?:[\.,]\d+)?\s*(?:°c|độ c)\b",
            re.IGNORECASE,
        )
        self.quantity_pattern = re.compile(
            r"\b\d+(?:[\.,]\d+)?\s*(?:kg|g|tấn|tạ|yến|km|m|cm|mm|ha|"
            r"m2|m²|km2|km²|lít|ml|giờ|phút|ngày|tháng|năm|người|"
            r"chiếc|căn|hộ|vé|đơn|ca|bộ|sản phẩm)\b",
            re.IGNORECASE,
        )
        self.score_pattern = re.compile(
            r"\b\d{1,2}\s*-\s*\d{1,2}\b"
        )
        self.legal_document_pattern = re.compile(
            r"\b(?:luật|bộ luật|nghị định|thông tư|nghị quyết|chỉ thị|quyết định)\s+"
            r"(?:số\s+)?\d{1,4}/\d{2,4}/[A-ZĐ0-9-]+\b",
            re.IGNORECASE,
        )

        vietnamese_surnames = (
            "Nguyễn|Trần|Lê|Phạm|Hoàng|Huỳnh|Phan|Vũ|Võ|Đặng|Bùi|Đỗ|Hồ|Ngô|"
            "Dương|Lý|Trịnh|Đinh|Đoàn|Lâm|Mai|Đào|Cao|Phùng|Tiêu|Thạch|Tô|"
            "Tạ|Chu|Chung|Khúc|Kiều|Kim|La|Lã|Lại|Lưu|Mạc|Mạch|Nghiêm|Ngụy|"
            "Phó|Quách|Tôn|Trang|Triệu|Vương|Hà|Tăng|Tống|Hứa|Âu|Âu Dương"
        )
        self.person_pattern = re.compile(
            rf"\b(?:{vietnamese_surnames})\s+[{VI_UPPER}][{VI_LOWER}]+"
            rf"(?:\s+[{VI_UPPER}][{VI_LOWER}]+){{1,3}}\b"
        )
        self.titled_person_pattern = re.compile(
            rf"\b(?:ông|bà|anh|chị|đồng chí|giáo sư|tiến sĩ|bác sĩ|luật sư)\s+"
            rf"([{VI_UPPER}][{VI_LOWER}]+(?:\s+[{VI_UPPER}][{VI_LOWER}]+){{1,3}})\b"
        )
        self.dynamic_loc_pattern = re.compile(
            rf"\b(?:tỉnh|thành phố|tp|quận|huyện|thị xã|xã|phường|đảo|vịnh|"
            rf"sông|núi|hồ)\s+(?:[{VI_UPPER}][{VI_LOWER}]+|\d+)"
            rf"(?:\s+(?:[{VI_UPPER}][{VI_LOWER}]+|\d+)){{0,3}}\b"
        )
        self.capitalized_loc_pattern = re.compile(
            r"\b(?:Mỹ|Anh|Pháp|Đức|Ý|Nga)\b"
        )

        self.lexicons = self._build_seed_lexicons()
        self._merge_external_lexicons()
        self.lexicons = {
            entity_type: {
                normalized
                for item in items
                if (normalized := _normalize_for_match(item))
            }
            for entity_type, items in self.lexicons.items()
        }
        self.lexicon_index: Dict[str, Set[str]] = {}
        for entity_type, values in self.lexicons.items():
            for value in values:
                self.lexicon_index.setdefault(value, set()).add(entity_type)
        self.max_lexicon_ngram = max(
            (len(value.split()) for value in self.lexicon_index),
            default=1,
        )
        self.titlecase_lexicons = self._load_titlecase_lexicons()
        self.titlecase_index: Dict[str, Set[str]] = {}
        for entity_type, values in self.titlecase_lexicons.items():
            for value in values:
                self.titlecase_index.setdefault(value, set()).add(entity_type)
        self.max_titlecase_ngram = max(
            (len(value.split()) for value in self.titlecase_index),
            default=1,
        )
        self.titlecase_connector_tokens = {
            "a",
            "an",
            "and",
            "da",
            "de",
            "del",
            "di",
            "do",
            "du",
            "la",
            "las",
            "le",
            "los",
            "of",
            "the",
            "van",
            "von",
        }

    def _build_seed_lexicons(self) -> Dict[str, Set[str]]:
        return {
            "ORG": _terms(
                """
                chính phủ|quốc hội|văn phòng chính phủ|tòa án nhân dân tối cao|viện kiểm sát nhân dân tối cao|
                bộ công an|bộ quốc phòng|bộ ngoại giao|bộ tư pháp|bộ tài chính|bộ công thương|bộ y tế|
                bộ giáo dục và đào tạo|bộ nông nghiệp và môi trường|bộ xây dựng|bộ nội vụ|bộ văn hóa thể thao và du lịch|
                bộ khoa học và công nghệ|ngân hàng nhà nước|ủy ban chứng khoán nhà nước|tổng cục thuế|tổng cục hải quan|
                đảng cộng sản việt nam|mặt trận tổ quốc việt nam|ủy ban nhân dân|hội đồng nhân dân|
                liên hợp quốc|united nations|nato|eu|asean|who|wto|imf|world bank|unesco|unicef|fao|iaea|opec|g7|g20|
                vtv|vtc|vov|vietnamnet|vnexpress|tuổi trẻ|thanh niên|dân trí|lao động|nhân dân|reuters|ap|afp|bbc|cnn|bloomberg|
                vingroup|vinfast|vinhomes|vinmec|vinschool|fpt|fpt software|fpt telecom|viettel|viettel post|viettel telecom|
                vnpt|mobifone|vng|zalo|masan|thaco|trường hải|sun group|flc|novaland|hòa phát|petrovietnam|pvn|petrolimex|
                vietnam airlines|vietjet air|vietjet|bamboo airways|pacific airlines|
                vietcombank|bidv|agribank|vietinbank|techcombank|mb bank|mbbank|vpbank|acb|sacombank|hdbank|shb|tpbank|vib|eximbank|
                ngân hàng thế giới|ngân hàng phát triển châu á|adb|
                apple|microsoft|google|alphabet|meta|facebook|instagram|whatsapp|tiktok|bytedance|openai|anthropic|nvidia|amd|intel|
                samsung|lg|sony|toyota|honda|ford|tesla|mercedes benz|bmw|audi|hyundai|xiaomi|huawei|oppo|vivo|
                đại học quốc gia hà nội|đại học quốc gia tp hcm|đại học bách khoa hà nội|đại học kinh tế quốc dân|
                đại học ngoại thương|đại học y hà nội|học viện kỹ thuật mật mã|học viện báo chí và tuyên truyền|
                bệnh viện bạch mai|bệnh viện chợ rẫy|bệnh viện việt đức|bệnh viện nhi trung ương|bệnh viện 108|
                fifa|uefa|afc|vff|ioc|nba|f1|formula one|premier league|la liga|serie a|bundesliga
                """
            ),
            "LOC": _terms(
                """
                hà nội|tp hcm|tp hồ chí minh|thành phố hồ chí minh|hồ chí minh|sài gòn|đà nẵng|hải phòng|cần thơ|
                an giang|bà rịa vũng tàu|bạc liêu|bắc giang|bắc kạn|bắc ninh|bến tre|bình dương|bình định|
                bình phước|bình thuận|cà mau|cao bằng|đắk lắk|đắk nông|điện biên|đồng nai|đồng tháp|gia lai|
                hà giang|hà nam|hà tĩnh|hải dương|hậu giang|hưng yên|khánh hòa|kiên giang|kon tum|
                lai châu|lâm đồng|lạng sơn|lào cai|long an|nam định|nghệ an|ninh bình|ninh thuận|phú thọ|phú yên|
                quảng bình|quảng nam|quảng ngãi|quảng ninh|quảng trị|sóc trăng|sơn la|tây ninh|thái bình|
                thái nguyên|thanh hóa|thừa thiên huế|huế|tiền giang|trà vinh|tuyên quang|vĩnh long|vĩnh phúc|yên bái|
                hoàng sa|trường sa|phú quốc|côn đảo|lý sơn|cát bà|cô tô|vịnh hạ long|biển đông|sông hồng|sông mekong|
                việt nam|lào|campuchia|thái lan|myanmar|malaysia|singapore|indonesia|philippines|brunei|
                trung quốc|đài loan|hồng kông|ma cao|nhật bản|hàn quốc|triều tiên|ấn độ|pakistan|bangladesh|
                nepal|bhutan|sri lanka|maldives|mông cổ|kazakhstan|uzbekistan|iran|iraq|israel|palestine|
                ả rập xê út|uae|qatar|kuwait|oman|thổ nhĩ kỳ|
                ukraine|vương quốc anh|tây ban nha|bồ đào nha|hà lan|bỉ|thụy sĩ|áo|
                thụy điển|na uy|đan mạch|phần lan|ba lan|séc|slovakia|hungary|romania|bulgaria|hy lạp|
                hoa kỳ|canada|mexico|brazil|argentina|chile|peru|colombia|cuba|
                ai cập|nam phi|nigeria|kenya|ethiopia|morocco|
                australia|new zealand|châu á|châu âu|châu phi|bắc mỹ|nam mỹ|châu đại dương|đông nam á|
                washington|new york|los angeles|san francisco|london|paris|berlin|rome|madrid|barcelona|
                tokyo|seoul|beijing|bắc kinh|thượng hải|hong kong|bangkok|jakarta|kuala lumpur|manila|sydney|
                melbourne|moscow|kyiv|dubai|doha|singapore
                """
            ),
            "JOB": _terms(
                """
                chủ tịch nước|tổng bí thư|thủ tướng|phó thủ tướng|chủ tịch quốc hội|bộ trưởng|thứ trưởng|
                bí thư|phó bí thư|chủ tịch|phó chủ tịch|đại biểu quốc hội|đại sứ|người phát ngôn|
                tổng giám đốc|giám đốc điều hành|ceo|cfo|cto|giám đốc|phó giám đốc|trưởng phòng|quản lý|
                doanh nhân|nhà sáng lập|chủ tịch hội đồng quản trị|
                giáo sư|phó giáo sư|tiến sĩ|thạc sĩ|giảng viên|giáo viên|hiệu trưởng|sinh viên|học sinh|
                bác sĩ|y sĩ|điều dưỡng|dược sĩ|chuyên gia|nhà khoa học|kỹ sư|kiến trúc sư|lập trình viên|
                nhà nghiên cứu|luật sư|thẩm phán|kiểm sát viên|điều tra viên|
                nhà báo|phóng viên|biên tập viên|người dẫn chương trình|
                đại tá|thượng tá|trung tá|thiếu tá|đại úy|trung úy|thiếu úy|tướng lĩnh|binh sĩ|
                huấn luyện viên|cầu thủ|vận động viên|trọng tài|tay vợt|kình ngư|
                diễn viên|ca sĩ|nhạc sĩ|đạo diễn|người mẫu|hoa hậu|nghệ sĩ|họa sĩ|nhà văn|nhà thơ
                """
            ),
            "EVENT": _terms(
                """
                sea games|asian games|world cup|fifa world cup|euro|asian cup|aff cup|olympic|paralympic|
                champions league|europa league|premier league|la liga|serie a|bundesliga|v league|
                giải vô địch quốc gia|giải bóng đá vô địch quốc gia|
                hội nghị thượng đỉnh|diễn đàn kinh tế thế giới|wef|đại hội đảng|kỳ họp quốc hội|bầu cử|
                hội nghị cop|cop28|cop29|cop30|aasc|apec|asean summit|
                tết nguyên đán|tết dương lịch|giỗ tổ hùng vương|quốc khánh|ngày giải phóng miền nam|
                ngày quốc tế lao động|ngày nhà giáo việt nam|ngày phụ nữ việt nam|
                liên hoan phim cannes|liên hoan phim berlin|liên hoan phim venice|met gala|
                ces|wwdc|google i o|mobile world congress|mwc|
                bão yagi|bão noru|el nino|la nina|động đất|sóng thần|hạn hán|lũ quét|nắng nóng
                """
            ),
            "PRODUCT": _terms(
                """
                iphone|iphone 15|iphone 15 pro|iphone 16|iphone 16 pro|ipad|ipad pro|macbook|macbook air|macbook pro|
                apple watch|airpods|vision pro|
                samsung galaxy|galaxy s24|galaxy s25|galaxy z fold|galaxy z flip|
                google pixel|pixel 8|pixel 9|xiaomi 14|xiaomi 15|oppo find x|vivo x|
                windows|windows 11|android|ios|ipados|macos|linux|ubuntu|
                chatgpt|gpt 4|gpt 4o|gemini|claude|copilot|deepseek|llama|
                chrome|edge|firefox|safari|youtube|facebook|instagram|threads|zalo|tiktok|
                playstation|xbox|nintendo switch|steam deck|
                geforce rtx|rtx 4090|rtx 5090|snapdragon|apple silicon|
                vinfast vf 3|vinfast vf 5|vinfast vf 6|vinfast vf 7|vinfast vf 8|vinfast vf 9|
                toyota camry|toyota vios|honda city|honda civic|ford ranger|tesla model 3|tesla model y|
                starlink|falcon 9|starship
                """
            ),
            "LAW": _terms(
                """
                luật đất đai|luật nhà ở|luật thủ đô|luật doanh nghiệp|luật đầu tư|luật giao thông đường bộ|
                luật trật tự an toàn giao thông đường bộ|luật căn cước|luật an ninh mạng|luật bảo hiểm xã hội|
                luật giáo dục|luật khám bệnh chữa bệnh|luật phòng chống tham nhũng|luật thuế giá trị gia tăng|
                luật thuế thu nhập cá nhân|luật ngân sách nhà nước|luật bảo vệ môi trường|luật cạnh tranh|
                luật sở hữu trí tuệ|luật báo chí|luật điện ảnh|luật công đoàn|luật hôn nhân và gia đình|
                bộ luật dân sự|bộ luật hình sự|bộ luật lao động|bộ luật tố tụng hình sự|bộ luật tố tụng dân sự
                """
            ),
            "FACILITY": _terms(
                """
                sân bay nội bài|sân bay tân sơn nhất|sân bay long thành|sân bay đà nẵng|sân bay cam ranh|
                cảng cái mép|cảng hải phòng|cảng cát lái|ga hà nội|ga sài gòn|
                sân vận động mỹ đình|sân vận động hàng đẫy|sân vận động thống nhất|sân vận động quốc gia|
                cầu nhật tân|cầu long biên|cầu rồng|cầu cần thơ|cầu mỹ thuận|
                bệnh viện bạch mai|bệnh viện chợ rẫy|bệnh viện việt đức|bệnh viện nhi trung ương|bệnh viện 108|
                đại học quốc gia hà nội|đại học quốc gia tp hcm|đại học bách khoa hà nội|đại học kinh tế quốc dân|
                nhà hát lớn hà nội|lăng chủ tịch hồ chí minh|dinh độc lập|phố đi bộ nguyễn huệ|
                khu công nghệ cao hòa lạc|khu công nghệ cao tp hcm|khu kinh tế vân phong|khu kinh tế nghi sơn|
                vườn quốc gia phong nha kẻ bàng|vườn quốc gia cúc phương|vườn quốc gia cát tiên
                """
            ),
            "VEHICLE": _terms(
                """
                vinfast vf 3|vinfast vf 5|vinfast vf 6|vinfast vf 7|vinfast vf 8|vinfast vf 9|
                toyota vios|toyota camry|toyota corolla cross|honda city|honda civic|honda cr v|
                ford ranger|ford everest|hyundai accent|hyundai tucson|kia seltos|kia carnival|
                mazda 3|mazda cx 5|tesla model 3|tesla model y|mercedes c class|bmw x5|
                airbus a320|airbus a350|boeing 737|boeing 787|f 16|f 35|su 30|
                metro số 1|tàu cát linh hà đông|shinkansen
                """
            ),
            "AWARD": _terms(
                """
                giải nobel|nobel hòa bình|nobel văn học|nobel y sinh|nobel vật lý|nobel hóa học|
                oscar|academy awards|grammy|emmy|golden globe|quả cầu vàng|bafta|cannes|
                quả bóng vàng|ballon d or|fifa the best|puskas|mvp|pulitzer|
                giải thưởng hồ chí minh|giải thưởng nhà nước|mai vàng|cánh diều vàng|làn sóng xanh
                """
            ),
            "DISEASE": _terms(
                """
                covid 19|covid-19|sars cov 2|cúm a|cúm b|cúm gia cầm|sởi|sốt xuất huyết|tay chân miệng|
                thủy đậu|bạch hầu|ho gà|uốn ván|lao|sốt rét|dịch tả|viêm gan b|viêm gan c|
                ung thư|ung thư phổi|ung thư gan|ung thư vú|tiểu đường|đái tháo đường|tăng huyết áp|
                đột quỵ|bệnh tim mạch|hen suyễn|trầm cảm|alzheimer|parkinson|ebola|mpox
                """
            ),
            "SPORT_TEAM": _terms(
                """
                đội tuyển việt nam|u23 việt nam|u20 việt nam|u17 việt nam|đội tuyển thái lan|đội tuyển nhật bản|
                real madrid|barcelona|atletico madrid|manchester united|manchester city|liverpool|arsenal|chelsea|
                tottenham|bayern munich|borussia dortmund|juventus|inter milan|ac milan|napoli|psg|
                argentina|brazil|tây ban nha|bồ đào nha|
                los angeles lakers|golden state warriors|boston celtics|miami heat|
                hà nội fc|công an hà nội|thể công viettel|hoàng anh gia lai|becamex bình dương
                """
            ),
            "WORK_OF_ART": _terms(
                """
                đất rừng phương nam|bố già|nhà bà nữ|mắt biếc|em và trịnh|đào phở và piano|
                parasite|oppenheimer|barbie|avatar|titanic|the godfather|dune|interstellar|
                squid game|game of thrones|friends|breaking bad|
                trống cơm|tiến quân ca|nối vòng tay lớn|see tình|flowers|
                truyện kiều|dế mèn phiêu lưu ký|số đỏ|nhật ký trong tù
                """
            ),
            "LANGUAGE": _terms(
                """
                tiếng việt|tiếng anh|tiếng trung|tiếng nhật|tiếng hàn|tiếng pháp|tiếng đức|tiếng nga|
                tiếng tây ban nha|tiếng bồ đào nha|tiếng thái|tiếng lào|tiếng khmer|tiếng indonesia|
                tiếng malaysia|tiếng ả rập|tiếng hindi|tiếng latin
                """
            ),
            "NATIONALITY": _terms(
                """
                người việt nam|người việt|người mỹ|người hoa kỳ|người trung quốc|người nhật bản|người hàn quốc|
                người nga|người ukraine|người anh|người pháp|người đức|người ý|người tây ban nha|
                người thái lan|người singapore|người indonesia|người malaysia|người philippines|
                người ấn độ|người australia|người canada|người brazil
                """
            ),
            "CRYPTO": _terms(
                """
                bitcoin|btc|ethereum|eth|tether|usdt|bnb|solana|sol|xrp|dogecoin|doge|
                cardano|ada|tron|trx|toncoin|ton|litecoin|ltc
                """
            ),
        }

    def _merge_external_lexicons(self) -> None:
        lexicon_path = Path(__file__).resolve().parents[1] / "data" / "ner_lexicons.json"
        if not lexicon_path.exists():
            return

        try:
            payload = json.loads(lexicon_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        if not isinstance(payload, dict):
            return

        for entity_type, values in payload.items():
            normalized_type = str(entity_type).upper().strip()
            if normalized_type not in self.TYPE_ORDER or not isinstance(values, Iterable) or isinstance(values, (str, bytes)):
                continue
            self.lexicons.setdefault(normalized_type, set()).update(
                str(value).strip() for value in values if str(value).strip()
            )

    def _load_titlecase_lexicons(self) -> Dict[str, Set[str]]:
        lexicon_path = Path(__file__).resolve().parents[1] / "data" / "ner_titlecase_lexicons.json"
        if not lexicon_path.exists():
            return {}

        try:
            payload = json.loads(lexicon_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

        if not isinstance(payload, dict):
            return {}

        lexicons: Dict[str, Set[str]] = {}
        for entity_type, values in payload.items():
            normalized_type = str(entity_type).upper().strip()
            if normalized_type not in self.TYPE_ORDER or not isinstance(values, Iterable) or isinstance(values, (str, bytes)):
                continue
            normalized_values = {
                normalized
                for value in values
                if (normalized := _normalize_for_match(str(value)))
            }
            if normalized_values:
                lexicons[normalized_type] = normalized_values
        return lexicons

    def _extract_lexicon_maxmatch(self, text: str) -> Dict[str, Set[str]]:
        words = _normalize_for_match(text).split()
        found: Dict[str, Set[str]] = {entity_type: set() for entity_type in self.lexicons}

        i = 0
        while i < len(words):
            matched_length = 0
            matched_phrase = ""
            matched_types: Set[str] = set()

            max_length = min(self.max_lexicon_ngram, len(words) - i)
            for length in range(max_length, 0, -1):
                phrase = " ".join(words[i : i + length])
                entity_types = self.lexicon_index.get(phrase)
                if entity_types:
                    matched_length = length
                    matched_phrase = phrase
                    matched_types = entity_types
                    break

            if matched_length:
                for entity_type in matched_types:
                    found.setdefault(entity_type, set()).add(matched_phrase)
                i += matched_length
            else:
                i += 1

        return found

    def _extract_titlecase_lexicon_maxmatch(self, text: str) -> Dict[str, Set[str]]:
        found: Dict[str, Set[str]] = {entity_type: set() for entity_type in self.titlecase_lexicons}
        if not self.titlecase_index:
            return found

        tokens = [
            (_normalize_for_match(match.group()), match.group(), match.start(), match.end())
            for match in re.finditer(r"\w+", text, flags=re.UNICODE)
        ]
        person_spans = [
            (match.start(), match.end())
            for pattern in (self.person_pattern, self.titled_person_pattern)
            for match in pattern.finditer(text)
        ]
        person_name_tokens = {
            token
            for span_start, span_end in person_spans
            for token in _normalize_for_match(text[span_start:span_end]).split()
        }

        def is_titleish(raw: str, normalized: str) -> bool:
            return (
                raw[0].isupper()
                or raw.isupper()
                or normalized in self.titlecase_connector_tokens
                or raw.isdigit()
            )

        def overlaps_person(start: int, end: int) -> bool:
            return any(start >= span_start and end <= span_end for span_start, span_end in person_spans)

        i = 0
        while i < len(tokens):
            matched_length = 0
            matched_phrase = ""
            matched_types: Set[str] = set()

            max_length = min(self.max_titlecase_ngram, len(tokens) - i)
            for length in range(max_length, 0, -1):
                window = tokens[i : i + length]
                normalized_tokens = [item[0] for item in window]
                raw_tokens = [item[1] for item in window]
                start = window[0][2]
                end = window[-1][3]
                phrase = " ".join(normalized_tokens)
                entity_types = self.titlecase_index.get(phrase)
                if not entity_types:
                    continue
                if not all(
                    is_titleish(raw, normalized)
                    for normalized, raw in zip(normalized_tokens, raw_tokens)
                ):
                    continue
                previous_token = tokens[i - 1] if i > 0 else None
                next_token = tokens[i + length] if i + length < len(tokens) else None
                if previous_token and is_titleish(previous_token[1], previous_token[0]):
                    continue
                if next_token and is_titleish(next_token[1], next_token[0]):
                    continue
                if overlaps_person(start, end):
                    continue
                if length == 1 and phrase in person_name_tokens:
                    continue
                matched_length = length
                matched_phrase = phrase
                matched_types = entity_types
                break

            if matched_length:
                for entity_type in matched_types:
                    found.setdefault(entity_type, set()).add(matched_phrase)
                i += matched_length
            else:
                i += 1

        return found

    @staticmethod
    def _sorted(values: Iterable[str]) -> List[str]:
        return sorted({value.strip() for value in values if value and value.strip()})

    def _extract_capitalized_single_token_locs(self, text: str) -> Set[str]:
        found: Set[str] = set()
        blocked_prefixes = re.compile(
            r"(?:tỉnh|thành phố|tp|quận|huyện|thị xã|xã|phường|sân vận động|người|tiếng)\s+$",
            re.IGNORECASE,
        )
        preceding_title_token = re.compile(rf"[{VI_UPPER}][{VI_LOWER}]+\s+$")
        following_title_token = re.compile(rf"^\s+[{VI_UPPER}][{VI_LOWER}]+")

        for match in self.capitalized_loc_pattern.finditer(text):
            before = text[max(0, match.start() - 24) : match.start()]
            after = text[match.end() : match.end() + 24]
            if (
                blocked_prefixes.search(before)
                or preceding_title_token.search(before)
                or following_title_token.search(after)
            ):
                continue
            found.add(_normalize_for_match(match.group()))

        return found

    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        entities: Dict[str, Set[str]] = {entity_type: set() for entity_type in self.TYPE_ORDER}
        if not text:
            return {entity_type: [] for entity_type in self.TYPE_ORDER}

        entities["MONEY"].update(match.lower() for match in self.money_pattern.findall(text))
        entities["DATE"].update(match.lower() for match in self.date_pattern.findall(text))
        entities["TIME"].update(match.lower() for match in self.time_pattern.findall(text))
        entities["PERCENT"].update(match.lower() for match in self.percent_pattern.findall(text))
        entities["PHONE"].update(self.phone_pattern.findall(text))
        entities["EMAIL"].update(self.email_pattern.findall(text))
        entities["URL"].update(self.url_pattern.findall(text))
        entities["AGE"].update(match.lower() for match in self.age_pattern.findall(text))
        entities["TEMPERATURE"].update(match.lower() for match in self.temperature_pattern.findall(text))
        entities["QUANTITY"].update(match.lower() for match in self.quantity_pattern.findall(text))
        entities["SCORE"].update(match.replace(" ", "") for match in self.score_pattern.findall(text))
        entities["LAW"].update(match.lower() for match in self.legal_document_pattern.findall(text))

        entities["PERSON"].update(self.person_pattern.findall(text))
        entities["PERSON"].update(self.titled_person_pattern.findall(text))
        entities["LOC"].update(_normalize_for_match(match) for match in self.dynamic_loc_pattern.findall(text))
        entities["LOC"].update(self._extract_capitalized_single_token_locs(text))

        lexicon_matches = self._extract_lexicon_maxmatch(text)
        for entity_type, values in lexicon_matches.items():
            entities.setdefault(entity_type, set()).update(values)
        titlecase_matches = self._extract_titlecase_lexicon_maxmatch(text)
        for entity_type, values in titlecase_matches.items():
            entities.setdefault(entity_type, set()).update(values)

        return {
            entity_type: self._sorted(entities.get(entity_type, set()))
            for entity_type in self.TYPE_ORDER
        }
