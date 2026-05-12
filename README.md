# -생성형AI와 비즈니스-
생성형AI와비즈니스 수업을 위한 생성형 모델 개발

청년정책 API 데이터를 기반으로 사용자 입력 조건을 추출하고, FAISS 기반 검색과 Qwen LLM을 활용해 맞춤형 청년정책을 추천하는 MVP 프로젝트

## 프로젝트 구조

```text
data/raw/        원본 API 데이터
data/processed/  전처리된 CSV 데이터
data/index/      FAISS 인덱스 및 임베딩 파일
src/             주요 파이프라인 코드
tests/           테스트 코드
prompts/         LLM 프롬프트
app.py           실행 진입점
