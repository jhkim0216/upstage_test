import fitz
import json
from typing import List, Dict, Any, Literal
from pathlib import Path

class PDFVisualizer:
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.doc = fitz.open(pdf_path)
    
    def _merge_blocks(self, blocks: List[Dict]) -> List[Dict]:
        """인접한 블록들을 병합"""
        if not blocks:
            return blocks
            
        # 페이지, y좌표, x좌표 순으로 정렬
        blocks.sort(key=lambda x: (x["page"], x["bbox"][1], x["bbox"][0]))
        
        merged = []
        current = blocks[0].copy()
        
        for next_block in blocks[1:]:
            # 같은 페이지의 블록만 병합
            if current["page"] != next_block["page"]:
                merged.append(current)
                current = next_block.copy()
                continue
                
            # 폰트 크기가 11 이하이고 본문으로 보이는 텍스트만 병합
            is_body_text = (
                current["font_size"] <= 11 and 
                next_block["font_size"] <= 11 and
                not any(current["text"].startswith(prefix) for prefix in ["제", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]) and
                not any(next_block["text"].startswith(prefix) for prefix in ["제", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9"])
            )
            
            # y좌표 차이가 글자 크기의 1.5배 이하인 경우 병합
            y_diff = abs(current["bbox"][3] - next_block["bbox"][1])
            max_y_diff = max(current["font_size"], next_block["font_size"]) * 1.5
            
            if is_body_text and y_diff <= max_y_diff:
                # 텍스트 병합 (공백으로 구분)
                current["text"] += " " + next_block["text"]
                # 바운딩 박스 확장
                current["bbox"] = (
                    min(current["bbox"][0], next_block["bbox"][0]),  # x0
                    min(current["bbox"][1], next_block["bbox"][1]),  # y0
                    max(current["bbox"][2], next_block["bbox"][2]),  # x1
                    max(current["bbox"][3], next_block["bbox"][3])   # y1
                )
            else:
                merged.append(current)
                current = next_block.copy()
        
        merged.append(current)
        return merged
    
    def extract_blocks(self, merge_blocks: bool = True) -> List[Dict[str, Any]]:
        """PDF에서 텍스트 블록 추출"""
        blocks = []
        
        for page_num in range(len(self.doc)):
            page = self.doc[page_num]
            page_blocks = []
            
            # 블록 단위로 텍스트 추출
            for block in page.get_text("dict")["blocks"]:
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
                        page_blocks.append({
                            "page": page_num + 1,
                            "text": text,
                            "bbox": block["bbox"],
                            "font_size": first_span["size"],
                            "font_name": first_span["font"]
                        })
            
            # 블록 병합 수행
            if merge_blocks:
                # y좌표로 정렬
                page_blocks.sort(key=lambda x: (x["bbox"][1], x["bbox"][0]))
                page_blocks = self._merge_blocks(page_blocks)
            
            blocks.extend(page_blocks)
        
        return blocks
    
    def visualize_blocks(self, output_dir: str, color: tuple = (1, 0, 0)):
        """텍스트 블록의 바운딩 박스를 시각화"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        for page_num in range(len(self.doc)):
            page = self.doc[page_num]
            
            # 페이지를 이미지로 변환
            zoom = 2
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            
            # 원본 이미지 저장
            image_path = output_dir / f"page_{page_num + 1}.png"
            pix.save(str(image_path))
            
            # 블록 추출 및 바운딩 박스 그리기
            blocks = self.extract_blocks()  # 병합된 블록 사용
            for block in blocks:
                if block["page"] == page_num + 1:  # 현재 페이지의 블록만 처리
                    rect = fitz.Rect(block["bbox"])
                    # 폰트 크기에 따라 다른 색상 사용
                    if block["font_size"] <= 11:
                        color = (0, 0, 1)  # 작은 폰트는 파란색
                    else:
                        color = (1, 0, 0)  # 큰 폰트는 빨간색
                    page.draw_rect(rect, color=color)
            
            # 바운딩 박스가 그려진 이미지 저장
            image_path = output_dir / f"page_{page_num + 1}_with_boxes.png"
            pix = page.get_pixmap(matrix=mat)
            pix.save(str(image_path))
    
    def save_blocks_to_json(self, blocks: List[Dict[str, Any]], output_path: str):
        """추출된 블록 정보를 JSON으로 저장"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({
                "blocks": blocks,
                "total_blocks": len(blocks),
                "pdf_path": self.pdf_path,
                "total_pages": len(self.doc)
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
        blocks = visualizer.extract_blocks()
        
        # JSON으로 저장
        visualizer.save_blocks_to_json(blocks, "./output/blocks_merged.json")
        
        # 시각화 (폰트 크기에 따라 다른 색상으로)
        visualizer.visualize_blocks(output_dir)
        
        print(f"총 {len(blocks)}개의 텍스트 블록을 추출했습니다.")
        print(f"결과가 {output_dir} 디렉토리에 저장되었습니다.")
        
    finally:
        visualizer.close()

if __name__ == "__main__":
    main() 