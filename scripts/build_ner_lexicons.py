from __future__ import annotations

import json
import re
import urllib.request
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
NORMAL_OUTPUT = DATA_DIR / "ner_lexicons.json"
TITLECASE_OUTPUT = DATA_DIR / "ner_titlecase_lexicons.json"

GEONAMES_COUNTRY_INFO_URL = "https://download.geonames.org/export/dump/countryInfo.txt"
GEONAMES_CITIES_URL = "https://download.geonames.org/export/dump/cities5000.zip"


def split_terms(blob: str) -> set[str]:
    return {item.strip() for item in blob.split("|") if item.strip()}


def normalize(term: str) -> str:
    term = re.sub(r"\s+", " ", term).strip()
    return term


def add_terms(target: dict[str, set[str]], entity_type: str, values: Iterable[str]) -> None:
    target.setdefault(entity_type, set()).update(
        normalize(str(value))
        for value in values
        if normalize(str(value))
    )


VN_PROVINCES = split_terms(
    """
    An Giang|Bà Rịa Vũng Tàu|Bạc Liêu|Bắc Giang|Bắc Kạn|Bắc Ninh|Bến Tre|Bình Dương|
    Bình Định|Bình Phước|Bình Thuận|Cà Mau|Cao Bằng|Đắk Lắk|Đắk Nông|Điện Biên|
    Đồng Nai|Đồng Tháp|Gia Lai|Hà Giang|Hà Nam|Hà Tĩnh|Hải Dương|Hậu Giang|Hòa Bình|
    Hưng Yên|Khánh Hòa|Kiên Giang|Kon Tum|Lai Châu|Lâm Đồng|Lạng Sơn|Lào Cai|Long An|
    Nam Định|Nghệ An|Ninh Bình|Ninh Thuận|Phú Thọ|Phú Yên|Quảng Bình|Quảng Nam|
    Quảng Ngãi|Quảng Ninh|Quảng Trị|Sóc Trăng|Sơn La|Tây Ninh|Thái Bình|Thái Nguyên|
    Thanh Hóa|Thừa Thiên Huế|Tiền Giang|Trà Vinh|Tuyên Quang|Vĩnh Long|Vĩnh Phúc|Yên Bái|
    Hà Nội|Hải Phòng|Đà Nẵng|Cần Thơ|Thành phố Hồ Chí Minh
    """
)

COUNTRIES_VI = split_terms(
    """
    Việt Nam|Lào|Campuchia|Thái Lan|Myanmar|Malaysia|Singapore|Indonesia|Philippines|Brunei|
    Trung Quốc|Nhật Bản|Hàn Quốc|Triều Tiên|Mông Cổ|Ấn Độ|Pakistan|Bangladesh|Nepal|Bhutan|
    Sri Lanka|Maldives|Kazakhstan|Uzbekistan|Kyrgyzstan|Tajikistan|Turkmenistan|Afghanistan|
    Iran|Iraq|Israel|Palestine|Ả Rập Xê Út|Các Tiểu vương quốc Ả Rập Thống nhất|Qatar|Kuwait|
    Oman|Jordan|Lebanon|Syria|Yemen|Thổ Nhĩ Kỳ|Nga|Ukraine|Belarus|Ba Lan|Đức|Pháp|Anh|
    Vương quốc Anh|Ireland|Tây Ban Nha|Bồ Đào Nha|Ý|Hà Lan|Bỉ|Luxembourg|Thụy Sĩ|Áo|
    Thụy Điển|Na Uy|Đan Mạch|Phần Lan|Iceland|Estonia|Latvia|Lithuania|Séc|Slovakia|
    Hungary|Romania|Bulgaria|Hy Lạp|Serbia|Croatia|Slovenia|Bosnia và Herzegovina|Albania|
    Bắc Macedonia|Moldova|Mỹ|Hoa Kỳ|Canada|Mexico|Brazil|Argentina|Chile|Peru|Colombia|
    Venezuela|Ecuador|Bolivia|Paraguay|Uruguay|Cuba|Jamaica|Haiti|Cộng hòa Dominica|
    Australia|New Zealand|Papua New Guinea|Ai Cập|Libya|Tunisia|Algeria|Morocco|Sudan|
    Ethiopia|Kenya|Uganda|Tanzania|Rwanda|Burundi|Somalia|Nam Phi|Nigeria|Ghana|Bờ Biển Ngà|
    Senegal|Cameroon|Angola|Mozambique|Madagascar
    """
)

LANGUAGES = split_terms(
    """
    Việt|Anh|Trung|Nhật|Hàn|Pháp|Đức|Nga|Tây Ban Nha|Bồ Đào Nha|Ý|Thái|Lào|Khmer|
    Indonesia|Malaysia|Tagalog|Hindi|Urdu|Bengali|Tamil|Telugu|Marathi|Gujarati|Punjabi|
    Ả Rập|Do Thái|Ba Tư|Thổ Nhĩ Kỳ|Hy Lạp|Latin|Hà Lan|Thụy Điển|Na Uy|Đan Mạch|
    Phần Lan|Ba Lan|Séc|Slovakia|Hungary|Romania|Bulgaria|Serbia|Croatia|Ukraine|Belarus|
    Swahili|Zulu|Afrikaans|Esperanto
    """
)

EXTRA_ORG = split_terms(
    """
    Bộ Kế hoạch và Đầu tư|Bộ Tài nguyên và Môi trường|Bộ Lao động Thương binh và Xã hội|
    Bộ Thông tin và Truyền thông|Bộ Giao thông Vận tải|Bộ Nông nghiệp và Phát triển Nông thôn|
    Bộ Văn hóa Thể thao và Du lịch|Bộ Khoa học và Công nghệ|Bộ Xây dựng|Bộ Nội vụ|
    Văn phòng Quốc hội|Văn phòng Chủ tịch nước|Kiểm toán Nhà nước|Thanh tra Chính phủ|
    Bảo hiểm Xã hội Việt Nam|Tập đoàn Điện lực Việt Nam|EVN|Tập đoàn Bưu chính Viễn thông Việt Nam|
    Tập đoàn Dầu khí Việt Nam|Tập đoàn Hóa chất Việt Nam|Tập đoàn Công nghiệp Than Khoáng sản Việt Nam|
    Tổng công ty Cảng hàng không Việt Nam|ACV|Tổng công ty Đường sắt Việt Nam|Vietnam Railways|
    Cục Hàng không Việt Nam|Cục Đường bộ Việt Nam|Cục Đăng kiểm Việt Nam|Cục Thuế|Cục Hải quan|
    Đại học Bách khoa TP HCM|Đại học Khoa học Tự nhiên|Đại học Khoa học Xã hội và Nhân văn|
    Đại học Cần Thơ|Đại học Huế|Đại học Đà Nẵng|Đại học Sư phạm Hà Nội|Đại học Y Dược TP HCM|
    Bệnh viện Đại học Y Dược TP HCM|Bệnh viện K|Bệnh viện Từ Dũ|Bệnh viện Hùng Vương|
    Bệnh viện Trung ương Huế|Bệnh viện Chấn thương Chỉnh hình|Bệnh viện Nhi Đồng 1|Bệnh viện Nhi Đồng 2|
    Reuters|Associated Press|Agence France Presse|Financial Times|The Guardian|The New York Times|
    Wall Street Journal|Forbes|Fortune|Nikkei Asia|The Economist|Al Jazeera|Bloomberg News|
    Amazon|Alibaba|Tencent|Baidu|Oracle|IBM|Cisco|Qualcomm|TSMC|ASML|SpaceX|Blue Origin|
    Boeing|Airbus|Lockheed Martin|Northrop Grumman|Pfizer|Moderna|AstraZeneca|Johnson and Johnson|
    Roche|Novartis|Sanofi|Siemens|Bosch|Panasonic|Canon|Nikon|Nintendo|Sony Interactive Entertainment|
    Shopee|Lazada|Tiki|Grab|Be|Gojek|MoMo|ZaloPay|VNPay|Sky Mavis|Axie Infinity|
    Manchester United|Manchester City|Liverpool FC|Arsenal FC|Chelsea FC|Real Madrid CF|FC Barcelona|
    Bayern Munich|Paris Saint Germain|Juventus FC|Inter Milan|AC Milan|Golden State Warriors|
    Los Angeles Lakers|Boston Celtics|Miami Heat
    """
)

EXTRA_JOB = split_terms(
    """
    quyền chủ tịch|quyền tổng giám đốc|phó tổng giám đốc|giám đốc tài chính|giám đốc công nghệ|
    giám đốc sản phẩm|giám đốc vận hành|chủ nhiệm ủy ban|chủ nhiệm văn phòng|chánh án|phó chánh án|
    viện trưởng|phó viện trưởng|cục trưởng|phó cục trưởng|vụ trưởng|phó vụ trưởng|trưởng ban|
    phó trưởng ban|chánh văn phòng|phó chánh văn phòng|người phát ngôn|cố vấn|trợ lý|phụ tá|
    nhà đầu tư|môi giới|kiểm toán viên|kế toán trưởng|chuyên viên phân tích|nhà quản lý quỹ|
    chuyên gia kinh tế|chuyên gia tài chính|chuyên gia y tế|chuyên gia khí tượng|nhà khí tượng học|
    kỹ thuật viên|dược tá|hộ sinh|bác sĩ nội trú|bác sĩ phẫu thuật|nhà trị liệu|chuyên gia tâm lý|
    đạo diễn hình ảnh|biên kịch|nhà sản xuất|vũ công|biên đạo múa|mc|streamer|youtuber|tiktoker|
    game thủ|bình luận viên|trợ lý huấn luyện viên|đội trưởng|thủ môn|tiền đạo|tiền vệ|hậu vệ|
    phi công|tiếp viên hàng không|thuyền trưởng|thủy thủ|lái tàu|tài xế|thợ máy|nông dân|ngư dân|
    công nhân|thợ mỏ|thợ điện|thợ hàn|đầu bếp|barista|nhân viên bán hàng|nhân viên cứu hộ
    """
)

EXTRA_EVENT = split_terms(
    """
    Đại hội Thể thao Đông Nam Á|Đại hội Thể thao châu Á|Thế vận hội mùa hè|Thế vận hội mùa đông|
    Paralympic mùa hè|Paralympic mùa đông|Cúp C1 châu Âu|Europa Conference League|
    Copa America|African Cup of Nations|AFC Champions League|Club World Cup|Vòng loại World Cup|
    Diễn đàn Hợp tác Kinh tế châu Á Thái Bình Dương|Hội nghị Bộ trưởng Ngoại giao ASEAN|
    Hội nghị An ninh Munich|Hội nghị Thượng đỉnh G7|Hội nghị Thượng đỉnh G20|Hội nghị Thượng đỉnh BRICS|
    Hội nghị Liên Hợp Quốc về Biến đổi Khí hậu|Ngày Trái Đất|Giờ Trái Đất|Tuần lễ thời trang Paris|
    Tuần lễ thời trang Milan|Tuần lễ thời trang New York|Lễ hội pháo hoa quốc tế Đà Nẵng|
    Festival Huế|Đường hoa Nguyễn Huệ|Hội sách TP HCM|Ngày hội khởi nghiệp đổi mới sáng tạo quốc gia|
    Vietnam Motor Show|Vietnam Expo|Vietnam Foodexpo|Vietnam International Fashion Week|
    Google Cloud Next|Microsoft Build|OpenAI DevDay|Apple Event|Samsung Galaxy Unpacked|
    Amazon Prime Day|Black Friday|Cyber Monday|Singles Day|Ngày của Mẹ|Ngày của Cha|
    Valentine|Halloween|Giáng sinh|Lễ Phục sinh|Ramadan|Tết Trung thu|Lễ Vu Lan
    """
)

EXTRA_PRODUCT = split_terms(
    """
    iPhone SE|iPhone Mini|iPhone Plus|iPhone Pro Max|iPad Mini|iPad Air|iMac|Mac Mini|Mac Studio|
    Apple TV|HomePod|Apple Pencil|Galaxy Note|Galaxy A|Galaxy M|Galaxy Tab|Galaxy Watch|Galaxy Buds|
    Pixel Watch|Pixel Fold|Pixel Tablet|Surface Laptop|Surface Pro|Surface Duo|ThinkPad|IdeaPad|
    Zenbook|ROG Phone|Redmi Note|Poco F|Poco X|Huawei Mate|Huawei P|Honor Magic|Oppo Reno|
    Vivo V|Vivo X|OnePlus|Nothing Phone|Nokia Lumia|PlayStation 5|Xbox Series X|Xbox Series S|
    Nintendo Switch OLED|Steam Deck OLED|Meta Quest|Quest 3|VisionOS|watchOS|tvOS|ChromeOS|
    Office 365|Microsoft 365|Google Workspace|OneDrive|Google Drive|Dropbox|Notion|Slack|Teams|
    Zoom|Meet|Gmail|Outlook|Photoshop|Illustrator|Premiere Pro|After Effects|Figma|Canva|
    TensorFlow|PyTorch|Kubernetes|Docker|PostgreSQL|MySQL|MongoDB|Redis|Kafka|Elasticsearch|
    Corolla Cross|Fortuner|Innova Cross|Land Cruiser|Hilux|Yaris Cross|Honda CR V|Honda HR V|
    Honda Accord|Mitsubishi Xpander|Mitsubishi Outlander|Hyundai Santa Fe|Hyundai Creta|Kia Sonet|
    Kia K3|Mazda CX 30|Mazda CX 8|Ford Territory|Ford Explorer|Mercedes E Class|Mercedes GLC|
    BMW 3 Series|BMW 5 Series|Audi A4|Audi Q5|Tesla Model S|Tesla Model X|Tesla Cybertruck|
    VF e34|VF 3|VF 5|VF 6|VF 7|VF 8|VF 9|Falcon Heavy|Dragon|Crew Dragon|Starship|
    GPT 3.5|GPT 4 Turbo|GPT 4.1|GPT 4o mini|Claude Sonnet|Claude Opus|Gemini Flash|Gemini Pro|
    Llama 3|Llama 4|DeepSeek R1|Qwen|Mistral|Grok
    """
)

EXTRA_LAW = split_terms(
    """
    Luật Quy hoạch|Luật Đấu thầu|Luật Đầu tư công|Luật Chứng khoán|Luật Các tổ chức tín dụng|
    Luật Kinh doanh bất động sản|Luật Công chứng|Luật Dược|Luật Khám bệnh chữa bệnh|
    Luật Phòng chống tác hại của rượu bia|Luật Phòng chống bạo lực gia đình|Luật Trẻ em|
    Luật Thanh niên|Luật Người lao động Việt Nam đi làm việc ở nước ngoài theo hợp đồng|
    Luật Bảo vệ quyền lợi người tiêu dùng|Luật Viễn thông|Luật Tần số vô tuyến điện|
    Luật Giao dịch điện tử|Luật Dữ liệu|Luật Công nghiệp công nghệ số|Luật Điện lực|
    Luật Tài nguyên nước|Luật Địa chất và khoáng sản|Luật Phòng cháy chữa cháy và cứu nạn cứu hộ|
    Luật Phòng chống thiên tai|Luật Đường sắt|Luật Hàng không dân dụng Việt Nam|
    Luật Biển Việt Nam|Luật Nghĩa vụ quân sự|Luật Quốc phòng|Luật Công an nhân dân|
    Luật Thi hành án hình sự|Luật Tố cáo|Luật Khiếu nại|Luật Tiếp công dân|Luật Cư trú|
    Luật Xuất cảnh nhập cảnh của công dân Việt Nam|Luật Giáo dục đại học|Luật Giáo dục nghề nghiệp|
    Luật Thư viện|Luật Di sản văn hóa|Luật Thể dục thể thao|Luật Du lịch|Luật Báo chí|
    Luật Xuất bản|Luật Quảng cáo|Luật Điện ảnh|Luật Sở hữu trí tuệ|Luật Khoa học và công nghệ
    """
)

EXTRA_FACILITY = split_terms(
    """
    Cảng hàng không quốc tế Nội Bài|Cảng hàng không quốc tế Tân Sơn Nhất|Cảng hàng không quốc tế Đà Nẵng|
    Cảng hàng không quốc tế Cam Ranh|Cảng hàng không quốc tế Phú Quốc|Cảng hàng không quốc tế Cát Bi|
    Cảng hàng không quốc tế Vân Đồn|Nhà ga T3 Tân Sơn Nhất|Ga Hà Nội|Ga Sài Gòn|Ga Đà Nẵng|
    Bến xe Mỹ Đình|Bến xe Giáp Bát|Bến xe Miền Đông|Bến xe Miền Tây|Cảng Cát Lái|Cảng Hải Phòng|
    Cảng Cái Mép|Cảng Tiên Sa|Cầu Vĩnh Tuy|Cầu Thanh Trì|Cầu Bãi Cháy|Cầu Thuận Phước|
    Cầu Trần Thị Lý|Cầu Rạch Miễu|Cầu Cao Lãnh|Cầu Vàm Cống|Hầm Hải Vân|Hầm Thủ Thiêm|
    Phố đi bộ Hồ Gươm|Hồ Hoàn Kiếm|Nhà hát Lớn Hà Nội|Nhà hát Thành phố Hồ Chí Minh|
    Trung tâm Hội nghị Quốc gia|Trung tâm Triển lãm Việt Nam|Sân vận động Hàng Đẫy|
    Sân vận động Thiên Trường|Sân vận động Lạch Tray|Sân vận động Pleiku|Sân vận động Cẩm Phả|
    Bệnh viện Bạch Mai|Bệnh viện Chợ Rẫy|Bệnh viện Việt Đức|Bệnh viện 108|Bệnh viện K|
    Bệnh viện Trung ương Huế|Bệnh viện Từ Dũ|Bệnh viện Hùng Vương|Bệnh viện Nhi Đồng 1|
    Bệnh viện Nhi Đồng 2|Bệnh viện Đại học Y Dược TP HCM|Bệnh viện Phổi Trung ương|
    Đại học Quốc gia Hà Nội|Đại học Quốc gia TP HCM|Đại học Bách khoa Hà Nội|Đại học Bách khoa TP HCM|
    Đại học Ngoại thương|Đại học Kinh tế Quốc dân|Đại học Y Hà Nội|Đại học Cần Thơ|
    Đại học Huế|Đại học Đà Nẵng|Học viện Kỹ thuật Mật mã|Học viện Ngoại giao|
    Vườn quốc gia Cúc Phương|Vườn quốc gia Cát Tiên|Vườn quốc gia Phong Nha Kẻ Bàng|
    Khu công nghệ cao Hòa Lạc|Khu công nghệ cao TP HCM|Khu kinh tế Nghi Sơn|Khu kinh tế Vân Phong
    """
)

EXTRA_VEHICLE = split_terms(
    """
    Toyota Corolla Cross|Toyota Fortuner|Toyota Hilux|Toyota Land Cruiser|Toyota Yaris Cross|
    Honda Accord|Honda CR V|Honda HR V|Honda Brio|Hyundai Accent|Hyundai Creta|Hyundai Santa Fe|
    Kia Sonet|Kia Seltos|Kia Carnival|Mazda CX 30|Mazda CX 5|Mazda CX 8|Mitsubishi Xpander|
    Mitsubishi Outlander|Ford Territory|Ford Everest|Ford Explorer|Mercedes GLC|Mercedes E Class|
    BMW 3 Series|BMW 5 Series|BMW X3|BMW X5|Audi A4|Audi Q5|Tesla Model S|Tesla Model X|
    Tesla Cybertruck|VinFast VF e34|VinFast VF 3|VinFast VF 5|VinFast VF 6|VinFast VF 7|
    VinFast VF 8|VinFast VF 9|Airbus A220|Airbus A321|Airbus A330|Airbus A350|Airbus A380|
    Boeing 737 MAX|Boeing 747|Boeing 777|Boeing 787 Dreamliner|C919|F 15|F 16|F 22|F 35|
    Su 27|Su 30|Su 35|MiG 29|Rafale|Eurofighter Typhoon|Leopard 2|Abrams|T 90|K2 Black Panther|
    Shinkansen|TGV|Eurostar|Metro số 1|Tàu Cát Linh Hà Đông|Tàu Nhổn Ga Hà Nội
    """
)

EXTRA_AWARD = split_terms(
    """
    Nobel Kinh tế|Nobel Hòa bình|Nobel Văn học|Nobel Vật lý|Nobel Hóa học|Nobel Y sinh|
    Oscar Phim hay nhất|Oscar Đạo diễn xuất sắc|Oscar Nam diễn viên chính xuất sắc|
    Oscar Nữ diễn viên chính xuất sắc|Grammy Album của năm|Grammy Bài hát của năm|
    Grammy Nghệ sĩ mới xuất sắc|Emmy|Tony Awards|Cannes Palme d Or|Sư tử vàng|Gấu vàng|
    BAFTA|Critics Choice Awards|SAG Awards|MTV Video Music Awards|Billboard Music Awards|
    Brit Awards|Mercury Prize|Pulitzer|Booker Prize|Goncourt|Cervantes|Hugo Award|Nebula Award|
    Quả bóng vàng|Chiếc giày vàng châu Âu|FIFA The Best|Puskas Award|Laureus World Sports Awards|
    VĐV của năm|MVP mùa giải|Giải thưởng Hồ Chí Minh|Giải thưởng Nhà nước|Mai Vàng|
    Cánh Diều Vàng|Bông Sen Vàng|Làn Sóng Xanh|WeChoice Awards|VinFuture Prize|Sao Khuê
    """
)

EXTRA_DISEASE = split_terms(
    """
    cúm mùa|cúm H1N1|cúm H5N1|cúm H7N9|viêm phổi|viêm phế quản|viêm màng não|viêm não Nhật Bản|
    viêm não mô cầu|viêm gan A|viêm gan D|viêm gan E|xơ gan|gan nhiễm mỡ|suy gan|suy thận|
    bệnh thận mạn|sỏi thận|viêm cầu thận|nhồi máu cơ tim|suy tim|rối loạn nhịp tim|xơ vữa động mạch|
    bệnh mạch vành|bệnh phổi tắc nghẽn mạn tính|copd|ung thư dạ dày|ung thư đại trực tràng|
    ung thư tuyến giáp|ung thư cổ tử cung|ung thư tiền liệt tuyến|ung thư máu|bạch cầu cấp|
    lymphoma|u lympho|đa u tủy xương|viêm khớp dạng thấp|gout|loãng xương|thoái hóa khớp|
    lupus ban đỏ|bệnh celiac|crohn|viêm loét đại tràng|dị ứng|hen phế quản|viêm mũi dị ứng|
    trầm cảm|rối loạn lo âu|rối loạn lưỡng cực|tâm thần phân liệt|mất ngủ|tự kỷ|adhd|
    đau nửa đầu|động kinh|bại não|tay chân miệng|sởi|rubella|quai bị|thủy đậu|bạch hầu|
    ho gà|uốn ván|dại|sốt vàng|zika|chikungunya|ebola|marburg|mpox|hiv|aids|
    lậu|giang mai|chlamydia|sùi mào gà|herpes|sán lá gan|giun đũa|giun móc|ngộ độc thực phẩm|
    sốc phản vệ|say nắng|hạ thân nhiệt|béo phì|suy dinh dưỡng|thiếu máu|thalassemia
    """
)

EXTRA_SPORT_TEAM = split_terms(
    """
    Đội tuyển Việt Nam|Đội tuyển Thái Lan|Đội tuyển Indonesia|Đội tuyển Malaysia|Đội tuyển Singapore|
    Đội tuyển Nhật Bản|Đội tuyển Hàn Quốc|Đội tuyển Trung Quốc|Đội tuyển Australia|Đội tuyển Iran|
    Đội tuyển Qatar|Đội tuyển Saudi Arabia|Đội tuyển Mỹ|Đội tuyển Mexico|Đội tuyển Canada|
    Đội tuyển Brazil|Đội tuyển Argentina|Đội tuyển Uruguay|Đội tuyển Colombia|Đội tuyển Chile|
    Đội tuyển Anh|Đội tuyển Pháp|Đội tuyển Đức|Đội tuyển Tây Ban Nha|Đội tuyển Bồ Đào Nha|
    Đội tuyển Ý|Đội tuyển Hà Lan|Đội tuyển Bỉ|Đội tuyển Croatia|Đội tuyển Serbia|
    U23 Việt Nam|U20 Việt Nam|U17 Việt Nam|U23 Thái Lan|U23 Nhật Bản|U23 Hàn Quốc|
    Hà Nội FC|Công an Hà Nội|Thể Công Viettel|Hoàng Anh Gia Lai|Đông Á Thanh Hóa|
    Becamex Bình Dương|Nam Định FC|Hải Phòng FC|Sông Lam Nghệ An|SHB Đà Nẵng|
    Real Madrid|Barcelona|Atletico Madrid|Manchester United|Manchester City|Liverpool|
    Arsenal|Chelsea|Tottenham|Newcastle United|Bayern Munich|Borussia Dortmund|RB Leipzig|
    Juventus|Inter Milan|AC Milan|Napoli|Roma|Lazio|Paris Saint Germain|Marseille|
    Ajax|PSV Eindhoven|Benfica|Porto|Sporting Lisbon|Celtic|Rangers|
    Los Angeles Lakers|Golden State Warriors|Boston Celtics|Miami Heat|Denver Nuggets|
    Milwaukee Bucks|Chicago Bulls|Phoenix Suns|Dallas Mavericks|New York Knicks
    """
)

EXTRA_WORK_OF_ART = split_terms(
    """
    Chí Phèo|Lão Hạc|Tắt đèn|Vợ nhặt|Rừng xà nu|Dế mèn phiêu lưu ký|Đất rừng phương Nam|
    Nhật ký trong tù|Truyện Kiều|Số đỏ|Nỗi buồn chiến tranh|Cho tôi xin một vé đi tuổi thơ|
    Tôi thấy hoa vàng trên cỏ xanh|Mắt biếc|Cánh đồng bất tận|Bố già|Nhà bà Nữ|
    Em và Trịnh|Đào phở và piano|Ròm|Song lang|Hai Phượng|Mùi cỏ cháy|Tôi thấy hoa vàng trên cỏ xanh|
    The Godfather|The Shawshank Redemption|Forrest Gump|Titanic|Avatar|Inception|Interstellar|
    Oppenheimer|Barbie|Dune|Parasite|La La Land|The Dark Knight|Avengers Endgame|Harry Potter|
    The Lord of the Rings|Game of Thrones|Breaking Bad|Friends|Squid Game|Money Heist|The Crown|
    Bohemian Rhapsody|Hotel California|Imagine|Shape of You|See Tình|Nối vòng tay lớn|
    Tiến quân ca|Trống cơm|Diễm xưa|Hạ trắng|Mùa xuân đầu tiên
    """
)

EXTRA_CRYPTO = split_terms(
    """
    Bitcoin Cash|Wrapped Bitcoin|USDC|Dai|Chainlink|Polkadot|Avalanche|Shiba Inu|Uniswap|
    Stellar|Monero|Cosmos|Filecoin|Aptos|Arbitrum|Optimism|Near Protocol|Internet Computer|
    Hedera|VeChain|Render|Kaspa|Injective|Celestia|Sui|Aave|Maker|Algorand|The Graph|
    Fantom|EOS|Tezos|Theta Network|Immutable|Sei|Bonk|Pepe|Floki|Worldcoin|
    Curve DAO Token|PancakeSwap|Jupiter|Lido DAO|Ethena|Ondo|Pendle|Raydium|Helium|
    Kava|Kusama|Axie Infinity|Decentraland|The Sandbox|Enjin Coin|Chiliz
    """
)


def generated_terms() -> dict[str, set[str]]:
    lexicons: dict[str, set[str]] = {}

    add_terms(lexicons, "ORG", EXTRA_ORG)
    add_terms(lexicons, "JOB", EXTRA_JOB)
    add_terms(lexicons, "EVENT", EXTRA_EVENT)
    add_terms(lexicons, "PRODUCT", EXTRA_PRODUCT)
    add_terms(lexicons, "LAW", EXTRA_LAW)
    add_terms(lexicons, "FACILITY", EXTRA_FACILITY)
    add_terms(lexicons, "VEHICLE", EXTRA_VEHICLE)
    add_terms(lexicons, "AWARD", EXTRA_AWARD)
    add_terms(lexicons, "DISEASE", EXTRA_DISEASE)
    add_terms(lexicons, "SPORT_TEAM", EXTRA_SPORT_TEAM)
    add_terms(lexicons, "WORK_OF_ART", EXTRA_WORK_OF_ART)
    add_terms(lexicons, "CRYPTO", EXTRA_CRYPTO)

    add_terms(
        lexicons,
        "LOC",
        {
            *(f"tỉnh {province}" for province in VN_PROVINCES if not province.startswith("Thành phố")),
            *(f"thành phố {province}" for province in VN_PROVINCES if province in {"Hà Nội", "Hải Phòng", "Đà Nẵng", "Cần Thơ"}),
            "thành phố Hồ Chí Minh",
        },
    )
    add_terms(
        lexicons,
        "ORG",
        {
            *(f"ủy ban nhân dân tỉnh {province}" for province in VN_PROVINCES if not province.startswith("Thành phố")),
            *(f"hội đồng nhân dân tỉnh {province}" for province in VN_PROVINCES if not province.startswith("Thành phố")),
            *(f"công an tỉnh {province}" for province in VN_PROVINCES if not province.startswith("Thành phố")),
            *(f"sở y tế tỉnh {province}" for province in VN_PROVINCES if not province.startswith("Thành phố")),
            *(f"sở giáo dục và đào tạo tỉnh {province}" for province in VN_PROVINCES if not province.startswith("Thành phố")),
            "ủy ban nhân dân thành phố Hà Nội",
            "ủy ban nhân dân thành phố Hồ Chí Minh",
            "ủy ban nhân dân thành phố Hải Phòng",
            "ủy ban nhân dân thành phố Đà Nẵng",
            "ủy ban nhân dân thành phố Cần Thơ",
        },
    )
    add_terms(
        lexicons,
        "FACILITY",
        {
            *(f"bệnh viện đa khoa tỉnh {province}" for province in VN_PROVINCES if not province.startswith("Thành phố")),
            *(f"trung tâm y tế tỉnh {province}" for province in VN_PROVINCES if not province.startswith("Thành phố")),
        },
    )
    add_terms(lexicons, "LANGUAGE", {f"tiếng {language}" for language in LANGUAGES})
    add_terms(lexicons, "NATIONALITY", {f"người {country}" for country in COUNTRIES_VI})
    add_terms(
        lexicons,
        "SPORT_TEAM",
        {
            *(f"đội tuyển {country}" for country in COUNTRIES_VI),
            *(f"u23 {country}" for country in COUNTRIES_VI),
            *(f"u20 {country}" for country in COUNTRIES_VI),
            *(f"u17 {country}" for country in COUNTRIES_VI),
        },
    )
    add_terms(
        lexicons,
        "EVENT",
        {
            *(f"world cup {year}" for year in range(1930, 2035, 4)),
            *(f"euro {year}" for year in range(1960, 2033, 4)),
            *(f"olympic {year}" for year in range(1896, 2033, 4)),
            *(f"sea games {edition}" for edition in range(1, 41)),
            *(f"cop{edition}" for edition in range(1, 41)),
        },
    )

    return lexicons


def fetch_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read().decode("utf-8", errors="replace")


def fetch_cities() -> set[str]:
    with urllib.request.urlopen(GEONAMES_CITIES_URL, timeout=120) as response:
        payload = response.read()

    with zipfile.ZipFile(BytesIO(payload)) as archive:
        file_name = next(name for name in archive.namelist() if name.endswith(".txt"))
        with archive.open(file_name) as handle:
            rows = handle.read().decode("utf-8", errors="replace").splitlines()

    cities = set()
    for row in rows:
        columns = row.split("\t")
        if len(columns) < 2:
            continue
        name = normalize(columns[1])
        if len(name) >= 2 and any(char.isalpha() for char in name):
            cities.add(name)
    return cities


def fetch_country_names() -> set[str]:
    text = fetch_text(GEONAMES_COUNTRY_INFO_URL)
    countries = set()
    for row in text.splitlines():
        if not row or row.startswith("#"):
            continue
        columns = row.split("\t")
        if len(columns) > 4:
            countries.add(normalize(columns[4]))
    return countries


def titlecase_terms() -> dict[str, set[str]]:
    cities = {
        city
        for city in fetch_cities()
        if keep_titlecase_location(city)
    }
    countries = fetch_country_names()
    return {
        "LOC": cities | countries,
        "ORG": {"Kia"},
    }


TITLECASE_LOC_SINGLETON_BLOCKLIST = {
    "a",
    "an",
    "anh",
    "ba",
    "binh",
    "bo",
    "cao",
    "da",
    "do",
    "ha",
    "ho",
    "kim",
    "la",
    "lam",
    "le",
    "mai",
    "my",
    "nam",
    "nga",
    "of",
    "son",
    "ta",
    "thu",
    "to",
    "ton",
    "trang",
    "van",
    "vi",
    "yen",
}


def keep_titlecase_location(name: str) -> bool:
    normalized = name.casefold()
    tokens = re.findall(r"\w+", normalized, flags=re.UNICODE)
    if not tokens:
        return False
    if len(tokens) > 1:
        return True
    token = tokens[0]
    return len(token) >= 4 and token not in TITLECASE_LOC_SINGLETON_BLOCKLIST


def write_json(path: Path, payload: dict[str, set[str]]) -> None:
    serializable = {
        key: sorted(values, key=lambda value: value.casefold())
        for key, values in sorted(payload.items())
        if values
    }
    path.write_text(
        json.dumps(serializable, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    normal = generated_terms()
    titlecase = titlecase_terms()
    write_json(NORMAL_OUTPUT, normal)
    write_json(TITLECASE_OUTPUT, titlecase)

    normal_count = sum(len(values) for values in normal.values())
    titlecase_count = sum(len(values) for values in titlecase.values())
    print(f"Wrote {normal_count} normal lexicon terms -> {NORMAL_OUTPUT}")
    print(f"Wrote {titlecase_count} titlecase lexicon terms -> {TITLECASE_OUTPUT}")


if __name__ == "__main__":
    main()
