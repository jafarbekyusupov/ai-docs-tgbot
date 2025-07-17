import PyPDF2
import re
import logging
from typing import List, Dict
from collections import Counter

logger = logging.getLogger(__name__)

class DocumentProcessor:
    def __init__(self):
        self.header_patterns =[
            r'^\d+\.\s+',
            r'^\d+\.\d+\s+', 
            r'^[A-Z]{2,}$',
            r'^[A-Z][A-Z\s]+[A-Z]$',
            r'^\w+:$',
            r'^[IVX]+\.\s+',
            r'^[a-z]\)\s+',
            r'^•\s+|^\*\s+|^-\s+',
        ]
    
    def extract_text_from_pdf(self, file_path:str) -> str:
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
    
    def analyze_doc_struct(self, txt: str) -> Dict:
        lines = [ll.strip() for ll in txt.split('\n') if ll.strip()]
        
        analysis = {
            'total_lines': len(lines),
            'potential_headers': [],
            'line_stats': {}
        }
        
        lens = [len(ll) for ll in lines]
        analysis['line_stats'] = {
            'avg': sum(lens) / len(lens) if lens else 0,
            'short_lines': len([l for l in lens if l < 50]),
            'medium_lines': len([l for l in lens if 50 <= l <= 200]),
            'long_lines': len([l for l in lens if l > 200])
        }
        
        for i, ll in enumerate(lines):
            hdr_score = self.calc_header_score(ll,i,lines)
            if hdr_score > 0.3:
                analysis['potential_headers'].append({
                    'line': ll,
                    'position': i,
                    'score': hdr_score
                })
        
        return analysis
    
    def calc_header_score(self, line: str, pos: int, all_lines: List[str]) -> float:
        score = 0.0
        
        for pp in self.header_patterns:
            if re.match(pp, line): score += 0.3
        
        if len(line)<60: score += 0.2
        elif len(line)<30: score+=0.3
        
        if pos>0 and pos<len(all_lines) - 1:
            prev_line = all_lines[pos - 1] if pos > 0 else ""
            next_line = all_lines[pos + 1] if pos < len(all_lines) - 1 else ""
            
            if len(prev_line) == 0: score += 0.2
            if len(next_line)>len(line)*1.5: score += 0.2
        
        words = line.split()
        if words:
            caps_ratio = sum(1 for wrd in words if wrd[0].isupper())/len(words)
            if caps_ratio > 0.5: score += 0.2
        
        if len(line)>100: score *= 0.5
        return min(score, 1.0)
    
    def extract_sections(self, txt:str) -> List[Dict[str,str]]:
        analysis = self.analyze_doc_struct(txt)
        lines = [ll.strip() for ll in txt.split('\n') if ll.strip()]
        
        sections = []
        curr_section = {"title": "Document Start", "content": "", "start_line": 0}
        
        hdrz = sorted(analysis['potential_headers'], key=lambda x: x['position'])
        if not hdrz:
            return self.extract_sections_fallback(txt)
        
        hdr_posz = [h['position'] for h in hdrz]
        for i,ll in enumerate(lines):
            if i in hdr_posz:
                if curr_section["content"].strip():
                    sections.append(curr_section)
                
                curr_section = {
                    "title": ll,
                    "content": "",
                    "start_line": i
                }
            else: curr_section["content"] += ll + " "
        
        if curr_section["content"].strip(): sections.append(curr_section)
        return sections
    
    def extract_sections_fallback(self, txt: str) -> List[Dict[str, str]]:
        pgphs = txt.split('\n\n')
        sections = []
        
        for i, para in enumerate(pgphs):
            if para.strip():
                lines = para.strip().split('\n')
                fline = lines[0].strip()
                
                if len(fline)<80 and len(lines)>1: title = fline; content = '\n'.join(lines[1:]) # → first line is likely a title
                else: title = f"Section {i+1}"; content = para.strip()
                
                sections.append({
                    "title": title,
                    "content": content,
                    "start_line": i
                })
        
        return sections
    
    def segment_text(self, txt: str, segment_size: int = 800, overlap: int = 100) -> List[Dict[str, str]]:
        sections = self.extract_sections(txt)
        segments = []
        
        if len(sections)<2: sections = self.extract_sections_fallback(txt)
        
        for sec in sections:
            sec_title = sec["title"]
            sec_content = sec["content"]
            
            title = re.sub(r'^\d+\.?\s*', '', sec_title)
            title = re.sub(r'^[•\-\*]\s*', '', title)
            
            if len(sec_content)<=segment_size:
                segments.append({
                    "text": f"{title}\n{sec_content}",
                    "section": title,
                    "type": "complete_section"
                })
            else: segments.extend(self.split_long_section( title,sec_content,segment_size))
        
        return segments
    
    def split_long_section(self, title: str, content: str, segment_size: int) -> List[Dict[str, str]]:
        segments = []
        
        lines = re.split(r'[.!?]+\s+', content)
        curr_sgmt = f"{title}\n"
        sgmt_num = 1
        
        for ll in lines:
            ll = ll.strip()
            if not ll: continue
            if len(curr_sgmt+ll)<segment_size: curr_sgmt += ll + ". "
            else:
                if curr_sgmt.strip():
                    segments.append({
                        "text": curr_sgmt.strip(),
                        "section": title,
                        "type": "section_part",
                        "part_number": sgmt_num
                    })
                
                sgmt_num += 1
                curr_sgmt = f"{title} (part {sgmt_num})\n{ll}. "
        
        if curr_sgmt.strip():
            segments.append({
                "text": curr_sgmt.strip(),
                "section": title,
                "type": "section_part", 
                "part_number": sgmt_num
            })
        
        return segments
    
    def segment_text_simple(self, txt: str, segment_size: int = 600, overlap: int = 50) -> List[str]:
        txt = re.sub(r'\s+', ' ', txt.strip())
        pgphs = txt.split('\n\n')
        if len(pgphs) == 1: lines = re.split(r'[.!?]+\s+', txt)
        else:
            lines = []
            for para in pgphs: lines.extend(re.split(r'[.!?]+\s+', para))
        
        segments = []
        curr_sgmt = ""
        
        for ll in lines:
            ll = ll.strip()
            if not ll: continue
            if len(curr_sgmt+ll)<segment_size: curr_sgmt += ll+". "
            else:
                if curr_sgmt: segments.append(curr_sgmt.strip())
                curr_sgmt = ll+". "

        if curr_sgmt: segments.append(curr_sgmt.strip())            
        return segments
    
    def segment_text(self, txt: str, segment_size: int = 800, overlap: int = 100) -> List[Dict[str, str]]:
        try:
            return self.segment_text(txt, segment_size, overlap)
        except Exception as e:
            logger.warning(f"advanced segmentation failed: {e}, using simple")
            simple_segments = self.segment_text_simple(txt, segment_size, overlap)
            return [{"text": seg, "section": f"Section {i+1}", "type": "simple"} for i, seg in enumerate(simple_segments)]