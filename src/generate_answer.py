import os
import pandas as pd


def policy_rows_to_text(top_policies: pd.DataFrame) -> str:
    lines = []

    for idx, row in top_policies.iterrows():
        lines.append(f"""
[{idx + 1}] {row.get("policy_name", "")}
- 키워드: {row.get("keyword", "")}
- 분야: {row.get("category_large", "")} / {row.get("category_middle", "")}
- 설명: {row.get("description", "")}
- 지원내용: {row.get("support_content", "")}
- 신청기간: {row.get("apply_period", "")}
- 사업기간: {row.get("business_period_text", "")}
- 신청방법: {row.get("apply_method", "")}
- 신청URL: {row.get("apply_url", "")}
- 참고URL: {row.get("reference_url", "")}
- 나이조건: {row.get("min_age", "")}세 ~ {row.get("max_age", "")}세
- 소득조건: {row.get("income_condition", "")}
- 추가조건: {row.get("extra_condition", "")}
- 참여제한/대상조건: {row.get("target_condition", "")}
- 유사도점수: {row.get("score", "")}
""")

    return "\n".join(lines)


def template_answer(user_input: str, user_condition: dict, top_policies: pd.DataFrame) -> str:
    answer = []
    answer.append("## 청년정책 추천 결과")
    answer.append("")
    answer.append(f"입력 내용: {user_input}")
    answer.append("")

    if user_condition.get("unclear_conditions"):
        answer.append("### 추가 확인이 필요한 정보")
        answer.append(", ".join(user_condition["unclear_conditions"]))
        answer.append("")

    for idx, row in top_policies.iterrows():
        policy_name = row.get("policy_name", "")
        support_content = row.get("support_content", "")
        apply_period = row.get("apply_period", "")
        apply_method = row.get("apply_method", "")
        apply_url = row.get("apply_url", "")
        reference_url = row.get("reference_url", "")
        extra_condition = row.get("extra_condition", "")
        target_condition = row.get("target_condition", "")

        answer.append(f"### {idx + 1}. {policy_name}")
        answer.append(f"- 추천 이유: 입력한 관심사와 정책 설명의 유사도가 높습니다.")
        answer.append(f"- 지원 내용: {support_content if support_content else '데이터에 명시되어 있지 않습니다.'}")
        answer.append(f"- 신청 기간: {apply_period if apply_period else '데이터에 명시되어 있지 않습니다.'}")
        answer.append(f"- 신청 방법: {apply_method if apply_method else '데이터에 명시되어 있지 않습니다.'}")

        if apply_url:
            answer.append(f"- 신청 URL: {apply_url}")

        if reference_url:
            answer.append(f"- 참고 URL: {reference_url}")

        if extra_condition:
            answer.append(f"- 추가 조건: {extra_condition}")

        if target_condition:
            answer.append(f"- 대상/제한 조건: {target_condition}")

        answer.append("- 확인 필요: 나이, 지역, 소득, 신청기간 조건은 실제 신청 전 반드시 공식 페이지에서 확인하세요.")
        answer.append("")

    answer.append("## 바로 할 일 체크리스트")
    answer.append("- 관심 있는 정책의 신청 기간을 확인한다.")
    answer.append("- 신청 URL 또는 참고 URL에 접속한다.")
    answer.append("- 나이, 지역, 소득, 재학/취업 상태 조건을 확인한다.")
    answer.append("- 필요한 제출서류를 준비한다.")

    return "\n".join(answer)


def llm_answer(user_input: str, user_condition: dict, top_policies: pd.DataFrame) -> str | None:
    if not os.getenv("OPENAI_API_KEY"):
        return None

    try:
        from openai import OpenAI

        client = OpenAI()
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        policy_text = policy_rows_to_text(top_policies)

        system_prompt = """
너는 청년정책 추천 안내문을 작성하는 도우미다.
반드시 제공된 정책 데이터만 사용한다.
데이터에 없는 내용은 추측하지 않는다.
신청 가능 여부가 확실하지 않으면 '추가 확인 필요'라고 말한다.
사용자가 바로 행동할 수 있도록 체크리스트를 포함한다.
"""

        user_prompt = f"""
사용자 입력:
{user_input}

추출된 사용자 조건:
{user_condition}

추천 후보 정책 데이터:
{policy_text}

아래 형식으로 한국어 답변을 작성해라.

1. 추천 정책명
2. 추천 이유
3. 신청 가능성
4. 추가 확인 필요 조건
5. 지원 내용
6. 신청 기간
7. 신청 방법
8. 행동 체크리스트
"""

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        print("LLM 답변 생성 실패, 템플릿 답변으로 대체합니다.")
        print("오류:", e)
        return None


def generate_final_answer(user_input: str, user_condition: dict, top_policies: pd.DataFrame) -> str:
    result = llm_answer(user_input, user_condition, top_policies)

    if result is not None:
        return result

    return template_answer(user_input, user_condition, top_policies)