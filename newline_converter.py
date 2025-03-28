def convert_newlines(input_file: str, output_file: str):
    """
    파일의 개행문자(\n)를 실제 개행으로 변환합니다.
    한글 인코딩을 유지하면서 처리합니다.
    
    Args:
        input_file (str): 입력 파일 경로
        output_file (str): 출력 파일 경로
    """
    try:
        # 입력 파일 읽기
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 리터럴 문자열로 변환하여 개행문자 처리
        content = content.replace('\\n', '\n')
        
        # 결과를 새 파일에 저장
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(content)
            
        print(f"변환이 완료되었습니다.")
        print(f"입력 파일: {input_file}")
        print(f"출력 파일: {output_file}")
        
    except Exception as e:
        print(f"오류가 발생했습니다: {str(e)}")

if __name__ == "__main__":
    # 예시 사용
    convert_newlines('./data/롯손보/output.txt', './data/롯손보/output_fixed.txt') 