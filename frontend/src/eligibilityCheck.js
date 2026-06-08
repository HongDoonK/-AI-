// 저장된 사용자 프로필(나이·지역·소득)을 정책의 지원 조건(min_age/max_age, region_*, income_*)과
// 비교해 "지금 신청 불가능"으로 보이는 정책과, 어디가 얼마나 부족한지를 1차로 걸러낸다.
// 정책 쪽 조건이 비어 있으면(데이터 미기재) 판단하지 않고 통과시킨다 — 데이터 부족을 결격으로 간주하지 않기 위함.

function hasValue(value) {
  return value !== null && value !== undefined && value !== '';
}

function checkAgeGap(profile, policy) {
  if (!hasValue(profile.age)) return null;
  const age = Number(profile.age);
  if (hasValue(policy.min_age) && age < policy.min_age) {
    return {
      label: '나이',
      detail: `최소 ${policy.min_age}세부터 지원 — 현재 ${age}세로 ${policy.min_age - age}세 부족`,
    };
  }
  if (hasValue(policy.max_age) && age > policy.max_age) {
    return {
      label: '나이',
      detail: `최대 ${policy.max_age}세까지 지원 — 현재 ${age}세로 ${age - policy.max_age}세 초과`,
    };
  }
  return null;
}

function checkRegionGap(profile, policy) {
  const policySido = (policy.region_sido || '').trim();
  if (!policySido || policySido === '전국') return null;
  if (!hasValue(profile.region_sido)) return null;

  if (profile.region_sido !== policySido) {
    return {
      label: '지역',
      detail: `${policySido}${policy.region_sigungu ? ` ${policy.region_sigungu}` : ''} 거주자 대상 — 현재 등록 지역은 ${profile.region_sido}${profile.region_sigungu ? ` ${profile.region_sigungu}` : ''}`,
    };
  }
  const policySigungu = (policy.region_sigungu || '').trim();
  if (policySigungu && hasValue(profile.region_sigungu) && profile.region_sigungu !== policySigungu) {
    return {
      label: '지역',
      detail: `${policySido} ${policySigungu} 거주자 대상 — 현재 등록 지역은 ${profile.region_sido} ${profile.region_sigungu}`,
    };
  }
  return null;
}

function checkIncomeGap(profile, policy) {
  if (policy.income_type !== '연소득') return null;
  if (!hasValue(profile.monthly_income)) return null;

  // income_min/income_max는 연소득 기준(만원 단위)
  const annualIncomeManwon = Number(profile.monthly_income) * 12;

  if (hasValue(policy.income_max) && annualIncomeManwon > policy.income_max) {
    return {
      label: '소득',
      detail: `연소득 ${policy.income_max.toLocaleString('ko-KR')}만 원 이하 대상 — 현재 약 ${Math.round(annualIncomeManwon).toLocaleString('ko-KR')}만 원으로 ${Math.round(annualIncomeManwon - policy.income_max).toLocaleString('ko-KR')}만 원 초과`,
    };
  }
  if (hasValue(policy.income_min) && annualIncomeManwon < policy.income_min) {
    return {
      label: '소득',
      detail: `연소득 ${policy.income_min.toLocaleString('ko-KR')}만 원 이상 대상 — 현재 약 ${Math.round(annualIncomeManwon).toLocaleString('ko-KR')}만 원으로 ${Math.round(policy.income_min - annualIncomeManwon).toLocaleString('ko-KR')}만 원 부족`,
    };
  }
  return null;
}

/**
 * @returns {{ eligible: boolean, gaps: { label: string, detail: string }[] }}
 */
export function checkEligibility(policy, profile) {
  if (!policy || !profile) return { eligible: true, gaps: [] };

  const gaps = [checkAgeGap(profile, policy), checkRegionGap(profile, policy), checkIncomeGap(profile, policy)].filter(
    Boolean
  );

  return { eligible: gaps.length === 0, gaps };
}

/**
 * 추천 목록 중 현재 프로필 기준으로 "신청 불가능"으로 보이는 정책과 부족분을 추려낸다.
 */
export function findIneligiblePolicies(recommendations, profile) {
  const policies = Array.isArray(recommendations) ? recommendations : [];
  if (!profile) return [];

  return policies
    .map((policy) => ({ policy, result: checkEligibility(policy, profile) }))
    .filter(({ result }) => !result.eligible)
    .map(({ policy, result }) => ({ policy, gaps: result.gaps }));
}
