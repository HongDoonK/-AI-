// 보건복지부 고시 2026년 기준 중위소득(월 기준, 원) — 가구원수별
// 8인 이상 가구는 1인 증가할 때마다 7인 가구 대비 증가분(959,198원)만큼 더해 계산한다.
const MEDIAN_INCOME_BY_HOUSEHOLD_SIZE = {
  1: 2564238,
  2: 4199292,
  3: 5359036,
  4: 6494738,
  5: 7556719,
  6: 8555952,
  7: 9515150,
};
const EXTRA_PER_PERSON_OVER_7 = 959198;

export function getStandardMedianIncome(householdSize) {
  const size = Math.max(1, Math.floor(Number(householdSize) || 1));
  if (size <= 7) return MEDIAN_INCOME_BY_HOUSEHOLD_SIZE[size];
  return MEDIAN_INCOME_BY_HOUSEHOLD_SIZE[7] + EXTRA_PER_PERSON_OVER_7 * (size - 7);
}

/**
 * 월 소득을 가구원수 기준 중위소득과 비교해 비율(%)로 환산한다.
 * @param {number} monthlyIncome 월 소득 (원)
 * @param {number} householdSize 가구원수 (본인 포함)
 */
export function convertToMedianIncomePercent(monthlyIncome, householdSize) {
  const income = Math.max(0, Number(monthlyIncome) || 0);
  const medianIncome = getStandardMedianIncome(householdSize);
  if (!medianIncome) return null;

  const percent = (income / medianIncome) * 100;
  return {
    monthlyIncome: income,
    householdSize: Math.max(1, Math.floor(Number(householdSize) || 1)),
    medianIncome,
    percent,
    percentLabel: `기준 중위소득 대비 ${Math.round(percent)}%`,
  };
}
