import json
import os
import re
from collections import defaultdict
from typing import Dict, List, Any, Tuple, Optional, Set
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

class DocumentStructureAnalyzer:
    """문서 구조 분석 및 목차 추출을 위한 클래스"""
    
    def __init__(self, json_file_path: str):
        """
        Args:
            json_file_path (str): 처리할 JSON 파일 경로
        """
        self.json_file_path = json_file_path
        self.document_data = self._load_json_file(json_file_path)
        self.elements = self.document_data.get('elements', [])
        self.structure_data = {}
        self.toc_tree = {}
        
    def _load_json_file(self, file_path: str) -> Dict:
        """JSON 파일을 로드하는 메서드"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"JSON 파일 로드 중 오류: {str(e)}")
            return {}
    
    def analyze_structure(self) -> Dict[str, Any]:
        """문서 구조 분석 실행"""
        if not self.elements:
            return {"error": "유효한 요소가 없습니다"}
            
        # 기본 통계
        self._extract_basic_structure()
        
        # 제목 계층 추출
        self._extract_heading_hierarchy()
        
        # 섹션 내용 분석
        self._analyze_section_contents()
        
        # 참조 및 링크 분석
        self._analyze_references()
        
        return self.structure_data
    
    def _extract_basic_structure(self) -> None:
        """기본 문서 구조 통계"""
        # 요소 유형 분포
        element_types = defaultdict(int)
        for elem in self.elements:
            elem_type = elem.get('type', 'unknown')
            element_types[elem_type] += 1
            
        # 페이지별 요소 수
        elements_per_page = defaultdict(int)
        for elem in self.elements:
            page = elem.get('page', 0)
            elements_per_page[page] += 1
            
        # 결과 저장
        self.structure_data['basic'] = {
            "total_elements": len(self.elements),
            "element_types": dict(element_types),
            "elements_per_page": dict(elements_per_page),
            "max_page": max(elements_per_page.keys()) if elements_per_page else 0
        }
    
    def _extract_heading_hierarchy(self) -> None:
        """제목 계층 구조 추출"""
        # 제목(heading) 요소 추출
        headings = [elem for elem in self.elements if elem.get('type') == 'heading']
        
        if not headings:
            # category 필드를 기반으로 추정
            headings = [elem for elem in self.elements if 
                       elem.get('category', '').startswith('heading')]
            
        if not headings:
            # 패턴 기반 추정
            heading_patterns = [
                r'^\s*\d+\.[\s]+[가-힣A-Za-z]',  # 숫자로 시작하는 패턴
                r'^\s*제\s*\d+\s*[장절항목]',  # 제X장/절 패턴
                r'^\s*[IVXLCDM]+\.[\s]+[가-힣A-Za-z]',  # 로마 숫자 패턴
                r'^\s*[가-힣]\.\s+',  # 한글 글자 + 점 패턴
                r'^\s*[A-Z]\.\s+'  # 영문 대문자 + 점 패턴
            ]
            
            for elem in self.elements:
                content = elem.get('content', {})
                text = content.get('text', '') or content.get('markdown', '')
                if not text:
                    continue
                    
                for pattern in heading_patterns:
                    if re.match(pattern, text):
                        headings.append(elem)
                        break
        
        if not headings:
            self.structure_data['headings'] = {
                "count": 0,
                "hierarchy": [],
                "levels": {}
            }
            return
            
        # 페이지 및 위치 기준으로 정렬
        headings.sort(key=lambda x: (x.get('page', 0), self._get_y_position(x)))
        
        # 제목 레벨 추정
        heading_levels = self._estimate_heading_levels(headings)
        
        # 계층 구조 구성
        hierarchy = []
        hierarchy_map = {}  # id -> hierarchy node
        
        for heading in headings:
            heading_id = heading.get('id', '')
            level = heading_levels.get(heading_id, 1)
            content = heading.get('content', {})
            text = content.get('text', '') or content.get('markdown', '')
            
            node = {
                "id": heading_id,
                "level": level,
                "text": text,
                "page": heading.get('page', 0),
                "children": []
            }
            
            # 상위 제목 찾기
            if level == 1:
                hierarchy.append(node)
            else:
                # 현재보다 낮은 레벨의 가장 최근 제목 찾기
                parent = None
                for h in reversed(headings):
                    h_id = h.get('id', '')
                    if h_id == heading_id:
                        break
                    if heading_levels.get(h_id, 1) < level:
                        parent = hierarchy_map.get(h_id)
                        if parent:
                            break
                
                if parent:
                    parent["children"].append(node)
                else:
                    # 부모를 찾지 못하면 최상위 레벨에 추가
                    hierarchy.append(node)
            
            hierarchy_map[heading_id] = node
            
        # 레벨별 제목 수
        levels_count = defaultdict(int)
        for _, level in heading_levels.items():
            levels_count[level] += 1
        
        # 결과 저장
        self.structure_data['headings'] = {
            "count": len(headings),
            "hierarchy": hierarchy,
            "levels": dict(levels_count)
        }
        
        # 목차 트리 저장
        self.toc_tree = hierarchy
    
    def _estimate_heading_levels(self, headings: List[Dict]) -> Dict[str, int]:
        """제목의 레벨 추정"""
        heading_levels = {}
        
        # 패턴 기반 레벨 추정
        level_patterns = [
            (re.compile(r'^\s*제\s*\d+\s*장'), 1),  # 제X장
            (re.compile(r'^\s*제\s*\d+\s*절'), 2),  # 제X절
            (re.compile(r'^\s*제\s*\d+\s*항'), 3),  # 제X항
            (re.compile(r'^\s*제\s*\d+\s*목'), 4),  # 제X목
            (re.compile(r'^\s*\d+\.[\s]+(?![0-9])'), 1),  # X. (다음에 숫자가 없는 경우)
            (re.compile(r'^\s*\d+\.\d+\.[\s]+'), 2),  # X.Y.
            (re.compile(r'^\s*\d+\.\d+\.\d+\.[\s]+'), 3),  # X.Y.Z.
            (re.compile(r'^\s*[IVXLCDM]+\.[\s]+'), 1),  # 로마 숫자
            (re.compile(r'^\s*[A-Z]\.[\s]+'), 2),  # 영문 대문자
            (re.compile(r'^\s*[a-z]\.[\s]+'), 3),  # 영문 소문자
            (re.compile(r'^\s*[가-힣]\.[\s]+'), 2),  # 한글 글자
        ]
        
        for heading in headings:
            heading_id = heading.get('id', '')
            content = heading.get('content', {})
            text = content.get('text', '') or content.get('markdown', '')
            
            # 기본 레벨
            level = 1
            
            # 패턴 기반 레벨 결정
            for pattern, lvl in level_patterns:
                if pattern.match(text):
                    level = lvl
                    break
            
            # 글꼴 크기 기반 레벨 결정
            spans = self._get_spans(heading)
            if spans:
                avg_font_size = self._get_average_font_size(spans)
                if avg_font_size:
                    # 크기가 클수록 레벨이 낮음 (1이 최상위)
                    size_levels = {
                        s: i+1 for i, s in enumerate(
                            sorted(set(self._get_average_font_size(self._get_spans(h)) 
                                      for h in headings if self._get_spans(h)), reverse=True)
                        )
                    }
                    size_level = size_levels.get(avg_font_size, 1)
                    
                    # 패턴과 크기 중 더 신뢰할 수 있는 방법 선택
                    # 여기서는 간단하게 두 정보를 모두 고려
                    level = min(level, size_level)
            
            heading_levels[heading_id] = level
            
        return heading_levels
    
    def _analyze_section_contents(self) -> None:
        """섹션 내용 분석"""
        # 제목 요소 추출
        headings = [elem for elem in self.elements if elem.get('type') == 'heading']
        
        if not headings:
            self.structure_data['sections'] = []
            return
            
        # 페이지 및 위치 기준으로 정렬
        headings.sort(key=lambda x: (x.get('page', 0), self._get_y_position(x)))
        
        # 섹션 분석
        sections = []
        
        for i, heading in enumerate(headings):
            heading_id = heading.get('id', '')
            content = heading.get('content', {})
            heading_text = content.get('text', '') or content.get('markdown', '')
            page = heading.get('page', 0)
            
            # 섹션의 시작과 끝 인덱스 결정
            start_idx = self.elements.index(heading) + 1
            end_idx = len(self.elements)
            
            if i < len(headings) - 1:
                next_heading = headings[i + 1]
                end_idx = self.elements.index(next_heading)
            
            # 섹션 내용 요소 추출
            section_elements = self.elements[start_idx:end_idx]
            
            # 섹션 분석 
            section_data = {
                "heading": heading_text,
                "page": page,
                "element_count": len(section_elements),
                "paragraph_count": sum(1 for e in section_elements if e.get('type') == 'paragraph'),
                "table_count": sum(1 for e in section_elements if e.get('category', '').startswith('table')),
                "image_count": sum(1 for e in section_elements if e.get('category', '').startswith('image')),
                "list_count": sum(1 for e in section_elements if e.get('category', '').startswith('list')),
                "page_range": self._get_section_page_range(section_elements, page)
            }
            
            sections.append(section_data)
        
        # 결과 저장
        self.structure_data['sections'] = sections
    
    def _analyze_references(self) -> None:
        """문서 내 참조 및 링크 분석"""
        if not self.elements:
            self.structure_data['references'] = {"count": 0}
            return
            
        # 텍스트 모두 가져오기
        all_text = ""
        for elem in self.elements:
            content = elem.get('content', {})
            text = content.get('text', '') or content.get('markdown', '')
            all_text += "\n" + text
        
        # 참조 패턴
        ref_patterns = {
            '페이지_참조': re.compile(r'(?:p\.|page|페이지)[\s]*\d+'),
            '그림_참조': re.compile(r'(?:그림|fig\.|figure)[\s]*\d+'),
            '표_참조': re.compile(r'(?:표|table)[\s]*\d+'),
            '장절_참조': re.compile(r'제[\s]*\d+[\s]*(?:장|절|항|호)'),
            '각주': re.compile(r'[\s]*\[\d+\][\s]*'),
            '별표': re.compile(r'[\s]*\*+[\s]*')
        }
        
        # 참조 추출
        references = {}
        total_count = 0
        
        for ref_type, pattern in ref_patterns.items():
            found = pattern.findall(all_text)
            if found:
                references[ref_type] = {
                    "count": len(found),
                    "examples": found[:5]  # 최대 5개 예시
                }
                total_count += len(found)
        
        # 결과 저장
        self.structure_data['references'] = {
            "count": total_count,
            "types": references
        }
    
    def _get_y_position(self, element: Dict) -> float:
        """요소의 Y 위치 반환"""
        coords = element.get('coordinates', [])
        if coords:
            y_values = [c.get('y', 0) for c in coords]
            return sum(y_values) / len(y_values) if y_values else 0
        return 0
    
    def _get_spans(self, element: Dict) -> List[Dict]:
        """요소의 span 정보 반환"""
        spans = []
        for line in element.get('lines', []):
            if 'spans' in line:
                spans.extend(line['spans'])
        return spans
    
    def _get_average_font_size(self, spans: List[Dict]) -> Optional[float]:
        """span의 평균 글꼴 크기 계산"""
        sizes = [span.get('size', 0) for span in spans if 'size' in span]
        return sum(sizes) / len(sizes) if sizes else None
    
    def _get_section_page_range(self, elements: List[Dict], start_page: int) -> Tuple[int, int]:
        """섹션의 페이지 범위 가져오기"""
        if not elements:
            return (start_page, start_page)
            
        pages = [elem.get('page', start_page) for elem in elements]
        return (start_page, max(pages)) if pages else (start_page, start_page)
    
    def create_toc_tree_visualization(self, output_path: str = None) -> str:
        """목차 트리 시각화"""
        if not self.toc_tree:
            self.analyze_structure()
            
        if not self.toc_tree:
            print("목차 트리를 구성할 수 없습니다.")
            return ""
            
        if output_path is None:
            base_name = os.path.splitext(os.path.basename(self.json_file_path))[0]
            output_path = f"{base_name}_toc_tree.png"
        
        # 그래프 생성
        G = nx.DiGraph()
        
        # 트리 구성
        self._add_nodes_to_graph(G, self.toc_tree, None)
        
        # 레이아웃 결정
        pos = nx.nx_agraph.graphviz_layout(G, prog='dot')
        
        # 그래프 그리기
        plt.figure(figsize=(20, 15))
        nx.draw(G, pos, with_labels=True, node_size=3000, node_color='skyblue', 
               font_size=10, font_family='NanumGothic', arrows=True)
        
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"목차 트리 시각화가 {output_path}에 저장되었습니다.")
        return output_path
    
    def _add_nodes_to_graph(self, G: nx.DiGraph, nodes: List[Dict], parent: Optional[str]) -> None:
        """그래프에 노드 추가 (재귀)"""
        for node in nodes:
            node_id = node['id']
            G.add_node(node_id, label=self._truncate_text(node['text'], 30))
            
            if parent:
                G.add_edge(parent, node_id)
                
            if node['children']:
                self._add_nodes_to_graph(G, node['children'], node_id)
    
    def _truncate_text(self, text: str, max_length: int) -> str:
        """텍스트 길이 제한"""
        text = text.strip()
        return text[:max_length] + '...' if len(text) > max_length else text
    
    def export_structure_to_json(self, output_path: str = None) -> str:
        """구조 정보를 JSON으로 저장"""
        if not self.structure_data:
            self.analyze_structure()
            
        if output_path is None:
            base_name = os.path.splitext(os.path.basename(self.json_file_path))[0]
            output_path = f"{base_name}_structure.json"
            
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.structure_data, f, ensure_ascii=False, indent=2)
            
        print(f"구조 분석 정보가 {output_path}에 저장되었습니다.")
        return output_path
    
    def export_toc_to_markdown(self, output_path: str = None) -> str:
        """목차를 Markdown 형식으로 저장"""
        if not self.toc_tree:
            self.analyze_structure()
            
        if output_path is None:
            base_name = os.path.splitext(os.path.basename(self.json_file_path))[0]
            output_path = f"{base_name}_toc.md"
            
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("# 문서 목차\n\n")
            self._write_toc_markdown(f, self.toc_tree, 0)
            
        print(f"목차가 {output_path}에 저장되었습니다.")
        return output_path
    
    def _write_toc_markdown(self, file, nodes: List[Dict], depth: int) -> None:
        """Markdown 목차 작성 (재귀)"""
        for node in nodes:
            indent = "    " * depth
            file.write(f"{indent}- {node['text']} (페이지: {node['page']})\n")
            
            if node['children']:
                self._write_toc_markdown(file, node['children'], depth + 1)

def main():
    """메인 실행 함수"""
    # 현재 디렉토리에서 처리할 JSON 파일 선택
    json_files = [f for f in os.listdir('.') if f.endswith('.json')]
    output_files = [f for f in os.listdir('output') if f.endswith('.json')]
    
    all_files = json_files + [os.path.join('output', f) for f in output_files]
    
    if not all_files:
        print("디렉토리에 JSON 파일이 없습니다.")
        return
        
    print("구조 분석할 JSON 파일을 선택하세요:")
    for i, json_file in enumerate(all_files):
        print(f"{i+1}. {json_file}")
    
    try:
        selection = int(input("번호 선택: ")) - 1
        if 0 <= selection < len(all_files):
            input_file = all_files[selection]
            
            print(f"'{input_file}'의 구조를 분석합니다...")
            
            # 구조 분석 실행
            analyzer = DocumentStructureAnalyzer(input_file)
            analyzer.analyze_structure()
            
            print("결과 내보내기 옵션을 선택하세요:")
            print("1. JSON으로 내보내기")
            print("2. Markdown 목차로 내보내기")
            print("3. 목차 트리 시각화")
            print("4. 모두")
            
            output_selection = int(input("번호 선택: "))
            
            if output_selection == 1 or output_selection == 4:
                analyzer.export_structure_to_json()
                
            if output_selection == 2 or output_selection == 4:
                analyzer.export_toc_to_markdown()
                
            if output_selection == 3 or output_selection == 4:
                analyzer.create_toc_tree_visualization()
                
            print("구조 분석이 완료되었습니다.")
        else:
            print("올바른 번호를 선택하세요.")
    except ValueError:
        print("숫자를 입력하세요.")

if __name__ == "__main__":
    main() 