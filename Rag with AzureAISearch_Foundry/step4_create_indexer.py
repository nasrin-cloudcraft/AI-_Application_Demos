"""
step4_create_indexer.py — Create and run the indexer.

CHANGE: all functions take IndexConfig — use idx_cfg.indexer_name,
idx_cfg.datasource_name, idx_cfg.index_name, idx_cfg.skillset_name.
"""

import time

from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexerClient
from azure.search.documents.indexes.models import (
    SearchIndexer, FieldMapping,
    FieldMappingFunction,
    IndexingParameters, IndexingParametersConfiguration,
)

import config
from config import IndexConfig


def get_indexer_client() -> SearchIndexerClient:
    return SearchIndexerClient(
        endpoint=config.SEARCH_ENDPOINT,
        credential=AzureKeyCredential(config.SEARCH_ADMIN_KEY),
    )


def create_indexer(idx_cfg: IndexConfig) -> SearchIndexer:
    field_mappings = [
        FieldMapping(source_field_name="metadata_storage_name", target_field_name="title"),
    ]
    if not config.ENABLE_SKILLS:
        field_mappings.insert(
            0,
            FieldMapping(
                source_field_name="metadata_storage_path",
                target_field_name="id",
                mapping_function=FieldMappingFunction(name="base64Encode"),
            ),
        )

    indexer_kwargs = dict(
        name=idx_cfg.indexer_name,
        description=f"Indexer for '{idx_cfg.index_name}' from container '{idx_cfg.container_name}'",
        data_source_name=idx_cfg.datasource_name,
        target_index_name=idx_cfg.index_name,
        field_mappings=field_mappings,
        parameters=IndexingParameters(
            batch_size=10,
            configuration=IndexingParametersConfiguration(
                data_to_extract="contentAndMetadata",
                parsing_mode="text",
                indexed_file_name_extensions=".txt",
                query_timeout=None,
            ),
        ),
    )

    if config.ENABLE_SKILLS:
        indexer_kwargs["skillset_name"] = idx_cfg.skillset_name

    indexer = SearchIndexer(**indexer_kwargs)
    result = get_indexer_client().create_or_update_indexer(indexer)
    print(f"  Indexer '{result.name}' created/updated.")
    return result


def trigger_indexer(idx_cfg: IndexConfig):
    client = get_indexer_client()
    try:
        client.run_indexer(idx_cfg.indexer_name)
        print(f"  Indexer '{idx_cfg.indexer_name}' triggered.")
    except Exception as exc:  # ResourceExistsError when already running
        message = str(exc)
        if "Another indexer invocation is currently in progress" in message:
            print(f"  Indexer '{idx_cfg.indexer_name}' already running.")
            return
        raise


def reset_and_run_indexer(idx_cfg: IndexConfig):
    client = get_indexer_client()
    print(f"  Resetting '{idx_cfg.indexer_name}'...")
    client.reset_indexer(idx_cfg.indexer_name)
    client.run_indexer(idx_cfg.indexer_name)
    print(f"  Indexer '{idx_cfg.indexer_name}' triggered for full re-index.")


def wait_for_indexer(idx_cfg: IndexConfig, timeout_seconds: int = 300, poll_interval: int = 10):
    print(f"  Waiting for '{idx_cfg.indexer_name}' (timeout: {timeout_seconds}s)...")
    elapsed = 0
    while elapsed < timeout_seconds:
        status = get_indexer_client().get_indexer_status(idx_cfg.indexer_name)
        last_result = status.last_result
        if last_result is not None:
            run_status = last_result.status
            print(f"  [{elapsed:>3}s] {idx_cfg.indexer_name}: {run_status} | "
                  f"ok={last_result.item_count} fail={last_result.failed_item_count}")
            if run_status in ("success", "transientFailure"):
                if last_result.errors:
                    for err in last_result.errors[:5]:
                        error_text = (
                            getattr(err, "error_message", None)
                            or getattr(err, "message", None)
                            or str(err)
                        )
                        print(f"    ERROR: {error_text}")
                return last_result
        time.sleep(poll_interval)
        elapsed += poll_interval
    print(f"  Timed out for '{idx_cfg.indexer_name}'.")
    return None


def run(idx_cfg: IndexConfig):
    """Create and run one indexer. Called once per IndexConfig."""
    create_indexer(idx_cfg)
    time.sleep(5)
    trigger_indexer(idx_cfg)
    time.sleep(2)
    result = wait_for_indexer(idx_cfg, timeout_seconds=300)
    if result and result.status == "success":
        print(f"  SUCCESS: {result.item_count} doc(s) indexed into '{idx_cfg.index_name}'.")
    return result
