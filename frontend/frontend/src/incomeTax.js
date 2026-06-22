// 근로소득세·4대보험을 반영한 연봉 실수령액 계산
// 국세청 근로소득 간이세액표는 급여 구간×부양가족수의 방대한 조견표라 그대로 옮길 수 없으므로,
// 같은 입력(소득세법상 근로소득공제·종합소득세율·근로소득세액공제·4대보험요율)을 사용하는
// 누진세율 기반 근사 계산식을 사용한다(2024년 세율 기준).

const PENSION_RATE = 0.045; // 국민연금 (근로자 부담분)
const PENSION_MONTHLY_CAP = 590400; // 국민연금 월 보험료 상한액(2024년 기준)
const HEALTH_RATE = 0.03545; // 건강보험 (근로자 부담분)
const LONG_TERM_CARE_RATE = 0.1295; // 장기요양보험 = 건강보험료 × 12.95%
const EMPLOYMENT_RATE = 0.009; // 고용보험 (근로자 부담분)
const LOCAL_TAX_RATE = 0.1; // 지방소득세 = 결정세액의 10%

const PERSONAL_DEDUCTION_PER_PERSON = 1500000; // 기본공제 1인당 150만 원

// 근로소득공제 (소득세법 제47조)
function calcEarnedIncomeDeduction(grossIncome) {
  if (grossIncome <= 5000000) return grossIncome * 0.7;
  if (grossIncome <= 15000000) return 3500000 + (grossIncome - 5000000) * 0.4;
  if (grossIncome <= 45000000) return 7500000 + (grossIncome - 15000000) * 0.15;
  if (grossIncome <= 100000000) return 12000000 + (grossIncome - 45000000) * 0.05;
  return 14750000 + (grossIncome - 100000000) * 0.02;
}

// 종합소득세 기본세율 누진공제표 (2023년 개정 세율)
const TAX_BRACKETS = [
  { upTo: 14000000, rate: 0.06, deduction: 0 },
  { upTo: 50000000, rate: 0.15, deduction: 1260000 },
  { upTo: 88000000, rate: 0.24, deduction: 5760000 },
  { upTo: 150000000, rate: 0.35, deduction: 15440000 },
  { upTo: 300000000, rate: 0.38, deduction: 19940000 },
  { upTo: 500000000, rate: 0.4, deduction: 25940000 },
  { upTo: 1000000000, rate: 0.42, deduction: 35940000 },
  { upTo: Infinity, rate: 0.45, deduction: 65940000 },
];

function calcCalculatedTax(taxBase) {
  if (taxBase <= 0) return 0;
  const bracket = TAX_BRACKETS.find((row) => taxBase <= row.upTo);
  return Math.max(0, taxBase * bracket.rate - bracket.deduction);
}

// 근로소득세액공제 (소득세법 제59조) : 산출세액과 총급여 구간에 따라 한도가 달라진다
function calcEarnedIncomeTaxCredit(calculatedTax, grossIncome) {
  if (calculatedTax <= 0) return 0;

  const base =
    calculatedTax <= 1300000 ? calculatedTax * 0.55 : 715000 + (calculatedTax - 1300000) * 0.3;

  let limit;
  if (grossIncome <= 33000000) {
    limit = 740000;
  } else if (grossIncome <= 70000000) {
    limit = Math.max(660000, 740000 - Math.floor((grossIncome - 33000000) / 1000) * 800);
  } else {
    limit = Math.max(500000, 660000 - Math.floor((grossIncome - 70000000) / 1000) * 500);
  }

  return Math.min(base, limit);
}

/**
 * @param {number} annualSalary 세전 연봉 (원)
 * @param {object} [options]
 * @param {number} [options.monthlyNonTaxable] 월 비과세액 (식대 등, 원)
 * @param {number} [options.dependents] 부양가족 수 (본인 포함, 인적공제 산정용)
 * @returns 연/월 단위의 공제 내역과 실수령액
 */
export function calculateIncomeTax(annualSalary, options = {}) {
  const monthlyNonTaxable = Math.max(0, Number(options.monthlyNonTaxable) || 0);
  const dependents = Math.max(1, Math.floor(Number(options.dependents) || 1));

  const salary = Math.max(0, Number(annualSalary) || 0);
  const annualNonTaxable = monthlyNonTaxable * 12;
  const grossTaxableIncome = Math.max(0, salary - annualNonTaxable);

  // 4대 보험은 과세대상 월급여(비과세 제외) 기준으로 산정
  const monthlyTaxablePay = grossTaxableIncome / 12;
  const pensionMonthly = Math.min(monthlyTaxablePay * PENSION_RATE, PENSION_MONTHLY_CAP);
  const healthMonthly = monthlyTaxablePay * HEALTH_RATE;
  const longTermCareMonthly = healthMonthly * LONG_TERM_CARE_RATE;
  const employmentMonthly = monthlyTaxablePay * EMPLOYMENT_RATE;

  const annualPension = pensionMonthly * 12;
  const annualHealth = healthMonthly * 12;
  const annualLongTermCare = longTermCareMonthly * 12;
  const annualEmployment = employmentMonthly * 12;
  const annualInsuranceTotal = annualPension + annualHealth + annualLongTermCare + annualEmployment;

  // 근로소득금액 = 총급여 - 근로소득공제
  const earnedIncomeDeduction = calcEarnedIncomeDeduction(grossTaxableIncome);
  const earnedIncomeAmount = Math.max(0, grossTaxableIncome - earnedIncomeDeduction);

  // 종합소득공제 = 인적공제(기본공제) + 국민연금 등 사회보험료 공제
  const personalDeduction = PERSONAL_DEDUCTION_PER_PERSON * dependents;
  const incomeDeductionTotal = personalDeduction + annualPension;

  const taxBase = Math.max(0, earnedIncomeAmount - incomeDeductionTotal);
  const calculatedTax = calcCalculatedTax(taxBase);
  const earnedIncomeTaxCredit = calcEarnedIncomeTaxCredit(calculatedTax, grossTaxableIncome);

  const determinedIncomeTax = Math.max(0, calculatedTax - earnedIncomeTaxCredit);
  const localIncomeTax = determinedIncomeTax * LOCAL_TAX_RATE;
  const annualTaxTotal = determinedIncomeTax + localIncomeTax;

  const annualDeductionTotal = annualInsuranceTotal + annualTaxTotal;
  const annualNetIncome = salary - annualDeductionTotal;

  return {
    input: { annualSalary: salary, monthlyNonTaxable, dependents },
    annual: {
      grossTaxableIncome,
      earnedIncomeDeduction,
      earnedIncomeAmount,
      personalDeduction,
      taxBase,
      calculatedTax,
      earnedIncomeTaxCredit,
      incomeTax: determinedIncomeTax,
      localIncomeTax,
      pension: annualPension,
      health: annualHealth,
      longTermCare: annualLongTermCare,
      employment: annualEmployment,
      insuranceTotal: annualInsuranceTotal,
      taxTotal: annualTaxTotal,
      deductionTotal: annualDeductionTotal,
      netIncome: annualNetIncome,
    },
    monthly: {
      grossSalary: salary / 12,
      pension: pensionMonthly,
      health: healthMonthly,
      longTermCare: longTermCareMonthly,
      employment: employmentMonthly,
      insuranceTotal: annualInsuranceTotal / 12,
      incomeTax: determinedIncomeTax / 12,
      localIncomeTax: localIncomeTax / 12,
      taxTotal: annualTaxTotal / 12,
      deductionTotal: annualDeductionTotal / 12,
      netIncome: annualNetIncome / 12,
    },
  };
}
