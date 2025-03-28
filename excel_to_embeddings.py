import pandas as pd
import os
import json
import time
from openai import OpenAI
import numpy as np

def create_embeddings(excel_file, output_file=None, batch_size=100):
    """
    Excel 파일의 내용을 읽고 OpenAI API를 사용하여 임베딩을 생성합니다.
    
    Args:
        excel_file (str): Excel 파일 경로
        output_file (str): 임베딩을 저장할 파일 경로 (기본값: excel 파일명_embeddings.json)
        batch_size (int): 한 번에 처리할 최대 항목 수
    """
    # API 키 설정 (환경 변수에서 가져오거나 직접 입력)
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        api_key = input("OpenAI API 키를 입력하세요: ")
        os.environ["OPENAI_API_KEY"] = api_key
    
    # OpenAI 클라이언트 초기화
    client = OpenAI(api_key=api_key)
    
    # Excel 파일 읽기
    print(f"'{excel_file}' 파일을 읽는 중...")
    df = pd.read_excel(excel_file)
    
    # 출력 파일 이름 설정
    if output_file is None:
        output_file = os.path.splitext(excel_file)[0] + "_embeddings.json"
    
    # 임베딩 저장을 위한 리스트
    embeddings_data = []
    
    print(f"총 {len(df)} 항목에 대한 임베딩을 생성합니다...")
    
    # 배치 단위로 처리
    for i in range(0, len(df), batch_size):
        batch = df.iloc[i:i + batch_size]
        batch_embeddings = []
        
        print(f"배치 처리 중: {i+1}~{min(i+batch_size, len(df))} / {len(df)}")
        
        for idx, row in batch.iterrows():
            content = row['content']
            metadata = row['metadata']
            
            try:
                # content에 대한 임베딩 생성
                content_embedding_response = client.embeddings.create(
                    model="text-embedding-ada-002",
                    input=content,
                    encoding_format="float"
                )
                content_embedding = content_embedding_response.data[0].embedding
                
                # 결과 저장
                item_data = {
                    "content": content,
                    "metadata": metadata,
                    "embedding": content_embedding
                }
                
                batch_embeddings.append(item_data)
                print(f"항목 {idx+1} 임베딩 완료")
                
                # API 요청 간 짧은 대기 시간 추가
                time.sleep(0.1)
                
            except Exception as e:
                print(f"항목 {idx+1} 임베딩 실패: {str(e)}")
        
        # 배치 결과를 전체 결과에 추가
        embeddings_data.extend(batch_embeddings)
    
    # 임베딩을 JSON 파일로 저장
    class NumpyEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            return json.JSONEncoder.default(self, obj)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(embeddings_data, f, ensure_ascii=False, cls=NumpyEncoder)
    
    print(f"임베딩이 성공적으로 생성되었습니다: {output_file}")

if __name__ == "__main__":
    # 현재 디렉토리에서 처리할 Excel 파일 선택
    excel_files = [f for f in os.listdir('.') if f.endswith('.xlsx') and not f.endswith('_embeddings.xlsx')]
    
    if not excel_files:
        print("디렉토리에 Excel 파일이 없습니다.")
    else:
        print("임베딩할 Excel 파일을 선택하세요:")
        for i, excel_file in enumerate(excel_files):
            print(f"{i+1}. {excel_file}")
        
        try:
            selection = int(input("번호 선택: ")) - 1
            if 0 <= selection < len(excel_files):
                input_file = excel_files[selection]
                
                print(f"'{input_file}'을(를) 임베딩합니다...")
                create_embeddings(input_file)
            else:
                print("올바른 번호를 선택하세요.")
        except ValueError:
            print("숫자를 입력하세요.") 