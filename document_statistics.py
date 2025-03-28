import json
import os
import pandas as pd
import matplotlib.pyplot as plt
import re
from collections import Counter, defaultdict
import numpy as np
from typing import Dict, List, Any, Tuple

class DocumentStatistics:
    """문서 통계 추출 및 시각화를 담당하는 클래스"""
    
    def __init__(self, json_file_path: str):
        """
        Args:
            json_file_path (str): 처리할 JSON 파일 경로
        """
        self.json_file_path = json_file_path
        self.document_data = self._load_json_file(json_file_path)
        self.elements = self.document_data.get('elements', [])
        self.stats = {}
        
    def _load_json_file(self, file_path: str) -> Dict:
        """JSON 파일을 로드하는 메서드"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"JSON 파일 로드 중 오류: {str(e)}")
            return {}
            
    def extract_basic_statistics(self) -> Dict[str, Any]:
        """기본 통계 정보 추출"""
        if not self.elements:
            return {"error": "유효한 요소가 없습니다"}
            
        # 페이지 수 계산
        page_numbers = [elem.get('page', 0) for elem in self.elements]
        total_pages = max(page_numbers) if page_numbers else 0
        
        # 요소 유형별 개수 계산
        element_types = Counter([elem.get('type', 'unknown') for elem in self.elements])
        
        # 텍스트 길이 분석
        text_lengths = []
        for elem in self.elements:
            content = elem.get('content', {})
            text = content.get('text', '') or content.get('markdown', '')
            if text:
                text_lengths.append(len(text))
        
        avg_text_length = sum(text_lengths) / len(text_lengths) if text_lengths else 0
        
        # 결과 저장
        self.stats['basic'] = {
            "total_elements": len(self.elements),
            "total_pages": total_pages,
            "element_types": dict(element_types),
            "avg_text_length": avg_text_length,
            "min_text_length": min(text_lengths) if text_lengths else 0,
            "max_text_length": max(text_lengths) if text_lengths else 0,
        }
        
        return self.stats['basic']
    
    def extract_content_statistics(self) -> Dict[str, Any]:
        """문서 콘텐츠 관련 통계 추출"""
        if not self.elements:
            return {"error": "유효한 요소가 없습니다"}
            
        # 전체 텍스트 추출
        all_text = ""
        for elem in self.elements:
            content = elem.get('content', {})
            text = content.get('text', '') or content.get('markdown', '')
            all_text += " " + text
            
        # 단어 빈도 분석 (한글 단어만)
        words = re.findall(r'[가-힣]+', all_text)
        word_counts = Counter(words)
        top_words = word_counts.most_common(20)
        
        # 특수 패턴 분석 (예: 연도, 금액 패턴)
        year_pattern = re.compile(r'\b\d{4}년\b')
        years = year_pattern.findall(all_text)
        year_counts = Counter(years)
        
        # 금액 패턴
        amount_pattern = re.compile(r'\d+(?:,\d{3})*(?:\.\d+)?\s*(?:원|만원|억원|천원)')
        amounts = amount_pattern.findall(all_text)
        
        # 페이지별 단어 수
        page_word_counts = defaultdict(int)
        for elem in self.elements:
            page = elem.get('page', 0)
            content = elem.get('content', {})
            text = content.get('text', '') or content.get('markdown', '')
            words_in_elem = re.findall(r'\b\w+\b', text)
            page_word_counts[page] += len(words_in_elem)
            
        # 결과 저장
        self.stats['content'] = {
            "total_characters": len(all_text),
            "total_words": len(re.findall(r'\b\w+\b', all_text)),
            "top_words": top_words,
            "year_mentions": dict(year_counts),
            "amount_mentions": amounts[:20] if len(amounts) > 20 else amounts,
            "page_word_counts": dict(page_word_counts)
        }
        
        return self.stats['content']
    
    def extract_document_structure(self) -> Dict[str, Any]:
        """문서 구조 분석 통계"""
        if not self.elements:
            return {"error": "유효한 요소가 없습니다"}
            
        # 제목(heading) 요소 식별
        headings = [elem for elem in self.elements if elem.get('type') == 'heading']
        
        # 페이지별 요소 수
        elements_per_page = defaultdict(int)
        for elem in self.elements:
            page = elem.get('page', 0)
            elements_per_page[page] += 1
        
        # 섹션 분석 (제목 사이의 콘텐츠를 하나의 섹션으로 간주)
        sections = []
        if headings:
            headings.sort(key=lambda x: (x.get('page', 0), x.get('id', '')))
            for i in range(len(headings)):
                heading = headings[i]
                section_title = ""
                content = heading.get('content', {})
                if content:
                    section_title = content.get('text', '') or content.get('markdown', '')
                    
                # 현재 제목과 다음 제목 사이의 요소 수
                start_idx = self.elements.index(heading)
                end_idx = len(self.elements)
                if i < len(headings) - 1:
                    next_heading = headings[i + 1]
                    end_idx = self.elements.index(next_heading)
                
                section_length = end_idx - start_idx - 1
                
                sections.append({
                    "title": section_title,
                    "page": heading.get('page', 0),
                    "elements_count": section_length
                })
        
        # 결과 저장
        self.stats['structure'] = {
            "heading_count": len(headings),
            "elements_per_page": dict(elements_per_page),
            "sections": sections
        }
        
        return self.stats['structure']
    
    def extract_layout_statistics(self) -> Dict[str, Any]:
        """레이아웃 관련 통계 추출"""
        if not self.elements:
            return {"error": "유효한 요소가 없습니다"}
            
        # 페이지별 요소의 위치 분포
        positions_by_page = defaultdict(list)
        
        for elem in self.elements:
            page = elem.get('page', 0)
            coords = elem.get('coordinates', [])
            if coords:
                # 요소의 중앙 위치 계산
                x_values = [c.get('x', 0) for c in coords]
                y_values = [c.get('y', 0) for c in coords]
                
                if x_values and y_values:
                    center_x = sum(x_values) / len(x_values)
                    center_y = sum(y_values) / len(y_values)
                    positions_by_page[page].append((center_x, center_y))
        
        # 분포 통계
        position_stats = {}
        for page, positions in positions_by_page.items():
            if positions:
                x_coords = [pos[0] for pos in positions]
                y_coords = [pos[1] for pos in positions]
                
                position_stats[page] = {
                    "x_mean": sum(x_coords) / len(x_coords),
                    "y_mean": sum(y_coords) / len(y_coords),
                    "x_std": np.std(x_coords) if len(x_coords) > 1 else 0,
                    "y_std": np.std(y_coords) if len(y_coords) > 1 else 0,
                    "element_count": len(positions)
                }
        
        # 결과 저장
        self.stats['layout'] = {
            "position_stats": position_stats
        }
        
        return self.stats['layout']
    
    def generate_all_statistics(self) -> Dict[str, Any]:
        """모든 통계 정보 생성"""
        self.extract_basic_statistics()
        self.extract_content_statistics()
        self.extract_document_structure()
        self.extract_layout_statistics()
        
        return self.stats
    
    def save_statistics(self, output_path: str = None) -> str:
        """통계 정보를 JSON 파일로 저장"""
        if not self.stats:
            self.generate_all_statistics()
            
        if output_path is None:
            base_name = os.path.splitext(os.path.basename(self.json_file_path))[0]
            output_path = f"{base_name}_statistics.json"
            
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.stats, f, ensure_ascii=False, indent=2)
            
        print(f"통계 정보가 {output_path}에 저장되었습니다.")
        return output_path
    
    def create_visualizations(self, output_dir: str = 'stats_visualizations'):
        """통계 시각화 생성"""
        if not self.stats:
            self.generate_all_statistics()
            
        # 출력 디렉토리 생성
        os.makedirs(output_dir, exist_ok=True)
        
        # 요소 유형 분포 시각화
        if 'basic' in self.stats and 'element_types' in self.stats['basic']:
            self._create_element_types_chart(self.stats['basic']['element_types'], output_dir)
        
        # 페이지별 단어 수 시각화
        if 'content' in self.stats and 'page_word_counts' in self.stats['content']:
            self._create_words_per_page_chart(self.stats['content']['page_word_counts'], output_dir)
            
        # 상위 단어 빈도 시각화
        if 'content' in self.stats and 'top_words' in self.stats['content']:
            self._create_top_words_chart(self.stats['content']['top_words'], output_dir)
            
        # 섹션 길이 시각화
        if 'structure' in self.stats and 'sections' in self.stats['structure']:
            self._create_section_length_chart(self.stats['structure']['sections'], output_dir)
            
        print(f"시각화 파일이 {output_dir} 디렉토리에 저장되었습니다.")
        
    def _create_element_types_chart(self, element_types: Dict[str, int], output_dir: str):
        """요소 유형 분포 차트 생성"""
        plt.figure(figsize=(10, 6))
        types = list(element_types.keys())
        counts = list(element_types.values())
        
        plt.bar(types, counts, color='skyblue')
        plt.title('문서 요소 유형 분포')
        plt.xlabel('요소 유형')
        plt.ylabel('개수')
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        plt.savefig(os.path.join(output_dir, 'element_types.png'))
        plt.close()
        
    def _create_words_per_page_chart(self, page_word_counts: Dict[int, int], output_dir: str):
        """페이지별 단어 수 차트 생성"""
        plt.figure(figsize=(12, 6))
        pages = sorted(page_word_counts.keys())
        counts = [page_word_counts[page] for page in pages]
        
        plt.plot(pages, counts, marker='o', linestyle='-', color='green')
        plt.title('페이지별 단어 수')
        plt.xlabel('페이지 번호')
        plt.ylabel('단어 수')
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.tight_layout()
        
        plt.savefig(os.path.join(output_dir, 'words_per_page.png'))
        plt.close()
        
    def _create_top_words_chart(self, top_words: List[Tuple[str, int]], output_dir: str):
        """상위 단어 빈도 차트 생성"""
        plt.figure(figsize=(12, 8))
        words = [word for word, count in top_words]
        counts = [count for word, count in top_words]
        
        y_pos = range(len(words))
        plt.barh(y_pos, counts, color='coral')
        plt.yticks(y_pos, words)
        plt.title('가장 많이 사용된 단어')
        plt.xlabel('빈도')
        plt.tight_layout()
        
        plt.savefig(os.path.join(output_dir, 'top_words.png'))
        plt.close()
        
    def _create_section_length_chart(self, sections: List[Dict], output_dir: str):
        """섹션 길이 차트 생성"""
        if not sections:
            return
            
        plt.figure(figsize=(14, 8))
        titles = [f"섹션 {i+1}" for i in range(len(sections))]
        lengths = [section['elements_count'] for section in sections]
        
        plt.bar(titles, lengths, color='lightblue')
        plt.title('섹션별 요소 수')
        plt.xlabel('섹션')
        plt.ylabel('요소 수')
        plt.xticks(rotation=90)
        plt.tight_layout()
        
        plt.savefig(os.path.join(output_dir, 'section_lengths.png'))
        plt.close()

def main():
    """메인 실행 함수"""
    # 현재 디렉토리에서 처리할 JSON 파일 선택
    json_files = [f for f in os.listdir('.') if f.endswith('.json')]
    output_files = [f for f in os.listdir('output') if f.endswith('.json')]
    
    all_files = json_files + [os.path.join('output', f) for f in output_files]
    
    if not all_files:
        print("디렉토리에 JSON 파일이 없습니다.")
        return
        
    print("통계를 생성할 JSON 파일을 선택하세요:")
    for i, json_file in enumerate(all_files):
        print(f"{i+1}. {json_file}")
    
    try:
        selection = int(input("번호 선택: ")) - 1
        if 0 <= selection < len(all_files):
            input_file = all_files[selection]
            
            print(f"'{input_file}'에 대한 통계를 생성합니다...")
            
            # 통계 분석 실행
            stats = DocumentStatistics(input_file)
            stats.generate_all_statistics()
            output_path = stats.save_statistics()
            
            # 시각화 생성
            stats.create_visualizations()
            
            print(f"통계 생성 완료. 결과는 {output_path}에 저장되었습니다.")
        else:
            print("올바른 번호를 선택하세요.")
    except ValueError:
        print("숫자를 입력하세요.")

if __name__ == "__main__":
    main() 