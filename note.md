embeddings/ is the brain — it owns the vector store (ChromaDB), the embedding pipeline, and the AI metadata enricher (auto-tags colour, style, material from product name/description). Both customer search_tool and owner product_tool import from it. owner_tools/ and tools/ are kept strictly separate — owner tools (Facebook API, analytics SQL) should never be callable by the customer agent.

