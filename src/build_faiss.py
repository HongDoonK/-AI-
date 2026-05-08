from pathlib import Path
import pandas as pd
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer


POLICY_CSV_PATH = Path("data/processed/youth_policy_clean.csv")
INDEX_DIR = Path("data/index")
FAISS_INDEX_PATH = INDEX_DIR / "faiss_index.index"
EMBEDDINGS_PATH = INDEX_DIR / "policy_embeddings.npy"

MODEL_NAME = "jhgan/ko-sroberta-multitask"


def build_faiss_index():
    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    policy_df = pd.read_csv(POLICY_CSV_PATH).fillna("")

    if "search_text" not in policy_df.columns:
        raise ValueError("youth_policy_clean.csv에 search_text 컬럼이 없습니다.")

    policy_texts = policy_df["search_text"].astype(str).tolist()

    print("임베딩 모델 로딩 중:", MODEL_NAME)
    model = SentenceTransformer(MODEL_NAME)

    print("정책 임베딩 생성 중...")
    embeddings = model.encode(
        policy_texts,
        convert_to_numpy=True,
        show_progress_bar=True,
    )

    embeddings = embeddings.astype("float32")

    # 코사인 유사도 검색을 위해 L2 정규화
    faiss.normalize_L2(embeddings)

    np.save(EMBEDDINGS_PATH, embeddings)

    embedding_dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(embedding_dim)
    index.add(embeddings)

    faiss.write_index(index, str(FAISS_INDEX_PATH))

    print("policy_embeddings.npy 생성 완료:", EMBEDDINGS_PATH)
    print("faiss_index.index 생성 완료:", FAISS_INDEX_PATH)
    print("임베딩 shape:", embeddings.shape)
    print("FAISS 벡터 개수:", index.ntotal)


if __name__ == "__main__":
    build_faiss_index()