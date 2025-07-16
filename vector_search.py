from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
from typing import List

class VectorSearch:
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.idx = None
        self.segments = []
    
    def create_embeddings(self, segments: List[str]):
        self.segments = segments
        mbdngS = self.model.encode(segments)
        
        dimension = mbdngS.shape[1]
        self.idx = faiss.IndexFlatIP(dimension)
        
        mbdngS = mbdngS / np.linalg.norm(mbdngS, axis=1, keepdims=True)
        self.idx.add(mbdngS.astype('float32'))
    
    def search(self, query: str, top_k: int = 3) -> List[str]:
        if not self.idx or not self.segments:
            return []
        
        qry_mbdng = self.model.encode([query])
        qry_mbdng = qry_mbdng / np.linalg.norm(qry_mbdng, axis=1, keepdims=True)
        
        scores, idxs = self.idx.search(qry_mbdng.astype('float32'), top_k)
        
        relevnt_txt = []
        for i, score in zip(idxs[0], scores[0]):
            if score > 0.1:
                relevnt_txt.append(self.segments[i])
        
        if not relevnt_txt and len(idxs[0]) > 0:
            relevnt_txt.append(self.segments[idxs[0][0]])
        
        return relevnt_txt