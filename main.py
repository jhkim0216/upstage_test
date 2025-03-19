# pip install requests
 
import requests
import json
api_key = "up_ExeugkiSIRUEIe6asWi1wDKaScVzQ"  # ex: up_xxxYYYzzzAAAbbbCCC
filename = "모니터1~2p.pdf"         # ex: ./image.png
 
url = "https://api.upstage.ai/v1/document-ai/document-parse"
headers = {"Authorization": f"Bearer {api_key}"}
 
files = {"document": open(filename, "rb")}
data = {"ocr": "force", "base64_encoding": "['table']", "model": "document-parse"}
response = requests.post(url, headers=headers, files=files, data=data)

# 응답 데이터 가져오기
response_data = response.json()
print(response_data)

# JSON 파일 저장
with open('output.json', 'w', encoding='utf-8') as f:
    json.dump(response_data, f, ensure_ascii=False, indent=4)

# HTML 콘텐츠 추출 및 저장
html_content = response_data.get('content', {}).get('html', '')

# HTML 기본 구조 만들기
full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>문서 파싱 결과</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
        }}
    </style>
</head>
<body>
{html_content}
</body>
</html>
"""

# HTML 파일로 저장
with open('document_result.html', 'w', encoding='utf-8') as f:
    f.write(full_html)

print("JSON 및 HTML 파일 생성 완료")
