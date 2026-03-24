"""
step5_query_and_rag.py — Hybrid search across BOTH indexes + RAG.

CHANGE vs single-index version:
  - hybrid_search() now queries EACH index in config.INDEXES
  - Results from both indexes are merged and sorted by reranker_score
  - Top-k across both indexes are used as context for the LLM
  - Works with both Azure OpenAI and Azure AI Foundry
"""

from openai import AzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import (
    VectorizedQuery, QueryType, QueryCaptionType, QueryAnswerType,
)

import config
from config import IndexConfig


# ----------------------------------------------------------------
# Clients
# ----------------------------------------------------------------

# One SearchClient per index
search_clients: dict[str, SearchClient] = {}
for idx_cfg in config.INDEXES:
    search_clients[idx_cfg.index_name] = SearchClient(
        endpoint=config.SEARCH_ENDPOINT,
        index_name=idx_cfg.index_name,
        credential=AzureKeyCredential(config.SEARCH_ADMIN_KEY),
    )

# Single model client — API key for OpenAI, Entra ID for Foundry
if config.MODEL_API_KEY:
    # Azure OpenAI with API key
    openai_client = AzureOpenAI(
        azure_endpoint=config.MODEL_ENDPOINT,
        api_key=config.MODEL_API_KEY,
        api_version=config.MODEL_API_VERSION,
    )
else:
    # Azure AI Foundry with Entra ID (DefaultAzureCredential)
    # Requires: `az login` or managed identity
    openai_client = AzureOpenAI(
        azure_endpoint=config.MODEL_ENDPOINT,
        azure_ad_token_provider=config.MODEL_TOKEN_PROVIDER,
        api_version=config.MODEL_API_VERSION,
    )


# ----------------------------------------------------------------
# Embedding
# ----------------------------------------------------------------

def get_embedding(text: str) -> list[float]:
    response = openai_client.embeddings.create(
        input=text, model=config.EMBEDDING_DEPLOYMENT,
    )
    return response.data[0].embedding


# ----------------------------------------------------------------
# Search one index
# ----------------------------------------------------------------

def _search_single_index(index_name: str, query: str, query_vector: list[float] | None, top_k: int) -> list[dict]:
    """Run search against one index."""
    client = search_clients[index_name]

    vector_queries = None
    if config.ENABLE_SKILLS and query_vector is not None:
        vector_queries = [
            VectorizedQuery(
                vector=query_vector, k_nearest_neighbors=50, fields="chunk_vector",
            )
        ]

    select_fields = (
        ["chunk_id", "chunk", "title", "parent_id"]
        if config.ENABLE_SKILLS
        else ["id", "content", "title", "metadata_storage_path"]
    )

    results = client.search(
        search_text=query,
        vector_queries=vector_queries,
        query_type=QueryType.SEMANTIC,
        semantic_configuration_name="my-semantic-config",
        query_caption=QueryCaptionType.EXTRACTIVE,
        query_answer=QueryAnswerType.EXTRACTIVE,
        select=select_fields,
        top=top_k,
    )

    docs = []
    for result in results:
        doc = {
            "chunk_id": result.get("chunk_id", ""),
            "chunk": result.get("chunk", "") or result.get("content", ""),
            "title": result.get("title", ""),
            "parent_id": result.get("parent_id", ""),
            "id": result.get("id", ""),
            "index_name": index_name,
            "score": result.get("@search.score", 0),
            "reranker_score": result.get("@search.reranker_score", 0),
        }
        captions = result.get("@search.captions")
        if captions:
            doc["caption"] = captions[0].text or ""
        docs.append(doc)

    return docs


# ----------------------------------------------------------------
# Search BOTH indexes and merge
# ----------------------------------------------------------------

def hybrid_search(query: str, top_k: int = 5) -> list[dict]:
    """
    Query both indexes, merge results, return top_k by reranker score.

    Each index is searched independently. Results are combined and
    sorted by semantic reranker score (descending) so the best
    chunks from either index rise to the top.
    """
    query_vector = get_embedding(query) if config.ENABLE_SKILLS else None

    all_docs = []
    for idx_cfg in config.INDEXES:
        docs = _search_single_index(idx_cfg.index_name, query, query_vector, top_k)
        all_docs.extend(docs)

    # Sort by reranker_score (semantic), fall back to RRF score
    all_docs.sort(key=lambda d: d.get("reranker_score") or d.get("score", 0), reverse=True)

    return all_docs[:top_k]


# ----------------------------------------------------------------
# RAG
# ----------------------------------------------------------------

SYSTEM_PROMPT = """You are a helpful assistant that answers questions based on the provided context.

RULES:
- Answer ONLY based on the context provided below.
- If the context does not contain enough information, say so clearly.
- Cite the source document title and index when referencing specific information.
- Be concise but thorough.
- Do not make up information not present in the context.
"""


def build_context(search_results: list[dict]) -> str:
    parts = []
    for i, doc in enumerate(search_results, 1):
        title = doc.get("title", "Unknown")
        index = doc.get("index_name", "?")
        chunk = doc.get("chunk", "")
        parts.append(f"[Source {i}: {title} (index: {index})]\n{chunk}")
    return "\n\n---\n\n".join(parts)


def ask(question: str, top_k: int = 5, show_sources: bool = True) -> str:
    """
    RAG across both indexes: search both → merge → build context → LLM.
    """
    provider_label = "Azure OpenAI" if config.MODEL_PROVIDER == "openai" else "Azure AI Foundry"

    print(f"\n{'─' * 50}")
    print(f"Question: {question}")
    print(f"Provider: {provider_label}")
    search_mode = "semantic + vector" if config.ENABLE_SKILLS else "semantic only"
    print(f"Searching: {[i.index_name for i in config.INDEXES]} ({search_mode})")
    print(f"{'─' * 50}")

    search_results = hybrid_search(question, top_k=top_k)

    if not search_results:
        return "No relevant documents found in either index."

    if show_sources:
        print(f"\n  Top {len(search_results)} chunk(s) across both indexes:")
        for i, doc in enumerate(search_results, 1):
            title = doc.get("title", "?")
            index = doc.get("index_name", "?")
            score = doc.get("reranker_score") or doc.get("score", 0)
            snippet = doc.get("chunk", "")[:60].replace("\n", " ")
            print(f"    {i}. [{index}] {title} (score: {score:.4f}) {snippet}...")

    context = build_context(search_results)

    print(f"\n  Generating answer with '{config.CHAT_DEPLOYMENT}'...")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer:"},
    ]

    response = openai_client.chat.completions.create(
        model=config.CHAT_DEPLOYMENT, messages=messages,
        temperature=0.3, max_tokens=1024,
    )
    return response.choices[0].message.content


# ----------------------------------------------------------------
# Interactive
# ----------------------------------------------------------------

def run():
    provider_label = "Azure OpenAI" if config.MODEL_PROVIDER == "openai" else "Azure AI Foundry"
    print("\n" + "=" * 60)
    print(f"RAG Query Interface — {provider_label}")
    print(f"Indexes: {[i.index_name for i in config.INDEXES]}")
    print("=" * 60)
    print("Type your questions. Type 'quit' to exit.\n")

    while True:
        question = input("\nYou: ").strip()
        if not question:
            continue
        if question.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break
        answer = ask(question)
        print(f"\nAssistant: {answer}")


if __name__ == "__main__":
    run()
