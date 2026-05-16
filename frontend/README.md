# 청년 맞춤 정책 안내 AI - Frontend

React + Vite 프론트엔드입니다.

## 실행
```bash
npm install
npm run dev
```

## 백엔드 연결
기본 백엔드 주소는 `http://localhost:8000/recommend` 입니다.
Vercel 배포 시 환경변수에 아래 값을 추가하세요.

```bash
VITE_API_URL=https://배포된-백엔드주소/recommend
```

백엔드가 없을 때는 화면의 `예시 결과 보기` 버튼으로 mock 데이터를 확인할 수 있습니다.
