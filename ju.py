import json
import re

def repair_json_string(json_str):
    """JSON 문자열 내의 이스케이프 문제를 수정합니다."""
    # 이스케이프 처리가 필요한 패턴 수정
    # 백슬래시를 두 개로 변경 (\\ -> \\\\)
    json_str = re.sub(r'([^\\])\\([^"\\/bfnrtu])', r'\1\\\\\2', json_str)
    
    # 원시 문자열 내의 잘못된 이스케이프 처리
    # 코드 블록 내에서 \를 \\로 변경
    in_code_block = False
    lines = json_str.split('\n')
    for i, line in enumerate(lines):
        if '"source": [' in line:
            in_code_block = True
        elif in_code_block and ']' in line and not re.search(r'^\s*"', line.strip()):
            in_code_block = False
        
        if in_code_block and '\\' in line:
            # 이미 이스케이프된 문자는 건너뛰기
            lines[i] = re.sub(r'([^\\])\\([^"\\/bfnrtu])', r'\1\\\\\2', line)
    
    return '\n'.join(lines)

def convert_to_notebook(input_file, output_file):
    """
    JSON 파일을 Jupyter Notebook(.ipynb) 파일로 변환합니다.
    이스케이프 문자 문제를 자동으로 수정합니다.
    
    Args:
        input_file (str): 입력 JSON 파일 경로
        output_file (str): 출력 Notebook 파일 경로
    """
    try:
        # 파일을 문자열로 읽기
        with open(input_file, 'r', encoding='utf-8') as f:
            json_str = f.read()
        
        # JSON 파싱 시도
        try:
            notebook_data = json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"JSON 파싱 오류 발생: {str(e)}")
            print("이스케이프 문제를 수정하고 다시 시도합니다...")
            
            # 이스케이프 문제 수정
            fixed_json_str = repair_json_string(json_str)
            
            # 다시 파싱 시도
            try:
                notebook_data = json.loads(fixed_json_str)
            except json.JSONDecodeError as e2:
                print(f"수정 후에도 오류 발생: {str(e2)}")
                
                # 직접 수정이 필요한 경우 백업 방법으로 정규식 사용
                print("대체 방법을 시도합니다...")
                with open('fixed_json.txt', 'w', encoding='utf-8') as f:
                    f.write(fixed_json_str)
                    
                print("수정된 JSON을 'fixed_json.txt'에 저장했습니다.")
                print("이 파일을 수동으로 편집한 후 다시 시도해보세요.")
                return False
        
        # 노트북 형식 확인
        if 'cells' not in notebook_data or 'metadata' not in notebook_data:
            print("파일이 Jupyter Notebook 형식이 아닙니다!")
            return False
        
        # .ipynb 파일로 저장
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(notebook_data, f, ensure_ascii=False, indent=1)
        
        print(f"변환 완료: {output_file}에 저장되었습니다.")
        return True
    
    except Exception as e:
        print(f"처리 중 오류 발생: {str(e)}")
        return False

# 실행 코드
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("사용법: python notebook_converter.py <입력_파일.json> <출력_파일.ipynb>")
        print("예시: python notebook_converter.py paste.txt notebook.ipynb")
        
        # 인자가 없으면 기본값 사용
        input_file = "paste.txt"
        output_file = "notebook.ipynb"
    else:
        input_file = sys.argv[1]
        output_file = sys.argv[2]
    
    convert_to_notebook(input_file, output_file)