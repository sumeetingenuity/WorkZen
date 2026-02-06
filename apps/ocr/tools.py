"""
OCR Tools for SecureAssist.
"""
import os
import base64
import logging
from typing import Optional
from core.decorators import agent_tool
from django.conf import settings

logger = logging.getLogger(__name__)


@agent_tool(
    name="extract_pdf_text",
    description="Extract text content from a PDF file. Supports OCR for scanned documents.",
    log_response_to_orm=True,
    timeout_seconds=120,
    category="ocr"
)
async def extract_pdf_text(file_path: str, use_ocr: bool = False) -> dict:
    """
    Extract text from PDF file.
    
    The LLM just calls: @extract_pdf_text(file_path="/path/to/doc.pdf")
    Full text is stored in ORM, LLM sees extraction status.
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        return {"error": "pypdf not installed. Run: pip install pypdf"}
    
    if not os.path.exists(file_path):
        return {"error": f"File not found: {file_path}"}
    
    try:
        reader = PdfReader(file_path)
        text_pages = []
        
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            
            # If no text and OCR requested
            if not text.strip() and use_ocr:
                try:
                    from pdf2image import convert_from_path
                    images = convert_from_path(file_path, first_page=i+1, last_page=i+1)
                    if images:
                        # Temporary save to OCR
                        tmp_img_path = f"/tmp/pdf_page_{i+1}.jpg"
                        images[0].save(tmp_img_path, "JPEG")
                        text = await ocr_image(tmp_img_path)
                        if os.path.exists(tmp_img_path):
                            os.remove(tmp_img_path)
                except Exception as ocr_err:
                    logger.error(f"OCR failed for page {i+1}: {ocr_err}")
                    text = f"[OCR Error: {ocr_err}]"
            
            text_pages.append({
                "page": i + 1,
                "text": text.strip()
            })
        
        return {
            "file_path": file_path,
            "total_pages": len(reader.pages),
            "pages": text_pages
        }
        
    except Exception as e:
        return {"error": f"PDF extraction failed: {str(e)}"}

async def ocr_image(image_path: str) -> str:
    """Helper to perform OCR on an image using configured engine."""
    engine = getattr(settings, "OCR_ENGINE", "tesseract")
    
    if engine == "ollama":
        try:
            import ollama
            model = getattr(settings, "LLM_VISION", "llava")
            with open(image_path, "rb") as f:
                response = ollama.chat(
                    model=model,
                    messages=[{
                        "role": "user",
                        "content": "Extract all text from this image exactly as it appears.",
                        "images": [f.read()]
                    }]
                )
                return response['message']['content']
        except Exception as e:
            logger.warning(f"Ollama OCR failed, falling back to Tesseract: {e}")
            engine = "tesseract"

    if engine == "tesseract":
        try:
            import pytesseract
            from PIL import Image
            return pytesseract.image_to_string(Image.open(image_path))
        except Exception as e:
            logger.error(f"Tesseract OCR failed: {e}")
            return f"[OCR Failed: {e}]"
    
    return "[No OCR engine configured]"

@agent_tool(
    name="ocr_image_file",
    description="Extract text from an image file using OCR.",
    category="ocr"
)
async def ocr_image_file(file_path: str) -> dict:
    if not os.path.exists(file_path):
        return {"error": f"File not found: {file_path}"}
    text = await ocr_image(file_path)
    return {"file_path": file_path, "text": text}
@agent_tool(
    name="analyze_visual_document",
    description="Analyze images or PDF layouts using Vision models. Extracts tables, form fields, and semantic structure.",
    log_response_to_orm=True,
    timeout_seconds=60,
    category="ocr"
)
async def analyze_visual_document(file_path: str, prompt: str = "Analyze the layout and extract key data.") -> dict:
    """
    Perform semantic vision analysis on a document or image.
    
    Uses GPT-4o Vision to understand complex layouts that OCR might miss.
    """
    import base64
    import os
    from agents.model_router import model_router
    
    if not os.path.exists(file_path):
        return {"error": f"File not found: {file_path}"}
        
    try:
        # 1. Read file and base64 encode
        with open(file_path, "rb") as f:
            base64_image = base64.b64encode(f.read()).decode('utf-8')
            
        # Determine mime type
        ext = os.path.splitext(file_path)[1].lower()
        mime_type = "image/jpeg"
        if ext == ".png": mime_type = "image/png"
        elif ext == ".pdf": 
            return {"error": "Vision analysis for PDF requires conversion to image first (Phase 9 ongoing)."}

        # 2. Call Vision model
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{base64_image}"
                        }
                    }
                ]
            }
        ]
        
        response = await model_router.complete(
            task_type="vision",
            messages=messages,
            max_tokens=1000
        )
        
        return {
            "file_path": file_path,
            "analysis": response.choices[0].message.content,
            "status": "success"
        }
    except Exception as e:
        return {"error": f"Vision analysis failed: {str(e)}"}
