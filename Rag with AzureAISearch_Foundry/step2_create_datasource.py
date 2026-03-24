"""
step2_create_datasource.py - Create data source connection to Blob.

CHANGE: run() takes IndexConfig - uses idx_cfg.container_name
and idx_cfg.datasource_name instead of config.CONTAINER_NAME.
"""

from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexerClient
from azure.search.documents.indexes.models import (
    SearchIndexerDataContainer,
    SearchIndexerDataSourceConnection,
    SearchIndexerDataUserAssignedIdentity,
)

import config
from config import IndexConfig


def run(idx_cfg: IndexConfig):
    """Create one data source. Called once per IndexConfig."""
    indexer_client = SearchIndexerClient(
        endpoint=config.SEARCH_ENDPOINT,
        credential=AzureKeyCredential(config.SEARCH_ADMIN_KEY),
    )
    container = SearchIndexerDataContainer(name=idx_cfg.container_name)
    identity = None
    if (
        config.STORAGE_AUTH_MODE == "managed_identity"
        and config.STORAGE_USER_ASSIGNED_IDENTITY_RESOURCE_ID
    ):
        identity = SearchIndexerDataUserAssignedIdentity(
            resource_id=config.STORAGE_USER_ASSIGNED_IDENTITY_RESOURCE_ID
        )

    data_source = SearchIndexerDataSourceConnection(
        name=idx_cfg.datasource_name,
        type="azureblob",
        connection_string=config.STORAGE_CONNECTION_STRING,
        container=container,
        description=f"Blob container '{idx_cfg.container_name}' for index '{idx_cfg.index_name}'",
        identity=identity,
    )
    result = indexer_client.create_or_update_data_source_connection(data_source)
    print(
        f"  Data source '{result.name}' -> container '{idx_cfg.container_name}' "
        f"({config.STORAGE_AUTH_MODE})"
    )
    return result
