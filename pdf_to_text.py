import fitz  # PyMuPDF
import os
import json
import re

def extract_toc(doc):
    """
    PDF 파일의 목차(Table of Contents)를 추출합니다.
    1. 대괄호로 시작하는 큰 제목
    2. 숫자. 로 시작하는 하위 제목
    3. '제N장', '제N절' 형식의 제목
    4. 연도로 시작하는 제목 (예: 2024년)
    5. >>>> 로 시작하는 제목
    6. 점(...) 또는 중간점으로 연결된 페이지 번호
    
    Args:
        doc: fitz.Document 객체
    Returns:
        list: 목차 항목 리스트 (들여쓰기 제거된 순수 제목만)
    """
    toc = doc.get_toc()
    if not toc:  # 목차가 없는 경우, 수동으로 추출 시도
        titles = []
        found_titles = set()  # 이미 발견된 제목들을 추적
        current_title_lines = []  # 현재 처리 중인 제목의 라인들
        
        def is_page_number_format(text):
            """페이지 번호 형식인지 확인"""
            return bool(re.search(r'[･·ㆍ]{2,}\s*\d+\s*$', text) or  # 중간점 + 숫자
                       re.search(r'[.]{2,}\s*\d+\s*$', text))        # 점(...) + 숫자
        
        def is_title_start(text):
            """제목 시작 패턴인지 확인"""
            text = text.strip()
            return (text.startswith('[') or                    # 대괄호로 시작
                    re.match(r'^\d+\.', text) or              # 숫자. 로 시작
                    re.match(r'^제\s*\d+\s*[장절]', text) or  # 제N장/절로 시작
                    re.match(r'^\d{4}년', text) or            # 연도로 시작
                    text.startswith('>>>>') or                # >>>> 로 시작
                    'Q&A' in text)                            # Q&A 포함
        
        def process_current_title():
            """현재 누적된 제목 라인들을 처리"""
            if current_title_lines:
                full_title = " ".join(line.strip() for line in current_title_lines)
                cleaned_text = clean_title(full_title)
                if cleaned_text and cleaned_text not in found_titles:
                    titles.append(full_title)
                    found_titles.add(cleaned_text)
                return True
            return False
        
        for page in doc:
            blocks = page.get_text("dict")["blocks"]
            for block in blocks:
                if "lines" not in block:
                    continue
                    
                for line in block["lines"]:
                    # 현재 라인의 텍스트 추출
                    line_text = ""
                    for span in line["spans"]:
                        span_text = span["text"].strip()
                        if span_text:
                            if line_text and not (line_text.endswith('･') or line_text.endswith('·') or 
                                                line_text.endswith('ㆍ') or line_text.endswith('-') or
                                                line_text.endswith('.')):
                                line_text += " "
                            line_text += span_text
                    
                    if not line_text:
                        continue
                    
                    # 새로운 제목 시작인 경우
                    if is_title_start(line_text):
                        # 이전 제목이 있다면 처리
                        if current_title_lines:
                            process_current_title()
                            current_title_lines = []
                        current_title_lines.append(line_text)
                        # 현재 라인이 페이지 번호로 끝나면 바로 처리
                        if is_page_number_format(line_text):
                            process_current_title()
                            current_title_lines = []
                    # 현재 제목의 연속되는 라인인 경우
                    elif current_title_lines:
                        current_title_lines.append(line_text)
                        # 현재 라인이 페이지 번호로 끝나면 전체 제목 처리
                        if is_page_number_format(line_text):
                            process_current_title()
                            current_title_lines = []
                
                # 블록이 끝날 때 남은 제목이 있고 페이지 번호로 끝나면 처리
                if current_title_lines:
                    full_title = " ".join(line.strip() for line in current_title_lines)
                    if is_page_number_format(full_title):
                        process_current_title()
                        current_title_lines = []
        
        # 마지막 제목이 남아있고 페이지 번호로 끝나면 처리
        if current_title_lines:
            full_title = " ".join(line.strip() for line in current_title_lines)
            if is_page_number_format(full_title):
                process_current_title()
        
        return titles
    
    # 기본 목차가 있는 경우
    titles = [title.strip() for _, title, _ in toc]
    return titles

def save_titles_to_file(doc, titles, output_path):
    """
    추출된 제목 리스트를 파일로 저장합니다.
    PyMuPDF로 추출한 원본 텍스트, 원본 제목, 정제된 제목을 함께 저장합니다.
    
    Args:
        doc (fitz.Document): PDF 문서 객체
        titles (list): 제목 리스트
        output_path (str): 저장할 파일 경로
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            # PyMuPDF로 추출한 원본 텍스트 저장
            f.write("=== PyMuPDF 원본 텍스트 ===\n")
            for page in doc:
                text = page.get_text()
                f.write(f"--- Page {page.number + 1} ---\n")
                f.write(text)
                f.write("\n")
            
            f.write("\n=== 원본 제목 리스트 ===\n")
            for title in titles:
                f.write(f"{title}\n")
            
            f.write("\n=== 정제된 제목 리스트 ===\n")
            for title in titles:
                cleaned = clean_title(title)
                if cleaned:  # 빈 문자열이 아닌 경우만 저장
                    f.write(f"{cleaned}\n")
        
        print(f"제목 리스트가 성공적으로 {output_path}에 저장되었습니다.")
    except Exception as e:
        print(f"제목 리스트 저장 중 에러 발생: {str(e)}")

def clean_title(text):
    """
    제목에서 불필요한 부분을 제거하고 순수 제목만 추출합니다.
    연도가 제목의 중요한 부분인 경우(예: "2024년 적용되는")는 유지합니다.
    특수문자로 연결된 단어들(예: "출산･보육수당")은 연결을 유지합니다.
    중간점이 두 개 이상 연속된 경우는 페이지 번호 구분자로 간주하여 제거합니다.
    장/절 번호는 유지합니다.
    중간점(･) 앞뒤의 공백은 원본 그대로 유지합니다.
    
    Args:
        text (str): 원본 제목 텍스트
    Returns:
        str: 정제된 제목
    """
    # >>>> 로 시작하는 부분 제거
    text = re.sub(r'^>>>>\s*', '', text)
    
    # 앞의 숫자(01., 1. 등)로 시작하는 경우만 제거
    # 단, 연도+년 패턴과 제N장/절 패턴은 유지
    if not (re.match(r'^\d{4}년', text) or re.match(r'^제\s*\d+\s*[장절]', text)):
        text = re.sub(r'^\d+\.?\s*', '', text)
    
    # 연도 패턴 정규화 (순서 중요)
    # 1. "2024년도" -> "2024년"
    text = re.sub(r'(\d{4})\s*년도', r'\1년', text)
    
    # 2. "2024 년" -> "2024년" (공백 제거)
    text = re.sub(r'(\d{4})\s*년(?!\s*적용)', r'\1년', text)  # '년 적용' 패턴이 아닌 경우만
    
    # 3. "'24년" -> "2024년" (2자리 연도를 4자리로 변환)
    text = re.sub(r'\'(\d{2})년(?!\s*적용)', r'20\1년', text)
    
    # 4. "24년" -> "2024년" (2자리 연도를 4자리로 변환, 시작 부분)
    text = re.sub(r'^(\d{2})년(?!\s*적용)', r'20\1년', text)
    
    # 5. "2024~2025년" -> "2024-2025년" (연도 범위 정규화)
    text = re.sub(r'(\d{4})\s*[~∼]\s*(\d{4})\s*년', r'\1-\2년', text)
    
    # 6. "2024.1.1" -> "2024년 1월 1일" (날짜 형식 정규화)
    text = re.sub(r'(\d{4})\.(\d{1,2})\.(\d{1,2})', r'\1년 \2월 \3일', text)
    
    # 두 개 이상 연속된 중간점과 페이지 번호 제거
    text = re.sub(r'\s*[･·ㆍ∙]{2,}\s*\d+\s*$', '', text)
    
    # 뒤의 페이지 번호와 점(...) 제거
    text = re.sub(r'\s*\.{3,}\s*\d+$', '', text)
    text = re.sub(r'\s*\d+$', '', text)
    
    # 남은 점(...) 제거
    text = re.sub(r'\s*\.{3,}\s*', '', text)
    
    # 단일 중간점(∙) 제거 (장/절 번호 사이의 중간점)
    text = re.sub(r'\s*[∙]\s*', ' ', text)
    
    # 특수문자 처리 (의미있는 연결은 유지)
    # 단일 중간점은 통일된 문자(･)로 변경하여 유지, 공백도 원본 그대로 유지
    def replace_middle_dot(match):
        original = match.group(0)
        # 원본에 공백이 있었다면 유지
        if ' ' in original:
            return ' ･ '
        return '･'
    text = re.sub(r'\s*[･·ㆍ]\s*', replace_middle_dot, text)
    
    # 날짜 패턴 정규화
    text = re.sub(r'(\d{1,2})\s*[월]\s*', r'\1월 ', text)
    text = re.sub(r'(\d{1,2})\s*[일]\s*', r'\1일 ', text)
    
    # 연속된 공백을 하나로 정규화
    text = re.sub(r'\s+', ' ', text)
    
    # 시작과 끝의 공백 제거
    text = text.strip()
    
    # 빈 괄호 제거
    text = re.sub(r'\(\s*\)', '', text)
    
    return text.strip()

def is_title_match(text, title):
    """
    텍스트가 제목과 매칭되는지 확인합니다.
    레이아웃 분리를 고려하여 부분 매칭도 허용합니다.
    특수문자로 연결된 단어들은 하나의 단위로 처리합니다.
    
    Args:
        text (str): 검사할 텍스트
        title (str): 목차 제목
    Returns:
        bool: 매칭 여부
    """
    # 텍스트와 제목을 정제
    cleaned_text = clean_title(text).lower()
    cleaned_title = clean_title(title).lower()
    
    if not cleaned_text or not cleaned_title:
        return False
    
    # 완전 일치 확인
    if cleaned_text == cleaned_title:
        return True
    
    # 특수문자로 연결된 단어들을 하나의 단위로 처리
    def split_with_delimiters(text):
        parts = re.split(r'(･|-)', text)
        words = []
        i = 0
        while i < len(parts):
            if i + 2 < len(parts) and parts[i+1] in ['･', '-']:
                # 특수문자로 연결된 부분을 하나의 단어로 처리
                words.append(parts[i] + parts[i+1] + parts[i+2])
                i += 3
            else:
                if parts[i].strip():
                    words.append(parts[i].strip())
                i += 1
        return [w for w in words if w and not w in ['･', '-']]
    
    title_words = split_with_delimiters(cleaned_title)
    text_words = split_with_delimiters(cleaned_text)
    
    # 제목의 주요 단어들이 텍스트에 포함되어 있는지 확인
    if len(title_words) > 1:
        main_words = [w for w in title_words if len(w) > 1]  # 2글자 이상 단어만
        matched_words = 0
        for word in main_words:
            # 특수문자로 연결된 단어는 전체가 포함되어야 함
            if '･' in word in word:
                if word in cleaned_text:
                    matched_words += 1
            # 일반 단어는 개별적으로 확인
            elif word in cleaned_text:
                matched_words += 1
        
        # 주요 단어의 70% 이상이 매칭되면 True
        return matched_words >= len(main_words) * 0.7
    else:
        # 한 단어 제목의 경우 완전 일치 필요
        return cleaned_text == cleaned_title

def modify_json_with_toc(json_path, titles, output_json_path):
    """
    문서 파싱 결과 JSON을 목차 정보를 기반으로 수정합니다.
    
    Args:
        json_path (str): 원본 JSON 파일 경로
        titles (list): 목차 제목 리스트
        output_json_path (str): 수정된 JSON을 저장할 경로
    """
    try:
        # JSON 파일 읽기
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # elements 배열의 각 항목을 확인하고 필요한 경우 카테고리 수정
        if 'elements' in data:
            for element in data['elements']:
                if 'content' in element and 'text' in element['content']:
                    text = element['content']['text'].strip()
                    # 각 제목과 매칭 확인
                    if any(is_title_match(text, title) for title in titles):
                        element['category'] = 'heading1'
        
        # 수정된 JSON 저장
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        print(f"JSON이 성공적으로 수정되어 {output_json_path}에 저장되었습니다.")
        
    except Exception as e:
        print(f"JSON 수정 중 에러 발생: {str(e)}")

def extract_pdf_pages(input_pdf_path, output_pdf_path, start_page, end_page):
    """
    PDF에서 특정 페이지 범위만 추출하여 새로운 PDF를 생성합니다.
    
    Args:
        input_pdf_path (str): 입력 PDF 파일 경로
        output_pdf_path (str): 출력 PDF 파일 경로
        start_page (int): 시작 페이지 (0-based)
        end_page (int): 끝 페이지 (0-based)
    Returns:
        bool: 성공 여부
    """
    try:
        # 원본 PDF 열기
        doc = fitz.open(input_pdf_path)
        
        # 새로운 PDF 문서 생성
        new_doc = fitz.open()
        
        # 지정된 페이지 범위 복사
        new_doc.insert_pdf(doc, from_page=start_page, to_page=end_page)
        
        # 새 PDF 저장
        new_doc.save(output_pdf_path)
        
        # 문서 닫기
        new_doc.close()
        doc.close()
        
        print(f"페이지 {start_page+1}~{end_page+1}가 {output_pdf_path}에 저장되었습니다.")
        return True
        
    except Exception as e:
        print(f"PDF 페이지 추출 중 에러 발생: {str(e)}")
        return False

def process_pdf_and_json(pdf_path, json_path, output_json_path, titles_path, toc_start_page=8, toc_end_page=13):
    """
    PDF에서 목차를 추출하고 JSON을 수정하는 전체 프로세스를 실행합니다.
    
    Args:
        pdf_path (str): PDF 파일 경로
        json_path (str): 원본 JSON 파일 경로
        output_json_path (str): 수정된 JSON을 저장할 경로
        titles_path (str): 제목 리스트를 저장할 경로
        toc_start_page (int): 목차 시작 페이지 (0-based)
        toc_end_page (int): 목차 끝 페이지 (0-based)
    """
    doc = None
    try:
        # 목차 부분만 추출하여 임시 PDF 생성
        temp_pdf_path = pdf_path.replace(".pdf", "_toc_temp.pdf")
        if extract_pdf_pages(pdf_path, temp_pdf_path, toc_start_page, toc_end_page):
            # 추출된 목차 PDF로 작업
            doc = fitz.open(temp_pdf_path)
            
            # 목차 추출
            titles = extract_toc(doc)
            print(f"추출된 목차 개수: {len(titles)}")
            
            # 제목 리스트 저장 (PyMuPDF 원본 텍스트 포함)
            save_titles_to_file(doc, titles, titles_path)
            
            # JSON 수정
            modify_json_with_toc(json_path, titles, output_json_path)
            
            # 문서 닫기
            if doc:
                doc.close()
                doc = None
            
            # 임시 파일 정리
            try:
                os.remove(temp_pdf_path)
                print("임시 PDF 파일이 삭제되었습니다.")
            except:
                print("임시 PDF 파일 삭제 실패")
        
    except Exception as e:
        print(f"처리 중 에러 발생: {str(e)}")
    finally:
        # 문서가 아직 열려있다면 닫기
        if doc:
            try:
                doc.close()
            except:
                pass

if __name__ == "__main__":
    # 파일 경로 설정
    pdf_path = "./data/pdf/연말정산-1-14.pdf"
    json_path = "./data/json/연말정산_1_14.json"
    output_json_path = "./data/json/연말정산_1_14_modified_result.json"
    titles_path = "./data/titles/연말정산_1_14_titles.txt"  # 제목 리스트 저장 경로
    
    # 목차 페이지 범위 설정 (0-based)
    toc_start_page = 3  # 실제 PDF의 9페이지
    toc_end_page = 7   # 실제 PDF의 14페이지
    
    # 전체 프로세스 실행
    if os.path.exists(pdf_path) and os.path.exists(json_path):
        process_pdf_and_json(pdf_path, json_path, output_json_path, titles_path, 
                           toc_start_page=toc_start_page, toc_end_page=toc_end_page)
    else:
        print("PDF 파일 또는 JSON 파일을 찾을 수 없습니다.") 