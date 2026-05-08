from pathlib import Path
import pandas as pd
import faiss
from sentence_transformers import SentenceTransformer


POLICY_CSV_PATH = Path("data/processed/youth_policy_clean.csv")
FAISS_INDEX_PATH = Path("data/index/faiss_index.index")

MODEL_NAME = "jhgan/ko-sroberta-multitask"


_model = None
_index = None
_policy_df = None


def get_model():
    global _model

    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)

    return _model


def get_index():
    global _index

    if _index is None:
        _index = faiss.read_index(str(FAISS_INDEX_PATH))

    return _index


def get_policy_df():
    global _policy_df

    if _policy_df is None:
        _policy_df = pd.read_csv(POLICY_CSV_PATH).fillna("")

    return _policy_df


def search_top_policies(
    user_input: str,
    candidate_policies: pd.DataFrame | None = None,
    top_k: int = 5,
    search_k: int = 50,
) -> pd.DataFrame:
    """
    전체 FAISS 인덱스에서 search_k개를 찾은 뒤,
    candidate_policies 안에 포함되는 정책만 남겨 top_k 반환.
    """
    model = get_model()
    index = get_index()
    policy_df = get_policy_df()

    query_embedding = model.encode(
        [user_input],
        convert_to_numpy=True,
    ).astype("float32")

    faiss.normalize_L2(query_embedding)

    max_search_k = min(search_k, len(policy_df))
    scores, indices = index.search(query_embedding, max_search_k)

    result_df = policy_df.iloc[indices[0]].copy()
    result_df["score"] = scores[0]

    if candidate_policies is not None and len(candidate_policies) > 0:
        if "policy_id" in candidate_policies.columns and "policy_id" in result_df.columns:
            candidate_ids = set(candidate_policies["policy_id"].astype(str))
            result_df = result_df[result_df["policy_id"].astype(str).isin(candidate_ids)]

    if len(result_df) < top_k:
        # 후보 필터 때문에 너무 적게 나오면 전체 검색 결과 사용
        result_df = policy_df.iloc[indices[0]].copy()
        result_df["score"] = scores[0]

    return result_df.head(top_k).reset_index(drop=True)


if __name__ == "__main__":
    sample = "서울 사는 25살 취준생인데 월세 지원이나 취업 지원 정책이 궁금해요."
    result = search_top_policies(sample)

    cols = [
        "policy_name",
        "keyword",
        "category_large",
        "category_middle",
        "support_content",
        "apply_period",
        "score",
    ]

    print(result[[col for col in cols if col in result.columns]])