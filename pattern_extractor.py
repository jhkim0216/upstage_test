import json
import re
import os
import pandas as pd
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Any

class PatternExtractor:
    """문서에서 다양한 패턴을 추출하는 클래스"""
    
    def __init__(self, json_file_path: str):
        """
        Args:
            json_file_path (str): 처리할 JSON 파일 경로
        """
        self.json_file_path = json_file_path
        self.document_data = self._load_json_file(json_file_path)
        self.elements = self.document_data.get('elements', [])
        self.extracted_patterns = {}
        
    def _load_json_file(self, file_path: str) -> Dict:
        """JSON 파일을 로드하는 메서드"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"JSON 파일 로드 중 오류: {str(e)}")
            return {}
    
    def extract_all_patterns(self) -> Dict[str, Any]:
        """모든 패턴 추출 실행"""
        self.extract_year_mentions()
        self.extract_financial_amounts()
        self.extract_legal_references()
        self.extract_date_expressions()
        self.extract_percentage_values()
        self.extract_contact_information()
        self.extract_organization_names()
        self.extract_bullet_points()
        
        return self.extracted_patterns
    
    def extract_year_mentions(self) -> Dict[str, int]:
        """년도 언급 추출"""
        if not self.elements:
            return {}
            
        # 모든 텍스트 데이터 결합
        all_text = self._get_all_text()
        
        # 연도 패턴 검색
        year_pattern = re.compile(r'(?:19|20)\d{2}[\s]*년')
        year_mentions = year_pattern.findall(all_text)
        
        # 결과 정리
        year_counts = Counter(year_mentions)
        
        # 결과 저장
        self.extracted_patterns['year_mentions'] = dict(year_counts)
        
        return self.extracted_patterns['year_mentions']
    
    def extract_financial_amounts(self) -> Dict[str, List[str]]:
        """금액 표현 추출"""
        if not self.elements:
            return {}
            
        all_text = self._get_all_text()
        
        # 다양한 금액 패턴 검색
        amount_patterns = {
            '원': re.compile(r'\d{1,3}(?:,\d{3})*(?:\.\d+)?\s*원'),
            '만원': re.compile(r'\d{1,3}(?:,\d{3})*(?:\.\d+)?\s*만원'),
            '억원': re.compile(r'\d{1,3}(?:,\d{3})*(?:\.\d+)?\s*억원'),
            '조원': re.compile(r'\d{1,3}(?:,\d{3})*(?:\.\d+)?\s*조원'),
            '천원': re.compile(r'\d{1,3}(?:,\d{3})*(?:\.\d+)?\s*천원')
        }
        
        amounts = {}
        for unit, pattern in amount_patterns.items():
            found = pattern.findall(all_text)
            if found:
                amounts[unit] = found
        
        # 결과 저장
        self.extracted_patterns['financial_amounts'] = amounts
        
        return self.extracted_patterns['financial_amounts']
    
    def extract_legal_references(self) -> Dict[str, List[str]]:
        """법률 참조 추출"""
        if not self.elements:
            return {}
            
        all_text = self._get_all_text()
        
        # 법률 참조 패턴
        law_patterns = {
            '법률명': re.compile(r'(?:「|제|｢)[^」｣]+(?:법|법률|령|규칙|고시|예규)(?:」|｣|제\s*\d+\s*조)'),
            '조항': re.compile(r'제\s*\d+\s*조(?:\s*제\s*\d+\s*항)?(?:\s*제\s*\d+\s*호)?'),
            '시행령': re.compile(r'[가-힣]+\s*시행령'),
            '시행규칙': re.compile(r'[가-힣]+\s*시행규칙')
        }
        
        legal_refs = {}
        for ref_type, pattern in law_patterns.items():
            found = pattern.findall(all_text)
            if found:
                legal_refs[ref_type] = list(set(found))  # 중복 제거
        
        # 결과 저장
        self.extracted_patterns['legal_references'] = legal_refs
        
        return self.extracted_patterns['legal_references']
    
    def extract_date_expressions(self) -> Dict[str, List[str]]:
        """날짜 표현 추출"""
        if not self.elements:
            return {}
            
        all_text = self._get_all_text()
        
        # 날짜 패턴
        date_patterns = {
            '연월일': re.compile(r'(?:19|20)\d{2}[\s]*년[\s]*\d{1,2}[\s]*월[\s]*\d{1,2}[\s]*일'),
            '연월': re.compile(r'(?:19|20)\d{2}[\s]*년[\s]*\d{1,2}[\s]*월(?!\d)'),
            '월일': re.compile(r'(?<!\d)\d{1,2}[\s]*월[\s]*\d{1,2}[\s]*일'),
            '기간': re.compile(r'(?:19|20)\d{2}[\s]*년[\s]*\d{1,2}[\s]*월[\s]*\d{1,2}[\s]*일\s*(?:~|부터|까지)\s*(?:19|20)\d{2}[\s]*년[\s]*\d{1,2}[\s]*월[\s]*\d{1,2}[\s]*일')
        }
        
        dates = {}
        for date_type, pattern in date_patterns.items():
            found = pattern.findall(all_text)
            if found:
                dates[date_type] = list(set(found))  # 중복 제거
        
        # 결과 저장
        self.extracted_patterns['date_expressions'] = dates
        
        return self.extracted_patterns['date_expressions']
    
    def extract_percentage_values(self) -> List[str]:
        """퍼센트 값 추출"""
        if not self.elements:
            return []
            
        all_text = self._get_all_text()
        
        # 퍼센트 패턴
        percent_pattern = re.compile(r'\d+(?:\.\d+)?[\s]*%')
        percentages = percent_pattern.findall(all_text)
        
        # 결과 저장
        self.extracted_patterns['percentage_values'] = percentages
        
        return self.extracted_patterns['percentage_values']
    
    def extract_contact_information(self) -> Dict[str, List[str]]:
        """연락처 정보 추출"""
        if not self.elements:
            return {}
            
        all_text = self._get_all_text()
        
        # 연락처 패턴
        contact_patterns = {
            '전화번호': re.compile(r'(?:\(?\d{2,3}\)?[-\s.]?)?(?:\d{3,4}[-\s.]?\d{4})'),
            '이메일': re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'),
            '웹사이트': re.compile(r'(?:https?://)?(?:www\.)?[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+(?:/[a-zA-Z0-9-._~:/?#[\]@!$&\'()*+,;=]*)?')
        }
        
        contacts = {}
        for contact_type, pattern in contact_patterns.items():
            found = pattern.findall(all_text)
            if found:
                contacts[contact_type] = list(set(found))  # 중복 제거
        
        # 결과 저장
        self.extracted_patterns['contact_information'] = contacts
        
        return self.extracted_patterns['contact_information']
    
    def extract_organization_names(self) -> List[str]:
        """기관명 추출"""
        if not self.elements:
            return []
            
        all_text = self._get_all_text()
        
        # 기관명 패턴
        org_patterns = [
            re.compile(r'[가-힣]+(?:부|청|위원회|공단|공사|센터|진흥원|재단|연구소|협회)'),
            re.compile(r'(?:재단법인|사단법인)\s[가-힣]+')
        ]
        
        organizations = []
        for pattern in org_patterns:
            found = pattern.findall(all_text)
            organizations.extend(found)
        
        # 중복 제거
        organizations = list(set(organizations))
        
        # 결과 저장
        self.extracted_patterns['organization_names'] = organizations
        
        return self.extracted_patterns['organization_names']
    
    def extract_bullet_points(self) -> Dict[str, List[str]]:
        """글머리 기호 항목 추출"""
        if not self.elements:
            return {}
            
        bullet_patterns = {
            '숫자_항목': re.compile(r'^\s*\d+\.[\s]+'),
            '영문_항목': re.compile(r'^\s*[A-Za-z]\.[\s]+'),
            '특수문자_항목': re.compile(r'^\s*[•◆■□○●★※▶-][\s]+')
        }
        
        bullet_points = defaultdict(list)
        
        # 각 요소의 텍스트 검사
        for elem in self.elements:
            content = elem.get('content', {})
            text = content.get('text', '') or content.get('markdown', '')
            if not text:
                continue
                
            # 줄 단위로 처리
            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                # 각 패턴 검사
                for bullet_type, pattern in bullet_patterns.items():
                    if pattern.match(line):
                        # 패턴 제거 후 내용만 저장
                        content_only = pattern.sub('', line).strip()
                        if content_only:
                            bullet_points[bullet_type].append(content_only)
        
        # 결과 저장
        self.extracted_patterns['bullet_points'] = dict(bullet_points)
        
        return self.extracted_patterns['bullet_points']
    
    def _get_all_text(self) -> str:
        """모든 텍스트 콘텐츠 추출"""
        all_text = ""
        for elem in self.elements:
            content = elem.get('content', {})
            text = content.get('text', '') or content.get('markdown', '')
            if text:
                all_text += " " + text
        return all_text
    
    def save_to_json(self, output_path: str = None) -> str:
        """추출된 패턴을 JSON 파일로 저장"""
        if not self.extracted_patterns:
            self.extract_all_patterns()
            
        if output_path is None:
            base_name = os.path.splitext(os.path.basename(self.json_file_path))[0]
            output_path = f"{base_name}_patterns.json"
            
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.extracted_patterns, f, ensure_ascii=False, indent=2)
            
        print(f"추출된 패턴이 {output_path}에 저장되었습니다.")
        return output_path
    
    def save_to_excel(self, output_path: str = None) -> str:
        """추출된 패턴을 Excel 파일로 저장"""
        if not self.extracted_patterns:
            self.extract_all_patterns()
            
        if output_path is None:
            base_name = os.path.splitext(os.path.basename(self.json_file_path))[0]
            output_path = f"{base_name}_patterns.xlsx"
        
        # 결과를 데이터프레임으로 변환
        dfs = {}
        
        # 연도 언급 시트
        if 'year_mentions' in self.extracted_patterns:
            year_data = []
            for year, count in self.extracted_patterns['year_mentions'].items():
                year_data.append({'연도': year, '언급 횟수': count})
            if year_data:
                dfs['연도_언급'] = pd.DataFrame(year_data)
        
        # 금액 표현 시트
        if 'financial_amounts' in self.extracted_patterns:
            amount_data = []
            for unit, amounts in self.extracted_patterns['financial_amounts'].items():
                for amount in amounts:
                    amount_data.append({'단위': unit, '금액 표현': amount})
            if amount_data:
                dfs['금액_표현'] = pd.DataFrame(amount_data)
        
        # 법률 참조 시트
        if 'legal_references' in self.extracted_patterns:
            legal_data = []
            for ref_type, refs in self.extracted_patterns['legal_references'].items():
                for ref in refs:
                    legal_data.append({'참조 유형': ref_type, '법률 참조': ref})
            if legal_data:
                dfs['법률_참조'] = pd.DataFrame(legal_data)
        
        # 날짜 표현 시트
        if 'date_expressions' in self.extracted_patterns:
            date_data = []
            for date_type, dates in self.extracted_patterns['date_expressions'].items():
                for date in dates:
                    date_data.append({'날짜 유형': date_type, '날짜 표현': date})
            if date_data:
                dfs['날짜_표현'] = pd.DataFrame(date_data)
        
        # 퍼센트 값 시트
        if 'percentage_values' in self.extracted_patterns:
            percent_data = [{'퍼센트 값': p} for p in self.extracted_patterns['percentage_values']]
            if percent_data:
                dfs['퍼센트_값'] = pd.DataFrame(percent_data)
        
        # 연락처 정보 시트
        if 'contact_information' in self.extracted_patterns:
            contact_data = []
            for contact_type, contacts in self.extracted_patterns['contact_information'].items():
                for contact in contacts:
                    contact_data.append({'연락처 유형': contact_type, '연락처': contact})
            if contact_data:
                dfs['연락처_정보'] = pd.DataFrame(contact_data)
        
        # 기관명 시트
        if 'organization_names' in self.extracted_patterns:
            org_data = [{'기관명': org} for org in self.extracted_patterns['organization_names']]
            if org_data:
                dfs['기관명'] = pd.DataFrame(org_data)
        
        # 글머리 기호 항목 시트
        if 'bullet_points' in self.extracted_patterns:
            bullet_data = []
            for bullet_type, points in self.extracted_patterns['bullet_points'].items():
                for point in points:
                    bullet_data.append({'글머리 유형': bullet_type, '내용': point})
            if bullet_data:
                dfs['글머리_항목'] = pd.DataFrame(bullet_data)
        
        # Excel 파일로 저장
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            for sheet_name, df in dfs.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        print(f"추출된 패턴이 {output_path}에 저장되었습니다.")
        return output_path

def main():
    """메인 실행 함수"""
    # 현재 디렉토리에서 처리할 JSON 파일 선택
    json_files = [f for f in os.listdir('.') if f.endswith('.json')]
    output_files = [f for f in os.listdir('output') if f.endswith('.json')]
    
    all_files = json_files + [os.path.join('output', f) for f in output_files]
    
    if not all_files:
        print("디렉토리에 JSON 파일이 없습니다.")
        return
        
    print("패턴을 추출할 JSON 파일을 선택하세요:")
    for i, json_file in enumerate(all_files):
        print(f"{i+1}. {json_file}")
    
    try:
        selection = int(input("번호 선택: ")) - 1
        if 0 <= selection < len(all_files):
            input_file = all_files[selection]
            
            print(f"'{input_file}'에서 패턴을 추출합니다...")
            
            # 패턴 추출 실행
            extractor = PatternExtractor(input_file)
            extractor.extract_all_patterns()
            
            # 결과 저장 형식 선택
            print("결과 저장 형식을 선택하세요:")
            print("1. JSON")
            print("2. Excel")
            print("3. 둘 다")
            
            format_selection = int(input("번호 선택: "))
            
            if format_selection == 1 or format_selection == 3:
                extractor.save_to_json()
                
            if format_selection == 2 or format_selection == 3:
                extractor.save_to_excel()
                
            print("패턴 추출이 완료되었습니다.")
        else:
            print("올바른 번호를 선택하세요.")
    except ValueError:
        print("숫자를 입력하세요.")

if __name__ == "__main__":
    main() 