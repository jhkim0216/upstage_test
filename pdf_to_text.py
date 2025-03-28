import fitz  # PyMuPDF
import os
import json
import re
from typing import List, Optional, Tuple, Dict, Any

class TitleCleaner:
    """제목 정제를 담당하는 클래스"""
    
    @staticmethod
    def clean_title(text: str) -> str:
        """제목 텍스트를 정제하는 메서드"""
        # >>>> 로 시작하는 부분 제거
        text = re.sub(r'^>>>>\s*', '', text)
        
        # 앞의 숫자(01., 1. 등)로 시작하는 경우만 제거
        if not (re.match(r'^\d{4}년', text) or re.match(r'^제\s*\d+\s*[장절]', text)):
            text = re.sub(r'^\d+\.?\s*', '', text)
        
        text = TitleCleaner._normalize_year_patterns(text)
        text = TitleCleaner._remove_page_numbers(text)
        text = TitleCleaner._process_middle_dots(text)
        text = TitleCleaner._normalize_date_patterns(text)
        text = TitleCleaner._normalize_spaces(text)
        
        return text.strip()
    
    @staticmethod
    def _normalize_year_patterns(text: str) -> str:
        """연도 패턴을 정규화"""
        patterns = [
            (r'(\d{4})\s*년도', r'\1년'),  # 2024년도 -> 2024년
            (r'(\d{4})\s*년(?!\s*적용)', r'\1년'),  # 2024 년 -> 2024년
            (r'\'(\d{2})년(?!\s*적용)', r'20\1년'),  # '24년 -> 2024년
            (r'^(\d{2})년(?!\s*적용)', r'20\1년'),  # 24년 -> 2024년
            (r'(\d{4})\s*[~∼]\s*(\d{4})\s*년', r'\1-\2년'),  # 2024~2025년 -> 2024-2025년
            (r'(\d{4})\.(\d{1,2})\.(\d{1,2})', r'\1년 \2월 \3일')  # 2024.1.1 -> 2024년 1월 1일
        ]
        
        for pattern, replacement in patterns:
            text = re.sub(pattern, replacement, text)
        return text
    
    @staticmethod
    def _remove_page_numbers(text: str) -> str:
        """페이지 번호와 관련 구분자 제거"""
        patterns = [
            r'\s*[･·ㆍ∙]{2,}\s*\d+\s*$',  # 중간점 + 숫자
            r'\s*\.{3,}\s*\d+$',  # 점(...) + 숫자
            r'\s*\d+$',  # 숫자
            r'\s*\.{3,}\s*'  # 남은 점(...)
        ]
        
        for pattern in patterns:
            text = re.sub(pattern, '', text)
        return text
    
    @staticmethod
    def _process_middle_dots(text: str) -> str:
        """중간점 처리"""
        # 단일 중간점(∙) 제거 (장/절 번호 사이)
        text = re.sub(r'\s*[∙]\s*', ' ', text)
        
        # 의미있는 중간점 처리
        def replace_middle_dot(match):
            original = match.group(0)
            return ' ･ ' if ' ' in original else '･'
            
        return re.sub(r'\s*[･·ㆍ]\s*', replace_middle_dot, text)
    
    @staticmethod
    def _normalize_date_patterns(text: str) -> str:
        """날짜 패턴 정규화"""
        text = re.sub(r'(\d{1,2})\s*[월]\s*', r'\1월 ', text)
        text = re.sub(r'(\d{1,2})\s*[일]\s*', r'\1일 ', text)
        return text
    
    @staticmethod
    def _normalize_spaces(text: str) -> str:
        """공백 정규화"""
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\(\s*\)', '', text)  # 빈 괄호 제거
        return text.strip()

class TitleMatcher:
    """제목 매칭을 담당하는 클래스"""
    
    def __init__(self, cleaner: TitleCleaner):
        self.cleaner = cleaner
    
    def is_title_match(self, text: str, title: str) -> bool:
        """텍스트가 제목과 매칭되는지 확인"""
        cleaned_text = self.cleaner.clean_title(text).lower()
        cleaned_title = self.cleaner.clean_title(title).lower()
        
        if not cleaned_text or not cleaned_title:
            return False
            
        # 정확히 일치하는 경우
        if cleaned_text == cleaned_title:
            return True
            
        # 페이지 번호와 점(...)을 제거한 후 비교
        text_without_page = re.sub(r'\s*[.·･]{2,}\s*\d+\s*$', '', cleaned_text)
        title_without_page = re.sub(r'\s*[.·･]{2,}\s*\d+\s*$', '', cleaned_title)
        
        if text_without_page == title_without_page:
            return True
            
        # 번호 패턴 제거 후 비교
        text_without_number = re.sub(r'^(?:\d+\.)?\s*', '', text_without_page)
        title_without_number = re.sub(r'^(?:\d+\.)?\s*', '', title_without_page)
        
        if text_without_number == title_without_number:
            return True
            
        return self._check_partial_match(text_without_number, title_without_number)
    
    def _check_partial_match(self, text: str, title: str) -> bool:
        """부분 매칭 확인"""
        # 특수문자로 구분된 단어들을 분리
        title_words = self._split_with_delimiters(title)
        text_words = self._split_with_delimiters(text)
        
        if len(title_words) > 1:
            # 의미있는 단어만 선택 (2글자 이상)
            main_words = [w for w in title_words if len(w) > 1]
            if not main_words:
                return False
                
            # 매칭되는 단어 수 계산
            matched_words = sum(1 for word in main_words if 
                              any(word in text_part for text_part in text_words))
            
            # 70% 이상 매칭되면 True
            return matched_words >= len(main_words) * 0.7
            
        # 단일 단어인 경우 정확히 일치해야 함
        return text == title
    
    @staticmethod
    def _split_with_delimiters(text: str) -> List[str]:
        """특수문자로 구분된 단어 분리"""
        # 특수문자로 분리
        parts = re.split(r'([-･·ㆍ])', text)
        words = []
        i = 0
        while i < len(parts):
            if i + 2 < len(parts) and parts[i+1] in ['-', '･', '·', 'ㆍ']:
                words.append(parts[i] + parts[i+1] + parts[i+2])
                i += 3
            else:
                if parts[i].strip():
                    words.append(parts[i].strip())
                i += 1
        return [w for w in words if w and not w in ['-', '･', '·', 'ㆍ']]

class PDFProcessor:
    """PDF 처리를 담당하는 클래스"""
    
    def __init__(self, cleaner: TitleCleaner, matcher: TitleMatcher):
        self.cleaner = cleaner
        self.matcher = matcher
    
    def extract_toc(self, doc: fitz.Document) -> List[str]:
        """목차 추출"""
        toc = doc.get_toc()
        if toc:
            return [title.strip() for _, title, _ in toc]
            
        return self._extract_toc_manually(doc)
    
    def _extract_toc_manually(self, doc: fitz.Document) -> List[str]:
        """수동으로 목차 추출"""
        titles = []
        found_titles = set()
        current_title_lines = []
        
        for page in doc:
            self._process_page_for_toc(page, titles, found_titles, current_title_lines)
            
        # 마지막 제목 처리
        if current_title_lines and self._is_page_number_format(" ".join(current_title_lines)):
            self._process_current_title(current_title_lines, titles, found_titles)
            
        return titles
    
    def _process_page_for_toc(self, page: fitz.Page, titles: List[str], 
                             found_titles: set, current_title_lines: List[str]) -> None:
        """페이지 단위 목차 처리"""
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if "lines" not in block:
                continue
                
            for line in block["lines"]:
                line_text = self._extract_line_text(line)
                if not line_text:
                    continue
                    
                self._process_line_for_toc(line_text, titles, found_titles, current_title_lines)
    
    @staticmethod
    def _extract_line_text(line: dict) -> str:
        """라인에서 텍스트 추출"""
        line_text = ""
        for span in line["spans"]:
            span_text = span["text"].strip()
            if span_text:
                if line_text and not (line_text.endswith('･') or line_text.endswith('·') or 
                                    line_text.endswith('ㆍ') or line_text.endswith('-') or
                                    line_text.endswith('.')):
                    line_text += " "
                line_text += span_text
        return line_text
    
    def _process_line_for_toc(self, line_text: str, titles: List[str], 
                             found_titles: set, current_title_lines: List[str]) -> None:
        """목차용 라인 처리"""
        if self._is_title_start(line_text):
            if current_title_lines:
                self._process_current_title(current_title_lines, titles, found_titles)
                current_title_lines.clear()
            current_title_lines.append(line_text)
            if self._is_page_number_format(line_text):
                self._process_current_title(current_title_lines, titles, found_titles)
                current_title_lines.clear()
        elif current_title_lines:
            current_title_lines.append(line_text)
            if self._is_page_number_format(line_text):
                self._process_current_title(current_title_lines, titles, found_titles)
                current_title_lines.clear()
    
    def _process_current_title(self, current_title_lines: List[str], 
                             titles: List[str], found_titles: set) -> None:
        """현재 제목 처리"""
        if current_title_lines:
            full_title = " ".join(line.strip() for line in current_title_lines)
            cleaned_text = self.cleaner.clean_title(full_title)
            if cleaned_text and cleaned_text not in found_titles:
                titles.append(full_title)
                found_titles.add(cleaned_text)
    
    @staticmethod
    def _is_title_start(text: str) -> bool:
        """제목 시작 패턴 확인"""
        text = text.strip()
        return (text.startswith('[') or
                re.match(r'^\d+\.', text) or
                re.match(r'^제\s*\d+\s*[장절]', text) or
                re.match(r'^\d{4}년', text) or
                text.startswith('>>>>') or
                'Q&A' in text)
    
    @staticmethod
    def _is_page_number_format(text: str) -> bool:
        """페이지 번호 형식 확인"""
        return bool(re.search(r'[･·ㆍ]{2,}\s*\d+\s*$', text) or
                   re.search(r'[.]{2,}\s*\d+\s*$', text))
    
    def extract_full_text(self, doc: fitz.Document) -> List[dict]:
        """PDF 전체 텍스트를 추출하고 정제"""
        pages = []
        for page in doc:
            # 텍스트를 딕셔너리 형태로 추출하여 구조 정보 보존
            text_dict = page.get_text("dict")
            
            # 페이지 내용 정제
            cleaned_content = self._clean_page_content(text_dict)
            
            if cleaned_content.strip():  # 빈 페이지가 아닌 경우만 추가
                page_content = {
                    'page_number': page.number + 1,
                    'text': cleaned_content
                }
                pages.append(page_content)
        return pages
    
    def _clean_page_content(self, text_dict: dict) -> str:
        """페이지 내용 정제"""
        if 'blocks' not in text_dict:
            return ""
            
        lines = []
        current_y = 0
        line_texts = []
        
        for block in text_dict['blocks']:
            if 'lines' not in block:
                continue
                
            for line in block['lines']:
                # 헤더/푸터 제외 (페이지 상단 10%와 하단 10% 영역)
                if 'bbox' in line:
                    y = line['bbox'][1]  # y 좌표
                    page_height = text_dict.get('height', 1000)  # 페이지 높이
                    if y < page_height * 0.1 or y > page_height * 0.9:
                        continue
                
                line_text = self._extract_line_text(line)
                if not line_text.strip():
                    continue
                    
                # 줄바꿈 처리
                if line_texts and abs(current_y - line['bbox'][1]) > 15:  # 줄간격이 큰 경우
                    if line_texts:
                        lines.append(' '.join(line_texts))
                        line_texts = []
                
                line_texts.append(line_text)
                current_y = line['bbox'][1]
        
        # 마지막 라인 처리
        if line_texts:
            lines.append(' '.join(line_texts))
        
        # 정제된 텍스트 생성
        text = '\n'.join(lines)
        
        # 불필요한 공백 및 특수문자 정리
        text = self._clean_text(text)
        
        return text
    
    def _clean_text(self, text: str) -> str:
        """텍스트 정제"""
        # 연속된 공백 제거
        text = re.sub(r'\s+', ' ', text)
        
        # 불필요한 줄바꿈 정리
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        # 줄 시작/끝 공백 제거
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(line for line in lines if line)
        
        return text.strip()

class FileHandler:
    """파일 처리를 담당하는 클래스"""
    
    @staticmethod
    def save_titles_to_file(doc: fitz.Document, titles: List[str], 
                           output_path: str, cleaner: TitleCleaner) -> None:
        """제목 리스트를 파일로 저장"""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                FileHandler._write_original_text(f, doc)
                FileHandler._write_title_lists(f, titles, cleaner)
            print(f"제목 리스트가 성공적으로 {output_path}에 저장되었습니다.")
        except Exception as e:
            print(f"제목 리스트 저장 중 에러 발생: {str(e)}")
    
    @staticmethod
    def _write_original_text(f, doc: fitz.Document) -> None:
        """원본 텍스트 작성"""
        f.write("=== PyMuPDF 원본 텍스트 ===\n")
        for page in doc:
            f.write(f"--- Page {page.number + 1} ---\n")
            f.write(page.get_text())
            f.write("\n")
    
    @staticmethod
    def _write_title_lists(f, titles: List[str], cleaner: TitleCleaner) -> None:
        """제목 리스트 작성"""
        f.write("\n=== 원본 제목 리스트 ===\n")
        for title in titles:
            f.write(f"{title}\n")
        
        f.write("\n=== 정제된 제목 리스트 ===\n")
        for title in titles:
            cleaned = cleaner.clean_title(title)
            if cleaned:
                f.write(f"{cleaned}\n")
    
    @staticmethod
    def save_full_text_to_file(doc: fitz.Document, output_path: str, processor: PDFProcessor) -> None:
        """PDF 전체 텍스트를 파일로 저장"""
        try:
            pages = processor.extract_full_text(doc)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write("=== PDF 전체 텍스트 ===\n")
                
                for page in pages:
                    f.write(f"\n{'=' * 30} Page {page['page_number']} {'=' * 30}\n\n")
                    f.write(page['text'])
                    f.write("\n")
                    
            print(f"PDF 전체 텍스트가 성공적으로 {output_path}에 저장되었습니다.")
        except Exception as e:
            print(f"PDF 전체 텍스트 저장 중 에러 발생: {str(e)}")

class JSONProcessor:
    """JSON 처리를 담당하는 클래스"""
    
    def __init__(self, matcher: TitleMatcher):
        self.matcher = matcher
    
    def process_json(self, json_path: str, output_json_path: str, titles: List[str]) -> None:
        """JSON 파일 전체 처리"""
        try:
            data = self._read_json(json_path)
            self._label_header_footer(data)  # 헤더/푸터 라벨링 먼저 수행
            self._update_json_with_titles(data, titles)  # 그 다음 제목 업데이트
            self._label_paragraphs(data)  # 마지막으로 단락 라벨링
            self._save_json(data, output_json_path)
            print(f"JSON이 성공적으로 수정되어 {output_json_path}에 저장되었습니다.")
        except Exception as e:
            print(f"JSON 수정 중 에러 발생: {str(e)}")
    
    def _label_header_footer(self, data: dict) -> None:
        """헤더와 푸터 라벨링"""
        if 'elements' not in data:
            return
            
        # 페이지별로 요소들을 그룹화
        pages = {}
        for element in data['elements']:
            if 'page' not in element or 'coordinates' not in element:
                continue
                
            page_num = element['page']
            if page_num not in pages:
                pages[page_num] = {
                    'elements': [],
                    'height': 0
                }
            pages[page_num]['elements'].append(element)
            
            # 페이지 높이 업데이트
            coordinates = element.get('coordinates', {})
            if isinstance(coordinates, dict):
                y2 = coordinates.get('y2', 0)
                pages[page_num]['height'] = max(pages[page_num]['height'], y2)
        
        # 각 페이지별로 헤더/푸터 처리
        for page_num, page_data in pages.items():
            page_height = page_data['height']
            if not page_height:
                continue
                
            header_threshold = page_height * 0.1  # 상위 10%
            footer_threshold = page_height * 0.9  # 하위 10%
            
            for element in page_data['elements']:
                coordinates = element.get('coordinates', {})
                if not isinstance(coordinates, dict):
                    continue
                    
                y1 = coordinates.get('y1', 0)
                y2 = coordinates.get('y2', 0)
                
                # 요소의 위치에 따라 헤더/푸터 라벨링
                if y2 <= header_threshold:
                    element['category'] = 'header'
                elif y1 >= footer_threshold:
                    element['category'] = 'footer'
    
    def _update_json_with_titles(self, data: dict, titles: List[str]) -> None:
        """제목 라벨링"""
        if 'elements' not in data:
            return
            
        # 제목 정제 및 매칭 사전 생성
        cleaned_titles = {self.matcher.cleaner.clean_title(title).lower(): title 
                        for title in titles if title.strip()}
        
        for element in data['elements']:
            if ('content' in element and 
                isinstance(element.get('content'), dict) and 
                'text' in element['content'] and
                element.get('category') not in ['header', 'footer']):
                
                text = element['content']['text'].strip()
                cleaned_text = self.matcher.cleaner.clean_title(text).lower()
                
                # 정확한 제목 매칭 확인
                for clean_title in cleaned_titles:
                    if self.matcher.is_title_match(cleaned_text, clean_title):
                        element['category'] = 'heading1'
                        # 원본 제목 저장
                        element['original_title'] = cleaned_titles[clean_title]
                        break
    
    def _label_paragraphs(self, data: dict) -> None:
        """단락 라벨링"""
        if 'elements' not in data:
            return
            
        for element in data['elements']:
            if ('content' in element and 
                isinstance(element.get('content'), dict) and 
                'text' in element['content'] and
                'category' not in element):
                # 카테고리가 지정되지 않은 텍스트는 단락으로 처리
                element['category'] = 'paragraph'
    
    @staticmethod
    def _read_json(json_path: str) -> dict:
        """JSON 파일 읽기"""
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    @staticmethod
    def _save_json(data: dict, output_path: str) -> None:
        """JSON 파일 저장"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

class PDFAnalyzer:
    def __init__(self):
        self.cleaner = TitleCleaner()
        self.titles = [
            "2024년 적용되는 연말정산 관련 주요내용",
            "출산･보육수당 비과세 한도 상향",
            "육아휴직수당 비과세 적용대상 추가",
            "원양어선･외항선원 및 해외건설 근로자 비과세 확대",
            "직무발명보상금 비과세 한도 상향",
            "자원봉사용역 특례기부금 가액 현실화",
            "주택연금 이자비용 소득공제 요건 완화",
            "장기주택저당 차입금 이자상환액 소득공제 확대",
            "자녀세액공제 확대",
            "산후조리원에 지급하는 비용 의료비 세액공제 강화",
            "장애인활동지원급여 비용 의료비 세액공제 대상 확대",
            "고액기부 대한 공제율 한시 상향",
            "주택청약종합저축 소득공제 한도 상향",
            "월세액 세액공제 소득기준 및 한도 상향",
            "성실사업자 등에 대한 의료비 등 세액공제 적용요건 완화 및 기한연장",
            "신용카드 등 사용금액 증가분에 대한 소득공제 추가",
            "신용카드 등 사용금액 소득공제 적용대상 조정",
            "2024년 연말정산 Q&A",
            "비과세 – 자기차량 운전보조금",
            "비과세 – 실비변상적 급여",
            "비과세 – 국외근로소득",
            "비과세 – 생산직 근로자의 연장근로 수당 등",
            "비과세 – 식대",
            "비과세 – 출산보육수당",
            "비과세 - 학자금",
            "비과세 – 그 밖의 비과세 소득",
            "인적공제 – 연간소득금액 100만원",
            "인적공제 – 직계존속",
            "인적공제 – 직계비속",
            "인적공제 – 형제자매",
            "추가공제 – 부녀자 공제",
            "(공적)연금보험료 공제 – 국민연금, 공무원연금 등",
            "보험료 공제 – 건강보험, 고용보험, 노인장기요양보험",
            "주택자금 공제 – 주택임차차입금 원리금 상환액",
            "주택자금 공제 – 장기주택저당차입금 이자 상환액",
            "주택마련저축 납입액 소득공제",
            "신용카드 등 사용금액 소득공제",
            "중소기업 취업자에 대한 소득세 감면",
            "자녀세액공제",
            "연금계좌 세액공제",
            "보험료 세액공제",
            "의료비 세액공제",
            "교육비 세액공제",
            "기부금 세액공제",
            "월세 세액공제",
            "제1장 근로소득 연말정산 (이론편)",
            "제1절 근로소득자의 연말정산",
            "연말정산 의의",
            "연말정산 흐름",
            "연말정산의무자",
            "연말정산의 시기",
            "연말정산 세액의 징수 및 환급",
            "근로소득원천징수영수증 작성 및 발급",
            "원천징수이행상황신고서 제출 및 세액납부",
            "연말정산 오류에 따른 가산세",
            "지급명세서 제출",
            "간이지급명세서 제출",
            "기타 세무서 제출서류",
            "비거주자의 연말정산",
            "제2절 근로소득의 원천징수",
            "근로소득",
            "일용근로소득",
            "비과세 근로소득",
            "조세특례제한법상 근로소득 특례",
            "근로소득의 수입금액 계산",
            "근로소득의 수입시기 (귀속시기)",
            "근로소득의 지급시기와 원천징수시기",
            "근로소득 원천징수 세율",
            "근로소득 원천징수의무자",
            "제2장 근로소득 연말정산 (실전편)",
            "제1절 연말정산 사전준비",
            "연말정산 사전준비",
            "연말정산 제출서류",
            "편리한 연말정산",
            "연말정산 간소화 서비스",
            "제3장 연말정산 세액의 계산",
            "세액계산의 흐름",
            "제1절 소득공제",
            "근로소득공제",
            "종합소득공제",
            "특별소득공제",
            "그 밖의 소득공제",
            "소득공제 종합한도",
            "제2절 세액과 감면",
            "산출세액",
            "종합소득 결정세액",
            "세액감면",
            "제3절 세액공제",
            "근로소득･자녀･연금계좌 세액공제",
            "보험료･의료비･교육비･기부금 세액공제",
            "이외 세액공제",
            "세액감면 및 세액공제의 한도",
            "제4장 근로소득자의 연말정산 후 4대보험 정산",
            "개요"
        ]
        # 정제된 제목 리스트 생성
        self.cleaned_titles = {self.cleaner.clean_title(title).lower(): title for title in self.titles}
        
    def analyze_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """PDF 파일을 분석하여 JSON 형식으로 변환"""
        doc = fitz.open(pdf_path)
        elements = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            page_dict = page.get_text("dict")
            page_elements = self._process_page(page_dict, page_num + 1)
            elements.extend(page_elements)
            
        doc.close()
        return {"elements": elements}
    
    def _process_page(self, page_dict: Dict[str, Any], page_num: int) -> List[Dict[str, Any]]:
        """페이지 단위 처리"""
        elements = []
        page_height = page_dict.get("height", 1000)
        
        for block in page_dict.get("blocks", []):
            if "lines" not in block:
                continue
                
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    element = self._create_element(span, page_num, page_height)
                    if element:
                        elements.append(element)
        
        return elements
    
    def _create_element(self, span: Dict[str, Any], page_num: int, page_height: float) -> Dict[str, Any]:
        """개별 요소 생성"""
        text = span.get("text", "").strip()
        if not text:
            return None
            
        # 좌표 정보
        bbox = span.get("bbox", [0, 0, 0, 0])
        coordinates = {
            "x1": bbox[0],
            "y1": bbox[1],
            "x2": bbox[2],
            "y2": bbox[3]
        }
        
        # 폰트 정보
        font_info = {
            "size": span.get("size", 0),
            "font": span.get("font", ""),
            "color": span.get("color", 0)
        }
        
        # 요소 생성
        element = {
            "page": page_num,
            "coordinates": coordinates,
            "content": {
                "text": text,
                "font_info": font_info
            }
        }
        
        # 카테고리 결정
        element["category"] = self._determine_category(text, coordinates, page_height)
        
        return element
    
    def _determine_category(self, text: str, coordinates: Dict[str, float], page_height: float) -> str:
        """요소의 카테고리 결정"""
        # 헤더/푸터 확인
        y1, y2 = coordinates["y1"], coordinates["y2"]
        if y2 <= page_height * 0.1:
            return "header"
        if y1 >= page_height * 0.9:
            return "footer"
        
        # 정제된 제목 리스트와 비교
        cleaned_text = self.cleaner.clean_title(text).lower()
        if cleaned_text in self.cleaned_titles:
            return "heading1"
        
        return "paragraph"

def process_pdf(pdf_path: str, output_path: str):
    """PDF 처리 및 JSON 저장"""
    try:
        # PDF 분석
        analyzer = PDFAnalyzer()
        result = analyzer.analyze_pdf(pdf_path)
        
        # 결과 저장
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
            
        print(f"PDF 분석이 완료되어 {output_path}에 저장되었습니다.")
        
    except Exception as e:
        print(f"PDF 처리 중 오류 발생: {str(e)}")

def main():
    """메인 실행 함수"""
    pdf_path = "./data/pdf/연말정산-1-14.pdf"
    output_path = "./data/json/연말정산_1_14_result.json"
    
    if not os.path.exists(pdf_path):
        print("PDF 파일을 찾을 수 없습니다.")
        return
        
    process_pdf(pdf_path, output_path)

if __name__ == "__main__":
    main() 