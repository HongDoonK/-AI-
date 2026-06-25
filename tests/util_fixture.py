"""테스트 공용 fixture DB 헬퍼."""
import os
from pathlib import Path

_FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "fixture_youth_policy.db"
_LGCV_FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "fixture_lgcv_policy.db"


def ensure_fixture_db() -> Path:
    """fixture DB가 없으면 생성하고 경로를 반환한다."""
    if not _FIXTURE_PATH.exists():
        from tools.make_fixture_db import build_fixture_db

        build_fixture_db(str(_FIXTURE_PATH))
    return _FIXTURE_PATH


def ensure_lgcv_fixture_db() -> Path:
    """충북 전용(lgcv) fixture DB가 없으면 생성하고 경로를 반환한다."""
    if not _LGCV_FIXTURE_PATH.exists():
        from tools.make_fixture_db import build_lgcv_fixture_db

        build_lgcv_fixture_db(str(_LGCV_FIXTURE_PATH))
    return _LGCV_FIXTURE_PATH


def set_test_env():
    """LLM/FAISS를 끄고 fixture DB를 사용하도록 환경을 맞춘다."""
    os.environ["LLM_PROVIDER"] = "none"  # ADR-002 §D2
    os.environ["USE_OPENAI_LLM"] = "0"   # 레거시 호환
    os.environ["USE_FAISS"] = "0"
    os.environ["YOUTH_POLICY_DB_PATH"] = str(ensure_fixture_db())
