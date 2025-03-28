import re
import json
from typing import Dict, List, Union, Optional, Tuple
from pathlib import Path

class TableOfContents:
    def __init__(self):
        self.entries = []  # [{title, page_number, pattern}]
        self.toc_page_range = None  # (start_page, end_page)
    
    def extract_toc_from_json(self, document: Dict, toc_page_range: Tuple[int, int]):
        """
        JSON 문서에서 목차 페이지의 내용을 추출하고 파싱합니다.
        """
        self.toc_page_range = toc_page_range
        toc_items = []
        
        # elements 배열에서 목차 페이지의 항목들만 추출
        for element in document.get('elements', []):
            page = element.get('page', 0)
            if not (toc_page_range[0] <= page <= toc_page_range[1]):
                continue
                
            content = element.get('content', {})
            text = content.get('text', '') or content.get('markdown', '')
            if not text:
                continue
            
            # 각 줄별로 처리
            for line in text.split('\n'):
                line = line.strip()
                if not line or len(line) < 3:  # 너무 짧은 텍스트는 제외
                    continue
                
                # 목차 항목 패턴 (예: "01. 비과세 - 자기차량 운전보조금 ... 15")
                # 페이지 번호가 끝에 있는 패턴 매칭
                match = re.search(r'^[-\s>]*([^.]+(?:\.[^.]+)*?)(?:[.]{2,}|\s{3,}|[.·]{1}\s+|\s*[.]{3,}\s*|\s+[·]\s+|\s+[>]+\s+)(\d+)\s*$', line.strip())
                if match:
                    title, target_page = match.groups()
                    title = title.strip()
                    target_page = int(target_page)
                    
                    # 제목에서 번호 부분 추출
                    number_match = re.match(r'^[-\s>]*(\d{2}\.|\([0-9]+\)|[IVX]+\.|[A-Z]\.)', title)
                    if number_match:
                        number_part = number_match.group(1)
                        # 제목 패턴 생성 (번호 부분은 선택적으로 포함)
                        title_pattern = title.replace(number_part, f"({number_part})?")
                    else:
                        title_pattern = title
                    
                    # 정규식 패턴으로 변환
                    pattern = re.escape(title_pattern).replace(r"\ ", r"\s+")
                    
                    toc_items.append({
                        'title': title,
                        'target_page': target_page,  # 실제 내용이 있는 페이지 번호
                        'pattern': pattern,
                        'coordinates': element.get('coordinates', [])
                    })
        
        # 페이지 번호 기준으로 정렬
        self.entries = sorted(toc_items, key=lambda x: x['target_page'])
    
    def save_toc_list(self, output_path: str):
        """
        목차 리스트를 파일로 저장합니다.
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("# 목차 리스트\n\n")
            for entry in self.entries:
                f.write(f"- {entry['title']} (페이지: {entry['target_page']})\n")
    
    def is_title(self, text: str, page: int, coordinates: List[Dict] = None) -> bool:
        """
        주어진 텍스트가 목차에 있는 제목과 일치하는지 확인합니다.
        """
        text = text.strip()
        
        # 텍스트 매칭 및 페이지 번호 확인
        for entry in self.entries:
            if re.search(entry['pattern'], text, re.IGNORECASE):
                # 페이지 번호가 일치하는지 확인
                if entry['target_page'] == page:
                    # 좌표 정보가 있는 경우 추가 검증
                    if coordinates and entry.get('coordinates'):
                        if self._check_coordinate_similarity(coordinates, entry['coordinates']):
                            return True
                    else:
                        return True
        return False
    
    def _check_coordinate_similarity(self, coords1: List[Dict], coords2: List[Dict]) -> bool:
        """
        두 좌표 집합의 유사성을 검사합니다.
        """
        if not coords1 or not coords2:
            return True
            
        # x 좌표의 유사성 검사 (왼쪽 정렬 여부)
        x1 = coords1[0].get('x', 0)
        x2 = coords2[0].get('x', 0)
        
        return abs(x1 - x2) < 0.1  # 10% 이내의 차이는 허용

class DocumentClassifier:
    def __init__(self, toc: TableOfContents):
        self.toc = toc
        self.headings = []  # 문서에서 발견된 모든 제목
    
    def classify_content(self, element: Dict) -> str:
        """
        콘텐츠를 제목 또는 본문으로 분류합니다.
        """
        page = element.get('page', 0)
        content = element.get('content', {})
        text = content.get('text', '') or content.get('markdown', '')
        if not text or len(text.strip()) < 3:  # 너무 짧은 텍스트는 제외
            return 'unknown'
            
        coordinates = element.get('coordinates', [])
        
        # 목차 페이지 범위에 있는 경우
        if self.toc.toc_page_range and self.toc.toc_page_range[0] <= page <= self.toc.toc_page_range[1]:
            # 특정 조건에 맞는 텍스트만 제목으로 처리
            if self._is_potential_title(text, coordinates):
                self.headings.append({
                    'text': text,
                    'page': page,
                    'source': 'toc_page'
                })
                return 'heading'
            return 'toc'
            
        # 목차 기반 제목 확인 (페이지 번호도 함께 확인)
        if self.toc.is_title(text, page, coordinates):
            self.headings.append({
                'text': text,
                'page': page,
                'source': 'toc_match'
            })
            return 'heading'
            
        # category가 heading으로 시작하면 제목으로 분류
        category = element.get('category', '')
        if category and category.startswith('heading'):
            self.headings.append({
                'text': text,
                'page': page,
                'source': 'category'
            })
            return 'heading'
            
        return 'paragraph'
    
    def _is_potential_title(self, text: str, coordinates: List[Dict]) -> bool:
        """
        텍스트가 제목일 가능성이 있는지 확인합니다.
        """
        text = text.strip()
        
        # 너무 긴 텍스트는 제외
        if len(text) > 200:
            return False
            
        # 특수문자나 숫자로만 이루어진 텍스트는 제외
        if re.match(r'^[0-9\s\.\-\=\>\<\(\)]+$', text):
            return False
            
        # 좌표 정보가 있는 경우, 왼쪽 정렬 여부 확인
        if coordinates and len(coordinates) > 0:
            x = coordinates[0].get('x', 0)
            if x > 0.5:  # 페이지 중간 이후에 시작하는 텍스트는 제외
                return False
        
        # 제목 패턴 확인
        title_patterns = [
            r'^\d+\.',  # 숫자로 시작하는 패턴
            r'^[IVX]+\.',  # 로마 숫자로 시작하는 패턴
            r'^[A-Z]\.',  # 대문자 알파벳으로 시작하는 패턴
            r'^제\d+',  # '제'로 시작하는 패턴
            r'^[■▶※●○◆□△▲▼]',  # 특수문자로 시작하는 패턴
            r'[가-힣]+\s*[편장절항목]$'  # 한글 + 편/장/절/항/목으로 끝나는 패턴
        ]
        
        for pattern in title_patterns:
            if re.search(pattern, text):
                return True
        
        return False
    
    def save_heading_list(self, output_path: str):
        """
        발견된 모든 제목을 파일로 저장합니다.
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("# 문서 제목 리스트\n\n")
            for heading in sorted(self.headings, key=lambda x: (x['page'], x['text'])):
                source_mark = {
                    'toc_match': '📚',
                    'category': '📝',
                    'toc_page': '📖'
                }.get(heading['source'], '❓')
                f.write(f"{source_mark} {heading['text']} (페이지: {heading['page']})\n")

def process_document(document: Dict, toc_page_range: Tuple[int, int]) -> Tuple[Dict, TableOfContents, DocumentClassifier]:
    """
    목차 정보를 기반으로 문서를 처리합니다.
    """
    # 목차 파싱
    toc = TableOfContents()
    toc.extract_toc_from_json(document, toc_page_range)
    
    # 문서 분류
    classifier = DocumentClassifier(toc)
    classified_elements = []
    
    for element in document.get('elements', []):
        content_type = classifier.classify_content(element)
        classified_element = {
            **element,
            'type': content_type
        }
        classified_elements.append(classified_element)
    
    # 원본 문서 구조 유지
    classified_document = {
        **document,
        'elements': classified_elements
    }
    
    return classified_document, toc, classifier

def process_json_file(input_path: str, toc_page_range: Tuple[int, int], output_path: str = None):
    """
    JSON 파일을 처리하고 결과를 새 파일로 저장합니다.
    """
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"입력 파일을 찾을 수 없습니다: {input_path}")
        
    if output_path is None:
        output_path = input_path.parent / f"{input_path.stem}_classified{input_path.suffix}"
    
    # JSON 파일 읽기
    with open(input_path, 'r', encoding='utf-8') as f:
        document_data = json.load(f)
    
    # 문서 처리
    classified_document, toc, classifier = process_document(document_data, toc_page_range)
    
    # 결과 저장
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(classified_document, f, ensure_ascii=False, indent=2)
    
    # 목차와 제목 리스트 저장
    toc_list_path = input_path.parent / f"{input_path.stem}_toc_list.md"
    heading_list_path = input_path.parent / f"{input_path.stem}_heading_list.md"
    
    toc.save_toc_list(toc_list_path)
    classifier.save_heading_list(heading_list_path)
    
    # 통계 출력
    elements = classified_document.get('elements', [])
    print(f"\n전체 항목 수: {len(elements)}")
    print(f"분류된 항목:")
    type_counts = {}
    for element in elements:
        type_counts[element['type']] = type_counts.get(element['type'], 0) + 1
    for type_name, count in sorted(type_counts.items()):
        print(f"- {type_name}: {count}개")
    
    print(f"\n목차 리스트 저장됨: {toc_list_path}")
    print(f"제목 리스트 저장됨: {heading_list_path}")
    
    return output_path

if __name__ == "__main__":
    # 파일 처리 예시
    input_file = "연말정산_1_14.json"
    output_file = "연말정산_1_14_classified.json"
    
    # 목차 페이지 범위 지정 (4-8 페이지가 목차)
    toc_page_range = (4, 8)
    
    try:
        output_path = process_json_file(input_file, toc_page_range, output_file)
        print(f"\n분류 완료. 결과가 저장된 파일: {output_path}")
    except Exception as e:
        print(f"오류 발생: {str(e)}") 