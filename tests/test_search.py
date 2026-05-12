import pandas as pd
import faiss
import torch
from sentence_transformers import SentenceTransformer


POLICY_CSV = "youth_policy_clean.csv"
FAISS_INDEX_FILE = "faiss_index.index"
EMBEDDING_MODEL_NAME = "jhgan/ko-sroberta-multitask"


policy_df = pd.read_csv(POLICY_CSV)
index = faiss.read_index(FAISS_INDEX_FILE)

device = "cuda" if torch.cuda.is_available() else "cpu"

embedding_model = SentenceTransformer(
    EMBEDDING_MODEL_NAME,
    device=device
)


def search_top5_policies(user_input, top_k=5):
    query_embedding = embedding_model.encode(
        [user_input],
        convert_to_numpy=True
    ).astype("float32")

    faiss.normalize_L2(query_embedding)

    scores, indices = index.search(query_embedding, top_k)

    top5 = policy_df.iloc[indices[0]].copy()
    top5["score"] = scores[0]

    return top5


if __name__ == "__main__":
    user_input = "서울 사는 25살 취준생인데 월세 지원이나 취업 지원 정책이 궁금해요."

    top5 = search_top5_policies(user_input)

    cols = [
        "policy_name",
        "keyword",
        "category_large",
        "category_middle",
        "support_content",
        "apply_period",
        "score",
    ]

    available_cols = [col for col in cols if col in top5.columns]

    print(top5[available_cols].to_string(index=False))