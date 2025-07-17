from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
from typing import List, Dict, Set
import re
from collections import Counter

class VectorSearch:
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.idx = None
        self.segments = []
        self.segment_metadata = []
        self.doc_keywords = set()
    
    def create_embeddings(self, segments: List[Dict[str, str]]):
        self.segments = [seg["text"] for seg in segments]
        self.segment_metadata = segments
        
        self.doc_keywords = self._extract_document_keywords()
        
        upd_txts = []
        for seg in segments:
            updtxt = f"{seg['section']} {seg['text']}" # UPD -- include title in embedding cntxt
            upd_txts.append(updtxt)
        
        embeddings = self.model.encode(upd_txts)
        
        dimension = embeddings.shape[1]
        self.idx = faiss.IndexFlatIP(dimension)
        
        embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
        self.idx.add(embeddings.astype('float32'))
    
    def _extract_document_keywords(self) -> Set[str]:
        full_txt = " ".join(self.segments).lower()
        
        words = re.findall(r'\b[a-zA-Z]{3,}\b', full_txt)
        total_word_cnt = len(words)
        wrd_cnts = Counter(words)
        pop_wrds = set()
        
        for word,cnt in wrd_cnts.items():
            if 2 <= cnt <= total_word_cnt*0.2 and len(word)>=4: # words that appear 2+ times but not more than 20% of doc
                pop_wrds.add(word)
        
        for mtdt in self.segment_metadata: # words that appear in short lines are LIKELY to be section indicators -- title, header, etc
            section_words = re.findall(r'\b[a-zA-Z]{4,}\b', mtdt['section'].lower())
            pop_wrds.update(section_words)
        
        return pop_wrds
    
    def create_embeddings_simple(self, segments: List[str]): # fallback func for simple str segments
        self.segments = segments
        self.segment_metadata = [{"text": seg, "section": "unknown", "type": "text"} for seg in segments]
        
        self.doc_keywords = self._extract_document_keywords() # evenf from smiple segments
        
        embeddings = self.model.encode(segments)
        
        dimension = embeddings.shape[1]
        self.idx = faiss.IndexFlatIP(dimension)
        
        embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
        self.idx.add(embeddings.astype('float32'))
    
    def search(self, query: str, top_k: int = 5) -> List[str]:
        """croe search method w multiple strategies combined:
            1. direct semantic search
            2. keyword-based search using document's own vocab
            3. fuzzy matching for partial terms
            4. section-title matching
            
            then:
            → combine all results
            → dedup n rank em
        """
        if not self.idx or not self.segments: return []
        
        semantic_resz = self._semantic_search(query, top_k * 2)
        keyword_resz = self._adaptive_keyword_search(query, top_k)
        fuzzy_resz = self._fuzzy_search(query, top_k)
        section_resz = self._section_search(query, top_k)
        
        all_resz = semantic_resz + keyword_resz + fuzzy_resz + section_resz
        
        seen_idxs = set()
        final_res = []        
        for res in all_resz:
            if res["index"] not in seen_idxs:
                final_res.append(res)
                seen_idxs.add(res["index"])
        
        final_res.sort(key=lambda x: x["score"], reverse=True)
        return [self.segments[r["index"]] for r in final_res[:top_k]]
    
    def _semantic_search(self, query: str, top_k: int) -> List[Dict]: # similarity saerch
        qry_embedding = self.model.encode([query])
        qry_embedding = qry_embedding / np.linalg.norm(qry_embedding, axis=1, keepdims=True)
        
        scores, idxs = self.idx.search(qry_embedding.astype('float32'), min(top_k, len(self.segments)))
        resz = []
        for i, score in zip(idxs[0], scores[0]):
            if score > 0.05:
                resz.append({"index": i, "score": float(score), "type": "semantic"})
        
        return resz
    
    def _adaptive_keyword_search(self, query: str, top_k: int) -> List[Dict]:
        qry_wrds = set(re.findall(r'\b[a-zA-Z]{3,}\b', query.lower()))
        resz = []
        
        for i, sgmt in enumerate(self.segments):
            segment_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', sgmt.lower()))
            
            exact_matches = qry_wrds.intersection(segment_words)
            
            # matches with doc keywords
            doc_keyword_matches = qry_wrds.intersection(self.doc_keywords)
            segment_keyword_matches = segment_words.intersection(self.doc_keywords)
            keyword_overlap = doc_keyword_matches.intersection(segment_keyword_matches)
            
            total_matches = len(exact_matches) + len(keyword_overlap)*0.5
            if total_matches>0:
                score = total_matches / max(len(qry_wrds), 1)
                resz.append({"index": i, "score": score, "type": "keyword"})
        
        return sorted(resz, key=lambda x: x["score"], reverse=True)[:top_k]
    
    def _fuzzy_search(self, query: str, top_k: int) ->List[Dict]:
        qry_wrds = re.findall(r'\b[a-zA-Z]{4,}\b', query.lower())
        resz = []
        
        for i, sgmt in enumerate(self.segments):
            segment_lower = sgmt.lower()
            score = 0
            
            for qrywrd in qry_wrds: # look for substr | partail matches
                if qrywrd in segment_lower: score += 1
                else: #4fuzzy matches - half of score for that
                    for sgmt_wrd in re.findall(r'\b[a-zA-Z]{4,}\b', segment_lower):
                        if self._fuzzy_match(qrywrd, sgmt_wrd): score += 0.5; break
            
            if score>0:
                finScore = score / len(qry_wrds) if qry_wrds else 0
                resz.append({"index": i, "score": finScore, "type": "fuzzy"})
        
        return sorted(resz, key=lambda x: x["score"], reverse=True)[:top_k]
    
    def _fuzzy_match(self, word1: str, word2: str, threshold: float = 0.7) -> bool: # based on char overlap
        if len(word1)<4 or len(word2)<4: return False
        
        # check if one word contains most of the other
        short_wrd, long_wrd = (word1, word2) if len(word1) <= len(word2) else (word2, word1)
        
        overlap = sum(1 for char in short_wrd if char in long_wrd)
        similarity = overlap / len(short_wrd)
        return similarity >= threshold
    
    def _section_search(self, query: str, top_k: int) -> List[Dict]:
        qry_lower = query.lower()
        qry_wrds = set(re.findall(r'\b[a-zA-Z]{3,}\b', qry_lower))
        resz = []
        
        for i, metadata in enumerate(self.segment_metadata):
            section_title = metadata.get("section", "").lower()
            if not section_title or section_title == "unknown": continue
            
            section_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', section_title))
            
            matches = qry_wrds.intersection(section_words) # exact word matches in section title
            substr_matches = sum(1 for wrd in qry_wrds if wrd in section_title) # substr matches
            
            total_score = len(matches) + substr_matches*0.5
            if total_score>0:
                finScore = total_score/len(qry_wrds) if qry_wrds else 0
                resz.append({"index": i, "score": finScore, "type": "section"})
        
        return sorted(resz, key=lambda x: x["score"], reverse=True)[:top_k]
    
    def debug_search(self, query: str) -> Dict: # to see what is going on pod kapotom -__-
        if not self.idx or not self.segments:
            return {"error": "no index or segments"}
        
        debug_info = {
            "query": query,
            "total_segments": len(self.segments),
            "document_keywords": list(self.doc_keywords)[:20],  # first 20 -- migth adjust it later
            "search_strategies": {}
        }
        
        strategies = [
            ("semantic", self._semantic_search),
            ("keyword", self._adaptive_keyword_search),
            ("fuzzy", self._fuzzy_search),
            ("section", self._section_search)
        ]
        
        for name, strategy_func in strategies:
            try:
                resz = strategy_func(query, 5)
                debug_info["search_strategies"][name] = {
                    "found": len(resz),
                    "top_3": [
                        {
                            "score": r["score"],
                            "preview": self.segments[r["index"]][:100] + "...",
                            "section": self.segment_metadata[r["index"]].get("section", "unknown")
                        }
                        for r in resz[:3]
                    ]
                }
            except Exception as e:
                debug_info["search_strategies"][name] = {"error": str(e)}
        
        return debug_info