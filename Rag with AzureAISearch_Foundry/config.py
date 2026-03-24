"""
config.py — Configuration for 2 indexes (one per blob container).

Supports:
  - MODEL_PROVIDER=openai  → API key auth
  - MODEL_PROVIDER=foundry → DefaultAzureCredential (Entra ID)

For Foundry with Entra ID: run `az login` first.
"""

import os
import sys
from dataclasses import dataclass
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

load_dotenv()


def _require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        print(f"ERROR: Missing required environment variable: {key}")
        print(f"       Copy .env.example to .env and fill in your values.")
        sys.exit(1)
    return val


def _normalize_storage_resource_id(value: str) -> tuple[str, str]:
    raw = value.strip().rstrip(";")
    if raw.lower().startswith("resourceid="):
        raw = raw.split("=", 1)[1]
    resource_id = raw.rstrip("/")
    connection_string = f"ResourceId={resource_id}/;"
    return resource_id, connection_string


# --------------- Model Provider Toggle ---------------
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "openai").lower().strip()
if MODEL_PROVIDER not in ("openai", "foundry"):
    print(f"ERROR: MODEL_PROVIDER must be 'openai' or 'foundry', got '{MODEL_PROVIDER}'")
    sys.exit(1)

# Toggle for skillset-based enrichment (split + embeddings).
ENABLE_SKILLS = os.getenv("ENABLE_SKILLS", "true").lower().strip() in ("1", "true", "yes", "y")

# --------------- Azure AI Search (shared) ---------------
SEARCH_ENDPOINT = _require("AZURE_SEARCH_ENDPOINT")
SEARCH_ADMIN_KEY = _require("AZURE_SEARCH_ADMIN_KEY")

# --------------- Azure Blob Storage (shared) ---------------
STORAGE_AUTH_MODE = os.getenv("AZURE_STORAGE_AUTH_MODE", "connection_string").lower().strip()
if STORAGE_AUTH_MODE not in ("connection_string", "managed_identity"):
    print(
        "ERROR: AZURE_STORAGE_AUTH_MODE must be "
        "'connection_string' or 'managed_identity', "
        f"got '{STORAGE_AUTH_MODE}'"
    )
    sys.exit(1)

STORAGE_CONNECTION_STRING: str = ""
STORAGE_RESOURCE_ID: str | None = None
STORAGE_USER_ASSIGNED_IDENTITY_RESOURCE_ID: str | None = None

if STORAGE_AUTH_MODE == "connection_string":
    STORAGE_CONNECTION_STRING = _require("AZURE_STORAGE_CONNECTION_STRING")
else:
    storage_resource_value = os.getenv("AZURE_STORAGE_RESOURCE_ID", "").strip()
    if not storage_resource_value:
        legacy_value = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "").strip()
        if legacy_value.lower().startswith("resourceid="):
            storage_resource_value = legacy_value
        else:
            print("ERROR: Missing required environment variable: AZURE_STORAGE_RESOURCE_ID")
            print(
                "       For managed identity storage auth, set "
                "AZURE_STORAGE_RESOURCE_ID to the Azure Storage resource ID."
            )
            sys.exit(1)

    STORAGE_RESOURCE_ID, STORAGE_CONNECTION_STRING = _normalize_storage_resource_id(
        storage_resource_value
    )
    STORAGE_USER_ASSIGNED_IDENTITY_RESOURCE_ID = os.getenv(
        "AZURE_SEARCH_USER_ASSIGNED_IDENTITY_RESOURCE_ID", ""
    ).strip() or None

# --------------- Model Configuration (provider-aware, shared) ---------------
# These will be set below — declared here so all code can reference them.
MODEL_ENDPOINT: str = ""
MODEL_API_KEY: str | None = None
MODEL_API_VERSION: str = ""
MODEL_CREDENTIAL = None          # DefaultAzureCredential for Foundry
MODEL_TOKEN_PROVIDER = None      # Token provider for AzureOpenAI client
EMBEDDING_DEPLOYMENT: str = ""
EMBEDDING_MODEL_NAME: str = ""
EMBEDDING_DIMENSIONS: int = 1536
CHAT_DEPLOYMENT: str = ""

# The OpenAI-compatible base endpoint for the skillset (no /api/projects/... suffix)
SKILLSET_RESOURCE_URL: str = ""

if MODEL_PROVIDER == "openai":
    MODEL_ENDPOINT = _require("AZURE_OPENAI_ENDPOINT")
    MODEL_API_KEY = _require("AZURE_OPENAI_API_KEY")
    MODEL_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01")
    EMBEDDING_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large")
    EMBEDDING_MODEL_NAME = os.getenv("AZURE_OPENAI_EMBEDDING_MODEL_NAME", "text-embedding-3-large")
    EMBEDDING_DIMENSIONS = int(os.getenv("AZURE_OPENAI_EMBEDDING_DIMENSIONS", "1536"))
    CHAT_DEPLOYMENT = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o")
    SKILLSET_RESOURCE_URL = MODEL_ENDPOINT

else:
    # ── Azure AI Foundry with Entra ID (DefaultAzureCredential) ──
    #
    # AZURE_FOUNDRY_ENDPOINT can be either:
    #   - Project endpoint: https://xxx.services.ai.azure.com/api/projects/yyy
    #   - Base endpoint:    https://xxx.services.ai.azure.com/
    #
    # The AzureOpenAI SDK client and the embedding skill both use the
    # OpenAI-compatible endpoint: https://xxx.openai.azure.com/
    #
    # We also need AZURE_FOUNDRY_OPENAI_ENDPOINT for the skillset, because
    # the skillset calls the OpenAI embedding API directly.

    _foundry_endpoint = _require("AZURE_FOUNDRY_ENDPOINT").rstrip("/")

    # Extract the base resource endpoint (strip /api/projects/... if present)
    if "/api/projects/" in _foundry_endpoint:
        _foundry_base = _foundry_endpoint.split("/api/projects/")[0]
    else:
        _foundry_base = _foundry_endpoint

    # The skillset needs an OpenAI-compatible endpoint.
    # If you have a separate Azure OpenAI resource backing Foundry, set this.
    # Otherwise we derive it from the Foundry base URL.
    SKILLSET_RESOURCE_URL = os.getenv(
        "AZURE_FOUNDRY_OPENAI_ENDPOINT",
        _foundry_base.replace(".services.ai.azure.com", ".openai.azure.com"),
    )
    MODEL_ENDPOINT = SKILLSET_RESOURCE_URL

    MODEL_API_KEY = None   # No API key — using Entra ID
    MODEL_API_VERSION = os.getenv("AZURE_FOUNDRY_API_VERSION", "2024-10-21")
    EMBEDDING_DEPLOYMENT = os.getenv("AZURE_FOUNDRY_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")
    EMBEDDING_MODEL_NAME = os.getenv("AZURE_FOUNDRY_EMBEDDING_MODEL_NAME", "text-embedding-3-small")
    EMBEDDING_DIMENSIONS = int(os.getenv("AZURE_FOUNDRY_EMBEDDING_DIMENSIONS", "1536"))
    CHAT_DEPLOYMENT = os.getenv("AZURE_FOUNDRY_CHAT_DEPLOYMENT", "gpt-4o")

    # Set up DefaultAzureCredential (uses az login, managed identity, etc.)
    MODEL_CREDENTIAL = DefaultAzureCredential()
    MODEL_TOKEN_PROVIDER = get_bearer_token_provider(
        MODEL_CREDENTIAL, "https://cognitiveservices.azure.com/.default"
    )


# --------------- Per-Index Configuration (NEW) ---------------

@dataclass
class IndexConfig:
    """Configuration for one index + its blob container."""
    index_name: str
    container_name: str

    @property
    def datasource_name(self) -> str:
        return f"{self.index_name}-datasource"

    @property
    def skillset_name(self) -> str:
        return f"{self.index_name}-skillset"

    @property
    def indexer_name(self) -> str:
        return f"{self.index_name}-indexer"


# Build the list of 2 indexes from .env
INDEXES: list[IndexConfig] = [
    IndexConfig(
        index_name=_require("INDEX_1_NAME"),
        container_name=_require("CONTAINER_1_NAME"),
    ),
    IndexConfig(
        index_name=_require("INDEX_2_NAME"),
        container_name=_require("CONTAINER_2_NAME"),
    ),
]


def print_config():
    provider_label = "Azure OpenAI" if MODEL_PROVIDER == "openai" else "Azure AI Foundry"
    auth_label = "API Key" if MODEL_API_KEY else "Entra ID (DefaultAzureCredential)"
    storage_auth_label = (
        "Connection String / Account Key"
        if STORAGE_AUTH_MODE == "connection_string"
        else "Managed Identity (Microsoft Entra ID)"
    )
    skills_label = "Enabled" if ENABLE_SKILLS else "Disabled"
    print("=" * 60)
    print("CONFIGURATION")
    print("=" * 60)
    print(f"  Model provider   : {provider_label}")
    print(f"  Authentication   : {auth_label}")
    print(f"  Storage auth     : {storage_auth_label}")
    print(f"  Skills           : {skills_label}")
    print(f"  Model endpoint   : {MODEL_ENDPOINT}")
    print(f"  Skillset endpoint: {SKILLSET_RESOURCE_URL}")
    print(f"  Search endpoint  : {SEARCH_ENDPOINT}")
    print(f"  Embedding model  : {EMBEDDING_DEPLOYMENT} ({EMBEDDING_DIMENSIONS}d)")
    print(f"  Chat model       : {CHAT_DEPLOYMENT}")
    print()
    for i, idx in enumerate(INDEXES, 1):
        print(f"  Index {i}:")
        print(f"    Name       : {idx.index_name}")
        print(f"    Container  : {idx.container_name}")
        print(f"    Datasource : {idx.datasource_name}")
        print(f"    Skillset   : {idx.skillset_name}")
        print(f"    Indexer    : {idx.indexer_name}")
    print("=" * 60)
