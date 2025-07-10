"""
PDF Merger Service for combining filled pages into a single PDF
"""

import io
from typing import List, Dict, Any
from PIL import Image
import base64

try:
    import fitz  # PyMuPDF
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

class PDFMergerService:
    """Service for merging multiple filled form pages into a single PDF"""
    
    def __init__(self):
        self.pdf_available = PDF_AVAILABLE
    
    def is_available(self) -> bool:
        """Check if PDF functionality is available"""
        return self.pdf_available
    
    def create_pdf_from_images(self, filled_pages: List[Dict[str, Any]], filename: str = "filled_form.pdf") -> bytes:
        """
        Create a PDF file from a list of filled page images
        
        Args:
            filled_pages: List of dictionaries containing:
                - page_number: int
                - image_data: bytes or base64 string
                - width: int (optional)
                - height: int (optional)
            filename: Name for the PDF file
            
        Returns:
            bytes: PDF file content
        """
        if not self.pdf_available:
            raise RuntimeError("PDF functionality not available. Please install PyMuPDF.")
        
        if not filled_pages:
            raise ValueError("No pages provided for PDF creation")
        
        # Create a new PDF document
        doc = fitz.open()
        
        # Sort pages by page number to ensure correct order
        sorted_pages = sorted(filled_pages, key=lambda x: x.get('page_number', 0))
        
        for page_data in sorted_pages:
            try:
                # Get image data
                image_data = page_data.get('image_data')
                if not image_data:
                    print(f"Warning: No image data for page {page_data.get('page_number', 'unknown')}")
                    continue
                    
                if isinstance(image_data, str):
                    # Assume it's base64 encoded
                    if image_data.startswith('data:image'):
                        # Remove data URL prefix
                        image_data = image_data.split(',', 1)[1]
                    try:
                        image_bytes = base64.b64decode(image_data)
                    except Exception as decode_error:
                        print(f"Warning: Failed to decode base64 image data for page {page_data.get('page_number', 'unknown')}: {decode_error}")
                        continue
                else:
                    # Assume it's already bytes
                    image_bytes = image_data
                
                if not image_bytes:
                    print(f"Warning: Empty image bytes for page {page_data.get('page_number', 'unknown')}")
                    continue
                
                # Convert bytes to PIL Image for processing
                try:
                    image = Image.open(io.BytesIO(image_bytes))
                except Exception as img_error:
                    print(f"Warning: Failed to open image for page {page_data.get('page_number', 'unknown')}: {img_error}")
                    continue
                
                # Convert to RGB if necessary
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                
                # Save image to bytes buffer
                try:
                    img_buffer = io.BytesIO()
                    image.save(img_buffer, format='PNG')
                    img_buffer.seek(0)
                except Exception as save_error:
                    print(f"Warning: Failed to save image to buffer for page {page_data.get('page_number', 'unknown')}: {save_error}")
                    continue
                
                # Create a new page in the PDF
                # Use A4 size or image size, whichever is appropriate
                page_width = page_data.get('width', image.width)
                page_height = page_data.get('height', image.height)
                
                # Ensure reasonable page dimensions (minimum 100x100, maximum 2000x2000)
                page_width = max(100, min(2000, page_width))
                page_height = max(100, min(2000, page_height))
                
                # Create page with appropriate size
                page_rect = fitz.Rect(0, 0, page_width, page_height)
                page = doc.new_page(width=page_width, height=page_height)
                
                # Insert the image into the page
                try:
                    page.insert_image(page_rect, stream=img_buffer.getvalue())
                    print(f"✅ Successfully added page {page_data.get('page_number', 'unknown')} to PDF")
                except Exception as insert_error:
                    print(f"Warning: Failed to insert image into PDF page {page_data.get('page_number', 'unknown')}: {insert_error}")
                    continue
                
            except Exception as e:
                print(f"Warning: Failed to add page {page_data.get('page_number', 'unknown')} to PDF: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        if doc.page_count == 0:
            doc.close()
            raise RuntimeError("No pages were successfully added to the PDF. Check image data and format.")
        
        try:
            # Save PDF to bytes
            pdf_bytes = doc.tobytes()
            print(f"📄 PDF successfully created with {doc.page_count} pages, size: {len(pdf_bytes)} bytes")
        except Exception as save_error:
            doc.close()
            raise RuntimeError(f"Failed to save PDF to bytes: {save_error}")
        finally:
            doc.close()
        
        return pdf_bytes
    
    def merge_pdf_pages(self, original_pdf_bytes: bytes, filled_page_images: List[Dict[str, Any]]) -> bytes:
        """
        Replace pages in the original PDF with filled versions
        
        Args:
            original_pdf_bytes: Original PDF file content
            filled_page_images: List of filled page images with page numbers
            
        Returns:
            bytes: Updated PDF file content
        """
        if not self.pdf_available:
            raise RuntimeError("PDF functionality not available. Please install PyMuPDF.")
        
        # Open the original PDF
        doc = fitz.open(stream=original_pdf_bytes, filetype="pdf")
        
        # Create a mapping of page numbers to filled images
        filled_pages_map = {
            page_data.get('page_number', 0): page_data 
            for page_data in filled_page_images
        }
        
        # Process each page
        for page_num in range(1, doc.page_count + 1):
            if page_num in filled_pages_map:
                try:
                    page_data = filled_pages_map[page_num]
                    
                    # Get the page
                    page = doc[page_num - 1]  # PyMuPDF uses 0-based indexing
                    
                    # Clear the page content
                    page.clean_contents()
                    
                    # Get image data
                    image_data = page_data.get('image_data')
                    if isinstance(image_data, str):
                        if image_data.startswith('data:image'):
                            image_data = image_data.split(',', 1)[1]
                        image_bytes = base64.b64decode(image_data)
                    else:
                        image_bytes = image_data
                    
                    # Get page dimensions
                    page_rect = page.rect
                    
                    # Insert the filled image
                    page.insert_image(page_rect, stream=image_bytes)
                    
                except Exception as e:
                    print(f"Warning: Failed to replace page {page_num} in PDF: {e}")
                    continue
        
        # Save the updated PDF
        pdf_bytes = doc.tobytes()
        doc.close()
        
        return pdf_bytes
    
    def create_single_page_pdf(self, image_data: bytes, width: int = None, height: int = None) -> bytes:
        """
        Create a single-page PDF from an image
        
        Args:
            image_data: Image bytes
            width: Optional page width
            height: Optional page height
            
        Returns:
            bytes: PDF file content
        """
        if not self.pdf_available:
            raise RuntimeError("PDF functionality not available. Please install PyMuPDF.")
        
        # Convert bytes to PIL Image
        image = Image.open(io.BytesIO(image_data))
        
        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Use provided dimensions or image dimensions
        page_width = width or image.width
        page_height = height or image.height
        
        # Create PDF document
        doc = fitz.open()
        page = doc.new_page(width=page_width, height=page_height)
        
        # Save image to buffer
        img_buffer = io.BytesIO()
        image.save(img_buffer, format='PNG')
        
        # Insert image into page
        page_rect = fitz.Rect(0, 0, page_width, page_height)
        page.insert_image(page_rect, stream=img_buffer.getvalue())
        
        # Get PDF bytes
        pdf_bytes = doc.tobytes()
        doc.close()
        
        return pdf_bytes
