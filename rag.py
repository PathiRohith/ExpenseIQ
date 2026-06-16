from pathlib import Path

from llama_index.core import (
    VectorStoreIndex,
    SimpleDirectoryReader,
    StorageContext,
    load_index_from_storage,
)
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

from config import (
    POLICY_DIR,
    CHROMA_DIR,
    EMBED_MODEL,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    TOP_K,
    RELEVANCE_THRESHOLD,
)

embed_model = HuggingFaceEmbedding(model_name=EMBED_MODEL)


def _get_policy_mtime():
    """Return max mtime of all policy files — used for cache invalidation."""
    policy_path = Path(POLICY_DIR)
    if not policy_path.exists():
        return 0
    mtimes = [f.stat().st_mtime for f in policy_path.iterdir() if f.is_file()]
    return max(mtimes) if mtimes else 0


def build_index():
    documents = SimpleDirectoryReader(str(POLICY_DIR)).load_data()

    splitter = SentenceSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    nodes = splitter.get_nodes_from_documents(documents)

    index = VectorStoreIndex(nodes, embed_model=embed_model)
    index.storage_context.persist(persist_dir=str(CHROMA_DIR))

    # Store mtime fingerprint for cache invalidation
    mtime_file = Path(CHROMA_DIR) / ".policy_mtime"
    mtime_file.write_text(str(_get_policy_mtime()))

    return index


def load_index():
    chroma_path = Path(CHROMA_DIR)
    mtime_file = chroma_path / ".policy_mtime"

    if not chroma_path.exists() or not any(
        f for f in chroma_path.iterdir() if f.name != ".policy_mtime"
    ) if chroma_path.exists() else True:
        return build_index()

    # Cache invalidation: rebuild if policies have changed
    current_mtime = _get_policy_mtime()
    if mtime_file.exists():
        try:
            cached_mtime = float(mtime_file.read_text().strip())
            if cached_mtime != current_mtime:
                return build_index()
        except (ValueError, OSError):
            return build_index()
    else:
        return build_index()

    storage_context = StorageContext.from_defaults(persist_dir=str(CHROMA_DIR))
    return load_index_from_storage(storage_context, embed_model=embed_model)


def retrieve_policies(query, top_k=None):
    index = load_index()
    retriever = index.as_retriever(similarity_top_k=top_k or TOP_K)
    nodes = retriever.retrieve(query)

    return [
        {
            "text": node.text,
            "score": node.score,
            "source": node.metadata.get("file_name", "policy"),
        }
        for node in nodes
    ]


def is_policy_relevant(query, threshold=RELEVANCE_THRESHOLD):
    """
    Returns (is_relevant, best_score, top_chunks).
    Used by Policy Chat to refuse out-of-scope questions.
    """
    results = retrieve_policies(query, top_k=3)
    if not results:
        return False, 0.0, []
    best_score = max(r["score"] for r in results)
    return best_score >= threshold, best_score, results
