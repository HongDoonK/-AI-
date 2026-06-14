import { useMemo, useState } from 'react';
import { Calculator } from 'lucide-react';
import { formatWon } from '../appConfig.js';
import { calculateIncomeTax } from '../incomeTax.js';

function ValuePill({ label, value }) {
  return (
    <div className="pill">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export default function IncomeCalculator() {
  const [form, setForm] = useState({
    annualSalary: '',
    monthlyNonTaxable: '200000',
    dependents: '1',
  });

  function updateField(name, value) {
    setForm((prev) => ({ ...prev, [name]: value }));
  }

  const result = useMemo(() => {
    const annualSalaryManwon = Number(form.annualSalary);
    if (!annualSalaryManwon || annualSalaryManwon <= 0) return null;
    return calculateIncomeTax(annualSalaryManwon * 10000, {
      monthlyNonTaxable: Number(form.monthlyNonTaxable) || 0,
      dependents: Number(form.dependents) || 1,
    });
  }, [form]);

  return (
    <section className="panel income-tax-panel">
      <p className="card-eyebrow">내 근로소득 계산</p>
      <h2><Calculator size={19} /> 연봉 실수령액 계산기</h2>
      <p className="hint">
        근로소득공제·종합소득세율·근로소득세액공제·4대보험요율을 반영한 근사 계산이며,
        실제 원천징수세액(간이세액표)과는 차이가 있을 수 있습니다.
      </p>
      <div className="form-grid">
        <label>
          연봉 (세전, 만원)
          <input
            value={form.annualSalary}
            onChange={(e) => updateField('annualSalary', e.target.value)}
            type="number"
            min="0"
            step="10"
            placeholder="예: 3600 (3,600만 원)"
          />
        </label>
        <label>
          월 비과세액 (원, 식대 등)
          <input
            value={form.monthlyNonTaxable}
            onChange={(e) => updateField('monthlyNonTaxable', e.target.value)}
            type="number"
            min="0"
            step="10000"
            placeholder="예: 200000"
          />
        </label>
        <label>
          부양가족 수 (본인 포함)
          <input
            value={form.dependents}
            onChange={(e) => updateField('dependents', e.target.value)}
            type="number"
            min="1"
            max="11"
            placeholder="1"
          />
        </label>
      </div>

      {result ? (
        <>
          <div className="pill-wrap">
            <ValuePill label="월 예상 실수령액" value={formatWon(result.monthly.netIncome)} />
            <ValuePill label="연 예상 실수령액" value={formatWon(result.annual.netIncome)} />
            <ValuePill label="월 공제 합계" value={formatWon(result.monthly.deductionTotal)} />
            <ValuePill label="연 공제 합계" value={formatWon(result.annual.deductionTotal)} />
          </div>
          <div className="income-tax-detail">
            <h4>월 공제 내역 (예상)</h4>
            <ul className="check-list">
              <li><span>국민연금</span><strong>{formatWon(result.monthly.pension)}</strong></li>
              <li><span>건강보험</span><strong>{formatWon(result.monthly.health)}</strong></li>
              <li><span>장기요양보험</span><strong>{formatWon(result.monthly.longTermCare)}</strong></li>
              <li><span>고용보험</span><strong>{formatWon(result.monthly.employment)}</strong></li>
              <li><span>근로소득세</span><strong>{formatWon(result.monthly.incomeTax)}</strong></li>
              <li><span>지방소득세</span><strong>{formatWon(result.monthly.localIncomeTax)}</strong></li>
            </ul>
          </div>
        </>
      ) : (
        <p className="muted">연봉을 입력하면 4대보험과 근로소득세를 반영한 예상 실수령액을 계산해드립니다.</p>
      )}
    </section>
  );
}
