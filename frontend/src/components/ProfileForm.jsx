import { useEffect, useMemo, useState } from 'react';
import { Loader2, LogIn } from 'lucide-react';
import { REGION_OPTIONS, displayValue, formatWon } from '../appConfig.js';
import { convertToMedianIncomePercent } from '../medianIncome.js';

export default function ProfileForm({ profile, onLogin, saving }) {
  const [form, setForm] = useState(() => ({
    age: profile?.age || '',
    gender: profile?.gender || '',
    region_sido: profile?.region_sido || '',
    region_sigungu: profile?.region_sigungu || '',
    employment_status: profile?.employment_status || '',
    household_size: profile?.household_size || '1',
    monthly_income: profile?.monthly_income || '',
  }));

  const sigunguOptions = REGION_OPTIONS[form.region_sido] || [];

  const medianIncomeInfo = useMemo(() => {
    if (!form.monthly_income) return null;
    return convertToMedianIncomePercent(Number(form.monthly_income) * 10000, form.household_size);
  }, [form.monthly_income, form.household_size]);

  useEffect(() => {
    if (!profile) return;
    setForm({
      age: profile.age || '',
      gender: profile.gender || '',
      region_sido: profile.region_sido || '',
      region_sigungu: profile.region_sigungu || '',
      employment_status: profile.employment_status || '',
      household_size: profile.household_size || '1',
      monthly_income: profile.monthly_income || '',
    });
  }, [profile]);

  function updateField(name, value) {
    setForm((prev) => {
      const next = { ...prev, [name]: value };
      if (name === 'region_sido') next.region_sigungu = '';
      return next;
    });
  }

  function submit(event) {
    event.preventDefault();
    onLogin({
      age: form.age ? Number(form.age) : null,
      gender: form.gender,
      region_sido: form.region_sido,
      region_sigungu: form.region_sigungu,
      employment_status: form.employment_status,
      household_size: form.household_size ? Number(form.household_size) : null,
      monthly_income: form.monthly_income ? Number(form.monthly_income) : null,
      median_income_percent: medianIncomeInfo ? Math.round(medianIncomeInfo.percent) : null,
    });
  }

  return (
    <form className="panel login-panel" onSubmit={submit}>
      <p className="card-eyebrow">사용자 프로필</p>
      <h2>조건 저장</h2>
      <div className="form-grid">
        <label>
          나이
          <input value={form.age} onChange={(e) => updateField('age', e.target.value)} type="number" min="14" max="49" placeholder="24" />
        </label>
        <label>
          성별
          <select value={form.gender} onChange={(e) => updateField('gender', e.target.value)}>
            <option value="">선택 안 함</option>
            <option value="남성">남성</option>
            <option value="여성">여성</option>
          </select>
        </label>
        <label>
          시도
          <select value={form.region_sido} onChange={(e) => updateField('region_sido', e.target.value)}>
            <option value="">선택 안 함</option>
            {Object.keys(REGION_OPTIONS).map((sido) => (
              <option key={sido} value={sido}>{sido}</option>
            ))}
          </select>
        </label>
        <label>
          시군구
          <select value={form.region_sigungu} onChange={(e) => updateField('region_sigungu', e.target.value)} disabled={!form.region_sido}>
            <option value="">선택 안 함</option>
            {sigunguOptions.map((sigungu) => (
              <option key={sigungu} value={sigungu}>{sigungu}</option>
            ))}
          </select>
        </label>
        <label>
          취업 상태
          <select value={form.employment_status} onChange={(e) => updateField('employment_status', e.target.value)}>
            <option value="">선택 안 함</option>
            <option value="미취업">미취업</option>
            <option value="재직">재직</option>
            <option value="창업">창업</option>
            <option value="자영업">자영업</option>
            <option value="프리랜서">프리랜서</option>
          </select>
        </label>
        <label>
          가구원 수 (본인 포함)
          <select value={form.household_size} onChange={(e) => updateField('household_size', e.target.value)}>
            {[1, 2, 3, 4, 5, 6, 7].map((size) => (
              <option key={size} value={size}>{size}인 가구</option>
            ))}
          </select>
        </label>
        <label>
          월 소득 (만원)
          <input
            value={form.monthly_income}
            onChange={(e) => updateField('monthly_income', e.target.value)}
            type="number"
            min="0"
            step="10"
            placeholder="예: 250 (250만 원)"
          />
        </label>
      </div>
      {medianIncomeInfo && (
        <p className="hint">
          2026년 {medianIncomeInfo.householdSize}인 가구 기준 중위소득({formatWon(medianIncomeInfo.medianIncome)}) 대비
          {' '}<strong>약 {Math.round(medianIncomeInfo.percent)}%</strong>로 환산되어 프로필에 함께 저장됩니다.
        </p>
      )}
      <button className="primary-button full-button" type="submit" disabled={saving}>
        {saving ? <><Loader2 className="spin" size={18} /> 저장 중</> : <><LogIn size={18} /> 프로필 저장</>}
      </button>
      {profile?.user_id && <p className="hint">저장 시점: {displayValue(profile.created_at)} · 사용자 ID: {profile.user_id.slice(0, 8)}</p>}
    </form>
  );
}
