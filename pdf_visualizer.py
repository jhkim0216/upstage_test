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
    
    def extract_blocks(self, merge_blocks: bool = True) -> List[Dict[str, Any]]:
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
            return merged_blocks
        
        return all_blocks
    
    def visualize_blocks(self, output_dir: str):
        """텍스트 블록의 바운딩 박스를 시각화"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 블록 추출
        blocks = self.extract_blocks()
        
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
        # 블록 추출 (폰트 크기 기반 병합)
        blocks = visualizer.extract_blocks(merge_blocks=True)
        
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