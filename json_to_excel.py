import json
import pandas as pd
from collections import defaultdict
import os

def json_to_excel(input_json_file, output_excel_file):
    """
    JSON 파일을 읽고 지정된 형식으로 Excel 파일을 생성합니다.
    
    Args:
        input_json_file (str): 입력 JSON 파일 경로
        output_excel_file (str): 출력 Excel 파일 경로
    """
    # JSON 파일 읽기
    with open(input_json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 요소 추출
    elements = data.get('elements', [])
    
    if not elements:
        print("요소를 찾을 수 없습니다.")
        return
    
    # Excel 데이터 준비
    excel_data = []
    
    # 페이지별 content 수집
    page_contents = defaultdict(list)
    
    for element in elements:
        element_id = element.get('id')
        page = element.get('page')
        
        # content 추출 (markdown 또는 text)
        content = ""
        content_obj = element.get('content', {})
        if content_obj:
            content = content_obj.get('markdown', '') or content_obj.get('text', '')
        
        # 페이지별 content 저장
        if content:
            page_contents[page].append((element_id, content))
        
        # Excel 데이터에 추가
        excel_data.append({
            'content': content,
            'id': element_id,
            'page': page
        })
    
    # 최종 Excel 데이터 준비
    final_excel_data = []
    
    # 각 요소를 Excel 데이터에 추가
    for item in excel_data:
        content = item['content']
        element_id = item['id']
        page = item['page']
        
        # 페이지의 모든 콘텐츠를 가져옴
        page_content_list = sorted(page_contents[page], key=lambda x: x[0])
        page_content_text = "\n".join([content for _, content in page_content_list])
        
        # 메타데이터 생성
        metadata_str = f'id:{element_id},\npage: {page},\npage_content: {{\n"{page_content_text}"\n}}'
        
        # 최종 데이터에 추가
        final_excel_data.append({
            'content': content,
            'metadata': metadata_str
        })
    
    # DataFrame 생성 및 Excel 파일로 저장
    df = pd.DataFrame(final_excel_data)
    
    # 전체 파일 저장
    df.to_excel(output_excel_file, index=False, engine='openpyxl')
    print(f"Excel 파일이 성공적으로 생성되었습니다: {output_excel_file}")

if __name__ == "__main__":
    # 현재 디렉토리에서 처리할 JSON 파일 선택
    json_files = [f for f in os.listdir('.') if f.endswith('.json')]
    
    # ./data/xlsx 디렉토리가 없으면 생성
    output_dir = './data/xlsx'
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    if not json_files:
        print("디렉토리에 JSON 파일이 없습니다.")
    else:
        print("변환할 JSON 파일을 선택하세요:")
        for i, json_file in enumerate(json_files):
            print(f"{i+1}. {json_file}")
        
        try:
            selection = int(input("번호 선택: ")) - 1
            if 0 <= selection < len(json_files):
                input_file = json_files[selection]
                # 출력 파일명 생성 (JSON 파일명에서 확장자만 바꿈)
                output_file = os.path.splitext(input_file)[0] + '.xlsx'
                
                print(f"'{input_file}'을(를) 엑셀 파일로 변환합니다...")
                json_to_excel(input_file, output_file)
            else:
                print("올바른 번호를 선택하세요.")
        except ValueError:
            print("숫자를 입력하세요.") 