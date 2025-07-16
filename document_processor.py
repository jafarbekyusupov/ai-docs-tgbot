import PyPDF2
import re
import logging
from typing import List

logger = logging.getLogger(__name__)

class DocumentProcessor:
    def extract_text_from_pdf(self, file_path: str) -> str:
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                txt = ""
                for pg in pdf_reader.pages:
                    txt += pg.extract_text() + "\n"
                return txt
        except Exception as e:
            logger.error(f"error extracting pdf text: {e}")
            return ""
    
    def segment_text(self, txt: str, segment_size: int = 500, overlap: int = 50) -> List[str]:
        txt = re.sub(r'\s+', ' ', txt.strip())

        lines = txt.split('. ')
        segments = []
        curr_sgmt = ""
        
        for ll in lines:
            if len(curr_sgmt + ll) < segment_size:
                curr_sgmt += ll + ". "
            else:
                if curr_sgmt:
                    segments.append(curr_sgmt.strip())
                curr_sgmt = ll + ". "
        
        if curr_sgmt:
            segments.append(curr_sgmt.strip())
            
        return segments