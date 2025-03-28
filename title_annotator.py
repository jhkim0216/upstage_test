import re
import json
from typing import List, Dict, Any, Optional

class TitleAnnotator:
    """제목 어노테이션을 처리하는 클래스"""
    
    def __init__(self, title_list: List[str]):
        self.title_list = title_list
        self.cleaned_titles = self._clean_titles()
    
    def _clean_titles(self) -> Dict[str, str]:
        """제목 리스트 정제"""
        cleaned = {}
        for title in self.title_list:
            # 특수문자 정규화
            normalized = re.sub(r'[･·ㆍ]', '·', title)
            # 공백 정규화
            normalized = re.sub(r'\s+', ' ', normalized).strip()
            cleaned[normalized.lower()] = title
        return cleaned
    
    def _normalize_text(self, text: str) -> str:
        """텍스트 정규화"""
        # 특수문자 정규화
        text = re.sub(r'[･·ㆍ]', '·', text)
        # 공백 정규화
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def _find_matching_title(self, text: str) -> Optional[str]:
        """정규화된 텍스트와 일치하는 제목 찾기"""
        normalized = self._normalize_text(text).lower()
        
        # 정확히 일치하는 경우
        if normalized in self.cleaned_titles:
            return self.cleaned_titles[normalized]
            
        # 번호를 제거하고 비교
        text_without_number = re.sub(r'^(?:0?\d{1,2})\s+', '', normalized)
        for clean_title, original in self.cleaned_titles.items():
            title_without_number = re.sub(r'^(?:0?\d{1,2})\s+', '', clean_title)
            if text_without_number == title_without_number:
                return original
                
        return None
    
    def process_line(self, text: str, line_number: int) -> Optional[Dict[str, Any]]:
        """텍스트 라인 처리"""
        text = text.strip()
        if not text:
            return None
            
        # 원본 제목 찾기
        original_title = self._find_matching_title(text)
        if not original_title:
            return None
            
        # 법률 근거 추출
        law_ref = re.search(r'\((?:소득|조특|법인|부가가치|상속|증여)(?:법|령)\s+제\d+조(?:의\d+)?(?:\s*제\d+항)?(?:\s*,\s*제\d+조(?:의\d+)?)*\)', text)
        
        # 적용시기 추출
        app_date = re.search(r'(?:적용시기|적용기한|시행일)\s*:\s*.*?(?=\n|$)|(?:\d{4}\.\d{1,2}\.\d{1,2}\.(?:까지|부터)(?:\s+한시)?(?:적용|시행))', text)
        
        result = {
            "text": text,
            "original_title": original_title,
            "line_number": line_number
        }
        
        if law_ref:
            result["law_reference"] = law_ref.group()
            
        if app_date:
            result["application_date"] = app_date.group()
            
        return result

class TextProcessor:
    """텍스트 파일을 처리하는 클래스"""
    
    def __init__(self, title_list: List[str]):
        self.annotator = TitleAnnotator(title_list)
    
    def process_text_file(self, file_path: str) -> List[Dict[str, Any]]:
        """텍스트 파일 처리"""
        titles = []
        current_title = None
        current_content = []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
                
            # 제목 정보 추출 시도
            title_info = self.annotator.process_line(line, i)
            
            if title_info:
                # 이전 제목과 내용이 있으면 저장
                if current_title:
                    current_title["content"] = "\n".join(current_content)
                    titles.append(current_title)
                
                # 새로운 제목 정보 설정
                current_title = title_info
                current_content = []
            elif current_title:
                # 제목이 아닌 경우 내용으로 추가
                current_content.append(line)
        
        # 마지막 제목과 내용 처리
        if current_title:
            current_title["content"] = "\n".join(current_content)
            titles.append(current_title)
        
        return titles
    
    def save_to_json(self, titles: List[Dict[str, Any]], output_path: str):
        """결과를 JSON 파일로 저장"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({
                "titles": titles,
                "total_count": len(titles)
            }, f, ensure_ascii=False, indent=2)

def main():
    # 예시 사용법
    title_list = [
        "2024년 적용되는 연말정산 관련 주요내용",
        "출산･보육수당 비과세 한도 상향",
        # ... 나머지 제목 리스트
    ]
    
    processor = TextProcessor(title_list)
    titles = processor.process_text_file("./연말정산-1-14.txt")
    processor.save_to_json(titles, "./output.json")
    
    # 결과 출력
    print(f"총 {len(titles)}개의 제목을 처리했습니다.")
    print("결과가 output.json 파일로 저장되었습니다.")

if __name__ == "__main__":
    main() 