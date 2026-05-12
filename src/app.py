import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"

sys.path.append(str(SRC_DIR))

from recommend_policy import recommend_policy


if __name__ == "__main__":
    user_input = input("청년정책 질문을 입력하세요: ")

    result = recommend_policy(user_input)

    if isinstance(result, tuple):
        for item in result:
            print(item)
    else:
        print(result)
