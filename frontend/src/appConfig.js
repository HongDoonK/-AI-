// App 전역 상수와 순수 헬퍼 (React 비의존, 단위 테스트 가능)

export const DEFAULT_API_BASE_URL = 'http://localhost:8000';
export const PROFILE_STORAGE_KEY = 'youth-policy-user-profile';
export const PREP_STORAGE_KEY = 'youth-policy-prep-checks';
export const NO_CONDITION_MESSAGE =
  '조건이 부족해서 정책을 추천할 수 없습니다. 나이, 성별, 지역, 취업 상태 또는 관심 분야를 입력해주세요.';

export const REGION_OPTIONS = {
  서울: ['종로구', '중구', '용산구', '성동구', '광진구', '마포구', '강서구', '영등포구', '관악구', '강남구', '송파구'],
  부산: ['중구', '서구', '동구', '영도구', '부산진구', '해운대구', '사하구', '금정구', '수영구'],
  대구: ['중구', '동구', '서구', '남구', '북구', '수성구', '달서구'],
  인천: ['중구', '동구', '미추홀구', '연수구', '남동구', '부평구', '계양구', '서구'],
  광주: ['동구', '서구', '남구', '북구', '광산구'],
  대전: ['동구', '중구', '서구', '유성구', '대덕구'],
  울산: ['중구', '남구', '동구', '북구', '울주군'],
  세종: ['세종시'],
  경기: ['수원시', '성남시', '고양시', '용인시', '부천시', '안산시', '안양시', '화성시', '평택시', '의정부시'],
  강원: ['춘천시', '원주시', '강릉시', '동해시', '속초시', '홍천군', '평창군'],
  충북: ['청주시', '충주시', '제천시', '보은군', '옥천군', '진천군'],
  충남: ['천안시', '공주시', '보령시', '아산시', '서산시', '당진시'],
  전북: ['전주시', '군산시', '익산시', '정읍시', '남원시', '김제시'],
  전남: ['목포시', '여수시', '순천시', '나주시', '광양시', '무안군'],
  경북: ['포항시', '경주시', '김천시', '안동시', '구미시', '경산시'],
  경남: ['창원시', '진주시', '통영시', '사천시', '김해시', '양산시'],
  제주: ['제주시', '서귀포시'],
};

export function resolveApiBaseUrl(value) {
  const raw = (value || DEFAULT_API_BASE_URL).replace(/\/$/, '');
  return raw.endsWith('/recommend') ? raw.slice(0, -'/recommend'.length) : raw;
}

export function normalizeResult(data) {
  return {
    user_condition: data?.user_condition || {},
    recommendations: Array.isArray(data?.recommendations) ? data.recommendations : [],
    centers: Array.isArray(data?.centers) ? data.centers : [],
    message: data?.message || '',
  };
}

export function getPossibilityClass(value = '') {
  if (value.includes('높음')) return 'badge green';
  if (value.includes('낮음')) return 'badge gray';
  if (value.includes('확인')) return 'badge orange';
  return 'badge blue';
}

export function displayValue(value, fallback = '확인 필요') {
  if (value === null || value === undefined || value === '') return fallback;
  return value;
}
