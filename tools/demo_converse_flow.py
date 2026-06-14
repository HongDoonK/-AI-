"""대화형 신청 도우미 흐름 시현 (ADR-001).

ConverseAgent 오케스트레이터로 '목돈 마련' 시나리오의 멀티턴 대화를
실제로 구동한다. 세션 상태(선택 정책, 최근 추천)를 턴 간 직접 스레드해
백엔드 conversation_store 없이도 동일한 흐름을 보여준다.

실행: python -m tools.demo_converse_flow
"""
from __future__ import annotations

import json

from ai.converse_agent import ConverseAgent


def main() -> None:
    agent = ConverseAgent()
    profile = {"age": 26, "region_sido": "서울", "employment_status": "재직", "interest": "금융"}
    selected, recommendations = None, []

    turns = [
        "저는 서울 사는 26살 직장인 청년인데, 목돈 마련하고 싶어요. 적금이나 자산형성 정책 있나요?",
        "그럼 정책 2 신청할래",
        "이거 신청하려면 무슨 서류가 필요해?",
        "그럼 신청하면 나는 얼마나 받을 수 있어?",
    ]

    for message in turns:
        result = agent.respond(
            message=message,
            selected_policy=selected,
            last_recommendations=recommendations,
            profile=profile,
        )
        print("=" * 64)
        print(f"사용자: {message}")
        print(f"[intent={result['intent']}]")
        print(result["reply"])
        if result.get("benefit"):
            detail = {k: v for k, v in result["benefit"].items()
                      if k not in {"summary_line", "kind", "confidence", "sources"} and v is not None}
            print(f"  · 정량 필드: {json.dumps(detail, ensure_ascii=False)}")
        actions = [a["label"] for a in result.get("suggested_actions", [])]
        if actions:
            print(f"  · 다음 액션칩: {actions}")

        # 세션 상태 스레드 (백엔드 라우트가 conversation_store로 하는 일을 데모에서 직접)
        if "last_recommendations" in result:
            recommendations = result["last_recommendations"]
        if result.get("selected_policy"):
            selected = result["selected_policy"]


if __name__ == "__main__":
    main()
