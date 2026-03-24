"""
step1_create_index.py — Create a search index with hybrid search.

CHANGE: run() now takes an IndexConfig so it can be called in a loop
for each of the 2 indexes. Internal logic unchanged.
"""

from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex, SearchField, SearchFieldDataType,
    SimpleField, SearchableField,
    VectorSearch, VectorSearchProfile,
    HnswAlgorithmConfiguration, HnswParameters,
    SemanticConfiguration, SemanticSearch,
    SemanticPrioritizedFields, SemanticField,
)

import config
from config import IndexConfig


def build_fields() -> list:
    if config.ENABLE_SKILLS:
        return [
            SimpleField(name="chunk_id", type=SearchFieldDataType.String,
                         key=True, filterable=True, sortable=True),
            SimpleField(name="parent_id", type=SearchFieldDataType.String,
                         filterable=True, sortable=True),
            SearchableField(name="chunk", type=SearchFieldDataType.String,
                             analyzer_name="en.microsoft"),
            SearchableField(name="title", type=SearchFieldDataType.String,
                             filterable=True, sortable=True),
            SearchField(name="chunk_vector",
                        type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                        searchable=True,
                        vector_search_dimensions=config.EMBEDDING_DIMENSIONS,
                        vector_search_profile_name="my-hnsw-profile"),
        ]

    return [
        SimpleField(name="id", type=SearchFieldDataType.String,
                     key=True, filterable=True, sortable=True),
        SearchableField(name="content", type=SearchFieldDataType.String,
                         analyzer_name="en.microsoft"),
        SearchableField(name="title", type=SearchFieldDataType.String,
                         filterable=True, sortable=True),
        SimpleField(name="metadata_storage_path", type=SearchFieldDataType.String,
                     filterable=True, sortable=True),
    ]


def build_vector_search() -> VectorSearch:
    return VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(
            name="my-hnsw-algo",
            parameters=HnswParameters(m=4, ef_construction=400, ef_search=500, metric="cosine"),
        )],
        profiles=[VectorSearchProfile(name="my-hnsw-profile", algorithm_configuration_name="my-hnsw-algo")],
    )


def build_semantic_search(content_field: str) -> SemanticSearch:
    return SemanticSearch(configurations=[
        SemanticConfiguration(
            name="my-semantic-config",
            prioritized_fields=SemanticPrioritizedFields(
                content_fields=[SemanticField(field_name=content_field)],
                title_field=SemanticField(field_name="title"),
            ),
        ),
    ])


def run(idx_cfg: IndexConfig):
    """Create one index. Called once per IndexConfig."""
    index_client = SearchIndexClient(
        endpoint=config.SEARCH_ENDPOINT,
        credential=AzureKeyCredential(config.SEARCH_ADMIN_KEY),
    )
    index = SearchIndex(
        name=idx_cfg.index_name,
        fields=build_fields(),
        vector_search=build_vector_search() if config.ENABLE_SKILLS else None,
        semantic_search=build_semantic_search("chunk" if config.ENABLE_SKILLS else "content"),
    )
    result = index_client.create_or_update_index(index)
    print(f"  Index '{result.name}' created/updated.")
    return result
