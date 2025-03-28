import os
import json
import pandas as pd
import numpy as np
import time
from openai import OpenAI
from collections import defaultdict
from sklearn.metrics.pairwise import cosine_similarity

class DocumentProcessor:
    """
    JSON 파일을 Excel로 변환하고, 임베딩을 생성하고, 벡터 검색을 수행하는 통합 클래스
    """
    def __init__(self):
        # API 키 설정 (환경 변수에서 가져오거나 직접 입력)
        self.api_key = os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            self.api_key = input("OpenAI API 키를 입력하세요: ")
            os.environ["OPENAI_API_KEY"] = self.api_key
        
        self.client = None
        self.vector_store = None
    
    def _init_openai_client(self):
        """OpenAI 클라이언트 초기화"""
        if not self.client:
            self.client = OpenAI(api_key=self.api_key)
    
    def json_to_excel(self, input_json_file, output_excel_file=None):
        """
        JSON 파일을 읽고 지정된 형식으로 Excel 파일을 생성합니다.
        
        Args:
            input_json_file (str): 입력 JSON 파일 경로
            output_excel_file (str): 출력 Excel 파일 경로
        """
        print(f"JSON 파일 '{input_json_file}'을 Excel로 변환하는 중...")
        
        # 출력 파일 이름 설정
        if output_excel_file is None:
            output_excel_file = os.path.splitext(input_json_file)[0] + '.xlsx'
        
        # JSON 파일 읽기
        with open(input_json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 요소 추출
        elements = data.get('elements', [])
        
        if not elements:
            print("요소를 찾을 수 없습니다.")
            return None
        
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
        
        return output_excel_file
    
    def create_embeddings(self, excel_file, output_file=None, batch_size=100):
        """
        Excel 파일의 내용을 읽고 OpenAI API를 사용하여 임베딩을 생성합니다.
        
        Args:
            excel_file (str): Excel 파일 경로
            output_file (str): 임베딩을 저장할 파일 경로
            batch_size (int): 한 번에 처리할 최대 항목 수
        """
        self._init_openai_client()
        
        print(f"Excel 파일 '{excel_file}'로부터 임베딩을 생성하는 중...")
        
        # 출력 파일 이름 설정
        if output_file is None:
            output_file = os.path.splitext(excel_file)[0] + "_embeddings.json"
        
        # Excel 파일 읽기
        df = pd.read_excel(excel_file)
        
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
                    content_embedding_response = self.client.embeddings.create(
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
        
        return output_file
    
    def load_vector_store(self, embeddings_file):
        """
        임베딩 파일을 로드하여 벡터 저장소를 초기화합니다.
        
        Args:
            embeddings_file (str): 임베딩 파일 경로
        """
        print(f"임베딩 파일 '{embeddings_file}'을 로드하는 중...")
        
        # 벡터 저장소 초기화
        self.vector_store = {
            'vectors': [],
            'contents': [],
            'metadata': []
        }
        
        # 임베딩 파일 로드
        with open(embeddings_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for item in data:
            self.vector_store['vectors'].append(item['embedding'])
            self.vector_store['contents'].append(item['content'])
            self.vector_store['metadata'].append(item['metadata'])
        
        self.vector_store['vectors'] = np.array(self.vector_store['vectors'])
        print(f"총 {len(self.vector_store['vectors'])} 개의 임베딩을 로드했습니다.")
    
    def search(self, query, top_k=5):
        """
        쿼리와 가장 유사한 문서를 검색합니다.
        
        Args:
            query (str): 검색 쿼리
            top_k (int): 반환할 최대 결과 수
            
        Returns:
            list: 유사도 순으로 정렬된 결과 목록
        """
        self._init_openai_client()
        
        if not self.vector_store:
            print("벡터 저장소가 초기화되지 않았습니다. 먼저 임베딩 파일을 로드하세요.")
            return []
        
        # 쿼리 임베딩 생성
        query_embedding_response = self.client.embeddings.create(
            model="text-embedding-ada-002",
            input=query,
            encoding_format="float"
        )
        query_embedding = np.array(query_embedding_response.data[0].embedding)
        
        # 코사인 유사도 계산
        similarities = cosine_similarity([query_embedding], self.vector_store['vectors'])[0]
        
        # 상위 k개 결과 인덱스
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        # 결과 구성
        results = []
        for i in top_indices:
            results.append({
                'content': self.vector_store['contents'][i],
                'metadata': self.vector_store['metadata'][i],
                'similarity': float(similarities[i])
            })
        
        return results
    
    def interactive_search(self):
        """
        대화형 검색을 실행합니다.
        """
        if not self.vector_store:
            print("벡터 저장소가 초기화되지 않았습니다. 먼저 임베딩 파일을 로드하세요.")
            return
        
        print("벡터 검색을 시작합니다. 종료하려면 'exit'를 입력하세요.")
        
        while True:
            query = input("\n검색어를 입력하세요: ")
            if query.lower() == 'exit':
                break
            
            top_k = input("반환할 결과 수(기본값 5): ")
            try:
                top_k = int(top_k) if top_k else 5
            except ValueError:
                top_k = 5
                print("잘못된 입력입니다. 기본값 5를 사용합니다.")
            
            results = self.search(query, top_k)
            
            print(f"\n검색 결과 ({len(results)}개):")
            for i, result in enumerate(results):
                print(f"\n결과 {i+1} (유사도: {result['similarity']:.4f}):")
                print(f"내용: {result['content'][:150]}..." if len(result['content']) > 150 else f"내용: {result['content']}")
                print(f"메타데이터: {result['metadata'][:150]}..." if len(result['metadata']) > 150 else f"메타데이터: {result['metadata']}")

def main():
    """
    메인 함수
    """
    processor = DocumentProcessor()
    
    print("문서 처리 프로그램을 시작합니다.")
    print("1. JSON 파일을 Excel로 변환")
    print("2. Excel 파일에서 임베딩 생성")
    print("3. 임베딩 파일로 벡터 검색")
    print("4. 전체 프로세스 실행 (JSON -> Excel -> 임베딩 -> 검색)")
    
    choice = input("수행할 작업을 선택하세요: ")
    
    if choice == '1':
        # JSON 파일 선택
        json_files = [f for f in os.listdir('.') if f.endswith('.json')]
        
        if not json_files:
            print("디렉토리에 JSON 파일이 없습니다.")
            return
        
        print("변환할 JSON 파일을 선택하세요:")
        for i, json_file in enumerate(json_files):
            print(f"{i+1}. {json_file}")
        
        selection = int(input("번호 선택: ")) - 1
        if 0 <= selection < len(json_files):
            input_file = json_files[selection]
            processor.json_to_excel(input_file)
    
    elif choice == '2':
        # Excel 파일 선택
        excel_files = [f for f in os.listdir('.') if f.endswith('.xlsx') and not f.endswith('_embeddings.xlsx')]
        
        if not excel_files:
            print("디렉토리에 Excel 파일이 없습니다.")
            return
        
        print("임베딩할 Excel 파일을 선택하세요:")
        for i, excel_file in enumerate(excel_files):
            print(f"{i+1}. {excel_file}")
        
        selection = int(input("번호 선택: ")) - 1
        if 0 <= selection < len(excel_files):
            input_file = excel_files[selection]
            processor.create_embeddings(input_file)
    
    elif choice == '3':
        # 임베딩 파일 선택
        embeddings_files = [f for f in os.listdir('.') if f.endswith('_embeddings.json')]
        
        if not embeddings_files:
            print("디렉토리에 임베딩 파일이 없습니다.")
            return
        
        print("검색할 임베딩 파일을 선택하세요:")
        for i, embeddings_file in enumerate(embeddings_files):
            print(f"{i+1}. {embeddings_file}")
        
        selection = int(input("번호 선택: ")) - 1
        if 0 <= selection < len(embeddings_files):
            input_file = embeddings_files[selection]
            processor.load_vector_store(input_file)
            processor.interactive_search()
    
    elif choice == '4':
        # JSON 파일 선택
        json_files = [f for f in os.listdir('.') if f.endswith('.json')]
        
        if not json_files:
            print("디렉토리에 JSON 파일이 없습니다.")
            return
        
        print("처리할 JSON 파일을 선택하세요:")
        for i, json_file in enumerate(json_files):
            print(f"{i+1}. {json_file}")
        
        selection = int(input("번호 선택: ")) - 1
        if 0 <= selection < len(json_files):
            input_json = json_files[selection]
            
            # JSON -> Excel
            excel_file = processor.json_to_excel(input_json)
            
            # Excel -> 임베딩
            if excel_file:
                embeddings_file = processor.create_embeddings(excel_file)
                
                # 임베딩 -> 벡터 검색
                if embeddings_file:
                    processor.load_vector_store(embeddings_file)
                    processor.interactive_search()
    
    else:
        print("올바른 옵션을 선택하세요.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"오류가 발생했습니다: {str(e)}")
        import traceback
        traceback.print_exc() 