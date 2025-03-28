# pip install requests
import requests
import json
import time
import asyncio
from datetime import datetime
from typing import Dict, List, Optional

api_key = "up_vnChyUEnu55aG09M11VjZy3TcyF2O"  # ex: up_xxxYYYzzzAAAbbbCCC

class DocumentParser:
    def __init__(self, filename):
        self.filename = filename

    def parse(self):
        url = "https://api.upstage.ai/v1/document-ai/document-parse"
        headers = {"Authorization": f"Bearer {api_key}"}
        
        files = {"document": open(self.filename, "rb")}
        data = {"ocr": "force", "base64_encoding": "['table','figure', 'chart']", "model": "document-parse", "output_formats": "['html', 'markdown','text']"}
        response = requests.post(url, headers=headers, files=files, data=data)
        response_data = response.json()
        return response_data
    
    # 응답 데이터 가져오기
    def save_to_json(self, filename):
        response_data = self.parse()
        now = datetime.now()
        output_filename = f'output_{now.strftime("%Y%m%d_%H%M%S")}.json'
        with open(output_filename, 'w', encoding='utf-8') as f:
            json.dump(response_data, f, ensure_ascii=False, indent=4)

class AsyncDocumentParser:
    def __init__(self, filename: str):
        self.filename = filename
        self.base_url = "https://api.upstage.ai/v1/document-ai"
        self.headers = {"Authorization": f"Bearer {api_key}"}
        self.request_id = None
        self.total_pages = 0
        self.completed_pages = 0
        self.current_id = 0  # ID 관리를 위한 카운터 추가

    async def submit_document(self):
        """문서를 업로드하고 비동기 처리 요청을 시작합니다."""
        url = f"{self.base_url}/async/document-parse"
        files = {"document": open(self.filename, "rb")}
        data = {
            "ocr": "auto",
            "coordinates": True,
            "chart_recognition": True,
            "base64_encoding": json.dumps(["table", "figure", "chart"]),
            "model": "document-parse",
            "output_formats": json.dumps(["markdown","text"])
        }
        
        print(f"API 요청 URL: {url}")
        print(f"API 요청 데이터: {json.dumps(data, indent=2, ensure_ascii=False)}")
        print(f"업로드 파일: {self.filename}")
        
        # multipart/form-data로 전송하기 위해 data를 문자열로 변환
        data = {k: str(v).lower() if isinstance(v, bool) else v for k, v in data.items()}
        
        try:
            response = await asyncio.to_thread(
                requests.post, 
                url=url, 
                headers=self.headers, 
                files=files, 
                data=data
            )
            
            print(f"문서 제출 응답 상태 코드: {response.status_code}")
            print(f"문서 제출 응답 헤더: {dict(response.headers)}")
            print(f"문서 제출 응답: {response.text}")
            
            # 요청 에러 처리
            if response.status_code == 400:
                error_data = response.json()
                if "invalid model name" in error_data.get("message", ""):
                    raise ValueError("잘못된 모델명입니다.")
                elif "no document in the request" in error_data.get("message", ""):
                    raise ValueError("요청에 문서가 포함되지 않았습니다.")
                else:
                    raise ValueError(f"잘못된 요청: {error_data.get('message', '알 수 없는 오류')}")
            elif response.status_code == 413:
                raise ValueError("업로드된 문서가 너무 큽니다. 최대 허용 크기는 50MB입니다.")
            elif response.status_code == 415:
                raise ValueError("지원하지 않는 문서 형식입니다.")
            elif response.status_code not in [200, 202]:
                raise Exception(f"API 요청 실패 (상태 코드: {response.status_code}): {response.text}")
            
            response_data = response.json()
            self.request_id = response_data.get("request_id")
            if not self.request_id:
                raise ValueError("API 응답에서 request_id를 찾을 수 없습니다.")
            return response_data
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"API 요청 중 네트워크 오류 발생: {str(e)}")
        except json.JSONDecodeError:
            raise Exception("API 응답을 JSON으로 파싱할 수 없습니다.")

    async def check_status(self):
        """처리 상태를 확인합니다."""
        if not self.request_id:
            raise ValueError("Request ID가 없습니다. 먼저 submit_document를 호출하세요.")
        
        try:
            url = f"{self.base_url}/requests/{self.request_id}"
            response = await asyncio.to_thread(
                requests.get, 
                url=url, 
                headers=self.headers
            )
            
            if response.status_code != 200:
                raise Exception(f"상태 확인 실패 (상태 코드: {response.status_code}): {response.text}")
            
            status_data = response.json()
            print(f"상태 확인 응답: {json.dumps(status_data, indent=2, ensure_ascii=False)}")
            
            # 배치 처리 에러 확인
            if status_data.get("status") == "failed":
                failure_message = status_data.get("failure_message", "알 수 없는 오류")
                raise Exception(f"문서 처리 실패: {failure_message}")
            
            # 배치별 상태 확인
            for batch in status_data.get("batches", []):
                if batch.get("status") == "failed":
                    failure_message = batch.get("failure_message", "알 수 없는 오류")
                    raise Exception(f"배치 처리 실패 (배치 ID: {batch.get('id')}): {failure_message}")
            
            self.total_pages = status_data.get("total_pages", 0)
            self.completed_pages = status_data.get("completed_pages", 0)
            return status_data
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"상태 확인 중 네트워크 오류 발생: {str(e)}")
        except json.JSONDecodeError:
            raise Exception("상태 확인 응답을 JSON으로 파싱할 수 없습니다.")

    async def download_batch_result(self, batch: dict):
        """각 배치의 결과를 다운로드합니다."""
        try:
            # URL 유효성 검사
            if not batch.get("download_url"):
                raise ValueError(f"배치 {batch.get('id')}의 다운로드 URL이 없습니다.")
            
            response = await asyncio.to_thread(
                requests.get, 
                url=batch["download_url"], 
                headers=self.headers
            )
            
            if response.status_code == 404:
                # URL이 만료된 경우 상태를 다시 확인하여 새로운 URL 획득
                print(f"배치 {batch.get('id')}의 다운로드 URL이 만료되었습니다. 상태를 다시 확인합니다.")
                status_data = await self.check_status()
                for new_batch in status_data.get("batches", []):
                    if new_batch.get("id") == batch.get("id"):
                        batch["download_url"] = new_batch.get("download_url")
                        return await self.download_batch_result(new_batch)
                raise Exception(f"배치 {batch.get('id')}의 새로운 다운로드 URL을 얻을 수 없습니다.")
            
            if response.status_code != 200:
                raise Exception(f"배치 다운로드 실패 (상태 코드: {response.status_code}): {response.text}")
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"배치 다운로드 중 네트워크 오류 발생: {str(e)}")
        except json.JSONDecodeError:
            raise Exception("배치 결과를 JSON으로 파싱할 수 없습니다.")

    async def process_document(self, polling_interval: int = 5, timeout: int = 3600):
        """전체 문서 처리 프로세스를 관리합니다."""
        try:
            # 문서 제출
            await self.submit_document()
            start_time = time.time()
            self.batch_results = []
            
            while True:
                # 타임아웃 체크
                if time.time() - start_time > timeout:
                    raise TimeoutError("문서 처리 시간이 초과되었습니다.")
                
                # 상태 확인
                status = await self.check_status()
                print(f"처리 진행률: {self.completed_pages}/{self.total_pages} 페이지")
                
                if status["status"] == "completed":
                    # 배치를 순차적으로 처리
                    for batch in status["batches"]:
                        if batch["status"] == "completed":
                            # 최대 3번까지 재시도
                            for attempt in range(3):
                                try:
                                    result = await self.download_batch_result(batch)
                                    if result:
                                        self.batch_results.append(result)
                                        break
                                except Exception as e:
                                    if attempt == 2:  # 마지막 시도였다면
                                        print(f"배치 {batch['id']} 다운로드 실패 (3회 시도): {str(e)}")
                                        raise
                                    print(f"배치 {batch['id']} 다운로드 재시도 중... ({attempt + 1}/3)")
                                    await asyncio.sleep(1)  # 잠시 대기 후 재시도
                    
                    if not self.batch_results:
                        raise Exception("배치 결과를 다운로드할 수 없습니다.")
                    
                    # 결과 병합
                    return self.merge_batch_results()
                
                elif status["status"] == "failed":
                    raise Exception(f"문서 처리 실패: {status.get('failure_message', '알 수 없는 오류')}")
                
                # 대기
                await asyncio.sleep(polling_interval)
                
        except Exception as e:
            print(f"문서 처리 중 오류 발생: {str(e)}")
            raise

    def merge_batch_results(self):
        """배치 결과들을 하나의 결과로 병합하고 ID를 순차적으로 재할당합니다."""
        if not self.batch_results:
            return {}
        
        merged = {
            "api": self.batch_results[0]["api"],
            "content": {
                "markdown": "",
                "text": ""

            },
            "elements": [],
            "model": self.batch_results[0]["model"],
            "usage": {"pages": 0}
        }
        
        current_id = 0
        id_mapping = {}  # 이전 ID와 새로운 ID의 매핑을 저장
        
        # 모든 배치의 elements를 순회하면서 ID 재할당
        for result in self.batch_results:
            if "elements" in result:
                for element in result["elements"]:
                    old_id = element["id"]
                    element["id"] = current_id
                    id_mapping[str(old_id)] = str(current_id)
                    current_id += 1
                merged["elements"].extend(result["elements"])
        
        # 마크다운 내용 병합
        for result in self.batch_results:
            content = result.get("content", {})
            merged["content"]["text"] += content.get("text", "")
            merged["content"]["markdown"] += content.get("markdown", "")
            merged["usage"]["pages"] += result.get("usage", {}).get("pages", 0)
        
        return merged

    async def save_to_json(self, output_filename: str = None):
        """처리 결과를 JSON 파일로 저장합니다."""
        try:
            result = await self.process_document()
            
            if not output_filename:
                now = datetime.now()
                output_filename = f'output_{now.strftime("%Y%m%d_%H%M%S")}.json'
            
            with open(output_filename, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=4)
            
            print(f"결과가 {output_filename}에 저장되었습니다.")
            
        except Exception as e:
            print(f"결과 저장 중 오류 발생: {str(e)}")
            raise

async def process_file(filename: str):
    """단일 파일을 처리합니다."""
    parser = AsyncDocumentParser(filename)
    await parser.save_to_json()

async def main():
    # 처리할 파일 목록
    files = [
        "./data/pdf/연말정산-1-14.pdf"
    ]
    
    # 모든 파일 처리
    tasks = [process_file(file) for file in files]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())