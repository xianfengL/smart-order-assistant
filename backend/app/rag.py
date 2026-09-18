import asyncio
import hashlib
import math
from pathlib import Path
import chromadb
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from .config import settings


def local_embeddings(texts):
    """Deterministic character-bigram vectors for offline demos, no model download."""
    result = []
    for value in texts:
        vector = [0.0] * 256
        chars = ''.join(value.lower().split())
        for i in range(max(1, len(chars) - 1)):
            key = hashlib.sha256(chars[i:i+2].encode()).digest()
            vector[int.from_bytes(key[:2], 'big') % 256] += 1
        norm = math.sqrt(sum(x*x for x in vector)) or 1
        result.append([x / norm for x in vector])
    return result


class PolicyStore:
    def __init__(self):
        self.embedder = None if settings.demo_mode else OpenAIEmbeddings(
            api_key=settings.openai_api_key, base_url=settings.openai_base_url, model=settings.embedding_model)
        self.client = chromadb.PersistentClient(path=str(settings.data_dir / 'chroma'))
        model = 'demo-bigram-256' if settings.demo_mode else settings.embedding_model
        suffix = hashlib.sha256((model + settings.openai_base_url).encode()).hexdigest()[:10]
        self.collection = self.client.get_or_create_collection('policies-' + suffix, metadata={'hnsw:space': 'cosine'}, embedding_function=None)

    def embed(self, texts):
        return local_embeddings(texts) if self.embedder is None else self.embedder.embed_documents(texts)

    def index(self):
        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=80, separators=['\n\n', '\n', '。', ' ', ''])
        chunks, metadata, ids = [], [], []
        for path in sorted((Path(__file__).parent.parent / 'policies').glob('*.md')):
            for i, chunk in enumerate(splitter.split_text(path.read_text(encoding='utf-8'))):
                chunks.append(chunk)
                metadata.append({'source': path.name, 'chunk': i})
                ids.append(hashlib.sha256((path.name + chunk).encode()).hexdigest())
        existing = set(self.collection.get()['ids'])
        removed = list(existing - set(ids))
        if removed:
            self.collection.delete(ids=removed)
        missing = [i for i, ident in enumerate(ids) if ident not in existing]
        if missing:
            self.collection.upsert(ids=[ids[i] for i in missing], documents=[chunks[i] for i in missing],
                                   metadatas=[metadata[i] for i in missing], embeddings=self.embed([chunks[i] for i in missing]))
        return len(ids)

    async def retrieve(self, question):
        def run():
            if not self.collection.count():
                return []
            vector = self.embedder.embed_query(question) if self.embedder else local_embeddings([question])[0]
            result = self.collection.query(query_embeddings=[vector], n_results=min(3, self.collection.count()))
            return [{'text': doc, 'source': meta['source'], 'distance': round(distance, 4)} for doc, meta, distance in
                    zip(result['documents'][0], result['metadatas'][0], result['distances'][0])]
        return await asyncio.to_thread(run)
