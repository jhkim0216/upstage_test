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
        
        # 패턴 기반 체크
        if re.match(r'^제\d+[장절]', text) or re.match(r'^[0-9]+[\.\s]', text):
            return True
            
        # 폰트 크기 기반 체크
        if font_size > self.font_stats["body_size"] * 1.2:
            return True
            
        # 특수 케이스: 대문자나 굵은 글씨체로 짧은 텍스트
        if len(text) < 100 and (text.isupper() or "bold" in block["font_name"].lower()):
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
                        all_blocks.append({
                            "page": page_num + 1,
                            "text": text,
                            "bbox": block["bbox"],
                            "font_size": first_span["size"],
                            "font_name": first_span["font"],
                            "is_title": False  # 일단 False로 초기화
                        })
        
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
            
            return merged_blocks
        
        return all_blocks
    
    def visualize_blocks(self, output_dir: str):
        """텍스트 블록의 바운딩 박스를 시각화"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 블록 추출 (겹치는 블록 병합 포함)
        blocks = self.extract_blocks(merge_blocks=True, merge_overlapping=True)
        
        for page_num in range(len(self.doc)):
            page = self.doc[page_num]
            
            # 페이지를 이미지로 변환
            zoom = 2
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            
            # 원본 이미지 저장
            image_path = output_dir / f"page_{page_num + 1}.png"
            pix.save(str(image_path))
            
            # 바운딩 박스 그리기
            for block in blocks:
                if block["page"] == page_num + 1:
                    rect = fitz.Rect(block["bbox"])
                    
                    # 제목은 빨간색, 본문은 파란색으로 표시
                    if block["is_title"]:
                        color = (1, 0, 0)  # 빨간색
                    else:
                        color = (0, 0, 1)  # 파란색
                        
                    page.draw_rect(rect, color=color)
            
            # 바운딩 박스가 그려진 이미지 저장
            image_path = output_dir / f"page_{page_num + 1}_with_boxes.png"
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
    
    def close(self):
        """PDF 문서 닫기"""
        self.doc.close()

def main():
    # 예시 사용법
    pdf_path = "./data/pdf/연말정산-1-14.pdf"
    output_dir = "./output/visualization"
    
    visualizer = PDFVisualizer(pdf_path)
    
    try:
        # 블록 추출 (겹치는 블록 병합 포함)
        blocks = visualizer.extract_blocks(merge_blocks=True, merge_overlapping=True)
        
        # JSON으로 저장
        visualizer.save_blocks_to_json(blocks, "./output/blocks_merged.json")
        
        # 시각화 (제목과 본문 구분하여 표시)
        visualizer.visualize_blocks(output_dir)
        
        print(f"총 {len(blocks)}개의 텍스트 블록을 추출했습니다.")
        print(f"결과가 {output_dir} 디렉토리에 저장되었습니다.")
        
    finally:
        visualizer.close()

if __name__ == "__main__":
    main() 