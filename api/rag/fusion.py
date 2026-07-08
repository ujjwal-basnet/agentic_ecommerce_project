"""Reciprocal Rank Fusion to combine results from multiple RAG paths."""


def reciprocal_rank_fusion(
    result_lists: list[list[dict]],
    k: int = 60,
    top_n: int = 8,
) -> list[dict]:
    """
    Combine multiple ranked result lists using Reciprocal Rank Fusion (RRF).

    RRF score = sum(1 / (k + rank_i)) for each list where the item appears.
    k=60 is the standard constant that prevents high-ranked items from dominating.

    Deduplicates by product_id, summing scores for items in multiple lists.
    Returns top_n results sorted by descending fused score.

    Each result dict must have a "product_id" key for deduplication.
    The output dicts have their "score" updated to the fused RRF score
    and "retrieval_method" set to "fused".
    """
    if not result_lists:
        return []

    # Map: product_id -> (accumulated_score, best_result_dict)
    fused: dict[int, tuple[float, dict]] = {}

    for result_list in result_lists:
        if not result_list:
            continue
        for rank, result in enumerate(result_list):
            product_id = result["product_id"]
            rrf_score = 1.0 / (k + rank + 1)

            if product_id in fused:
                existing_score, existing_result = fused[product_id]
                fused[product_id] = (existing_score + rrf_score, existing_result)
            else:
                fused[product_id] = (rrf_score, result.copy())

    # Sort by descending fused score
    ranked = sorted(fused.values(), key=lambda x: x[0], reverse=True)

    # Return top_n with updated score and retrieval_method
    results = []
    for score, result in ranked[:top_n]:
        result["score"] = score
        result["retrieval_method"] = "fused"
        results.append(result)

    return results
