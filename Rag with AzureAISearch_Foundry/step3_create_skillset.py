"""
step3_create_skillset.py — Create skillset for chunking + embedding.

CHANGE: run() takes IndexConfig — uses idx_cfg.skillset_name and
idx_cfg.index_name for index projections.
Works with both Azure OpenAI and Azure AI Foundry endpoints.
"""

from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexerClient
from azure.search.documents.indexes.models import (
    SearchIndexerSkillset, SplitSkill, AzureOpenAIEmbeddingSkill,
    InputFieldMappingEntry, OutputFieldMappingEntry,
    SearchIndexerIndexProjectionSelector, SearchIndexerIndexProjection,
)

import config
from config import IndexConfig


def build_text_split_skill() -> SplitSkill:
    return SplitSkill(
        name="text-split-skill", description="Split documents into chunks",
        text_split_mode="pages", context="/document",
        maximum_page_length=2000, page_overlap_length=500,
        inputs=[InputFieldMappingEntry(name="text", source="/document/content")],
        outputs=[OutputFieldMappingEntry(name="textItems", target_name="pages")],
    )


def build_embedding_skill() -> AzureOpenAIEmbeddingSkill:
    """
    Works with BOTH Azure OpenAI (API key) and Azure AI Foundry (Entra ID).

    - For API key auth: pass api_key parameter.
    - For Entra ID: omit api_key. The search service's managed identity
      must have 'Cognitive Services OpenAI User' role on the OpenAI/Foundry resource.
    - resource_url uses SKILLSET_RESOURCE_URL (the OpenAI-compatible endpoint).
    """
    skill_kwargs = dict(
        name="embedding-skill",
        description=f"Embeddings via {config.MODEL_PROVIDER}",
        context="/document/pages/*",
        resource_url=config.SKILLSET_RESOURCE_URL,
        deployment_name=config.EMBEDDING_DEPLOYMENT,
        model_name=config.EMBEDDING_MODEL_NAME,
        inputs=[InputFieldMappingEntry(name="text", source="/document/pages/*")],
        outputs=[OutputFieldMappingEntry(name="embedding", target_name="chunk_vector")],
    )

    # Only pass api_key if using API key auth (Azure OpenAI).
    # For Foundry with Entra ID, omit it — the search service uses its
    # managed identity to call the embedding endpoint.
    if config.MODEL_API_KEY:
        skill_kwargs["api_key"] = config.MODEL_API_KEY

    return AzureOpenAIEmbeddingSkill(**skill_kwargs)


def build_index_projections(idx_cfg: IndexConfig) -> SearchIndexerIndexProjection:
    return SearchIndexerIndexProjection(
        selectors=[SearchIndexerIndexProjectionSelector(
            target_index_name=idx_cfg.index_name,
            parent_key_field_name="parent_id",
            source_context="/document/pages/*",
            mappings=[
                InputFieldMappingEntry(name="chunk", source="/document/pages/*"),
                InputFieldMappingEntry(name="chunk_vector", source="/document/pages/*/chunk_vector"),
                InputFieldMappingEntry(name="title", source="/document/metadata_storage_name"),
            ],
        )],
        parameters={"projection_mode": "generatedKeyAsId"},
    )


def run(idx_cfg: IndexConfig):
    """Create one skillset. Called once per IndexConfig."""
    if not config.ENABLE_SKILLS:
        print("  Skillset skipped (ENABLE_SKILLS=false).")
        return None
    indexer_client = SearchIndexerClient(
        endpoint=config.SEARCH_ENDPOINT,
        credential=AzureKeyCredential(config.SEARCH_ADMIN_KEY),
    )
    skillset = SearchIndexerSkillset(
        name=idx_cfg.skillset_name,
        description=f"Skillset for index '{idx_cfg.index_name}'",
        skills=[build_text_split_skill(), build_embedding_skill()],
        index_projections=build_index_projections(idx_cfg),
    )
    result = indexer_client.create_or_update_skillset(skillset)
    print(f"  Skillset '{result.name}' → index '{idx_cfg.index_name}'")
    return result
