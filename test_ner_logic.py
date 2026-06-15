import sys
from etl.ner_extractor import NERExtractor

def main():
    extractor = NERExtractor()
    
    text1 = "Ai Cập chia sẻ thông tin về hiệp định."
    text2 = "Đội trưởng Quang Hải đã ghi bàn."
    
    print("Test 1:", text1)
    attrs1 = extractor.extract_attributes(text1)
    for a in attrs1:
        print(f"  {a}")
        
    print("\nTest 2:", text2)
    attrs2 = extractor.extract_attributes(text2)
    for a in attrs2:
        print(f"  {a}")

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    main()
