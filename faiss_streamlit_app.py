import streamlit as st
import pandas as pd
import numpy as np
import faiss
import pickle
import os
import json
import time
import datetime
from tqdm.auto import tqdm
from dotenv import load_dotenv
from openai import OpenAI

# 환경 변수 로드
load_dotenv()

# 페이지 설정
st.set_page_config(
    page_title="FAISS 벡터 저장소 탐색기",
    page_icon="🔍",
    layout="wide"
)

# prompt 템플릿 로드
with open('prompt.txt', 'r', encoding='utf-8') as f:
    PROMPT_TEMPLATE = f.read()

# 로그 디렉토리 생성
LOG_DIR = 'logs'
os.makedirs(LOG_DIR, exist_ok=True)

def log_gpt_interaction(question, context, model, response, metadata_only=None, system_prompt=None):
    """
    GPT와의 상호작용을 로그 파일에 기록합니다.
    
    Args:
        question (str): 사용자 질문
        context (str): 제공된 컨텍스트
        model (str): 사용된 모델
        response (str): GPT의 응답
        metadata_only (str, optional): 메타데이터만 추출한 컨텍스트
        system_prompt (str, optional): GPT에게 전송된 system 메시지
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(LOG_DIR, f"gpt_interaction_{timestamp}.json")
    
    log_data = {
        "timestamp": timestamp,
        "model": model,
        "question": question,
        "system_prompt": system_prompt,  # 실제 전송된 system 프롬프트
        "response": response,
        # 디버깅용 데이터
        "full_context": context,
        "metadata_context": metadata_only
    }
    
    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump(log_data, f, ensure_ascii=False, indent=2)
    
    return log_file

class FAISSVectorStore:
    """
    FAISS를 사용하여 임베딩 벡터를 저장하고 검색하는 벡터 저장소 클래스
    """
    def __init__(self, index=None, contents=None, metadata=None):
        self.index = index
        self.contents = contents or []
        self.metadata = metadata or []
        self.dimension = 1536  # OpenAI text-embedding-3-small 임베딩 차원
    
    def load_embeddings(self, embeddings_file, index_file=None, force_recreate=False):
        """
        Excel 파일에서 데이터를 로드하고 임베딩을 생성한 후 FAISS 인덱스를 생성합니다.
        
        Args:
            embeddings_file (str): Excel 파일 경로
            index_file (str): 저장된 FAISS 인덱스 파일 경로 (있는 경우)
            force_recreate (bool): 기존 인덱스가 있어도 무시하고 새로 생성할지 여부
        """
        status_placeholder = st.empty()
        progress_bar = st.progress(0)
        
        status_placeholder.info(f"임베딩 파일 '{embeddings_file}'을 로드하는 중...")
        progress_bar.progress(10)
        
        # 이미 저장된 인덱스가 있는지 확인
        if not force_recreate and index_file and os.path.exists(index_file):
            status_placeholder.info(f"저장된 FAISS 인덱스 '{index_file}'을 로드하는 중...")
            progress_bar.progress(30)
            
            self.index = faiss.read_index(index_file)
            progress_bar.progress(50)
            
            # 메타데이터 파일도 로드
            meta_file = index_file + '.meta'
            if os.path.exists(meta_file):
                with open(meta_file, 'rb') as f:
                    meta_data = pickle.load(f)
                    self.contents = meta_data['contents']
                    self.metadata = meta_data['metadata']
                progress_bar.progress(80)
                status_placeholder.success(f"메타데이터가 로드되었습니다. 총 {len(self.contents)} 개의 항목.")
                progress_bar.progress(100)
                return True
        
        # Excel 파일로부터 임베딩 생성
        status_placeholder.info("Excel 파일로부터 임베딩을 생성합니다...")
        progress_bar.progress(20)
        
        # Excel 파일 읽기
        df = pd.read_excel(embeddings_file)
        progress_bar.progress(30)
        
        # 벡터 추출 및 인덱스 구축
        vectors = []
        
        # OpenAI API 키 설정
        api_key = os.environ.get("OPENAI_API_KEY", st.session_state.get('api_key'))
        if not api_key:
            status_placeholder.error("OpenAI API 키가 설정되지 않았습니다.")
            progress_bar.progress(0)
            return False
        
        # OpenAI 클라이언트 초기화
        client = OpenAI(api_key=api_key)
        
        # 배치 크기 설정
        batch_size = 10  # 작은 배치 크기로 시작
        
        status_placeholder.info(f"총 {len(df)} 항목에 대한 임베딩을 생성합니다...")
        
        for i in range(0, len(df), batch_size):
            batch = df.iloc[i:i + batch_size]
            
            # 진행 상황 업데이트
            progress = 30 + (50 * i / len(df))
            progress_bar.progress(int(progress))
            status_placeholder.info(f"배치 처리 중: {i+1}~{min(i+batch_size, len(df))} / {len(df)}")
            
            for idx, row in batch.iterrows():
                content = row['content']
                metadata = row['metadata']
                
                try:
                    # content에 대한 임베딩 생성
                    content_embedding_response = client.embeddings.create(
                        model="text-embedding-3-small",
                        input=content,
                        encoding_format="float"
                    )
                    content_embedding = content_embedding_response.data[0].embedding
                    
                    # 결과 저장
                    vectors.append(content_embedding)
                    self.contents.append(content)
                    self.metadata.append(metadata)
                    
                    # API 요청 간 짧은 대기 시간 추가
                    time.sleep(0.1)
                    
                except Exception as e:
                    status_placeholder.error(f"항목 {idx+1} 임베딩 실패: {str(e)}")
        
        progress_bar.progress(80)
        
        if not vectors:
            status_placeholder.error("처리할 벡터가 없습니다.")
            progress_bar.progress(0)
            return False
        
        # NumPy 배열로 변환
        vectors = np.array(vectors).astype('float32')
        
        # FAISS 인덱스 생성
        status_placeholder.info("FAISS 인덱스 생성 중...")
        self.dimension = vectors.shape[1]
        self.index = faiss.IndexFlatIP(self.dimension)  # 내적(코사인 유사도)을 위한 인덱스
        
        # 정규화 (코사인 유사도 계산을 위해)
        faiss.normalize_L2(vectors)
        
        # 인덱스에 벡터 추가
        self.index.add(vectors)
        
        progress_bar.progress(90)
        status_placeholder.success(f"총 {len(vectors)} 개의 임베딩이 FAISS 인덱스에 로드되었습니다.")
        
        # 인덱스 및 메타데이터 저장
        if index_file:
            status_placeholder.info(f"FAISS 인덱스를 '{index_file}'에 저장하는 중...")
            faiss.write_index(self.index, index_file)
            
            # 메타데이터 저장
            meta_data = {
                'contents': self.contents,
                'metadata': self.metadata
            }
            with open(index_file + '.meta', 'wb') as f:
                pickle.dump(meta_data, f)
            status_placeholder.success(f"FAISS 인덱스 및 메타데이터가 저장되었습니다.")
        
        progress_bar.progress(100)
        return True
    
    def search(self, query_embedding, top_k=5):
        """
        쿼리 임베딩과 가장 유사한 문서를 FAISS를 사용하여 검색합니다.
        
        Args:
            query_embedding (ndarray): 검색할 쿼리 임베딩
            top_k (int): 반환할 최대 결과 수
            
        Returns:
            list: 유사도 순으로 정렬된 결과 목록
        """
        if self.index is None:
            st.error("인덱스가 초기화되지 않았습니다.")
            return []
        
        # 쿼리 정규화 (코사인 유사도를 위해)
        query_embedding = query_embedding.astype('float32').reshape(1, -1)
        faiss.normalize_L2(query_embedding)
        
        # 검색 수행
        start_time = time.time()
        distances, indices = self.index.search(query_embedding, top_k)
        end_time = time.time()
        
        st.info(f"검색 완료 (소요 시간: {end_time - start_time:.4f}초)")
        
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

def get_embedding(text, model="text-embedding-3-small"):
    """
    OpenAI API를 사용하여 텍스트의 임베딩을 생성합니다.
    
    Args:
        text (str): 임베딩할 텍스트
        model (str): 임베딩 모델 이름
        
    Returns:
        ndarray: 생성된 임베딩 벡터
    """
    api_key = os.environ.get("OPENAI_API_KEY", st.session_state.get('api_key'))
    if not api_key:
        st.error("OpenAI API 키가 설정되지 않았습니다.")
        return np.zeros(1536)  # 기본 차원의 빈 벡터 반환
    
    # OpenAI 클라이언트 초기화
    client = OpenAI(api_key=api_key)
    
    try:
        with st.spinner("임베딩 생성 중..."):
            response = client.embeddings.create(
                model=model,
                input=text,
                encoding_format="float"
            )
        return np.array(response.data[0].embedding)
    except Exception as e:
        st.error(f"임베딩 생성 오류: {str(e)}")
        return np.zeros(1536)

def format_metadata(metadata_str):
    """메타데이터 문자열을 포맷팅하여 표시합니다."""
    try:
        # 간단한 형식화를 위한 기본 처리
        lines = metadata_str.split('\n')
        formatted_text = ""
        for line in lines:
            if line.strip().startswith("id:") or line.strip().startswith("page:"):
                formatted_text += f"**{line.strip()}**\n\n"
            elif "page_content" in line:
                formatted_text += f"**{line.strip()}**\n"
            else:
                formatted_text += f"{line}\n"
        return formatted_text
    except:
        return metadata_str

def generate_answer(question, context, client, model="gpt-4o"):
    """
    OpenAI API를 사용하여 RAG 기반 답변을 생성합니다.
    
    Args:
        question (str): 사용자의 질문
        context (str): 검색 결과에서 추출한 컨텍스트
        client (OpenAI): OpenAI API 클라이언트
        model (str): 사용할 언어 모델
        
    Returns:
        str: 생성된 답변
    """
    try:
        # 프롬프트 템플릿에 질문과 컨텍스트의 metadata 삽입
        # context에서 metadata만 추출
        metadata_only = ""
        
        # context는 이미 문자열이므로 파싱할 필요 없이 그대로 사용
        # 원본 문서의 메타데이터 부분만 추출
        metadata_lines = []
        lines = context.split('\n')
        for i, line in enumerate(lines):
            if line.strip().startswith("메타데이터:"):
                # 메타데이터 행을 찾았으면, 그 다음 행부터 다음 "내용:" 또는 "문서"가 나올 때까지 추가
                j = i + 1
                while j < len(lines) and not (lines[j].strip().startswith("내용:") or lines[j].strip().startswith("문서")):
                    metadata_lines.append(lines[j])
                    j += 1
        
        metadata_only = "\n".join(metadata_lines)
        
        system_prompt = PROMPT_TEMPLATE.format(question=question, context=metadata_only)
        
        # OpenAI API 호출하여 답변 생성
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ],
            temperature=0.3,
            max_tokens=2000
        )
        
        answer_content = response.choices[0].message.content
        
        # 요청과 응답을 로그 파일에 저장
        log_file = log_gpt_interaction(
            question=question,
            context=context,
            model=model,
            response=answer_content,
            metadata_only=metadata_only,
            system_prompt=system_prompt  # 실제 GPT에게 전송된 system 프롬프트 추가
        )
        
        # 로그 저장 알림
        st.info(f"GPT 요청/응답이 다음 파일에 저장되었습니다: {log_file}")
        
        return answer_content
    except Exception as e:
        return f"답변 생성 중 오류가 발생했습니다: {str(e)}"

def get_xlsx_files():
    """
    data/xlsx 디렉토리에서 모든 엑셀 파일 목록을 반환합니다.
    """
    xlsx_dir = "./data/xlsx"
    os.makedirs(xlsx_dir, exist_ok=True)
    
    xlsx_files = [f for f in os.listdir(xlsx_dir) if f.endswith('.xlsx')]
    return xlsx_files

def get_faiss_files():
    """
    data/vdb 디렉토리에서 모든 FAISS 인덱스 파일 목록을 반환합니다.
    """
    vdb_dir = "./data/vdb"
    os.makedirs(vdb_dir, exist_ok=True)
    
    faiss_files = [f for f in os.listdir(vdb_dir) if f.endswith('.faiss')]
    return faiss_files

def main():
    # 제목
    st.title("🔍 FAISS 벡터 저장소 탐색기")
    
    # 사이드바 설정
    st.sidebar.title("설정")
    
    # API 키 설정
    api_key = st.sidebar.text_input("OpenAI API 키", 
                                   value=os.environ.get("OPENAI_API_KEY", ""), 
                                   type="password")
    
    if api_key:
        st.session_state['api_key'] = api_key
        os.environ["OPENAI_API_KEY"] = api_key
    
    # OpenAI 모델 선택
    model_options = ["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"]
    selected_model = st.sidebar.selectbox("OpenAI 모델 선택", model_options)
    
    # 디렉토리 생성
    os.makedirs("./data/xlsx", exist_ok=True)
    os.makedirs("./data/vdb", exist_ok=True)
    
    # 파일 설정
    st.sidebar.subheader("파일 설정")
    
    # 엑셀 파일 목록 가져오기
    xlsx_files = get_xlsx_files()
    
    # 직접 입력 또는 드롭다운 선택 옵션
    file_selection_mode = st.sidebar.radio("파일 선택 방식", ["드롭다운에서 선택", "직접 경로 입력"])
    
    if file_selection_mode == "드롭다운에서 선택":
        if xlsx_files:
            selected_xlsx = st.sidebar.selectbox(
                "Excel 파일 선택", 
                xlsx_files,
                index=0 if xlsx_files else None,
                format_func=lambda x: x
            )
            input_file = os.path.join("./data/xlsx", selected_xlsx) if selected_xlsx else ""
        else:
            st.sidebar.warning("./data/xlsx 디렉토리에 Excel 파일이 없습니다.")
            input_file = ""
            
        # FAISS 인덱스 파일 목록
        faiss_files = get_faiss_files()
        
        if faiss_files:
            # 선택된 Excel 파일에 대응하는 FAISS 파일 찾기
            if input_file:
                base_name_without_ext = os.path.splitext(os.path.basename(input_file))[0]
                matching_faiss = [f for f in faiss_files if f.startswith(base_name_without_ext)]
                
                # 기본 선택값 설정
                default_index = 0
                if matching_faiss:
                    default_index = faiss_files.index(matching_faiss[0])
                
                selected_faiss = st.sidebar.selectbox(
                    "FAISS 인덱스 파일 선택",
                    faiss_files,
                    index=default_index if faiss_files else None,
                    format_func=lambda x: x
                )
                index_file = os.path.join("./data/vdb", selected_faiss) if selected_faiss else ""
            else:
                selected_faiss = st.sidebar.selectbox(
                    "FAISS 인덱스 파일 선택",
                    faiss_files,
                    index=0 if faiss_files else None,
                    format_func=lambda x: x
                )
                index_file = os.path.join("./data/vdb", selected_faiss) if selected_faiss else ""
        else:
            st.sidebar.warning("./data/vdb 디렉토리에 FAISS 인덱스 파일이 없습니다.")
            index_file = ""
    else:
        # 직접 경로 입력 모드
        input_file = st.sidebar.text_input("Excel 파일 경로", "./data/xlsx/output_20250326_111000.xlsx")
        
        # 인덱스 파일은 엑셀 파일 이름을 기반으로 하되, ./data/vdb 디렉토리에 저장
        base_filename = os.path.basename(input_file)
        base_name_without_ext = os.path.splitext(base_filename)[0]
        index_file = st.sidebar.text_input(
            "FAISS 인덱스 파일 경로", 
            f"./data/vdb/{base_name_without_ext}.faiss" if input_file else "./data/vdb/embeddings.faiss"
        )
    
    # 탭 생성
    tab1, tab2, tab3, tab4 = st.tabs(["📊 데이터 로드", "⚙️ 인덱스 생성/로드", "🔍 검색", "🤖 RAG 답변 생성"])
    
    # 탭 1: 데이터 미리보기
    with tab1:
        st.header("데이터 미리보기")
        
        if st.button("데이터 로드"):
            if not os.path.exists(input_file):
                st.error(f"파일을 찾을 수 없습니다: {input_file}")
            else:
                try:
                    df = pd.read_excel(input_file)
                    st.session_state['df'] = df
                    
                    st.success(f"{len(df)}개 행을 로드했습니다.")
                    st.subheader("데이터 샘플")
                    st.dataframe(df.head())
                    
                    # 컬럼 정보 표시
                    st.subheader("컬럼 정보")
                    col_info = pd.DataFrame({
                        "컬럼명": df.columns,
                        "데이터 타입": df.dtypes,
                        "NULL 값 수": df.isnull().sum().values,
                        "고유값 수": [df[col].nunique() for col in df.columns]
                    })
                    st.dataframe(col_info)
                    
                except Exception as e:
                    st.error(f"Excel 파일 로드 오류: {str(e)}")
    
    # 탭 2: 인덱스 생성 또는 로드
    with tab2:
        st.header("인덱스 생성 또는 로드")
        
        # 선택한 Excel 파일의 FAISS 인덱스 파일이 없는지 확인하는 메시지 표시
        if input_file and os.path.exists(input_file):
            base_name_without_ext = os.path.splitext(os.path.basename(input_file))[0]
            expected_faiss_file = os.path.join("./data/vdb", f"{base_name_without_ext}.faiss")
            
            if not os.path.exists(expected_faiss_file):
                st.warning(f"선택한 Excel 파일({os.path.basename(input_file)})에 대응하는 FAISS 인덱스가 없습니다. '인덱스 생성' 버튼을 클릭하여 생성해주세요.")
        
        col1, col2 = st.columns(2)
        with col1:
            create_button = st.button("인덱스 생성", key="create_index_button")
        with col2:
            load_button = st.button("인덱스 로드", key="load_index_button")
        
        if create_button or load_button:
            if not os.path.exists(input_file):
                st.error(f"파일을 찾을 수 없습니다: {input_file}")
            elif not api_key:
                st.error("OpenAI API 키를 입력해주세요.")
            else:
                # 벡터 저장소 초기화
                vector_store = FAISSVectorStore()
                
                # 임베딩 로드 또는 생성
                if create_button:
                    # Excel 파일 기반으로 새 인덱스 생성 시 기존 인덱스 파일은 무시
                    success = vector_store.load_embeddings(input_file, index_file, force_recreate=True)
                else:
                    # 로드만 할 경우, 인덱스 파일이 없으면 자동으로 생성
                    if not os.path.exists(index_file):
                        st.warning(f"인덱스 파일이 없어 Excel 파일로부터 새로 생성합니다: {index_file}")
                    success = vector_store.load_embeddings(input_file, index_file)
                
                if success:
                    st.session_state['vector_store'] = vector_store
                    
                    # 인덱스 정보 표시
                    st.subheader("인덱스 정보")
                    st.write(f"벡터 수: {vector_store.index.ntotal}")
                    st.write(f"벡터 차원: {vector_store.dimension}")
                    st.write(f"문서 수: {len(vector_store.contents)}")
                    
                    # 첫 번째 문서 샘플 표시
                    if len(vector_store.contents) > 0:
                        st.subheader("첫 번째 문서 샘플")
                        st.text_area(label="문서 내용", value=vector_store.contents[0], height=150)
                        st.markdown("**메타데이터:**")
                        st.markdown(format_metadata(vector_store.metadata[0]))
    
    # 탭 3: 검색
    with tab3:
        st.header("검색")
        
        query = st.text_input("검색어 입력", "", key="search_query_input")
        top_k = st.slider("검색 결과 수", min_value=1, max_value=20, value=5, key="search_top_k_slider")
        
        if st.button("검색", key="search_button") and query:
            if 'vector_store' not in st.session_state:
                st.error("먼저 '인덱스 생성/로드' 탭에서 인덱스를 생성하거나 로드해주세요.")
            elif not api_key:
                st.error("OpenAI API 키를 입력해주세요.")
            else:
                # 쿼리 임베딩 생성
                vector_store = st.session_state['vector_store']
                query_embedding = get_embedding(query)
                
                # 검색
                results = vector_store.search(query_embedding, top_k)
                
                # 결과 표시
                if results:
                    st.subheader(f"검색 결과 ({len(results)}개)")
                    
                    for i, result in enumerate(results):
                        with st.expander(f"결과 {i+1} (유사도: {result['similarity']:.4f})"):
                            st.markdown("**내용:**")
                            st.text_area(label="문서 내용", value=result['content'], height=150, key=f"content_{i}")
                            
                            st.markdown("**메타데이터:**")
                            st.markdown(format_metadata(result['metadata']))
                else:
                    st.warning("검색 결과가 없습니다.")
    
    # 탭 4: RAG 답변 생성
    with tab4:
        st.header("RAG 답변 생성")
        
        question = st.text_area("질문 입력", "", height=100, key="rag_question_input")
        top_k = st.slider("검색 결과 수", min_value=1, max_value=20, value=5, key="rag_top_k_slider")
        
        col1, col2 = st.columns(2)
        with col1:
            generate_button = st.button("답변 생성", key="rag_generate_button")
        with col2:
            clear_button = st.button("초기화", key="rag_clear_button")
        
        if clear_button:
            if 'rag_results' in st.session_state:
                del st.session_state['rag_results']
            if 'rag_answer' in st.session_state:
                del st.session_state['rag_answer']
        
        if generate_button and question:
            if 'vector_store' not in st.session_state:
                st.error("먼저 '인덱스 생성/로드' 탭에서 인덱스를 생성하거나 로드해주세요.")
            elif not api_key:
                st.error("OpenAI API 키를 입력해주세요.")
            else:
                with st.spinner("검색 결과를 찾는 중..."):
                    # 쿼리 임베딩 생성
                    vector_store = st.session_state['vector_store']
                    query_embedding = get_embedding(question)
                    
                    # 검색
                    results = vector_store.search(query_embedding, top_k)
                    st.session_state['rag_results'] = results
                
                if results:
                    # 컨텍스트 구성
                    context = ""
                    for i, result in enumerate(results):
                        context += f"문서 {i+1}:\n"
                        context += f"내용: {result['content']}\n"
                        context += f"메타데이터: {result['metadata']}\n\n"
                    
                    # OpenAI 클라이언트 초기화
                    client = OpenAI(api_key=api_key)
                    
                    with st.spinner("GPT-4o로 답변을 생성하는 중..."):
                        answer = generate_answer(question, context, client, model=selected_model)
                        st.session_state['rag_answer'] = answer
                else:
                    st.warning("검색 결과가 없습니다. 다른 질문을 시도해 보세요.")
        
        # 결과 표시 섹션
        if 'rag_results' in st.session_state and 'rag_answer' in st.session_state:
            # 답변 표시
            st.subheader("생성된 답변")
            st.markdown(st.session_state['rag_answer'])
            
            # 검색 결과 표시
            st.subheader("사용된 참고 문서")
            for i, result in enumerate(st.session_state['rag_results']):
                with st.expander(f"문서 {i+1} (유사도: {result['similarity']:.4f})"):
                    st.markdown("**내용:**")
                    st.text_area(label="문서 내용", value=result['content'], height=150, key=f"rag_content_{i}")
                    
                    st.markdown("**메타데이터:**")
                    st.markdown(format_metadata(result['metadata']))

if __name__ == "__main__":
    main() 