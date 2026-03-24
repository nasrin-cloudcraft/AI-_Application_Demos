# Azure AI Search RAG Pipeline

## Supports Both Azure OpenAI and Azure AI Foundry

```
Text Files (in Blob) → Indexer + Skillset → Azure AI Search Index
                                                      ↓
User Question → Hybrid Search (Keyword+Vector+Semantic) → Chunks → LLM → Answer
```

## Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env
```

### For Azure OpenAI:
```bash
# In .env set:
MODEL_PROVIDER=openai
# Fill in AZURE_OPENAI_* variables
python run_pipeline.py
```

### For Azure AI Foundry:
```bash
# In .env set:
MODEL_PROVIDER=foundry
# Fill in AZURE_FOUNDRY_* variables
# AZURE_FOUNDRY_ENDPOINT should be your Foundry project endpoint:
#   https://<resource>.services.ai.azure.com/api/projects/<project>
# AZURE_FOUNDRY_OPENAI_ENDPOINT should be your OpenAI-compatible endpoint:
#   https://<resource>.openai.azure.com/
python run_pipeline.py
```

## Storage Authentication

The blob data source can use either a storage connection string or the
Azure AI Search service's managed identity.

### Option 1: Storage connection string

```bash
AZURE_STORAGE_AUTH_MODE=connection_string
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=<account>;AccountKey=<key>;EndpointSuffix=core.windows.net
```

### Option 2: Microsoft Entra auth via managed identity

```bash
AZURE_STORAGE_AUTH_MODE=managed_identity
AZURE_STORAGE_RESOURCE_ID=/subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.Storage/storageAccounts/<account>
```

When using managed identity, grant the Azure AI Search service identity the
`Storage Blob Data Reader` role on the storage account before running
`python run_pipeline.py --setup`.

If you use a user-assigned managed identity for the Azure AI Search service,
set the following and ensure the identity is attached to the search service:

```bash
AZURE_SEARCH_USER_ASSIGNED_IDENTITY_RESOURCE_ID=/subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.ManagedIdentity/userAssignedIdentities/<identity>
```

## Skills Toggle

This project uses a skillset to split documents and generate embeddings for
vector search. If you want text + semantic only (no embeddings), disable it:

```bash
ENABLE_SKILLS=false
```

With skills disabled, the indexer skips the skillset and the index contains
plain `content` and `title` fields. Vector search is not available in this mode.

## How Switching Works

The `MODEL_PROVIDER` toggle in `.env` controls which set of credentials
`config.py` loads. The Python code is **identical** for both — the
`openai.AzureOpenAI` client and the `AzureOpenAIEmbeddingSkill`
both accept any OpenAI-compatible endpoint.

| Setting | Endpoint format | Key source |
|---------|----------------|------------|
| `openai` | `https://<res>.openai.azure.com/` | OpenAI resource keys |
| `foundry` | `https://<res>.services.ai.azure.com/` | Foundry resource keys |

## CLI Commands

```bash
python run_pipeline.py              # Full pipeline + interactive Q&A
python run_pipeline.py --setup      # Steps 1-4 only
python run_pipeline.py --query      # Interactive Q&A only
python run_pipeline.py --reindex    # Reset + re-run indexer
```

## Client Guide

See `Demo_AI_Search_RAG_Guide.md` for a client-facing walkthrough.
