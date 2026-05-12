import pandas as pd
import faiss
import torch
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from extract_user_condition import extract_user_condition
from filter_policy import filter_policies


POLICY_CSV = "youth_policy_clean.csv"
FAISS_INDEX_FILE = "faiss_index.index"

EMBEDDING_MODEL_NAME = "jhgan/ko-sroberta-multitask"
LLM_MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct"


print("데이터 로드 중...")
policy_df = pd.read_csv(POLICY_CSV)
index = faiss.read_index(FAISS_INDEX_FILE)

device = "cuda" if torch.cuda.is_available() else "cpu"

print("임베딩 모델 로드 중...")
embedding_model = SentenceTransformer(
    EMBEDDING_MODEL_NAME,
    device=device
)

print("LLM 로드 중...")
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_use_double_quant=True,
    bnb_4bit_quant_type="nf4"
)

tokenizer = AutoTokenizer.from_pretrained(LLM_MODEL_NAME)

llm = AutoModelForCausalLM.from_pretrained(
    LLM_MODEL_NAME,
    quantization_config=bnb_config,
    device_map="auto"
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


def make_policy_context(top5_df):
    policy_texts = []

    for _, row in top5_df.iterrows():
        text = f"""
정책명: {row.get('policy_name', '')}
키워드: {row.get('keyword', '')}
분야: {row.get('category_large', '')} / {row.get('category_middle', '')}
정책 설명: {row.get('description', '')}
지원 내용: {row.get('support_content', '')}
신청 기간: {row.get('apply_period', '')}
신청 방법: {row.get('apply_method', '')}
신청 URL: {row.get('apply_url', '')}
참고 URL: {row.get('reference_url', '')}
추가 조건: {row.get('extra_condition', '')}
대상 조건: {row.get('target_condition', '')}
유사도 점수: {row.get('score', '')}
"""
        policy_texts.append(text)

    return "\n---\n".join(policy_texts)


def generate_answer(user_input, top5_df):
    policy_context = make_policy_context(top5_df)

    prompt = f"""
너는 청년정책 추천 도우미다.

사용자 질문:
{user_input}

LLM이 추출한 사용자 조건:
{user_condition}

아래는 검색 및 필터링된 청년정책 Top 5 정보다.

{policy_context}

답변 규칙:
1. 반드시 위 정책 데이터에 있는 내용만 사용해라.
2. 데이터에 없는 내용은 추측하지 마라.
3. 신청 가능 여부가 불명확하면 "추가 확인 필요"라고 써라.
4. 사용자가 바로 행동할 수 있도록 체크리스트를 포함해라.
5. 답변은 한국어로 작성해라.
6. 정책별로 핵심만 정리해라.

출력 형식:
1. 사용자 조건 요약
2. 추천 정책 Top 5
3. 정책별 추천 이유
4. 추가 확인 필요 조건
5. 바로 할 일 체크리스트
"""

    messages = [
        {
            "role": "system",
            "content": "너는 청년정책 추천을 도와주는 신중한 AI assistant다. 제공된 데이터 밖의 내용은 만들지 않는다."
        },
        {
            "role": "user",
            "content": prompt
        }
    ]

    input_text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )

    inputs = tokenizer(input_text, return_tensors="pt").to(llm.device)

    outputs = llm.generate(
        **inputs,
        max_new_tokens=900,
        temperature=0.2,
        do_sample=True,
        repetition_penalty=1.05
    )

    response = tokenizer.decode(outputs[0], skip_special_tokens=True)

    # 모델 출력에 프롬프트가 같이 섞여 나오면 마지막 assistant 답변 중심으로 보기 위한 단순 처리
    return response


def recommend_policy(user_input):
    # 1. 사용자 조건 추출
    user_condition = extract_user_condition(user_input)

    print("===== 추출된 사용자 조건 =====")
    print(user_condition)

    # 2. 전체 FAISS에서 넉넉하게 Top 30 검색
    top_candidates = search_top_policies(user_input, top_k=30)

    # 3. Top 30 안에서 사용자 조건 필터링
    filtered_top = filter_policies(user_condition, top_candidates)

    # 4. 필터링 결과가 너무 적으면 원래 Top 30 중 상위 5개 사용
    if len(filtered_top) >= 5:
        top5 = filtered_top.head(5)
    else:
        top5 = top_candidates.head(5)

    # 5. LLM 최종 답변 생성
    answer = generate_answer(user_input, user_condition, top5)

    return user_condition, top5, answer


if __name__ == "__main__":
    user_input = input("청년정책 질문을 입력하세요: ")

    top5, answer = recommend_policy(user_input)

    print("\n===== 검색된 Top 5 정책 =====")

    cols = [
        "policy_name",
        "keyword",
        "category_large",
        "category_middle",
        "apply_period",
        "score",
    ]

    available_cols = [col for col in cols if col in top5.columns]

    print(top5[available_cols].to_string(index=False))

    print("\n===== LLM 최종 답변 =====")
    print(answer)