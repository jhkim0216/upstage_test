import fitz
import json
import re
from typing import List, Dict, Any, Literal, Tuple
from pathlib import Path
from collections import Counter

class PDFVisualizer:
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.doc = fitz.open(pdf_path)
        self.font_stats = self._analyze_font_statistics()
        self.block_positions = {}  # 페이지별 블럭 위치 통계
        self.block_types = {
            "title": (1, 0, 0),       # 빨간색 (기존과 동일)
            "body": (0, 0, 1),        # 파란색 (기존과 동일)
            "header": (0, 0.5, 0),    # 녹색
            "footer": (1, 0.5, 0),    # 주황색
            "page_number": (0.5, 0, 0.5),  # 자주색
            "index": (0.6, 0.3, 0)    # 갈색
        }
        self._analyze_block_positions()
    
    def _analyze_font_statistics(self) -> Dict[str, Any]:
        """문서 전체의 폰트 통계 분석"""
        font_sizes = []
        for page_num in range(len(self.doc)):
            page = self.doc[page_num]
            for block in page.get_text("dict")["blocks"]:
                if "lines" not in block:
                    continue
                for line in block["lines"]:
                    for span in line["spans"]:
                        font_sizes.append(span["size"])
        
        if not font_sizes:
            return {"mean": 0, "median": 0, "most_common": 0, "min": 0, "max": 0, "body_size": 0}
        
        # 가장 많이 사용된 폰트 크기 (본문 텍스트로 가정)
        counter = Counter(font_sizes)
        most_common_sizes = counter.most_common(3)
        
        stats = {
            "mean": sum(font_sizes) / len(font_sizes),
            "median": sorted(font_sizes)[len(font_sizes)//2],
            "most_common": most_common_sizes[0][0],
            "min": min(font_sizes),
            "max": max(font_sizes),
            "body_size": most_common_sizes[0][0],  # 가장 많이 사용된 크기를 본문 크기로 가정
            "title_sizes": [size for size, _ in most_common_sizes[1:] if size > most_common_sizes[0][0]]
        }
        
        print(f"폰트 통계: {stats}")
        return stats
    
    def _is_title(self, block: Dict) -> bool:
        """블록이 제목인지 판단"""
        # 제목 특성:
        # 1. 일반적으로 본문보다 큰 폰트
        # 2. 특정 패턴으로 시작 (제X장, 숫자. 등)
        # 3. 비교적 짧은 텍스트
        
        text = block["text"].strip()
        font_size = block["font_size"]
        
        # 텍스트가 너무 길면 제목이 아닐 가능성이 높음
        if len(text) > 150:
            return False
        
        # 패턴 기반 체크 (강한 제목 패턴)
        if re.match(r'^제\d+[장절]', text) or re.match(r'^[0-9]+[\.\s]', text):
            # 숫자로 시작하는 경우, 제목은 일반적으로 30자 이내
            if re.match(r'^[0-9]+[\.\s]', text) and len(text) > 100:
                return False
            return True
        
        # 폰트 크기 기반 체크 (더 엄격한 기준 적용)
        body_size = self.font_stats["body_size"]
        
        # 폰트 크기가 본문보다 충분히 큰 경우에만 제목으로 간주 (1.2배 -> 1.5배)
        if font_size > body_size * 1.5:
            # 폰트가 크더라도 텍스트가 길면 제목이 아닐 가능성이 높음
            if len(text) > 70:
                return False
            return True
        
        # 특수 케이스: 대문자나 굵은 글씨체로 짧은 텍스트
        if len(text) < 50 and (text.isupper() or "bold" in block["font_name"].lower()):
            # Bold 폰트이면서 본문보다 약간 큰 경우 (1.1배 이상)
            if "bold" in block["font_name"].lower() and font_size > body_size * 1.1:
                return True
            # 모두 대문자인 경우 (일반적으로 짧은 헤딩)
            if text.isupper() and len(text) < 25:
                return True
        
        return False
    
    def _is_complete_sentence(self, text: str) -> bool:
        """완전한 문장인지 판단"""
        if not text:
            return False
            
        # 마침표, 느낌표, 물음표 등으로 끝나는지 확인
        if text.rstrip().endswith((".", "!", "?", ":", ";", '"', "'", ")")):
            # 숫자 다음의 점은 소수점일 수 있으므로 제외
            if re.search(r'\d\.$', text.rstrip()):
                return False
            return True
            
        return False
    
    def _is_vertically_overlapping(self, block1: Dict, block2: Dict) -> bool:
        """두 블록이 수직으로 겹치는지 확인"""
        y1_top, y1_bottom = block1["bbox"][1], block1["bbox"][3]
        y2_top, y2_bottom = block2["bbox"][1], block2["bbox"][3]
        
        # 수직 겹침 계산
        y_overlap = min(y1_bottom, y2_bottom) - max(y1_top, y2_top)
        
        return y_overlap > 0
    
    def _is_content_related(self, block1: Dict, block2: Dict) -> bool:
        """두 블록이 내용적으로 연관되어 있는지 확인"""
        text1, text2 = block1["text"].strip(), block2["text"].strip()
        
        # 블록2가 괄호로 시작하고 블록1이 제목인 경우 (법령 참조)
        if text2.startswith("(") and block1["is_title"]:
            return True
        
        # 블록2가 법률 참조 형식인 경우
        if re.match(r'^\((?:소득|조특|법인|부가가치|상속|증여)(?:법|령)\s+제\d+조', text2):
            return True
            
        # 블록2가 적용시기 형식인 경우
        if text2.startswith("적용시기") or text2.startswith("<적용시기"):
            return True
        
        # 폰트 유사성 확인
        font_size_diff = abs(block1["font_size"] - block2["font_size"])
        if block1["font_name"] == block2["font_name"] and font_size_diff < 5:
            # 두 블록 모두 제목이거나 둘 다 제목이 아님
            if block1["is_title"] == block2["is_title"]:
                return True
        
        return False
    
    def _should_merge_overlapping_blocks(self, block1: Dict, block2: Dict) -> bool:
        """겹치는 블록을 병합해야 하는지 판단"""
        # 같은 페이지에 있는지 확인
        if block1["page"] != block2["page"]:
            return False
        
        # 수직 겹침 확인
        if not self._is_vertically_overlapping(block1, block2):
            return False
        
        # 내용적 연관성 확인
        if not self._is_content_related(block1, block2):
            return False
        
        # x좌표 범위 겹침 확인
        x1_left, x1_right = block1["bbox"][0], block1["bbox"][2]
        x2_left, x2_right = block2["bbox"][0], block2["bbox"][2]
        x_overlap = min(x1_right, x2_right) - max(x1_left, x2_left)
        
        if x_overlap <= 0:
            return False
        
        return True
    
    def _should_merge_blocks(self, current: Dict, next_block: Dict) -> bool:
        """두 블록을 병합해야 하는지 판단"""
        # 같은 페이지가 아니면 병합하지 않음
        if current["page"] != next_block["page"]:
            return False
            
        # 둘 중 하나라도 제목이면 병합하지 않음
        if self._is_title(current) or self._is_title(next_block):
            return False
        
        # x좌표 범위가 많이 다르면 병합하지 않음 (다른 열)
        x_overlap = min(current["bbox"][2], next_block["bbox"][2]) - max(current["bbox"][0], next_block["bbox"][0])
        width_current = current["bbox"][2] - current["bbox"][0]
        if x_overlap < 0 or x_overlap < 0.5 * width_current:
            return False
            
        # y좌표 거리가 적당하면 병합
        y_diff = next_block["bbox"][1] - current["bbox"][3]
        max_y_diff = 1.8 * max(current["font_size"], next_block["font_size"])
        
        if y_diff < 0 or y_diff > max_y_diff:
            return False
            
        # 현재 블록이 완전한 문장으로 끝나면 병합하지 않음
        if self._is_complete_sentence(current["text"]):
            return False
            
        return True
    
    def _analyze_block_positions(self):
        """모든 페이지의 블럭 위치 통계 분석"""
        # 페이지별 상단 및 하단 블럭 수집
        top_blocks = []
        bottom_blocks = []
        page_numbers = []
        
        for page_num in range(len(self.doc)):
            page = self.doc[page_num]
            page_height = page.rect.height
            page_width = page.rect.width
            blocks_dict = page.get_text("dict")["blocks"]
            
            for block in blocks_dict:
                if "lines" not in block:
                    continue
                
                # 텍스트 추출
                text_parts = []
                first_span = None
                
                for line in block["lines"]:
                    for span in line["spans"]:
                        if not first_span:
                            first_span = span
                        text_parts.append(span["text"])
                
                if not text_parts or not first_span:
                    continue
                    
                text = " ".join(text_parts).strip()
                if not text:
                    continue
                
                # 상대적 위치 계산
                y_rel_top = block["bbox"][1] / page_height
                y_rel_bottom = block["bbox"][3] / page_height
                x_rel_left = block["bbox"][0] / page_width
                x_rel_right = block["bbox"][2] / page_width
                
                # 상단 10% 영역의 블럭
                if y_rel_top < 0.1:
                    top_blocks.append({
                        "page": page_num + 1,
                        "text": text,
                        "y_rel": y_rel_top,
                        "x_rel_left": x_rel_left,
                        "x_rel_right": x_rel_right,
                        "font_size": first_span["size"]
                    })
                
                # 하단 10% 영역의 블럭
                if y_rel_bottom > 0.9:
                    bottom_blocks.append({
                        "page": page_num + 1,
                        "text": text,
                        "y_rel": y_rel_bottom,
                        "x_rel_left": x_rel_left,
                        "x_rel_right": x_rel_right,
                        "font_size": first_span["size"]
                    })
                
                # 페이지 번호 후보 (짧은 숫자 텍스트, 주로 모서리에 위치)
                if len(text) <= 5 and text.replace('.', '').isdigit():
                    # 모서리에 위치한 경우 (왼쪽 하단, 오른쪽 하단, 오른쪽 상단)
                    is_corner = (x_rel_left < 0.15 and y_rel_bottom > 0.85) or \
                                (x_rel_right > 0.85 and y_rel_bottom > 0.85) or \
                                (x_rel_right > 0.85 and y_rel_top < 0.15)
                    if is_corner:
                        page_numbers.append({
                            "page": page_num + 1,
                            "text": text,
                            "y_rel": y_rel_top if y_rel_top < 0.15 else y_rel_bottom,
                            "x_rel_left": x_rel_left,
                            "x_rel_right": x_rel_right
                        })
        
        # 머리말 패턴 찾기 (여러 페이지에 걸쳐 유사한 y좌표와 내용을 가진 상단 블럭)
        headers = self._find_repeating_blocks(top_blocks)
        
        # 꼬리말 패턴 찾기 (여러 페이지에 걸쳐 유사한 y좌표와 내용을 가진 하단 블럭)
        footers = self._find_repeating_blocks(bottom_blocks)
        
        # 결과 저장
        self.block_positions = {
            "headers": headers,
            "footers": footers,
            "page_numbers": page_numbers
        }
        
        print(f"머리말: {len(headers)}개, 꼬리말: {len(footers)}개, 페이지 번호: {len(page_numbers)}개 식별됨")
    
    def _find_repeating_blocks(self, blocks):
        """여러 페이지에 걸쳐 반복되는 블럭 패턴 찾기"""
        if not blocks:
            return []
            
        # y 좌표별로 그룹화
        y_groups = {}
        for block in blocks:
            y_key = round(block["y_rel"], 2)  # 2자리 반올림으로 유사한 y좌표 그룹화
            if y_key not in y_groups:
                y_groups[y_key] = []
            y_groups[y_key].append(block)
        
        # 3페이지 이상에 나타나는 패턴 찾기
        repeating_blocks = []
        for y_key, group in y_groups.items():
            if len(set(block["page"] for block in group)) >= 3:  # 3페이지 이상 등장
                # 각 페이지별로 하나씩만 선택
                seen_pages = set()
                filtered_group = []
                for block in group:
                    if block["page"] not in seen_pages:
                        seen_pages.add(block["page"])
                        filtered_group.append(block)
                
                repeating_blocks.extend(filtered_group)
        
        return repeating_blocks
    
    def _classify_block_type(self, block):
        """블럭 유형 분류 (제목, 본문, 머리말, 꼬리말, 페이지 번호, 인덱스)"""
        # 이미 제목으로 분류되었다면 추가 검증
        if block["is_title"]:
            text = block["text"]
            # 제목으로 분류되었지만 텍스트가 매우 길거나 마침표가 많은 경우 본문일 가능성이 높음
            if len(text) > 100 or text.count('.') > 3:
                if not re.match(r'^제\d+[장절]', text) and not re.match(r'^\d+[\.\s]', text):
                    return "body"
            
            # 괄호나 콜론이 있고 설명이 긴 경우 본문일 가능성이 높음
            if ('(' in text and ')' in text) or ':' in text:
                if len(text) > 80:
                    return "body"
            
            return "title"
        
        page_num = block["page"]
        text = block["text"]
        bbox = block["bbox"]
        
        # 페이지 크기 가져오기
        page = self.doc[page_num - 1]
        page_height = page.rect.height
        page_width = page.rect.width
        
        # 상대적 위치 계산
        y_rel_top = bbox[1] / page_height
        y_rel_bottom = bbox[3] / page_height
        x_rel_left = bbox[0] / page_width
        x_rel_right = bbox[2] / page_width
        
        # 세로로 긴 텍스트 블럭 인식 (Y 사이즈만 크게 증가한 경우)
        block_width = bbox[2] - bbox[0]
        block_height = bbox[3] - bbox[1]
        aspect_ratio = block_height / block_width if block_width > 0 else 0
        
        # 이미지에서 보이는 것처럼 세로로 긴 블럭(종횡비가 높음)이면 인덱스로 간주
        if aspect_ratio > 3.0 and block_width < page_width * 0.15:
            return "index"
        
        # 1. 페이지 번호 확인
        if len(text) <= 5 and text.replace('.', '').isdigit():
            # 모서리에 위치한 경우 (왼쪽 하단, 오른쪽 하단, 오른쪽 상단)
            is_corner = (x_rel_left < 0.15 and y_rel_bottom > 0.85) or \
                        (x_rel_right > 0.85 and y_rel_bottom > 0.85) or \
                        (x_rel_right > 0.85 and y_rel_top < 0.15)
            if is_corner:
                return "page_number"
        
        # 2. 머리말 확인 (상단 10% 영역)
        if y_rel_top < 0.1:
            # 통계에서 식별된 머리말과 비교
            for header in self.block_positions.get("headers", []):
                if abs(y_rel_top - header["y_rel"]) < 0.02:  # y좌표가 유사함
                    return "header"
        
        # 3. 꼬리말 확인 (하단 10% 영역)
        if y_rel_bottom > 0.9:
            # 통계에서 식별된 꼬리말과 비교
            for footer in self.block_positions.get("footers", []):
                if abs(y_rel_bottom - footer["y_rel"]) < 0.02:  # y좌표가 유사함
                    return "footer"
        
        # 4. 인덱스/목차 패턴 확인
        index_pattern = re.compile(r'^\d+[\.\s].*\d+$')  # 숫자로 시작하고 숫자로 끝나는 패턴 (예: "1. 제목 ... 123")
        if index_pattern.match(text) and '.' in text:
            dot_pos = text.find('.')
            if dot_pos > 0 and dot_pos < len(text) - 1:
                # 앞부분은 숫자, 뒷부분 끝이 숫자인지 확인
                prefix = text[:dot_pos]
                if prefix.isdigit() and any(c.isdigit() for c in text[-5:]):
                    return "index"
        
        # 5. 본문 추가 확인 (본문 특성)
        # 긴 텍스트, 마침표가 많은 경우, 괄호나 콜론이 있는 설명적 텍스트
        if len(text) > 80 or text.count('.') > 2 or text.count(',') > 2:
            return "body"
        
        # 문장이 완전한 형태인 경우 (마침표, 물음표, 느낌표로 끝나는 경우)
        if self._is_complete_sentence(text):
            return "body"
        
        # 기본값은 본문
        return "body"
    
    def extract_blocks(self, merge_blocks: bool = True, merge_overlapping: bool = True) -> List[Dict[str, Any]]:
        """PDF에서 텍스트 블록 추출"""
        all_blocks = []
        
        # 모든 페이지에서 블록 추출
        for page_num in range(len(self.doc)):
            page = self.doc[page_num]
            blocks_dict = page.get_text("dict")["blocks"]
            
            for block in blocks_dict:
                if "lines" not in block:
                    continue
                
                # 각 블록의 텍스트와 속성 추출
                text_parts = []
                first_span = None
                
                for line in block["lines"]:
                    for span in line["spans"]:
                        if not first_span:
                            first_span = span
                        text_parts.append(span["text"])
                
                if text_parts and first_span:
                    text = " ".join(text_parts).strip()
                    if text:
                        block_info = {
                            "page": page_num + 1,
                            "text": text,
                            "bbox": block["bbox"],
                            "font_size": first_span["size"],
                            "font_name": first_span["font"],
                            "is_title": False,  # 일단 False로 초기화
                            "block_type": "body"  # 기본 유형은 본문
                        }
                        all_blocks.append(block_info)
        
        # 제목 식별
        for block in all_blocks:
            block["is_title"] = self._is_title(block)
        
        # 병합 수행
        if merge_blocks and all_blocks:
            # 페이지, y좌표, x좌표 순으로 정렬
            all_blocks.sort(key=lambda x: (x["page"], x["bbox"][1], x["bbox"][0]))
            
            merged_blocks = []
            current = all_blocks[0].copy()
            
            for next_block in all_blocks[1:]:
                if self._should_merge_blocks(current, next_block):
                    # 텍스트 병합
                    current["text"] += " " + next_block["text"]
                    # 바운딩 박스 확장
                    current["bbox"] = (
                        min(current["bbox"][0], next_block["bbox"][0]),
                        min(current["bbox"][1], next_block["bbox"][1]),
                        max(current["bbox"][2], next_block["bbox"][2]),
                        max(current["bbox"][3], next_block["bbox"][3])
                    )
                else:
                    merged_blocks.append(current)
                    current = next_block.copy()
            
            merged_blocks.append(current)
            
            # 겹치는 블록 병합
            if merge_overlapping:
                i = 0
                while i < len(merged_blocks) - 1:
                    if self._should_merge_overlapping_blocks(merged_blocks[i], merged_blocks[i+1]):
                        # 텍스트 병합 (제목 + 부제목)
                        if merged_blocks[i+1]["text"].strip().startswith("("):
                            # 괄호로 시작하는 경우 공백 추가
                            merged_blocks[i]["text"] = merged_blocks[i]["text"] + " " + merged_blocks[i+1]["text"]
                        else:
                            # 그 외에는 줄바꿈 추가
                            merged_blocks[i]["text"] = merged_blocks[i]["text"] + "\n" + merged_blocks[i+1]["text"]
                        
                        # 바운딩 박스 확장
                        merged_blocks[i]["bbox"] = (
                            min(merged_blocks[i]["bbox"][0], merged_blocks[i+1]["bbox"][0]),
                            min(merged_blocks[i]["bbox"][1], merged_blocks[i+1]["bbox"][1]),
                            max(merged_blocks[i]["bbox"][2], merged_blocks[i+1]["bbox"][2]),
                            max(merged_blocks[i]["bbox"][3], merged_blocks[i+1]["bbox"][3])
                        )
                        
                        # 병합된 블록 제거
                        merged_blocks.pop(i+1)
                    else:
                        i += 1
            
            # 블럭 유형 분류
            for block in merged_blocks:
                block["block_type"] = self._classify_block_type(block)
            
            return merged_blocks
        
        # 블럭 유형 분류
        for block in all_blocks:
            block["block_type"] = self._classify_block_type(block)
        
        return all_blocks
    
    def visualize_blocks(self, output_dir: str, blocks=None, suffix="", is_original=False):
        """텍스트 블록의 바운딩 박스를 시각화"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 지정된 블록이 없으면 추출
        if blocks is None:
            blocks = self.extract_blocks(merge_blocks=True, merge_overlapping=True)
        
        for page_num in range(len(self.doc)):
            page = self.doc[page_num]
            
            # 페이지를 이미지로 변환
            zoom = 2
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            
            # 원본 이미지 저장 (접미사가 없는 경우에만 저장)
            if not suffix:
                image_path = output_dir / f"page_{page_num + 1}.png"
                pix.save(str(image_path))
            
            # 바운딩 박스 그리기
            for block in blocks:
                if block["page"] == page_num + 1:
                    rect = fitz.Rect(block["bbox"])
                    
                    if is_original:
                        # 원본 블록은 모두 동일한 색상(초록색)으로 표시
                        color = (0, 0.7, 0)
                        page.draw_rect(rect, color=color, width=1)
                    else:
                        # 병합된 블록은 유형에 따라 색상 결정
                        block_type = block["block_type"]
                        color = self.block_types.get(block_type, (0, 0, 1))  # 기본은 파란색
                        
                        # 제목이 우선순위가 높음
                        if block["is_title"]:
                            color = self.block_types["title"]
                            
                        page.draw_rect(rect, color=color)
                        
                        # 블럭 유형 표시 (병합된 블록에만 적용)
                        text_point = fitz.Point(rect.x0, rect.y0 - 2)
                        page.insert_text(text_point, block_type, 
                                        color=color, fontsize=6)
            
            # 바운딩 박스가 그려진 이미지 저장 (접미사 추가)
            file_name = f"page_{page_num + 1}_with_boxes{suffix}.png"
            image_path = output_dir / file_name
            pix = page.get_pixmap(matrix=mat)
            pix.save(str(image_path))
    
    def save_blocks_to_json(self, blocks: List[Dict[str, Any]], output_path: str):
        """추출된 블록 정보를 JSON으로 저장"""
        # JSON 직렬화를 위해 바운딩 박스 튜플을 리스트로 변환
        serializable_blocks = []
        for block in blocks:
            b = block.copy()
            b["bbox"] = list(b["bbox"])
            serializable_blocks.append(b)
            
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({
                "blocks": serializable_blocks,
                "total_blocks": len(blocks),
                "pdf_path": self.pdf_path,
                "total_pages": len(self.doc),
                "font_stats": self.font_stats
            }, f, ensure_ascii=False, indent=2)
    
    def extract_raw_blocks(self) -> List[Dict[str, Any]]:
        """어노테이션 없이 PDF에서 원본 텍스트 블록만 추출"""
        all_blocks = []
        
        # 모든 페이지에서 블록 추출
        for page_num in range(len(self.doc)):
            page = self.doc[page_num]
            blocks_dict = page.get_text("dict")["blocks"]
            
            for block in blocks_dict:
                if "lines" not in block:
                    continue
                
                # 각 블록의 텍스트와 속성 추출
                text_parts = []
                first_span = None
                
                for line in block["lines"]:
                    for span in line["spans"]:
                        if not first_span:
                            first_span = span
                        text_parts.append(span["text"])
                
                if text_parts and first_span:
                    text = " ".join(text_parts).strip()
                    if text:
                        block_info = {
                            "page": page_num + 1,
                            "text": text,
                            "bbox": block["bbox"],
                            "font_size": first_span["size"],
                            "font_name": first_span["font"]
                        }
                        all_blocks.append(block_info)
        
        return all_blocks
    
    def close(self):
        """PDF 문서 닫기"""
        self.doc.close()

def main():
    # 예시 사용법
    pdf_path = "./data/pdf/연말정산.pdf"
    output_dir = "./output/visualization"
    
    visualizer = PDFVisualizer(pdf_path)
    
    try:
        # 원본 블록 추출 (어노테이션 없이)
        original_blocks = visualizer.extract_raw_blocks()
        
        # 원본 블록 JSON으로 저장
        visualizer.save_blocks_to_json(original_blocks, "./output/blocks_original.json")
        print(f"원본 블록 {len(original_blocks)}개가 blocks_original.json에 저장되었습니다.")
        
        # 원본 블록 시각화 (어노테이션 없이)
        visualizer.visualize_blocks(output_dir, blocks=original_blocks, suffix="_original", is_original=True)
        print(f"원본 블록의 바운딩 박스가 {output_dir} 디렉토리에 저장되었습니다.")
        
        # 병합 및 어노테이션된 블록 추출
        merged_blocks = visualizer.extract_blocks(merge_blocks=True, merge_overlapping=True)
        
        # 블록 유형 통계 출력
        block_type_count = {}
        for block in merged_blocks:
            block_type = block["block_type"]
            if block_type not in block_type_count:
                block_type_count[block_type] = 0
            block_type_count[block_type] += 1
        
        print("블록 유형 통계:")
        for block_type, count in block_type_count.items():
            print(f"  - {block_type}: {count}개")
        
        # 병합된 블록 JSON으로 저장
        visualizer.save_blocks_to_json(merged_blocks, "./output/blocks_merged.json")
        
        # 병합된 블록 시각화 (어노테이션 적용)
        visualizer.visualize_blocks(output_dir, blocks=merged_blocks, suffix="_merged")
        print(f"병합된 블록의 바운딩 박스가 {output_dir} 디렉토리에 저장되었습니다.")
        
        print(f"총 {len(merged_blocks)}개의 병합된 텍스트 블록을 추출했습니다.")
        print(f"결과가 {output_dir} 디렉토리에 저장되었습니다.")
        
    finally:
        visualizer.close()

if __name__ == "__main__":
    main() 