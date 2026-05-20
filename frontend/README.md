# 청년 맞춤 정책 안내 AI - Frontend

React + Vite 프론트엔드입니다.

## 로컬 실행

```bash
npm install
npm run dev
```

기본 백엔드 주소는 `http://localhost:8000/recommend`입니다.

## Vercel 배포

Vercel에서 프로젝트 Root Directory를 `frontend`로 설정합니다.

- Framework Preset: `Vite`
- Build Command: `npm run build`
- Output Directory: `dist`

환경 변수:

```text
VITE_API_URL=https://배포된-백엔드-주소
```

`VITE_API_URL`에는 `/recommend`를 붙여도 되고, 백엔드 기본 주소만 넣어도 됩니다.
예: `https://api.example.com` 또는 `https://api.example.com/recommend`

## 발표용 로컬 백엔드 연결

백엔드를 Render/Railway 등에 상시 배포하지 않는 경우, 발표 PC에서 백엔드를 직접 실행한 뒤 Vercel 프론트가 로컬 백엔드를 호출하게 할 수 있습니다.

백엔드 실행:

```bash
uvicorn backend.main:app --reload
```

Vercel 환경 변수 `VITE_API_URL`을 비워두거나 아래처럼 설정하면, 프론트는 발표 PC의 로컬 백엔드를 호출합니다.

```text
VITE_API_URL=http://localhost:8000
```

주의: 이 방식은 Vercel 사이트에 접속한 사람의 컴퓨터에서 `localhost:8000`을 찾습니다. 따라서 발표자 PC에서 백엔드를 켜고 발표자 PC 브라우저로 접속할 때만 정상 동작합니다.
