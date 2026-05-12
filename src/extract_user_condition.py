import json
import re
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig


LLM_MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct"


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


def extract_json_from_text(text: str) -> dict:
    """
    LLM 출력에서 실제 JSON 객체를 찾아 dict로 변환한다.
    여러 개의 { }가 있어도 파싱 가능한 JSON 중 마지막 것을 사용한다.
    """
    decoder = json.JSONDecoder()
    json_candidates = []

    for i, char in enumerate(text):
        if char == "{":
            try:
                obj, end = decoder.raw_decode(text[i:])
                if isinstance(obj, dict):
                    json_candidates.append(obj)
            except json.JSONDecodeError:
                continue

    if not json_candidates:
        print("===== JSON 파싱 실패 원본 출력 =====")
        print(text)
        print("===================================")
        raise ValueError("LLM 출력에서 유효한 JSON 객체를 찾지 못했습니다.")

    return json_candidates[-1]


def extract_user_condition(user_input: str) -> dict:
    """
    사용자 자연어 입력에서 나이, 지역, 관심분야 등을 JSON으로 추출한다.
    """

    prompt = f"""
너는 청년정책 추천 시스템의 사용자 조건 추출기다.

사용자 입력:
{user_input}

반드시 JSON 객체 하나만 출력해라.
마크다운 코드블록(```json)을 쓰지 마라.
설명 문장, 예시, 해설을 출력하지 마라.
모르는 값은 null로 둬라.
관심분야는 배열로 작성해라.

관심분야 후보:
["주거", "취업", "창업", "교육", "금융", "복지", "문화", "기타"]

출력 형식:
{{
  "age": null,
  "region": null,
  "employment_status": null,
  "interests": [],
  "income": null,
  "housing_status": null,
  "unclear_conditions": []
}}

예시:
사용자 입력: "서울 사는 24살인데 월세 지원 받고 싶어"
출력:
{{
  "age": 24,
  "region": "서울",
  "employment_status": null,
  "interests": ["주거"],
  "income": null,
  "housing_status": "월세",
  "unclear_conditions": ["income", "employment_status"]
}}
"""

    messages = [
        {
            "role": "system",
            "content": "너는 사용자 입력에서 청년정책 추천에 필요한 조건만 JSON으로 추출하는 assistant다."
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
        max_new_tokens=300,
        do_sample=False,
        repetition_penalty=1.05
    )

    response = tokenizer.decode(outputs[0], skip_special_tokens=True)

    user_condition = extract_json_from_text(response)

    return user_condition


if __name__ == "__main__":
    test_input = "서울 사는 24살인데 주거 정책이나 월세 지원 받고 싶어"

    result = extract_user_condition(test_input)

    print(result)