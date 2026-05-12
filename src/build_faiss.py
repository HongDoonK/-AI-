import pandas as pd
import numpy as np
import faiss
import torch
from sentence_transformers import SentenceTransformer


CSV_FILE = "youth_policy_clean.csv"
EMBEDDING_FILE = "policy_embeddings.npy"
FAISS_INDEX_FILE = "faiss_index.index"

EMBEDDING_MODEL_NAME = "jhgan/ko-sroberta-multitask"


def main():
    print("GPU 사용 가능 여부:", torch.cuda.is_available())

    device = "cuda" if torch.cuda.is_available() else "cpu"

    policy_df = pd.read_csv(CSV_FILE)

    if "search_text" not in policy_df.columns:
        raise ValueError("youth_policy_clean.csv에 search_text 컬럼이 없습니다.")

    policy_df["search_text"] = policy_df["search_text"].fillna("").astype(str)

    print("정책 개수:", len(policy_df))
    print("임베딩 모델 로드 중...")

    model = SentenceTransformer(
        EMBEDDING_MODEL_NAME,
        device=device
    )

    policy_texts = policy_df["search_text"].tolist()

    print("정책 텍스트 임베딩 생성 중...")

    policy_embeddings = model.encode(
        policy_texts,
        convert_to_numpy=True,
        show_progress_bar=True,
        batch_size=64
    )

    policy_embeddings = policy_embeddings.astype("float32")

    # 코사인 유사도 검색을 위해 L2 정규화
    faiss.normalize_L2(policy_embeddings)

    np.save(EMBEDDING_FILE, policy_embeddings)

    embedding_dim = policy_embeddings.shape[1]

    index = faiss.IndexFlatIP(embedding_dim)
    index.add(policy_embeddings)

    faiss.write_index(index, FAISS_INDEX_FILE)

    print("policy_embeddings.npy 생성 완료")
    print("임베딩 shape:", policy_embeddings.shape)
    print("faiss_index.index 생성 완료")
    print("FAISS 벡터 개수:", index.ntotal)


if __name__ == "__main__":
    main()