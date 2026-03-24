# Client Guide: Azure AI Search RAG with Foundry (Entra ID)

Page 1 of 3

## 1. Solution Overview

This solution builds a Retrieval Augmented Generation (RAG) workflow using:
- Azure Blob Storage for document storage
- Azure AI Search for indexing and retrieval
- Azure AI Foundry (OpenAI-compatible endpoint) for embeddings and chat

High-level flow:
1. Documents are stored in Blob Storage.
2. An Azure AI Search indexer reads the documents and creates a search index.
3. The app runs hybrid search (keyword + vector + semantic) against the index.
4. The top results are injected into the prompt for the Foundry-deployed model.

## 2. Why Blob Storage + Indexer

Blob Storage is:
- Cost-effective for large document collections.
- Natively supported by Azure AI Search indexers.
- Compatible with managed identity, access control, and scalable indexing.

Indexers reduce custom ETL work. Azure AI Search can:
- Pull content directly from Blob Storage.
- Split and enrich text using skillsets.
- Keep content fresh via incremental indexing.

## 3. Permissions Required

At minimum:
- Azure AI Search admin key (or Search service RBAC) for indexing and querying.
- Storage access for the Search service identity:
  - Role: `Storage Blob Data Reader` on the storage account.
- OpenAI/Foundry access for the Search service identity:
  - Role: `Cognitive Services OpenAI User` on the OpenAI/Foundry resource.

When using system-assigned managed identity:
- Enable the managed identity on the Search service.
- Assign the roles above to that identity.

## 4. Code Walkthrough (This Repo)

Key files:
- `config.py`: Loads endpoints and credentials. Foundry uses Entra ID auth.
- `step1_create_index.py`: Creates the search index (schema + vector/semantic).
- `step2_create_datasource.py`: Creates the Blob data source.
- `step3_create_skillset.py`: Creates skillset for splitting and embeddings.
- `step4_create_indexer.py`: Creates and runs the indexer.
- `step5_query_and_rag.py`: Runs hybrid search and generates answers.

Minimal `.env` (redacted):
```env
MODEL_PROVIDER=foundry
AZURE_FOUNDRY_ENDPOINT=https://<resource>.services.ai.azure.com/api/projects/<project>
AZURE_FOUNDRY_OPENAI_ENDPOINT=https://<resource>.openai.azure.com/
AZURE_FOUNDRY_EMBEDDING_DEPLOYMENT=<deployment-name>
AZURE_FOUNDRY_CHAT_DEPLOYMENT=<deployment-name>

AZURE_SEARCH_ENDPOINT=https://<search>.search.windows.net
AZURE_SEARCH_ADMIN_KEY=<key>

AZURE_STORAGE_AUTH_MODE=managed_identity
AZURE_STORAGE_RESOURCE_ID=/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.Storage/storageAccounts/<account>
```

## 5. How RAG Is Implemented

In `step5_query_and_rag.py`:
- The app embeds the question with the Foundry embedding model.
- It executes semantic + vector search in Azure AI Search.
- It builds a context window from the best chunks.
- It calls the Foundry chat model with the context and question.

This yields responses grounded in indexed content.

\f

Page 2 of 3

## 6. Step-by-Step: Create Index and Indexer (Code Path)

1. Configure `.env` values.
2. Run setup:
   ```powershell
   python run_pipeline.py --setup
   ```
3. This executes, in order:
   - `step1_create_index.py` (index)
   - `step2_create_datasource.py` (data source)
   - `step3_create_skillset.py` (skillset)
   - `step4_create_indexer.py` (indexer)

4. Indexer starts and reports success/fail counts.

## 7. Step-by-Step: Create Indexer via Azure Portal

1. Open your Azure AI Search service in the portal.
2. Go to **Data sources**:
   - Create a data source of type **Azure Blob Storage**.
   - Choose managed identity for auth.
3. Go to **Skillsets** (if using vector embeddings):
   - Add a skillset with a split skill and OpenAI embedding skill.
4. Go to **Indexes**:
   - Create an index with fields for text, vectors, and metadata.
5. Go to **Indexers**:
   - Create an indexer that links the data source, index, and skillset.
   - Save and run the indexer.
6. Check status in the indexer run history.

## 8. Run the Indexer Manually

Use the CLI in this repo:
```powershell
python run_pipeline.py --reindex
```

## 9. Run Step 5 Query + RAG

Interactive Q&A:
```powershell
python run_pipeline.py --query
```

Sample question:
```
What locations are mentioned in the documents?
```

The app will retrieve top chunks and generate a grounded answer.

\f

Page 3 of 3

## 10. Foundry IQ: Add Knowledge and Use It for RAG

Foundry IQ (preview) provides a managed knowledge base with:
- Knowledge sources (Blob Storage, SharePoint, OneLake, web, etc.).
- Agentic retrieval that plans and executes multi-step queries.
- Permission-aware retrieval and citations.
- Integration with Azure AI Search for indexing and retrieval.

### Step-by-step: Add Knowledge in Foundry IQ

1. Open the Microsoft Foundry portal.
2. Create or select a project.
3. Go to **Build** > **Knowledge**.
4. Create a **Knowledge base**.
5. Add a **Knowledge source** (Blob, SharePoint, OneLake, web).
6. Configure retrieval behavior and indexing schedule.
7. Save the knowledge base.

### Use Foundry IQ with Your RAG App

Option A: Use Foundry IQ retrieval for context, then call the same Foundry model.

Pseudo-code:
```python
# Pseudocode: adapt to the Agentic SDK you use
kb_results = foundry_knowledge.retrieve(query="your question", top_k=5)
context = "\n\n".join([r.text for r in kb_results])

response = openai_client.chat.completions.create(
    model=CHAT_DEPLOYMENT,
    messages=[
        {"role": "system", "content": "Answer only from context."},
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: ..."},
    ],
)
```

Option B: Use Foundry IQ directly inside an agent (Agentic SDK)
- Attach the knowledge base to the agent.
- The agent calls Foundry IQ automatically for retrieval.
- The agent returns answers with citations from the knowledge base.

## 11. Notes for Client

Foundry IQ is preview and UI labels may change by tenant. Use the Foundry
portal help for the most current steps. If needed, the CSA can provide
tenant-specific documentation.
