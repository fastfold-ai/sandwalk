"""
protein.embed: ESM-2 protein sequence embeddings.

Split from tools/protein.py.
"""

from tools import registry


@registry.register(
    name="protein.embed",
    description="Generate protein sequence embeddings using ESM-2 (local) or ESMFold API",
    category="protein",
    parameters={
        "sequence": "Amino acid sequence (single-letter code, e.g. 'MKTL...')",
        "model": "Embedding model: 'esm2' (default) or 'esm2_small'",
    },
    usage_guide="You have a protein sequence and need a numerical representation for downstream analysis (similarity, clustering, property prediction). ESM-2 embeddings capture evolutionary and structural information. Use for comparing proteins, predicting function, or as features for ML models.",
)
def embed(sequence: str, model: str = "esm2", **kwargs) -> dict:
    """Generate ESM-2 protein embeddings.

    If torch + fair-esm are installed, generates embeddings locally using
    esm2_t33_650M_UR50D (or esm2_t6_8M_UR50D for 'esm2_small').
    Otherwise, returns an error with install instructions.
    """
    import numpy as np

    # Validate sequence
    valid_aa = set("ACDEFGHIKLMNPQRSTVWY")
    sequence = sequence.strip().upper()
    invalid_chars = set(sequence) - valid_aa - {"X", "U", "B", "Z", "O", "J"}
    if invalid_chars:
        return {
            "error": f"Invalid amino acid characters: {invalid_chars}",
            "summary": f"Sequence contains invalid characters: {invalid_chars}",
        }

    if len(sequence) == 0:
        return {"error": "Empty sequence provided", "summary": "No sequence to embed"}

    if len(sequence) > 2048:
        return {
            "error": f"Sequence too long ({len(sequence)} aa). Max 2048 for ESM-2 t33.",
            "summary": f"Sequence length {len(sequence)} exceeds limit of 2048 residues",
        }

    # Try local ESM-2
    try:
        import esm
        import torch

        if model == "esm2_small":
            esm_model, alphabet = esm.pretrained.esm2_t6_8M_UR50D()
            repr_layer = 6
            embed_dim = 320
        else:
            esm_model, alphabet = esm.pretrained.esm2_t33_650M_UR50D()
            repr_layer = 33
            embed_dim = 1280

        esm_model.eval()
        batch_converter = alphabet.get_batch_converter()

        data = [("protein", sequence)]
        batch_labels, batch_strs, batch_tokens = batch_converter(data)

        with torch.no_grad():
            results = esm_model(batch_tokens, repr_layers=[repr_layer], return_contacts=False)

        # Extract representations
        token_repr = results["representations"][repr_layer]
        # Remove BOS and EOS tokens: [0, 1:-1]
        per_residue = token_repr[0, 1:len(sequence) + 1].numpy()
        mean_pooled = per_residue.mean(axis=0)

        return {
            "summary": (
                f"ESM-2 embedding for sequence ({len(sequence)} aa): "
                f"{embed_dim}-dim representation generated"
            ),
            "sequence_length": len(sequence),
            "embedding_dim": embed_dim,
            "model": model,
            "embedding_shape": list(per_residue.shape),
            "mean_embedding_stats": {
                "mean": round(float(np.mean(mean_pooled)), 6),
                "std": round(float(np.std(mean_pooled)), 6),
                "min": round(float(np.min(mean_pooled)), 6),
                "max": round(float(np.max(mean_pooled)), 6),
                "norm": round(float(np.linalg.norm(mean_pooled)), 4),
            },
            "per_residue_stats": {
                "mean_norm": round(float(np.mean(np.linalg.norm(per_residue, axis=1))), 4),
                "shape": list(per_residue.shape),
            },
            "computed_locally": True,
        }

    except ImportError:
        return {
            "error": (
                "ESM-2 requires torch and fair-esm. Install with:\n"
                "  pip install torch fair-esm\n"
                "For GPU support: pip install torch --index-url https://download.pytorch.org/whl/cu118"
            ),
            "summary": (
                f"Cannot generate embedding for {len(sequence)} aa sequence — "
                "torch and fair-esm not installed"
            ),
            "sequence_length": len(sequence),
            "computed_locally": False,
        }
