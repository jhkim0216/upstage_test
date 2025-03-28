import os
import json
import pandas as pd
import numpy as np
import time
from openai import OpenAI
from collections import defaultdict
import faiss
import pickle

class DocumentProcessor:
    """
    JSON 파일을 Excel로 변환하고, 임베딩을 생성하고, FAISS를 사용한 벡터 검색을 수행하는 통합 클래스
    """
    def __init__(self):
        # API 키 설정 (환경 변수에서 가져오거나 직접 입력)
        self.api_key = os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            self.api_key = input("OpenAI API 키를 입력하세요: ")
            os.environ["OPENAI_API_KEY"] = self.api_key
        
        self.client = None
        self.faiss_index = None
        self.contents = []
        self.metadata = []
        self.dimension = 1536  # OpenAI Ada-002 임베딩 차원
    
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
    
    def load_faiss_index(self, embeddings_file, index_file=None):
        """
        임베딩 파일을 로드하여 FAISS 인덱스를 초기화합니다.
        
        Args:
            embeddings_file (str): 임베딩 파일 경로
            index_file (str): FAISS 인덱스 파일 경로 (선택사항)
        """
        print(f"임베딩 파일 '{embeddings_file}'을 FAISS 인덱스로 로드하는 중...")
        
        # 인덱스 파일 이름 설정
        if index_file is None:
            index_file = os.path.splitext(embeddings_file)[0] + ".faiss"
        
        # 이미 저장된 인덱스가 있는지 확인
        if os.path.exists(index_file):
            print(f"저장된 FAISS 인덱스 '{index_file}'을 로드하는 중...")
            self.faiss_index = faiss.read_index(index_file)
            
            # 메타데이터 파일도 로드
            meta_file = index_file + '.meta'
            if os.path.exists(meta_file):
                with open(meta_file, 'rb') as f:
                    meta_data = pickle.load(f)
                    self.contents = meta_data['contents']
                    self.metadata = meta_data['metadata']
                print(f"메타데이터가 로드되었습니다. 총 {len(self.contents)} 개의 항목.")
                return True
        
        # 임베딩 데이터 로드
        with open(embeddings_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 벡터 추출 및 인덱스 구축
        vectors = []
        self.contents = []
        self.metadata = []
        
        for item in data:
            vectors.append(item['embedding'])
            self.contents.append(item['content'])
            self.metadata.append(item['metadata'])
        
        vectors = np.array(vectors).astype('float32')
        
        # FAISS 인덱스 생성
        self.dimension = vectors.shape[1]
        self.faiss_index = faiss.IndexFlatIP(self.dimension)  # 내적(코사인 유사도)을 위한 인덱스
        
        # 정규화 (코사인 유사도 계산을 위해)
        faiss.normalize_L2(vectors)
        
        # 인덱스에 벡터 추가
        self.faiss_index.add(vectors)
        
        print(f"총 {len(vectors)} 개의 임베딩이 FAISS 인덱스에 로드되었습니다.")
        
        # 인덱스 및 메타데이터 저장
        print(f"FAISS 인덱스를 '{index_file}'에 저장하는 중...")
        faiss.write_index(self.faiss_index, index_file)
        
        # 메타데이터 저장
        meta_data = {
            'contents': self.contents,
            'metadata': self.metadata
        }
        with open(index_file + '.meta', 'wb') as f:
            pickle.dump(meta_data, f)
        print(f"FAISS 인덱스 및 메타데이터가 저장되었습니다.")
        
        return True
    
    def search(self, query, top_k=5):
        """
        쿼리와 가장 유사한 문서를 FAISS를 사용하여 검색합니다.
        
        Args:
            query (str): 검색 쿼리
            top_k (int): 반환할 최대 결과 수
            
        Returns:
            list: 유사도 순으로 정렬된 결과 목록
        """
        self._init_openai_client()
        
        if self.faiss_index is None:
            print("FAISS 인덱스가 초기화되지 않았습니다. 먼저 임베딩 파일을 로드하세요.")
            return []
        
        # 쿼리 임베딩 생성
        query_embedding_response = self.client.embeddings.create(
            model="text-embedding-ada-002",
            input=query,
            encoding_format="float"
        )
        query_embedding = np.array(query_embedding_response.data[0].embedding).astype('float32').reshape(1, -1)
        
        # 정규화 (코사인 유사도를 위해)
        faiss.normalize_L2(query_embedding)
        
        # 검색 수행
        distances, indices = self.faiss_index.search(query_embedding, top_k)
        
        # 결과 구성
        results = []
        for i, (dist, idx) in enumerate(zip(distances[0], indices[0])):
            if idx >= 0 and idx < len(self.contents):  # 유효한 인덱스인지 확인
                results.append({
                    'content': self.contents[idx],
                    'metadata': self.metadata[idx],
                    'similarity': float(dist)  # 코사인 유사도 (높을수록 유사)
                })
        
        return results
    
    def interactive_search(self):
        """
        대화형 검색을 실행합니다.
        """
        if self.faiss_index is None:
            print("FAISS 인덱스가 초기화되지 않았습니다. 먼저 임베딩 파일을 로드하세요.")
            return
        
        print("FAISS 벡터 검색을 시작합니다. 종료하려면 'exit'를 입력하세요.")
        
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
            
            try:
                results = self.search(query, top_k)
                
                print(f"\n검색 결과 ({len(results)}개):")
                for i, result in enumerate(results):
                    print(f"\n결과 {i+1} (유사도: {result['similarity']:.4f}):")
                    print(f"내용: {result['content'][:150]}..." if len(result['content']) > 150 else f"내용: {result['content']}")
                    print(f"메타데이터: {result['metadata'][:150]}..." if len(result['metadata']) > 150 else f"메타데이터: {result['metadata']}")
            
            except Exception as e:
                print(f"검색 중 오류가 발생했습니다: {str(e)}")

def main():
    """
    메인 함수
    """
    processor = DocumentProcessor()
    
    print("FAISS를 사용한 문서 처리 프로그램을 시작합니다.")
    print("1. JSON 파일을 Excel로 변환")
    print("2. Excel 파일에서 임베딩 생성")
    print("3. 임베딩 파일로 FAISS 인덱스 생성 및 벡터 검색")
    print("4. 전체 프로세스 실행 (JSON -> Excel -> 임베딩 -> FAISS 인덱스 -> 검색)")
    
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
        
        print("FAISS 인덱스를 생성할 임베딩 파일을 선택하세요:")
        for i, embeddings_file in enumerate(embeddings_files):
            print(f"{i+1}. {embeddings_file}")
        
        selection = int(input("번호 선택: ")) - 1
        if 0 <= selection < len(embeddings_files):
            input_file = embeddings_files[selection]
            
            # FAISS 인덱스 파일 경로
            index_file = os.path.splitext(input_file)[0] + ".faiss"
            
            processor.load_faiss_index(input_file, index_file)
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
                
                # 임베딩 -> FAISS 인덱스 -> 벡터 검색
                if embeddings_file:
                    # FAISS 인덱스 파일 경로
                    index_file = os.path.splitext(embeddings_file)[0] + ".faiss"
                    
                    processor.load_faiss_index(embeddings_file, index_file)
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