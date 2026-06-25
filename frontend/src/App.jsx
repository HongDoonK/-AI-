import { useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  AlertTriangle,
  Bell,
  Bookmark,
  Calculator,
  CalendarDays,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  ExternalLink,
  Home,
  Loader2,
  LogIn,
  MapPin,
  MessageCircle,
  Search,
  Send,
  UserRound,
} from 'lucide-react';
import { buildAgentReport } from './agentPlanner.js';
import { calculateIncomeTax } from './incomeTax.js';
import { convertToMedianIncomePercent } from './medianIncome.js';
import { findIneligiblePolicies } from './eligibilityCheck.js';
import { getScoreMood } from './scoreMood.js';
import {
  buildDemoAlarmPolicies,
  buildSavedCalendarEvents,
  clearSentDeadlineAlerts,
  defaultNotificationSettings,
  downloadIcsFile,
  enableDeadlineNotifications,
  formatDdayLabel,
  formatMonthTitle,
  formatTodayKey,
  FREE_SAVED_LIMIT,
  buildMonthCalendarCells,
  groupEventsByDeadlineDate,
  getDeadlineAlerts,
  hasDemoAlarmPolicies,
  isDemoAlarmPolicy,
  processScheduledDeadlineNotifications,
  requestNotificationPermission,
  runDemoAlarmTest,
} from './policyCalendar.js';
import {
  fetchNotificationSettings,
  saveNotificationSettings,
  syncSavedPolicies,
} from './savedPolicyApi.js';
import {
  buildPreparationItems,
  getPreparationLink,
  getCompletionStats,
  togglePreparationItem,
} from './prepTracker.js';
import { useTodayTick } from './useTodayTick.js';
import ApplyPanel from './components/ApplyPanel.jsx';
import ChatFlowPanel from './components/ChatFlowPanel.jsx';
import MyApplicationsPanel from './components/MyApplicationsPanel.jsx';
import {
  createApplyPlan,
  fetchApplication,
  fetchApplications,
  toggleApplyItem,
  updateApplyStatus,
} from './applyPlan.js';

const DEFAULT_API_BASE_URL = 'http://localhost:8000';
const API_BASE_URL = resolveApiBaseUrl(import.meta.env.VITE_API_URL);
const RECOMMEND_URL = `${API_BASE_URL}/recommend`;
const USER_URL = `${API_BASE_URL}/user`;
const CHAT_URL = `${API_BASE_URL}/chat`;
const PROFILE_STORAGE_KEY = 'youth-policy-user-profile';
const PREP_STORAGE_KEY = 'youth-policy-prep-checks';
const NOTIFICATION_STORAGE_KEY = 'youth-policy-notification-settings';
const NO_CONDITION_MESSAGE =
  '조건이 부족해서 정책을 추천할 수 없습니다. 나이, 성별, 지역, 취업 상태 또는 관심 분야를 입력해주세요.';

const REGION_OPTIONS = {
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

function resolveApiBaseUrl(value) {
  if (value) {
    const raw = String(value).replace(/\/$/, '');
    return raw.endsWith('/recommend') ? raw.slice(0, -'/recommend'.length) : raw;
  }

  if (typeof window !== 'undefined') {
    const { hostname, protocol } = window.location;
    if (hostname !== 'localhost' && hostname !== '127.0.0.1') {
      return `${protocol}//${hostname}:8000`;
    }
  }

  return DEFAULT_API_BASE_URL;
}

function normalizeResult(data) {
  return {
    user_condition: data?.user_condition || {},
    recommendations: Array.isArray(data?.recommendations) ? data.recommendations : [],
    centers: Array.isArray(data?.centers) ? data.centers : [],
    message: data?.message || '',
  };
}

function getPossibilityClass(value = '') {
  if (value.includes('높음')) return 'badge green';
  if (value.includes('낮음')) return 'badge gray';
  if (value.includes('확인')) return 'badge orange';
  if (value.includes('보통')) return 'badge blue';
  return 'badge blue';
}

function getPossibilityDisplay(value = '') {
  if (value.includes('높음')) return { emoji: '😄', label: '높음' };
  if (value.includes('보통')) return { emoji: '🙂', label: '보통' };
  if (value.includes('확인')) return { emoji: '🤔', label: '확인 필요' };
  if (value.includes('낮음')) return { emoji: '😐', label: '낮음' };
  return { emoji: '🙂', label: displayValue(value, '보통') };
}

function buildRecommendKeywords(policy) {
  const badges = (Array.isArray(policy.match_badges) ? policy.match_badges : []).filter(Boolean);
  const scoreLabel = policy.match_score_label ? String(policy.match_score_label).trim() : '';
  const keywords = [];

  for (const badge of badges) {
    if (keywords.length >= 3) break;
    if (scoreLabel && badge.includes(scoreLabel)) continue;
    keywords.push(badge);
  }

  const fallbacks = [policy.domain_label || policy.domain, policy.region_match, '충북 청년'].filter(Boolean);
  for (const item of fallbacks) {
    if (keywords.length >= 3) break;
    if (!keywords.includes(item)) keywords.push(item);
  }

  keywords.push(scoreLabel ? `FAISS 임베딩 ${scoreLabel}` : 'FAISS 임베딩');
  return keywords.slice(0, 4);
}

function DetailSectionCard({ title, children }) {
  return (
    <section className="detail-card">
      <h3>{title}</h3>
      {children}
    </section>
  );
}

function ExpandableSummary({ text, fallback = '내용 확인 필요', maxChars = 140 }) {
  const [expanded, setExpanded] = useState(false);
  const raw = text === null || text === undefined || String(text).trim() === '' ? fallback : String(text);
  const needsToggle = raw.length > maxChars;
  const shown = needsToggle && !expanded ? `${raw.slice(0, maxChars).trim()}…` : raw;

  return (
    <div className="detail-expand-block">
      <p className="detail-card-text">{shown}</p>
      {needsToggle && (
        <button className="detail-expand-button" type="button" onClick={() => setExpanded((prev) => !prev)}>
          {expanded ? '접기' : '더보기'}
        </button>
      )}
    </div>
  );
}

function displayValue(value, fallback = '확인 필요') {
  if (value === null || value === undefined || value === '') return fallback;
  return value;
}

function regionLabel(profile) {
  if (profile?.region_sido) {
    return profile.region_sigungu ? `${profile.region_sido} ${profile.region_sigungu}` : profile.region_sido;
  }
  return '지역 미설정';
}

function getRegionForCenters(profile, userCondition = {}) {
  const regionText = [
    userCondition.region_sido,
    userCondition.region_sigungu,
    userCondition.region,
    profile?.region_sido,
    profile?.region_sigungu,
  ]
    .filter(Boolean)
    .join(' ');
  return regionText || '충북';
}

const DEFAULT_YOUTH_CENTERS = [
  {
    center_name: '충북청년희망센터',
    center_addr: '충청북도 청주시',
    center_tel: '043-000-0000',
    center_url: 'https://www.chungbuk.go.kr/young/index.do',
  },
];

function getDisplayCenters(centers) {
  return Array.isArray(centers) && centers.length > 0 ? centers : DEFAULT_YOUTH_CENTERS;
}

function YouthCenterCard({ regionText, center, onViewCenters, buttonLabel = '센터 보기' }) {
  return (
    <section className="youth-center-card">
      <p className="youth-center-eyebrow">가까운 청년센터</p>
      <p className="youth-center-copy">정책 신청이 헷갈리면 가까운 청년센터에서 상담을 받을 수 있어요.</p>
      <p className="youth-center-region">{regionText} 기준 상담센터 안내</p>
      {center?.center_name && <p className="youth-center-name">{center.center_name}</p>}
      <button className="youth-center-button" type="button" onClick={onViewCenters}>{buttonLabel}</button>
    </section>
  );
}

function sanitizeProfile(profile) {
  if (!profile) return null;
  return {
    user_id: profile.user_id,
    age: profile.age ?? null,
    gender: profile.gender || '',
    region_sido: profile.region_sido || '',
    region_sigungu: profile.region_sigungu || '',
    employment_status: profile.employment_status || '',
    household_size: profile.household_size ?? null,
    monthly_income: profile.monthly_income ?? null,
    median_income_percent: profile.median_income_percent ?? null,
    created_at: profile.created_at,
  };
}

function buildProfileText(profile) {
  if (!profile) return '';
  const parts = [];
  if (profile.region_sido) parts.push(profile.region_sido);
  if (profile.region_sigungu) parts.push(profile.region_sigungu);
  if (profile.age) parts.push(`${profile.age}세`);
  if (profile.gender) parts.push(profile.gender);
  if (profile.employment_status) parts.push(profile.employment_status);
  if (profile.household_size) parts.push(`${profile.household_size}인 가구`);
  if (profile.median_income_percent != null) parts.push(`기준 중위소득 대비 ${profile.median_income_percent}%`);
  return parts.join(' ');
}

function hasMeaningfulProfile(profile) {
  if (!profile) return false;
  return Boolean(
    profile.age ||
      profile.gender ||
      profile.region_sido ||
      profile.region_sigungu ||
      profile.employment_status
  );
}

function buildChatUserContext(condition = {}, profile = {}) {
  const regionSido = condition.region_sido || profile?.region_sido || '';
  const regionSigungu = condition.region_sigungu || profile?.region_sigungu || '';
  const merged = {
    age: condition.age ?? profile?.age ?? null,
    gender: condition.gender || profile?.gender || '',
    region: condition.region || [regionSido, regionSigungu].filter(Boolean).join(' '),
    region_sido: regionSido,
    region_sigungu: regionSigungu,
    status: condition.status || '',
    employment_status: condition.employment_status || profile?.employment_status || '',
    interest: condition.interest || '',
    income: condition.income || '',
    housing_status: condition.housing_status || '',
  };
  return Object.fromEntries(
    Object.entries(merged).filter(([, value]) => value !== null && value !== undefined && value !== '')
  );
}

function formatDaysLeft(daysLeft) {
  if (daysLeft === null || daysLeft === undefined) return '날짜 확인 필요';
  if (daysLeft < 0) return '신청 종료';
  if (daysLeft === 0) return '오늘 마감';
  return `${daysLeft}일 남음`;
}

function statusLabel(status) {
  if (status === 'urgent') return '마감 임박';
  if (status === 'needs_date_check') return '날짜 확인';
  if (status === 'expired') return '종료';
  return '신청 가능';
}

function ValuePill({ label, value }) {
  return (
    <div className="pill">
      <span>{label}</span>
      <strong>{displayValue(value)}</strong>
    </div>
  );
}

function LoginPanel({ profile, onLogin, saving }) {
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

function formatWon(value) {
  if (!Number.isFinite(value)) return '0원';
  return `${Math.round(value).toLocaleString('ko-KR')}원`;
}

function IncomeTaxCalculator() {
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

function ApplicationAgentPanel({ recommendations }) {
  const report = useMemo(() => buildAgentReport(recommendations), [recommendations]);
  const topItems = report.priority.slice(0, 3);

  return (
    <section className="panel agent-panel">
      <p className="card-eyebrow">정책 실행 에이전트</p>
      <h2><Bell size={19} /> 신청 준비 리포트</h2>
      <p className="agent-copy">
        검색 결과를 맡겨두면 AI가 신청 우선순위, 마감 위험, 준비 체크리스트를 즉시 정리합니다.
        외부 계정 연동 없이 서비스 안에서 다음 행동을 안내합니다.
      </p>
      <div className="agent-stats">
        <div><strong>{report.total}</strong><span>분석 정책</span></div>
        <div><strong>{report.urgentCount}</strong><span>마감 임박</span></div>
        <div><strong>{report.needsDateCheckCount}</strong><span>확인 필요</span></div>
      </div>
      <p className="agent-status">{report.summary}</p>
      <div className="agent-report-list">
        {topItems.length === 0 ? (
          <div className="report-card empty-report">
            <ClipboardList size={20} />
            <p>추천을 실행하면 에이전트가 Top 5 정책을 분석해 신청 순서와 준비 작업을 생성합니다.</p>
          </div>
        ) : topItems.map((item, idx) => (
          <article className="report-card" key={`${item.policy.policy_name || 'policy'}-${idx}`}>
            <div className="report-card-head">
              <div>
                <span className="report-rank">{idx + 1}순위</span>
                <strong>{displayValue(item.policy.policy_name, '정책명 확인 필요')}</strong>
              </div>
              <span className={`status-chip ${item.status}`}>{statusLabel(item.status)}</span>
            </div>
            <p className="report-meta">{formatDaysLeft(item.daysLeft)} · {displayValue(item.policy.application_period)}</p>
            <ul className="task-list">
              {item.checklist.slice(0, 4).map((task) => (
                <li key={task}><CheckCircle2 size={15} /><span>{task}</span></li>
              ))}
            </ul>
          </article>
        ))}
      </div>
    </section>
  );
}

function EligibilityGapPanel({ recommendations, profile }) {
  const ineligible = useMemo(() => findIneligiblePolicies(recommendations, profile), [recommendations, profile]);

  if (!hasMeaningfulProfile(profile)) return null;
  if (!Array.isArray(recommendations) || recommendations.length === 0) return null;

  return (
    <section className="panel eligibility-panel">
      <p className="card-eyebrow">자동 적격성 1차 검증</p>
      <h2><AlertTriangle size={19} /> 지금은 신청이 어려운 정책</h2>
      <p className="agent-copy">
        저장된 프로필(나이·지역·소득)을 정책의 지원 조건과 비교해 1차로 걸러낸 결과입니다.
        조건이 명시되지 않은 정책은 판단하지 않으며, 실제 자격은 공고문에서 다시 확인하세요.
      </p>
      {ineligible.length === 0 ? (
        <p className="muted">현재 프로필 기준으로 조건 미충족이 확인된 정책이 없습니다.</p>
      ) : (
        <div className="agent-report-list">
          {ineligible.map(({ policy, gaps }, idx) => (
            <article className="report-card gap-card" key={`${policy.policy_name || 'policy'}-${idx}`}>
              <div className="report-card-head">
                <div>
                  <span className="report-rank">신청 불가</span>
                  <strong>{displayValue(policy.policy_name, '정책명 확인 필요')}</strong>
                </div>
              </div>
              <ul className="task-list gap-list">
                {gaps.map((gap, gapIdx) => (
                  <li key={`${gap.label}-${gapIdx}`}>
                    <AlertCircle size={15} />
                    <span><strong>{gap.label}</strong> 조건 미충족 — {gap.detail}</span>
                  </li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function getPrepItemDisplay(item = '') {
  const value = String(item).trim();
  if (!value) return { title: '확인 항목', description: '' };

  if (value.startsWith('신청 기간')) {
    const detail = value.includes(':') ? value.split(':').slice(1).join(':').trim() : '';
    return {
      title: '신청 기간 확인',
      description: detail || '신청 기간이 현재 접수 중인지 확인하세요',
    };
  }
  if (value.includes('서류') || value.includes('주민등록')) {
    return {
      title: '기본 서류 준비',
      description: '주민등록등본, 신분증, 소득 증빙 등 필요 서류 확인',
    };
  }
  if (value.includes('신청 링크') || value.includes('접수 절차') || value.includes('담당 기관')) {
    return {
      title: '신청 링크 확인',
      description: '공식 신청 페이지에서 접수 방법을 확인하세요',
    };
  }
  if (value.includes('자격')) {
    return {
      title: '자격 조건 확인',
      description: value.includes(':')
        ? value.split(':').slice(1).join(':').trim()
        : '나이, 거주, 취업 상태 등 자격 요건을 확인하세요',
    };
  }
  if (value.includes('소득')) {
    return {
      title: '소득 조건 확인',
      description: value.includes(':')
        ? value.split(':').slice(1).join(':').trim()
        : '소득 기준 충족 여부를 확인하세요',
    };
  }
  if (value.includes('지역')) {
    return {
      title: '지역 조건 확인',
      description: '거주지 및 지역 요건을 확인하세요',
    };
  }
  if (value.includes('상담') || value.includes('문의')) {
    return {
      title: '상담 필요 여부 확인',
      description: '청년센터 또는 담당 기관 상담이 필요한지 확인하세요',
    };
  }

  const colonIndex = value.indexOf(':');
  if (colonIndex > -1) {
    return {
      title: value.slice(0, colonIndex).trim(),
      description: value.slice(colonIndex + 1).trim(),
    };
  }

  return { title: value, description: '' };
}

function PreparationBoard({ policy, checkedItems, onToggle }) {
  const policyId = policyKey(policy);
  const items = useMemo(() => buildPreparationItems(policy), [policy]);
  const stats = getCompletionStats(items, checkedItems);
  const done = stats.total > 0 && stats.completed === stats.total;

  return (
    <section className="prep-board">
      <article className="prep-hero-card">
        <p className="prep-hero-label">신청 준비</p>
        <h2>{displayValue(policy.policy_name, '정책명 확인 필요')}</h2>
        <div className="prep-progress-head">
          <span className="prep-rate">완료 <strong>{stats.completed}/{stats.total}</strong></span>
          <span className="prep-percent">{stats.percent}%</span>
        </div>
        <div className="prep-progress" aria-label={`준비 진행률 ${stats.percent}%`}>
          <div style={{ width: `${stats.percent}%` }} />
        </div>
      </article>
      <ul className="prep-check-list">
        {items.map((item) => {
          const checked = Boolean(checkedItems?.[item]);
          const itemLink = getPreparationLink(item, policy);
          const display = getPrepItemDisplay(item);
          return (
            <li className={`prep-check-item${checked ? ' done' : ''}`} key={item}>
              <label className="prep-check-row">
                <input
                  className="prep-checkbox"
                  type="checkbox"
                  checked={checked}
                  onChange={(event) => onToggle(policyId, item, event.target.checked)}
                />
                <span className="prep-item-body">
                  <span className="prep-item-title">{display.title}</span>
                  {display.description && <span className="prep-item-desc">{display.description}</span>}
                  {itemLink && (
                    <a className="prep-resource-link" href={itemLink.href} target="_blank" rel="noreferrer">
                      {itemLink.label}
                    </a>
                  )}
                </span>
              </label>
            </li>
          );
        })}
      </ul>
      {done && <p className="prep-complete"><CheckCircle2 size={16} /> 준비 항목을 모두 체크했습니다.</p>}
    </section>
  );
}

function PolicyCard({ policy, index, onChat, onPrepare }) {
  const checklist = Array.isArray(policy.checklist) ? policy.checklist : [];
  const url = policy.application_url || policy.url || policy.ref_url;
  const badges = Array.isArray(policy.match_badges) ? policy.match_badges.filter(Boolean) : [];
  const hasEvidence =
    badges.length > 0 ||
    policy.region_match ||
    policy.domain_label ||
    policy.source_label ||
    policy.match_score_label;
  const supportSummary = policy.support_summary || policy.support_content;
  const scoreMood = getScoreMood(policy);

  return (
    <article className="policy-card">
      <div className="policy-head">
        <div className="policy-title-block">
          <p className="card-eyebrow">추천 정책 {index + 1}</p>
          <h3>{displayValue(policy.policy_name, '정책명 확인 필요')}</h3>
          <div className="policy-rank-row">
            <span className={getPossibilityClass(policy.apply_possibility)}>{displayValue(policy.apply_possibility)}</span>
          </div>
        </div>
      </div>
      <div className="policy-meta">
        <span>신청 기간: {displayValue(policy.application_period)}</span>
      </div>
      {hasEvidence && (
        <section className="evidence-box">
          <div className="evidence-head">
            <strong>추천 근거</strong>
            {policy.match_score_label && (
              <div className="score-summary">
                {scoreMood && (
                  <span className={scoreMood.className} aria-label={scoreMood.label} title={scoreMood.label}>
                    {scoreMood.emoji}
                  </span>
                )}
                <span>{displayValue(policy.match_method, '검색 점수')} {policy.match_score_label}</span>
              </div>
            )}
          </div>
          <div className="evidence-grid">
            {badges.map((badge, idx) => (
              <span key={`${badge}-${idx}`}>{badge}</span>
            ))}
          </div>
        </section>
      )}
      {supportSummary && (
        <section className="mini-section">
          <h4>지원 내용 요약</h4>
          <p>{supportSummary}</p>
        </section>
      )}
      {checklist.length > 0 && (
        <section className="mini-section checklist-block">
          <h4>신청 체크리스트</h4>
          <ul className="check-list">
            {checklist.map((item, idx) => (
              <li key={`${item}-${idx}`}><CheckCircle2 size={16} /><span>{item}</span></li>
            ))}
          </ul>
        </section>
      )}
      <div className="policy-actions">
        <button className="ghost-button" type="button" onClick={() => onPrepare(policy)}><ClipboardList size={16} /> 준비 체크 시작</button>
        <button className="ghost-button" type="button" onClick={() => onChat(policy)}><MessageCircle size={16} /> 정책 상담하기</button>
        {url && <a className="link-button" href={url} target="_blank" rel="noreferrer">신청/참고 링크 열기 <ExternalLink size={15} /></a>}
      </div>
    </article>
  );
}

function policyKey(policy) {
  return policy?.doc_id || `${policy?.source_table || 'policy'}:${policy?.source_id || policy?.policy_name || 'unknown'}`;
}

function ChatPanel({ policy, messages, input, loading, suggestions, onInput, onSend, onUseSuggestion }) {
  if (!policy) return null;
  return (
    <div className="chat-screen">
      <div className="chat-context-bar">
        <p className="chat-context-label">상담 중인 정책</p>
        <h2>{displayValue(policy.policy_name, '선택한 정책')}</h2>
        <span className="count-badge">{displayValue(policy.domain_label || policy.source_label, '청년정책')}</span>
      </div>
      <div className="chat-window">
        {messages.length === 0 ? (
          <div className="chat-empty">
            <MessageCircle size={22} />
            <p>서류, 신청 방법, 자격 조건을 편하게 물어보세요.</p>
          </div>
        ) : messages.map((message, index) => (
          <div className={`chat-bubble ${message.role === 'user' ? 'user' : 'assistant'}`} key={`${message.role}-${index}`}>
            <p>{message.content}</p>
          </div>
        ))}
        {loading && <div className="chat-bubble assistant"><p><Loader2 className="spin inline-spin" size={16} /> 답변 작성 중</p></div>}
      </div>
      {suggestions.length > 0 && (
        <div className="chat-quick-questions">
          <p className="chat-quick-label">빠른 질문</p>
          <div className="suggestion-row">
            {suggestions.slice(0, 3).map((suggestion) => (
              <button type="button" className="suggestion-chip" key={suggestion} onClick={() => onUseSuggestion(suggestion)}>{suggestion}</button>
            ))}
          </div>
        </div>
      )}
      <form className="chat-composer" onSubmit={onSend}>
        <input value={input} onChange={(event) => onInput(event.target.value)} placeholder="예: 필요한 서류가 뭐예요?" />
        <button className="primary-button icon-button" type="submit" disabled={loading || !input.trim()} aria-label="전송"><Send size={17} /></button>
      </form>
    </div>
  );
}

function HomeQuickChip({ label, query, onSelect }) {
  return (
    <button className="category-chip" type="button" onClick={() => onSelect(query)}>
      {label}
    </button>
  );
}

function HomeScreen({
  userInput,
  onUserInputChange,
  onSubmit,
  loading,
  errorMessage,
  onDemo,
  onNavigate,
  savedCount,
  profileRegion,
}) {
  return (
    <main className="mobile-shell home-screen">
      <section className="home-hero-card">
        <span className="home-hero-badge">충북 청년정책 도우미</span>
        <h1 className="home-headline">내 상황에 맞는<br />정책을 찾아드려요</h1>
        <p className="home-lead">나이, 지역, 관심 분야를 입력하면 받을 수 있는 정책과 신청 준비 정보를 한 번에 확인할 수 있어요.</p>
        <p className="home-region-note">청주 · 충주 · 제천 등 충북 전역 지원</p>
      </section>

      <section className="home-search-section">
        <form className="home-search-form" onSubmit={onSubmit}>
          <label htmlFor="query-input" className="search-label">내 상황을 알려주세요</label>
          <textarea
            id="query-input"
            value={userInput}
            onChange={(event) => onUserInputChange(event.target.value)}
            placeholder="예: 충북 청주시 24살 대학생인데 월세 지원 받을 수 있을까?"
          />
          <button className="primary-button full-button" type="submit" disabled={loading}>
            {loading ? <><Loader2 className="spin" size={18} /> 찾는 중</> : <><Search size={18} /> 맞춤 정책 찾기</>}
          </button>
          <button className="text-button" type="button" onClick={onDemo}>예시 결과 보기</button>
          {errorMessage && <p className="mobile-error"><AlertCircle size={16} /> {errorMessage}</p>}
        </form>
      </section>

      <section className="home-category-section">
        <p className="section-label">관심 분야</p>
        <div className="category-scroll">
          <HomeQuickChip label="주거" query="충북 청년 주거·월세 지원 정책 추천해줘" onSelect={onUserInputChange} />
          <HomeQuickChip label="취업" query="충북 청년 취업·훈련 지원 정책 추천해줘" onSelect={onUserInputChange} />
          <HomeQuickChip label="창업" query="충북 청년 창업 지원 정책 추천해줘" onSelect={onUserInputChange} />
          <HomeQuickChip label="금융" query="충북 청년 금융·생활안정 지원 정책 추천해줘" onSelect={onUserInputChange} />
        </div>
      </section>

      <section className="home-shortcuts" aria-label="바로가기">
        <button type="button" className="home-shortcut" onClick={() => onNavigate('saved')}>
          <Bookmark size={18} aria-hidden="true" />
          <span className="home-shortcut-label">내 정책함</span>
          <strong>{savedCount}개</strong>
        </button>
        <button type="button" className="home-shortcut" onClick={() => onNavigate('profile')}>
          <UserRound size={18} aria-hidden="true" />
          <span className="home-shortcut-label">내 정보</span>
          <strong>{profileRegion}</strong>
        </button>
      </section>
    </main>
  );
}

function MobileHeader({ title, backTo = 'home', onNavigate, action }) {
  return (
    <header className="mobile-header">
      <button className="round-button" type="button" onClick={() => onNavigate(backTo)} aria-label="뒤로가기">‹</button>
      <div>
        <p className="header-brand">충북 청년정책</p>
        <h1>{title}</h1>
      </div>
      {action || <button className="round-button muted-button" type="button" onClick={() => onNavigate('saved')} aria-label="정책함">☰</button>}
    </header>
  );
}

function BottomNav({ page, onNavigate }) {
  const items = [
    ['home', '홈', Home],
    ['results', '추천', ClipboardList],
    ['saved', '정책함', Bookmark],
    ['centers', '센터', MapPin],
    ['profile', '내정보', UserRound],
  ];
  return (
    <nav className="bottom-nav" aria-label="하단 메뉴">
      {items.map(([target, label, Icon]) => (
        <button
          type="button"
          key={target}
          className={page === target ? 'active' : ''}
          onClick={() => onNavigate(target)}
        >
          <Icon size={20} strokeWidth={page === target ? 2.4 : 1.9} aria-hidden="true" />
          <span>{label}</span>
        </button>
      ))}
    </nav>
  );
}

function EmptyAction({ copy, actionLabel = '홈으로 가기', onAction }) {
  return (
    <section className="empty-mobile-card">
      <ClipboardList size={28} />
      <h2>{copy}</h2>
      <p>충북 청년에게 맞는 정책을 먼저 찾아보세요.</p>
      <button className="primary-button full-button" type="button" onClick={onAction}>{actionLabel}</button>
    </section>
  );
}

function ResultsScreen({
  recommendations,
  errorMessage,
  savedPolicyKeys,
  onNavigate,
  onSelectPolicy,
  onSavePolicy,
}) {
  return (
    <main className="mobile-shell results-screen">
      <MobileHeader title="추천 결과" onNavigate={onNavigate} />
      {errorMessage && <p className="mobile-notice">{errorMessage}</p>}
      {recommendations.length > 0 && (
        <p className="results-lead">입력하신 조건에 맞는 정책 {recommendations.length}건입니다. 자세한 내용은 상세 화면에서 확인하세요.</p>
      )}

      {recommendations.length === 0 ? (
        <section className="empty-mobile-card">
          <UserRound size={28} />
          <h2>추천 결과가 아직 없어요</h2>
          <p>홈에서 상황을 입력하거나 예시 결과를 확인해보세요.</p>
          <button className="primary-button full-button" type="button" onClick={() => onNavigate('home')}>홈으로 가기</button>
        </section>
      ) : (
        <section className="result-list">
          {recommendations.map((policy, index) => {
            const isSaved = savedPolicyKeys.has(policyKey(policy));
            return (
              <article className="result-card" key={`${policyKey(policy)}-${index}`}>
                <div className="result-card-head">
                  <span className={getPossibilityClass(policy.apply_possibility)}>{displayValue(policy.apply_possibility)}</span>
                </div>
                <h3>{displayValue(policy.policy_name, '정책명 확인 필요')}</h3>
                <p className="result-card-reason">
                  {displayValue(policy.recommend_reason || policy.reason || policy.support_summary, '추천 이유를 확인 중입니다.')}
                </p>
                <div className="result-card-actions">
                  <button type="button" className="result-detail-button" onClick={() => onSelectPolicy(policy, 'detail')}>자세히 보기</button>
                  <button
                    type="button"
                    className={`result-save-button${isSaved ? ' saved' : ''}`}
                    onClick={() => onSavePolicy(policy)}
                  >
                    {isSaved ? '담김' : '담기'}
                  </button>
                </div>
              </article>
            );
          })}
        </section>
      )}
    </main>
  );
}

function DetailScreen({
  policy,
  recommendations,
  profile,
  userCondition,
  centers,
  onNavigate,
  onSavePolicy,
  onSelectPolicy,
  onViewCenters,
  onApplyAssistant,
}) {
  if (!policy) {
    return (
      <main className="mobile-shell">
        <MobileHeader title="정책 상세" backTo="results" onNavigate={onNavigate} />
        <EmptyAction copy="선택한 정책이 없어요." onAction={() => onNavigate('home')} />
      </main>
    );
  }

  const url = policy.application_url || policy.url || policy.ref_url;
  const checklist = Array.isArray(policy.checklist) ? policy.checklist : [];
  const policyIndex = recommendations.findIndex((item) => policyKey(item) === policyKey(policy));
  const rankLabel = policyIndex >= 0 ? `추천 정책 ${policyIndex + 1}` : '관심 정책';
  const possibility = getPossibilityDisplay(policy.apply_possibility);
  const keywords = buildRecommendKeywords(policy);
  const supportText = policy.support_summary || policy.support_content;
  const reasonText = policy.recommend_reason || policy.reason || supportText;
  const periodText = displayValue(policy.application_period || policy.apply_period, '신청 기간 확인 필요');

  return (
    <main className="mobile-shell detail-page">
      <MobileHeader title="정책 상세" backTo="results" onNavigate={onNavigate} />

      <article className="detail-summary-hero">
        <p className="detail-rank-label">{rankLabel}</p>
        <h1 className="detail-policy-title">{displayValue(policy.policy_name, '정책명 확인 필요')}</h1>
        <div className="detail-meta-row">
          <div className="detail-score-group">
            <span className="detail-score-emoji" aria-hidden="true">{possibility.emoji}</span>
            <span className={getPossibilityClass(policy.apply_possibility)}>{possibility.label}</span>
          </div>
          <span className="detail-period-pill">{periodText}</span>
        </div>
      </article>

      <div className="detail-card-stack">
        <DetailSectionCard title="추천 근거">
          <ul className="detail-keyword-list">
            {keywords.map((keyword, index) => (
              <li key={`${keyword}-${index}`}>{keyword}</li>
            ))}
          </ul>
          <ExpandableSummary text={reasonText} fallback="추천 근거를 확인 중입니다." maxChars={120} />
        </DetailSectionCard>

        <DetailSectionCard title="지원 내용 요약">
          <ExpandableSummary text={supportText} fallback="지원 내용을 확인 중입니다." />
        </DetailSectionCard>

        {checklist.length > 0 && (
          <DetailSectionCard title="신청 체크리스트">
            <ul className="detail-checklist">
              {checklist.map((item, index) => (
                <li key={`${item}-${index}`}>
                  <CheckCircle2 size={16} aria-hidden="true" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </DetailSectionCard>
        )}

        <DetailSectionCard title="신청 방법">
          <ExpandableSummary text={policy.apply_method} fallback="공고문 또는 담당 기관에서 확인해주세요." maxChars={120} />
          {url ? (
            <a className="detail-apply-link" href={url} target="_blank" rel="noreferrer">
              공식 신청 링크 열기 <ExternalLink size={14} />
            </a>
          ) : (
            <p className="detail-apply-link-missing">공식 신청 링크는 데이터에서 확인 필요</p>
          )}
        </DetailSectionCard>
      </div>

      <YouthCenterCard
        regionText={getRegionForCenters(profile, userCondition)}
        center={getDisplayCenters(centers)[0]}
        onViewCenters={onViewCenters}
        buttonLabel="센터 보기"
      />

      <div className="detail-action-bar" aria-label="정책 액션">
        <button className="detail-action-button primary" type="button" onClick={() => onSavePolicy(policy)}>담기</button>
        <button className="detail-action-button" type="button" onClick={() => onSelectPolicy(policy, 'prep')}>준비</button>
        <button className="detail-action-button" type="button" onClick={() => onSelectPolicy(policy, 'chat')}>상담</button>
        <button className="detail-action-button" type="button" onClick={() => onApplyAssistant(policy)}>신청 도우미</button>
      </div>
    </main>
  );
}

function SavedMonthCalendar({ events, today }) {
  const initialMonth = useMemo(() => {
    const firstDated = events.find((event) => event.deadlineAt);
    if (firstDated?.deadlineAt) {
      const [year, month] = firstDated.deadlineAt.split('-').map(Number);
      return { year, month: month - 1 };
    }
    const now = new Date();
    return { year: now.getFullYear(), month: now.getMonth() };
  }, [events]);

  const [viewYear, setViewYear] = useState(initialMonth.year);
  const [viewMonth, setViewMonth] = useState(initialMonth.month);
  const [selectedDate, setSelectedDate] = useState(null);

  useEffect(() => {
    setViewYear(initialMonth.year);
    setViewMonth(initialMonth.month);
  }, [initialMonth.year, initialMonth.month]);

  const eventsByDate = useMemo(() => groupEventsByDeadlineDate(events), [events]);
  const cells = useMemo(() => buildMonthCalendarCells(viewYear, viewMonth, today), [viewYear, viewMonth, today]);
  const weekdayLabels = ['일', '월', '화', '수', '목', '금', '토'];
  const selectedEvents = selectedDate ? eventsByDate.get(selectedDate) || [] : [];

  function shiftMonth(delta) {
    const next = new Date(viewYear, viewMonth + delta, 1);
    setViewYear(next.getFullYear());
    setViewMonth(next.getMonth());
    setSelectedDate(null);
  }

  return (
    <section className="saved-month-calendar" aria-label="마감 월간 캘린더">
      <div className="saved-month-calendar-head">
        <button type="button" className="round-button muted-button" onClick={() => shiftMonth(-1)} aria-label="이전 달">
          <ChevronLeft size={18} />
        </button>
        <strong>{formatMonthTitle(viewYear, viewMonth)}</strong>
        <button type="button" className="round-button muted-button" onClick={() => shiftMonth(1)} aria-label="다음 달">
          <ChevronRight size={18} />
        </button>
      </div>
      <div className="saved-month-weekdays">
        {weekdayLabels.map((label) => (
          <span key={label}>{label}</span>
        ))}
      </div>
      <div className="saved-month-grid">
        {cells.map((cell) => {
          if (cell.type === 'padding') {
            return <div className="saved-month-cell padding" key={cell.key} aria-hidden="true" />;
          }
          const dayEvents = eventsByDate.get(cell.iso) || [];
          const isSelected = selectedDate === cell.iso;
          return (
            <button
              type="button"
              key={cell.key}
              className={`saved-month-cell${cell.isToday ? ' today' : ''}${isSelected ? ' selected' : ''}${dayEvents.length ? ' has-events' : ''}`}
              onClick={() => setSelectedDate(cell.iso)}
              aria-label={`${cell.day}일, 마감 ${dayEvents.length}건`}
            >
              <span className="saved-month-day">{cell.day}</span>
              <div className="saved-month-events">
                {dayEvents.slice(0, 2).map((event) => (
                  <span
                    className={`saved-month-event ${event.deadlineStatus || 'open'}`}
                    key={`${event.policyKey}-${cell.iso}`}
                    title={event.policyName}
                  >
                    <em>{formatDdayLabel(event.daysLeft, event.deadlineStatus)}</em>
                    <span>{event.policyName}</span>
                  </span>
                ))}
                {dayEvents.length > 2 && (
                  <span className="saved-month-more">+{dayEvents.length - 2}</span>
                )}
              </div>
            </button>
          );
        })}
      </div>
      {selectedDate && (
        <div className="saved-month-selected">
          <p className="saved-month-selected-title">{selectedDate} 마감 일정</p>
          {selectedEvents.length === 0 ? (
            <p className="muted">이 날짜에 마감 정책이 없습니다.</p>
          ) : (
            <ul className="saved-month-selected-list">
              {selectedEvents.map((event) => (
                <li key={`${event.policyKey}-${selectedDate}`}>
                  <strong>{formatDdayLabel(event.daysLeft, event.deadlineStatus)}</strong>
                  <span>{event.policyName}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}

function SavedScreen({
  savedPolicies,
  checkedPrepByPolicy,
  hasResult,
  onNavigate,
  onSelectPolicy,
  onRemoveSavedPolicy,
  planTier,
  savedLimit,
  notificationSettings,
  onNotificationChange,
  onPlanTierChange,
  onAddDemoAlarmPolicies,
  onClearDemoAlarm,
  onNotify,
  calendarEvents,
  today,
}) {
  const [savedTab, setSavedTab] = useState('list');
  const [alarmTestMessage, setAlarmTestMessage] = useState('');
  const urgentCount = calendarEvents.filter((event) => event.deadlineStatus === 'urgent').length;
  const demoAlarmActive = useMemo(() => hasDemoAlarmPolicies(savedPolicies), [savedPolicies]);
  const todayAlerts = useMemo(
    () => getDeadlineAlerts(calendarEvents, notificationSettings, today),
    [calendarEvents, notificationSettings, today],
  );
  const isPro = planTier === 'pro';

  function handleExportCalendar() {
    if (!isPro) return;
    downloadIcsFile(calendarEvents, 'chungbuk-youth-policy-deadlines.ics', notificationSettings);
  }

  async function handleAlarmTest() {
    const result = await runDemoAlarmTest(calendarEvents, notificationSettings, today);
    setAlarmTestMessage(result.message);
    if (result.ok) onNotify?.(result.message);
  }

  function handleClearDemoAlarm() {
    onClearDemoAlarm?.();
    setAlarmTestMessage('');
  }

  function toggleNotification(enabled) {
    if (!isPro) return;
    if (!enabled) {
      onNotificationChange({ ...notificationSettings, enabled: false });
      return;
    }
    enableDeadlineNotifications(notificationSettings).then((result) => {
      if (!result.ok) {
        window.alert(result.message);
        return;
      }
      onNotificationChange({ ...notificationSettings, enabled: true });
    });
  }

  return (
    <main className="mobile-shell saved-screen">
      <MobileHeader title="내 정책함" onNavigate={onNavigate} />
      <section className="saved-intro">
        <div className="saved-intro-head">
          <div>
            <h2>관심 정책함</h2>
            <p>마음에 드는 정책을 모아두고, 신청 준비와 마감 일정까지 이어가세요.</p>
          </div>
          <div className="saved-plan-switch" role="group" aria-label="시연용 요금제 전환">
            <button
              type="button"
              className={!isPro ? 'active' : ''}
              aria-pressed={!isPro}
              onClick={() => onPlanTierChange('free')}
            >
              Free
            </button>
            <button
              type="button"
              className={isPro ? 'active pro' : ''}
              aria-pressed={isPro}
              onClick={() => onPlanTierChange('pro')}
            >
              Pro
            </button>
          </div>
        </div>
        <p className="saved-limit-note">
          저장 {savedPolicies.length}/{savedLimit}개
          {!isPro && ' · Pro 모드에서 무제한'}
        </p>
      </section>

      <div className="saved-tab-bar" role="tablist" aria-label="정책함 보기">
        <button type="button" className={savedTab === 'list' ? 'active' : ''} onClick={() => setSavedTab('list')}>목록</button>
        <button type="button" className={savedTab === 'alerts' ? 'active' : ''} onClick={() => setSavedTab('alerts')}>
          마감 알림{todayAlerts.length > 0 ? ` (${todayAlerts.length})` : ''}
        </button>
        <button type="button" className={savedTab === 'calendar' ? 'active' : ''} onClick={() => setSavedTab('calendar')}>
          캘린더{urgentCount > 0 ? ` (${urgentCount})` : ''}
        </button>
      </div>

      {savedTab === 'alerts' && (
        <section className="saved-calendar-panel">
          <div className="saved-calendar-actions">
            <button
              type="button"
              className="secondary-button full-button"
              onClick={handleExportCalendar}
              disabled={!isPro}
            >
              <CalendarDays size={16} /> 캘린더 파일 내보내기{!isPro ? ' (Pro)' : ''}
            </button>
          </div>
          <div className="saved-notification-card">
            <div className="saved-notification-head">
              <Bell size={18} aria-hidden="true" />
              <div>
                <strong>마감 알림</strong>
                <p>D-7 · D-3 · D-1 · 당일 알림 {!isPro && '(Pro)'}</p>
              </div>
              <label className="saved-toggle">
                <input
                  type="checkbox"
                  checked={Boolean(notificationSettings.enabled)}
                  disabled={!isPro}
                  onChange={(event) => toggleNotification(event.target.checked)}
                />
                <span />
              </label>
            </div>
            {notificationSettings.enabled && (
              <>
                <p className="saved-notification-copy">
                  D-7 · D-3 · D-1 · 당일 알림이 오늘 해당되면 앱이 켜져 있을 때 자동 발송됩니다. (하루 1회)
                </p>
                {isPro && (
                  <div className="saved-alarm-demo">
                    <p className="saved-alarm-preview-title">
                      오늘 예정 알림 {todayAlerts.length}건
                    </p>
                    {todayAlerts.length > 0 ? (
                      <ul className="saved-alarm-preview-list">
                        {todayAlerts.map((alert) => (
                          <li key={`${alert.policyKey}-${alert.alertLabel}`}>
                            <strong>{alert.alertLabel}</strong> {alert.policyName}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="muted">오늘 울릴 알림이 없습니다. 아래 버튼으로 시연 데이터를 추가하세요.</p>
                    )}
                    <button type="button" className="secondary-button full-button" onClick={onAddDemoAlarmPolicies}>
                      시연용 마감 정책 추가 (D-7/D-3/D-1/당일)
                    </button>
                    <button type="button" className="primary-button full-button" onClick={handleAlarmTest}>
                      브라우저 알림 테스트
                    </button>
                    {(demoAlarmActive || notificationSettings.enabled) && (
                      <button type="button" className="ghost-button full-button saved-alarm-off-button" onClick={handleClearDemoAlarm}>
                        알림 시연 끄기
                      </button>
                    )}
                    {alarmTestMessage && <p className="saved-alarm-result">{alarmTestMessage}</p>}
                    <p className="saved-alarm-hint">
                      캘린더 앱 알람은 「캘린더 파일 내보내기」로 .ics를 가져온 뒤, 일정 알림을 확인하세요.
                    </p>
                  </div>
                )}
              </>
            )}
          </div>
          {calendarEvents.length === 0 ? (
            <EmptyAction copy="알림을 설정할 마감 정책이 없어요." actionLabel="추천 보러 가기" onAction={() => onNavigate(hasResult ? 'results' : 'home')} />
          ) : (
            <>
              <h3 className="saved-calendar-subtitle">마감 일정 목록</h3>
              <div className="saved-calendar-list">
                {calendarEvents.map((event) => (
                  <article className={`saved-calendar-item ${event.deadlineStatus || ''}`} key={event.policyKey}>
                    <div className="saved-calendar-item-head">
                      <span className={`status-chip ${event.deadlineStatus || 'needs_date_check'}`}>
                        {formatDdayLabel(event.daysLeft, event.deadlineStatus)}
                      </span>
                      {event.deadlineAt && <time dateTime={event.deadlineAt}>{event.deadlineAt}</time>}
                    </div>
                    <h3>{event.policyName}</h3>
                    <p>{event.applicationPeriod || '신청 기간 확인 필요'}</p>
                  </article>
                ))}
              </div>
            </>
          )}
        </section>
      )}

      {savedTab === 'calendar' && (
        <section className="saved-calendar-panel">
          {calendarEvents.length === 0 ? (
            <EmptyAction copy="캘린더에 표시할 정책이 없어요." actionLabel="추천 보러 가기" onAction={() => onNavigate(hasResult ? 'results' : 'home')} />
          ) : (
            <SavedMonthCalendar events={calendarEvents} today={today} />
          )}
        </section>
      )}

      {savedTab === 'list' && (
        savedPolicies.length === 0 ? (
          <EmptyAction
            copy="아직 담은 정책이 없어요."
            actionLabel="추천 보러 가기"
            onAction={() => onNavigate(hasResult ? 'results' : 'home')}
          />
        ) : (
          <section className="saved-list">
            {savedPolicies.map((policy) => {
              const items = buildPreparationItems(policy);
              const stats = getCompletionStats(items, checkedPrepByPolicy[policyKey(policy)] || {});
              const calendarEvent = calendarEvents.find((event) => event.policyKey === policyKey(policy));
              return (
                <article className="saved-item-card" key={policyKey(policy)}>
                  <div className="saved-item-head">
                    <span className="saved-item-badge">준비 {stats.percent}%</span>
                    {calendarEvent && (
                      <span className={`saved-deadline-pill ${calendarEvent.deadlineStatus || ''}`}>
                        {formatDdayLabel(calendarEvent.daysLeft, calendarEvent.deadlineStatus)}
                      </span>
                    )}
                    <h3>{displayValue(policy.policy_name, '정책명 확인 필요')}</h3>
                    <p className="saved-item-meta">{displayValue(policy.application_period, '신청 기간 확인 필요')}</p>
                  </div>
                  <div className="saved-item-progress" aria-hidden="true"><div style={{ width: `${stats.percent}%` }} /></div>
                  <div className="saved-item-actions">
                    <button type="button" onClick={() => onSelectPolicy(policy, 'prep')}>신청 준비</button>
                    <button type="button" onClick={() => onSelectPolicy(policy, 'detail')}>상세 보기</button>
                    <button type="button" className="danger-text" onClick={() => onRemoveSavedPolicy(policy)}>삭제</button>
                  </div>
                </article>
              );
            })}
          </section>
        )
      )}
    </main>
  );
}

function PrepScreen({
  policy,
  checkedItems,
  onNavigate,
  onSelectPolicy,
  onTogglePreparation,
}) {
  if (!policy) {
    return (
      <main className="mobile-shell">
        <MobileHeader title="신청 준비" backTo="saved" onNavigate={onNavigate} />
        <EmptyAction copy="준비할 정책을 먼저 선택해주세요." onAction={() => onNavigate('saved')} />
      </main>
    );
  }

  return (
    <main className="mobile-shell prep-screen">
      <MobileHeader title="신청 준비" backTo="detail" onNavigate={onNavigate} />
      <PreparationBoard policy={policy} checkedItems={checkedItems} onToggle={onTogglePreparation} />
      <div className="prep-action-buttons">
        <button className="primary-button full-button" type="button" onClick={() => onSelectPolicy(policy, 'chat')}>정책 상담하기</button>
        <button className="secondary-button full-button" type="button" onClick={() => onNavigate('centers')}>청년센터 상담하기</button>
        <button className="secondary-button full-button" type="button" onClick={() => onNavigate('saved')}>정책함으로 돌아가기</button>
      </div>
    </main>
  );
}

function ChatScreen({
  policy,
  messages,
  chatInput,
  chatLoading,
  chatSuggestions,
  onChatInput,
  onSendChat,
  onUseSuggestion,
  onNavigate,
}) {
  if (!policy) {
    return (
      <main className="mobile-shell">
        <MobileHeader title="정책 상담" backTo="detail" onNavigate={onNavigate} />
        <EmptyAction copy="상담할 정책을 먼저 선택해주세요." onAction={() => onNavigate('detail')} />
      </main>
    );
  }

  return (
    <main className="mobile-shell chat-screen-page">
      <MobileHeader title="정책 상담" backTo="detail" onNavigate={onNavigate} />
      <ChatPanel
        policy={policy}
        messages={messages}
        input={chatInput}
        loading={chatLoading}
        suggestions={chatSuggestions}
        onInput={onChatInput}
        onSend={onSendChat}
        onUseSuggestion={onUseSuggestion}
      />
    </main>
  );
}

function CenterScreen({ regionText, centers, onNavigate, backTo = 'home' }) {
  return (
    <main className="mobile-shell center-screen">
      <MobileHeader title="청년센터" backTo={backTo} onNavigate={onNavigate} />
      <section className="center-intro-card">
        <span className="home-hero-badge">충북 청년정책 도우미</span>
        <h2>{regionText} 지역 청년센터</h2>
        <p>정책 신청이 헷갈리면 가까운 청년센터에서 상담을 받을 수 있어요.</p>
      </section>
      <section className="center-list">
        {centers.map((center, index) => (
          <article className="center-item-card" key={`${center.center_name || 'center'}-${index}`}>
            <h3>{displayValue(center.center_name, '센터명 확인 필요')}</h3>
            <p>{displayValue(center.center_addr, '주소 확인 필요')}</p>
            {center.center_tel && <p className="center-item-tel">{center.center_tel}</p>}
            {center.center_url ? (
              <a className="detail-apply-link" href={center.center_url} target="_blank" rel="noreferrer">
                상담 연결 <ExternalLink size={14} />
              </a>
            ) : (
              <p className="detail-apply-link-missing">센터 연락처는 데이터에서 확인 필요</p>
            )}
          </article>
        ))}
      </section>
    </main>
  );
}

function ProfileScreen({ profile, recommendations, onLogin, savingProfile, onNavigate }) {
  return (
    <main className="mobile-shell profile-screen">
      <MobileHeader title="내 정보" onNavigate={onNavigate} />
      <LoginPanel profile={profile} onLogin={onLogin} saving={savingProfile} />
      <IncomeTaxCalculator />
      {recommendations.length > 0 && <EligibilityGapPanel recommendations={recommendations} profile={profile} />}
    </main>
  );
}

function ApplyAssistantScreen({
  policy,
  baseUrl,
  userId,
  applyPlan,
  applyLoading,
  applyError,
  myApplications,
  myApplicationsLoading,
  onApplyPlan,
  onToggleItem,
  onStatusChange,
  onOpenApplication,
  onNavigate,
}) {
  return (
    <main className="mobile-shell apply-assistant-screen">
      <MobileHeader title="신청 도우미" backTo="detail" onNavigate={onNavigate} />
      {policy && (
        <section className="apply-policy-summary">
          <span className="home-hero-badge">AI 신청 도우미</span>
          <h2>{policy.policy_name || '선택한 정책'}</h2>
          <p>대화로 신청 자격을 확인하고, 맞춤 신청 체크리스트를 만들어 드려요.</p>
        </section>
      )}
      <ChatFlowPanel
        baseUrl={baseUrl}
        userId={userId}
        seededPolicy={policy}
        seededRecommendation={policy}
        onApplyPlan={onApplyPlan}
      />
      <div id="apply-plan-anchor">
        {(applyPlan || applyLoading) && (
          <ApplyPanel
            plan={applyPlan}
            loading={applyLoading}
            error={applyError}
            onToggleItem={onToggleItem}
            onStatusChange={onStatusChange}
          />
        )}
      </div>
      <MyApplicationsPanel
        applications={myApplications}
        loading={myApplicationsLoading}
        onOpen={onOpenApplication}
      />
    </main>
  );
}


export default function App() {
  const SAVED_STORAGE_KEY = 'youth-policy-saved-policies';
  const [page, setPage] = useState('home');
  const [userInput, setUserInput] = useState('');
  const [profile, setProfile] = useState(() => {
    try {
      const saved = localStorage.getItem(PROFILE_STORAGE_KEY);
      return saved ? sanitizeProfile(JSON.parse(saved)) : null;
    } catch {
      return null;
    }
  });
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [savingProfile, setSavingProfile] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [activePolicy, setActivePolicy] = useState(null);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [chatByPolicy, setChatByPolicy] = useState({});
  const [chatSuggestions, setChatSuggestions] = useState([]);
  const [selectedPrepPolicy, setSelectedPrepPolicy] = useState(null);
  const [toast, setToast] = useState('');
  const [savedPolicies, setSavedPolicies] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem(SAVED_STORAGE_KEY) || '[]');
    } catch {
      return [];
    }
  });
  const [checkedPrepByPolicy, setCheckedPrepByPolicy] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem(PREP_STORAGE_KEY) || '{}');
    } catch {
      return {};
    }
  });
  const [centersBackTo, setCentersBackTo] = useState('home');
  const [applyPlan, setApplyPlan] = useState(null);
  const [applyLoading, setApplyLoading] = useState(false);
  const [applyError, setApplyError] = useState('');
  const [myApplications, setMyApplications] = useState([]);
  const [myApplicationsLoading, setMyApplicationsLoading] = useState(false);
  const [notificationSettings, setNotificationSettings] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem(NOTIFICATION_STORAGE_KEY) || 'null') || defaultNotificationSettings();
    } catch {
      return defaultNotificationSettings();
    }
  });
  const planTier = notificationSettings.plan_tier || 'free';
  const savedLimit = planTier === 'pro' ? 999 : FREE_SAVED_LIMIT;
  const today = useTodayTick(60000);
  const todayKey = formatTodayKey(today);
  const savedCalendarEvents = useMemo(
    () => buildSavedCalendarEvents(savedPolicies, today),
    [savedPolicies, todayKey],
  );

  const data = useMemo(() => normalizeResult(result), [result]);
  const activePolicyKey = activePolicy ? policyKey(activePolicy) : '';
  const activeMessages = activePolicyKey ? (chatByPolicy[activePolicyKey] || []) : [];
  const selectedPrepPolicyKey = selectedPrepPolicy ? policyKey(selectedPrepPolicy) : '';
  const selectedPrepChecked = selectedPrepPolicyKey ? (checkedPrepByPolicy[selectedPrepPolicyKey] || {}) : {};
  const savedPolicyKeys = useMemo(() => new Set(savedPolicies.map(policyKey)), [savedPolicies]);

  useEffect(() => {
    localStorage.setItem(PREP_STORAGE_KEY, JSON.stringify(checkedPrepByPolicy));
  }, [checkedPrepByPolicy]);

  useEffect(() => {
    localStorage.setItem(SAVED_STORAGE_KEY, JSON.stringify(savedPolicies));
  }, [savedPolicies]);

  useEffect(() => {
    localStorage.setItem(NOTIFICATION_STORAGE_KEY, JSON.stringify(notificationSettings));
  }, [notificationSettings]);

  useEffect(() => {
    if (planTier !== 'pro' || !notificationSettings.enabled || savedPolicies.length === 0) {
      return undefined;
    }

    let cancelled = false;
    const run = async () => {
      if (cancelled) return;
      const permission = await requestNotificationPermission();
      if (cancelled || permission !== 'granted') return;
      processScheduledDeadlineNotifications(savedCalendarEvents, notificationSettings, new Date());
    };

    run();
    const intervalId = window.setInterval(run, 60000);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [planTier, notificationSettings, savedCalendarEvents, todayKey, savedPolicies.length]);

  useEffect(() => {
    if (!profile?.user_id) return;
    fetchNotificationSettings(profile.user_id)
      .then((settings) => setNotificationSettings(settings))
      .catch(() => {});
  }, [profile?.user_id]);

  useEffect(() => {
    if (!profile?.user_id || savedPolicies.length === 0) return;
    syncSavedPolicies(profile.user_id, savedPolicies).catch(() => {});
  }, [profile?.user_id, savedPolicies]);

  useEffect(() => {
    refreshMyApplications(profile?.user_id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profile?.user_id]);

  function setDemoPlanTier(tier) {
    setNotificationSettings((prev) => ({ ...prev, plan_tier: tier }));
  }

  async function updateNotificationSettings(nextSettings) {
    setNotificationSettings(nextSettings);
    if (!profile?.user_id) return;
    try {
      const saved = await saveNotificationSettings(profile.user_id, nextSettings);
      setNotificationSettings(saved);
    } catch (error) {
      console.error(error);
    }
  }

  function notify(message) {
    setToast(message);
    window.clearTimeout(window.__policyToastTimer);
    window.__policyToastTimer = window.setTimeout(() => setToast(''), 1800);
  }

  function go(nextPage) {
    setPage(nextPage);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function openCenters(backTo = 'home') {
    setCentersBackTo(backTo);
    go('centers');
  }

  function navigateTab(target) {
    if (target === 'centers') {
      openCenters('home');
      return;
    }
    go(target);
  }

  async function handleLogin(profileInput) {
    setSavingProfile(true);
    setErrorMessage('');
    try {
      const response = await fetch(USER_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(profileInput),
      });
      if (!response.ok) throw new Error(`사용자 저장 실패: ${response.status}`);
      const savedProfile = sanitizeProfile({
        ...(await response.json()),
        household_size: profileInput.household_size,
        monthly_income: profileInput.monthly_income,
        median_income_percent: profileInput.median_income_percent,
      });
      setProfile(savedProfile);
      localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(savedProfile));
      notify('내 정보가 저장됐어요');
      go('home');
    } catch (error) {
      const offlineProfile = sanitizeProfile({
        ...profileInput,
        user_id: `local-${Date.now()}`,
        created_at: new Date().toLocaleString('ko-KR'),
      });
      setProfile(offlineProfile);
      localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(offlineProfile));
      notify('백엔드 없이 기기에 임시 저장했어요');
      go('home');
      console.error(error);
    } finally {
      setSavingProfile(false);
    }
  }

  async function handleSubmit(event, fallbackToDemo = true) {
    event?.preventDefault();
    const trimmedInput = userInput.trim();
    const profileText = buildProfileText(profile);
    if (!trimmedInput && !hasMeaningfulProfile(profile)) {
      setResult(null);
      setErrorMessage(NO_CONDITION_MESSAGE);
      return;
    }
    setLoading(true);
    setErrorMessage('');
    const enrichedInput = profileText
      ? `질문: ${trimmedInput || '맞춤 정책 추천해줘'}\n저장된 사용자 정보: ${profileText}`
      : trimmedInput;
    try {
      const response = await fetch(RECOMMEND_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_input: enrichedInput }),
      });
      if (!response.ok) throw new Error(`서버 응답 오류: ${response.status} ${await response.text()}`);
      const nextResult = await response.json();
      setResult(nextResult);
      setActivePolicy(null);
      setSelectedPrepPolicy(null);
      setChatInput('');
      setChatSuggestions([]);
      go('results');
    } catch (error) {
      console.error(error);
      if (fallbackToDemo) {
        setResult(buildDemoResult(trimmedInput, profile));
        setErrorMessage('백엔드 연결 전이라 충북 시연용 예시 결과를 보여줍니다.');
        go('results');
      } else {
        setErrorMessage('백엔드 연결에 실패했습니다. VITE_API_URL과 서버 CORS 설정을 확인해주세요.');
      }
    } finally {
      setLoading(false);
    }
  }

  function openDemo() {
    setResult(buildDemoResult(userInput, profile));
    setErrorMessage('시연용 예시 결과를 확인할 수 있습니다.');
    go('results');
  }

  function selectPolicy(policy, nextPage = 'detail') {
    setActivePolicy(policy);
    setSelectedPrepPolicy(policy);
    setChatInput('');
    setChatSuggestions([
      '이 정책에서 필요한 서류는 뭐야?',
      '내가 신청 가능할까?',
      '신청 순서를 알려줘',
    ]);
    go(nextPage);
  }

  function openApplyAssistant(policy) {
    setActivePolicy(policy);
    setApplyPlan(null);
    setApplyError('');
    go('apply');
  }

  async function refreshMyApplications(userId) {
    if (!userId) {
      setMyApplications([]);
      return;
    }
    setMyApplicationsLoading(true);
    try {
      setMyApplications(await fetchApplications(API_BASE_URL, userId));
    } catch (error) {
      console.error(error);
    } finally {
      setMyApplicationsLoading(false);
    }
  }

  async function openMyApplication(applicationId) {
    setApplyLoading(true);
    setApplyError('');
    try {
      setApplyPlan(await fetchApplication(API_BASE_URL, applicationId));
    } catch (error) {
      setApplyError('신청 건을 불러오지 못했습니다.');
      console.error(error);
    } finally {
      setApplyLoading(false);
    }
  }

  // ChatFlowPanel의 onApplyPlan 콜백 — 신청 플랜 생성 후 해당 패널로 스크롤
  async function startApplyPlan(policy) {
    setApplyLoading(true);
    setApplyError('');
    try {
      const plan = await createApplyPlan(API_BASE_URL, policy, profile?.user_id);
      setApplyPlan(plan);
      refreshMyApplications(profile?.user_id);
      window.requestAnimationFrame(() => {
        document.getElementById('apply-plan-anchor')?.scrollIntoView({
          behavior: 'smooth',
          block: 'start',
        });
      });
    } catch (error) {
      setApplyPlan(null);
      setApplyError('신청 플랜을 만들지 못했습니다. 백엔드 서버를 확인해주세요.');
      console.error(error);
    } finally {
      setApplyLoading(false);
    }
  }

  async function handleApplyItemToggle(itemId, checked) {
    if (!applyPlan) return;
    try {
      const updated = await toggleApplyItem(API_BASE_URL, applyPlan.application_id, itemId, checked);
      setApplyPlan((prev) => ({ ...prev, ...updated }));
      setApplyError('');
    } catch (error) {
      setApplyError('체크 상태를 저장하지 못했습니다.');
      console.error(error);
    }
  }

  async function handleApplyStatusChange(status) {
    if (!applyPlan) return;
    try {
      const updated = await updateApplyStatus(API_BASE_URL, applyPlan.application_id, status);
      setApplyPlan((prev) => ({ ...prev, ...updated }));
      setApplyError('');
      refreshMyApplications(profile?.user_id);
    } catch (error) {
      setApplyError('상태를 변경하지 못했습니다.');
      console.error(error);
    }
  }

  function savePolicy(policy) {
    const key = policyKey(policy);
    if (savedPolicyKeys.has(key)) {
      notify('이미 정책함에 담긴 정책이에요');
      return;
    }
    if (savedPolicies.length >= savedLimit) {
      notify(`Free 모드는 ${FREE_SAVED_LIMIT}개까지 저장할 수 있어요. Pro 버튼을 눌러 무제한으로 체험해 보세요.`);
      return;
    }
    setSavedPolicies((prev) => [...prev, policy]);
    notify('정책함에 담았어요');
  }

  function removeSavedPolicy(policy) {
    const key = policyKey(policy);
    setSavedPolicies((prev) => prev.filter((item) => policyKey(item) !== key));
    notify('정책함에서 삭제했어요');
  }

  function addDemoAlarmPolicies() {
    const demoPolicies = buildDemoAlarmPolicies();
    setSavedPolicies((prev) => {
      const existing = new Set(prev.map(policyKey));
      const next = [...prev];
      demoPolicies.forEach((policy) => {
        if (!existing.has(policyKey(policy))) next.push(policy);
      });
      return next;
    });
    setNotificationSettings((prev) => ({ ...prev, enabled: true, plan_tier: 'pro' }));
    notify('시연용 마감 정책 4건을 추가했어요. 알림 테스트를 진행하세요.');
  }

  function clearDemoAlarmDemo() {
    setSavedPolicies((prev) => prev.filter((policy) => !isDemoAlarmPolicy(policy)));
    setNotificationSettings((prev) => ({ ...prev, enabled: false }));
    clearSentDeadlineAlerts();
    notify('알림 시연을 종료했어요.');
  }

  function togglePreparation(policyId, item, checked) {
    setCheckedPrepByPolicy((prev) => togglePreparationItem(prev, policyId, item, checked));
  }

  async function sendChatMessage(event, forcedText = '') {
    event?.preventDefault();
    if (!activePolicy) return;
    const text = (forcedText || chatInput).trim();
    if (!text) return;
    const key = policyKey(activePolicy);
    const nextMessages = [...(chatByPolicy[key] || []), { role: 'user', content: text }];
    setChatByPolicy((prev) => ({ ...prev, [key]: nextMessages }));
    setChatInput('');
    setChatLoading(true);
    try {
      const response = await fetch(CHAT_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          policy: activePolicy,
          user_context: buildChatUserContext(data.user_condition || {}, profile || {}),
          messages: nextMessages,
        }),
      });
      if (!response.ok) throw new Error(`챗봇 응답 오류: ${response.status} ${await response.text()}`);
      const payload = await response.json();
      const answer = payload.answer || '답변을 생성하지 못했습니다.';
      setChatByPolicy((prev) => ({ ...prev, [key]: [...nextMessages, { role: 'assistant', content: answer }] }));
      setChatSuggestions(Array.isArray(payload.suggested_questions) ? payload.suggested_questions : []);
    } catch (error) {
      setChatByPolicy((prev) => ({
        ...prev,
        [key]: [
          ...nextMessages,
          {
            role: 'assistant',
            content:
              '현재는 모바일 시연 모드입니다. 실제 배포 시 /chat API에 연결되어 선택한 정책의 서류·자격·신청 방법을 DB 근거로 답변합니다.',
          },
        ],
      }));
      setChatSuggestions(['신청 기간은 언제야?', '필요 서류를 정리해줘', '청년센터 상담이 필요해']);
      console.error(error);
    } finally {
      setChatLoading(false);
    }
  }

  function useChatSuggestion(suggestion) {
    sendChatMessage(null, suggestion);
  }

  const homeScreenProps = {
    userInput,
    onUserInputChange: setUserInput,
    onSubmit: handleSubmit,
    loading,
    errorMessage,
    onDemo: openDemo,
    onNavigate: go,
    savedCount: savedPolicies.length,
    profileRegion: regionLabel(profile),
  };

  const currentScreen = {
    home: <HomeScreen {...homeScreenProps} />,
    results: (
      <ResultsScreen
        recommendations={data.recommendations.slice(0, 5)}
        errorMessage={errorMessage}
        savedPolicyKeys={savedPolicyKeys}
        onNavigate={go}
        onSelectPolicy={selectPolicy}
        onSavePolicy={savePolicy}
      />
    ),
    detail: (
      <DetailScreen
        policy={activePolicy || selectedPrepPolicy}
        recommendations={data.recommendations}
        profile={profile}
        userCondition={data.user_condition}
        centers={data.centers}
        onNavigate={go}
        onSavePolicy={savePolicy}
        onSelectPolicy={selectPolicy}
        onViewCenters={() => openCenters('detail')}
        onApplyAssistant={openApplyAssistant}
      />
    ),
    apply: (
      <ApplyAssistantScreen
        policy={activePolicy || selectedPrepPolicy}
        baseUrl={API_BASE_URL}
        userId={profile?.user_id}
        applyPlan={applyPlan}
        applyLoading={applyLoading}
        applyError={applyError}
        myApplications={myApplications}
        myApplicationsLoading={myApplicationsLoading}
        onApplyPlan={startApplyPlan}
        onToggleItem={handleApplyItemToggle}
        onStatusChange={handleApplyStatusChange}
        onOpenApplication={openMyApplication}
        onNavigate={go}
      />
    ),
    saved: (
      <SavedScreen
        savedPolicies={savedPolicies}
        checkedPrepByPolicy={checkedPrepByPolicy}
        hasResult={Boolean(result)}
        onNavigate={go}
        onSelectPolicy={selectPolicy}
        onRemoveSavedPolicy={removeSavedPolicy}
        planTier={planTier}
        savedLimit={savedLimit}
        notificationSettings={notificationSettings}
        onNotificationChange={updateNotificationSettings}
        onPlanTierChange={setDemoPlanTier}
        onAddDemoAlarmPolicies={addDemoAlarmPolicies}
        onClearDemoAlarm={clearDemoAlarmDemo}
        onNotify={notify}
        calendarEvents={savedCalendarEvents}
        today={today}
      />
    ),
    prep: (
      <PrepScreen
        policy={selectedPrepPolicy || activePolicy}
        checkedItems={selectedPrepChecked}
        onNavigate={go}
        onSelectPolicy={selectPolicy}
        onTogglePreparation={togglePreparation}
      />
    ),
    chat: (
      <ChatScreen
        policy={activePolicy || selectedPrepPolicy}
        messages={activeMessages}
        chatInput={chatInput}
        chatLoading={chatLoading}
        chatSuggestions={chatSuggestions}
        onChatInput={setChatInput}
        onSendChat={sendChatMessage}
        onUseSuggestion={useChatSuggestion}
        onNavigate={go}
      />
    ),
    centers: (
      <CenterScreen
        regionText={getRegionForCenters(profile, data.user_condition)}
        centers={getDisplayCenters(data.centers)}
        backTo={centersBackTo}
        onNavigate={go}
      />
    ),
    profile: (
      <ProfileScreen
        profile={profile}
        recommendations={data.recommendations}
        onLogin={handleLogin}
        savingProfile={savingProfile}
        onNavigate={go}
      />
    ),
  }[page] || <HomeScreen {...homeScreenProps} />;

  return (
    <>
      {currentScreen}
      {page !== 'detail' && <BottomNav page={page} onNavigate={navigateTab} />}
      {toast && <div className={`toast${page === 'detail' ? ' toast-detail' : ''}`}>{toast}</div>}
    </>
  );
}

function buildDemoResult(query, profile) {
  const conditionRegion = profile?.region_sido || (query?.includes('충북') ? '충북' : '충북');
  const sigungu = profile?.region_sigungu || (query?.includes('충주') ? '충주시' : query?.includes('제천') ? '제천시' : '청주시');
  return {
    user_condition: {
      age: profile?.age || 24,
      region_sido: conditionRegion,
      region_sigungu: sigungu,
      status: profile?.employment_status || '대학생/미취업',
      interest: query?.includes('창업') ? '창업' : query?.includes('취업') ? '취업' : '주거',
    },
    message: '충북 창업경진대회용 모바일 시연 데이터입니다.',
    centers: [
      {
        center_name: '충북청년희망센터',
        center_addr: '충청북도 청주시 상당구 일원',
        center_tel: '043-000-0000',
        center_url: 'https://www.chungbuk.go.kr/young/index.do',
      },
    ],
    recommendations: [
      {
        doc_id: 'demo-chungbuk-housing-1',
        source_table: 'policies_processed',
        source_id: 'demo-1',
        policy_name: '청년 월세 한시 특별지원',
        domain: '주거',
        domain_label: '주거',
        source_label: '온통청년 정책 데이터',
        apply_possibility: '높음',
        match_method: 'FAISS',
        match_score_label: '0.89',
        match_badges: ['충북 지역 조건', '월세·주거비 관심', '24세 청년'],
        region_match: `${conditionRegion} ${sigungu}`,
        application_period: '상시 또는 지자체 공고 확인 필요',
        application_url: 'https://www.youthcenter.go.kr',
        recommend_reason: '충북에 거주하는 20대 청년의 월세 부담 완화 목적과 입력 조건이 가장 가깝습니다.',
        support_summary: '월세 부담을 줄이기 위한 주거비 지원 정책입니다.',
        support_content: '소득·거주 요건을 충족하는 청년에게 월세 일부를 지원합니다. 실제 금액과 기간은 공고문 확인이 필요합니다.',
        checklist: ['주민등록상 거주지 확인', '임대차계약서 준비', '소득·재산 기준 확인', '신청 기간과 접수처 확인'],
      },
      {
        doc_id: 'demo-chungbuk-job-2',
        source_table: 'hrd_trainings',
        source_id: 'demo-2',
        policy_name: '국민내일배움카드 직무훈련 지원',
        domain: '취업',
        domain_label: '취업·교육',
        source_label: 'HRD-Net 훈련 데이터',
        apply_possibility: '보통',
        match_method: '키워드/벡터 혼합',
        match_score_label: '0.76',
        match_badges: ['취업 준비', '직무훈련', '전국 단위'],
        region_match: '전국 단위 정책',
        application_period: '훈련 과정별 상이',
        application_url: 'https://www.hrd.go.kr',
        recommend_reason: '취업 준비나 역량 개발이 필요한 충북 청년에게 활용 가능한 전국 단위 훈련 지원입니다.',
        support_summary: '직무훈련 비용 일부를 지원받을 수 있습니다.',
        support_content: '직업훈련 과정 수강 시 훈련비 일부를 지원하며, 과정별 자부담과 자격은 별도 확인이 필요합니다.',
        checklist: ['HRD-Net 회원가입', '카드 발급 가능 여부 확인', '희망 훈련 과정 검색', '자부담 금액 확인'],
      },
      {
        doc_id: 'demo-chungbuk-startup-3',
        source_table: 'kstartup_notices',
        source_id: 'demo-3',
        policy_name: '청년 창업 사업화 지원 공고',
        domain: '창업',
        domain_label: '창업',
        source_label: 'K-Startup 공고 데이터',
        apply_possibility: query?.includes('창업') ? '높음' : '추가 확인 필요',
        match_method: '도메인 힌트',
        match_score_label: '0.71',
        match_badges: ['창업 관심', '사업화 자금', '공고 확인 필요'],
        region_match: '충북 또는 전국 공고 우선 확인',
        application_period: '공고별 상이',
        application_url: 'https://www.k-startup.go.kr',
        recommend_reason: '창업을 준비하는 청년이라면 사업화 자금, 멘토링, 공간 지원 공고와 연결될 수 있습니다.',
        support_summary: '창업 아이템 사업화와 멘토링을 지원합니다.',
        support_content: '창업 단계와 업종에 따라 사업화 자금, 교육, 멘토링, 입주공간 등을 지원합니다.',
        checklist: ['사업계획서 초안 준비', '공고 대상 연령 확인', '사업자등록 여부 확인', '제출 서류 목록 확인'],
      },
      {
        doc_id: 'demo-chungbuk-finance-4',
        source_table: 'smallloan_youth',
        source_id: 'demo-4',
        policy_name: '청년 생활안정 금융 지원',
        domain: '금융',
        domain_label: '금융',
        source_label: '청년 금융 지원 데이터',
        apply_possibility: '추가 확인 필요',
        match_method: '유사도 검색',
        match_score_label: '0.64',
        match_badges: ['생활비', '금융', '소득 조건 확인'],
        region_match: '전국 또는 지자체 공고 확인',
        application_period: '기관별 상이',
        application_url: 'https://www.youthcenter.go.kr',
        recommend_reason: '주거비와 생활비 부담이 함께 있는 청년에게 금융 지원성 정책을 추가 확인할 필요가 있습니다.',
        support_summary: '생활안정 목적의 금융 지원 정보를 안내합니다.',
        support_content: '대출·보증·이자지원 등 형태가 다르므로 신청 전 조건 확인이 필요합니다.',
        checklist: ['신용·소득 요건 확인', '이자율 확인', '상환 조건 확인', '중복 지원 가능 여부 확인'],
      },
      {
        doc_id: 'demo-chungbuk-center-5',
        source_table: 'centers',
        source_id: 'demo-5',
        policy_name: '충북 청년센터 상담 연계',
        domain: '상담',
        domain_label: '청년센터',
        source_label: '청년센터 API',
        apply_possibility: '높음',
        match_method: '지역 매칭',
        match_score_label: '0.82',
        match_badges: ['충북', '상담', '정책 매칭'],
        region_match: `${conditionRegion} ${sigungu}`,
        application_period: '운영시간 확인 필요',
        application_url: 'https://www.chungbuk.go.kr/young/index.do',
        recommend_reason: '정책 신청 전 자격과 서류를 오프라인 또는 온라인 상담으로 확인할 수 있습니다.',
        support_summary: '충북 청년센터 상담과 정책 안내를 연결합니다.',
        support_content: '청년정책, 취업, 창업, 주거 등 분야별 상담과 프로그램 안내를 받을 수 있습니다.',
        checklist: ['센터 운영시간 확인', '상담 예약 가능 여부 확인', '문의할 정책명 정리', '필요 서류 사전 확인'],
      },
    ],
  };
}
