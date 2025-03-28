import fitz
from pathlib import Path
from typing import Optional, List, Tuple
import os

class PDFToImage:
    """PDF 문서를 이미지로 변환하는 클래스"""
    
    def __init__(self, pdf_path: str):
        """
        Args:
            pdf_path (str): PDF 파일 경로
        """
        self.pdf_path = pdf_path
        self.doc = fitz.open(pdf_path)
    
    def convert_to_images(
        self,
        output_dir: str,
        zoom: float = 2.0,
        output_format: str = "png",
        start_page: Optional[int] = None,
        end_page: Optional[int] = None,
        quality: int = 95,
        prefix: str = "page"
    ) -> List[str]:
        """PDF 페이지들을 이미지로 변환
        
        Args:
            output_dir (str): 출력 디렉토리 경로
            zoom (float): 확대/축소 비율 (기본값: 2.0)
            output_format (str): 출력 이미지 형식 ('png' 또는 'jpg')
            start_page (int, optional): 시작 페이지 번호 (1부터 시작)
            end_page (int, optional): 끝 페이지 번호 (포함)
            quality (int): JPG 이미지 품질 (1-100)
            prefix (str): 출력 파일명 접두사
            
        Returns:
            List[str]: 생성된 이미지 파일 경로 목록
        """
        # 출력 디렉토리 생성
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 페이지 범위 설정
        start_page = max(0, (start_page or 1) - 1)  # 0-based index로 변환
        end_page = min(len(self.doc), end_page or len(self.doc))
        
        # 이미지 변환 매트릭스 설정
        mat = fitz.Matrix(zoom, zoom)
        
        # 각 페이지를 이미지로 변환
        output_files = []
        for page_num in range(start_page, end_page):
            page = self.doc[page_num]
            
            # 페이지를 이미지로 렌더링
            pix = page.get_pixmap(matrix=mat)
            
            # 출력 파일명 생성
            if output_format.lower() == "jpg":
                output_file = output_dir / f"{prefix}_{page_num + 1}.jpg"
            else:
                output_file = output_dir / f"{prefix}_{page_num + 1}.png"
            
            # 이미지 저장
            pix.save(str(output_file))
            
            output_files.append(str(output_file))
            print(f"페이지 {page_num + 1} 변환 완료: {output_file}")
        
        return output_files
    
    def get_page_dimensions(self, zoom: float = 1.0) -> List[Tuple[float, float]]:
        """각 페이지의 크기 정보를 반환
        
        Args:
            zoom (float): 확대/축소 비율
            
        Returns:
            List[Tuple[float, float]]: 각 페이지의 (너비, 높이) 목록
        """
        dimensions = []
        for page in self.doc:
            rect = page.rect
            width = rect.width * zoom
            height = rect.height * zoom
            dimensions.append((width, height))
        return dimensions
    
    def close(self):
        """PDF 문서 닫기"""
        self.doc.close()

def convert_pdf_to_images(
    pdf_path: str,
    output_dir: str,
    zoom: float = 2.0,
    output_format: str = "png",
    start_page: Optional[int] = None,
    end_page: Optional[int] = None,
    quality: int = 95,
    prefix: str = "page"
) -> List[str]:
    """PDF를 이미지로 변환하는 편의 함수
    
    Args:
        pdf_path (str): PDF 파일 경로
        output_dir (str): 출력 디렉토리 경로
        zoom (float): 확대/축소 비율 (기본값: 2.0)
        output_format (str): 출력 이미지 형식 ('png' 또는 'jpg')
        start_page (int, optional): 시작 페이지 번호 (1부터 시작)
        end_page (int, optional): 끝 페이지 번호 (포함)
        quality (int): JPG 이미지 품질 (1-100)
        prefix (str): 출력 파일명 접두사
        
    Returns:
        List[str]: 생성된 이미지 파일 경로 목록
    """
    converter = PDFToImage(pdf_path)
    try:
        return converter.convert_to_images(
            output_dir=output_dir,
            zoom=zoom,
            output_format=output_format,
            start_page=start_page,
            end_page=end_page,
            quality=quality,
            prefix=prefix
        )
    finally:
        converter.close()

if __name__ == "__main__":
    # 사용 예시
    pdf_path = "./data/pdf/연말정산-1-14.pdf"
    output_dir = "./output/images"
    
    # 방법 1: 클래스 사용
    converter = PDFToImage(pdf_path)
    try:
        # 전체 PDF를 PNG 이미지로 변환 (2배 확대)
        image_files = converter.convert_to_images(
            output_dir=output_dir,
            zoom=2.0,
            output_format="png"
        )
        print(f"총 {len(image_files)}개의 이미지 파일이 생성되었습니다.")
        
        # 페이지 크기 정보 출력
        dimensions = converter.get_page_dimensions(zoom=1.0)
        for i, (width, height) in enumerate(dimensions, 1):
            print(f"페이지 {i}: {width:.1f} x {height:.1f} 포인트")
    
    finally:
        converter.close()
    
    # 방법 2: 편의 함수 사용
    image_files = convert_pdf_to_images(
        pdf_path=pdf_path,
        output_dir=output_dir,
        zoom=2.0,
        output_format="jpg",
        quality=95
    )
    print(f"총 {len(image_files)}개의 이미지 파일이 생성되었습니다.") 