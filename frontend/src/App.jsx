import { useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  AlertTriangle,
  Bell,
  CheckCircle2,
  ClipboardList,
  Loader2,
  Search,
  Sparkles,
  UserRound,
} from 'lucide-react';
import { buildAgentReport } from './agentPlanner.js';
import { findIneligiblePolicies } from './eligibilityCheck.js';
import { getScoreMood } from './scoreMood.js';
import {
  buildPreparationItems,
  getPreparationLink,
  getCompletionStats,
  togglePreparationItem,
} from './prepTracker.js';
import {
  NO_CONDITION_MESSAGE,
  PREP_STORAGE_KEY,
  PROFILE_STORAGE_KEY,
  displayValue,
  formatWon,
  normalizeResult,
  resolveApiBaseUrl,
} from './appConfig.js';
import ApplyPanel from './components/ApplyPanel.jsx';
import MyApplicationsPanel from './components/MyApplicationsPanel.jsx';
import ChatFlowPanel from './components/ChatFlowPanel.jsx';
import ProfileForm from './components/ProfileForm.jsx';
import IncomeCalculator from './components/IncomeCalculator.jsx';
import PolicyCard from './components/PolicyCard.jsx';
import {
  createApplyPlan,
  fetchApplication,
  fetchApplications,
  toggleApplyItem,
  updateApplyStatus,
} from './applyPlan.js';

const API_BASE_URL = resolveApiBaseUrl(import.meta.env.VITE_API_URL);
const RECOMMEND_URL = `${API_BASE_URL}/recommend`;
const USER_URL = `${API_BASE_URL}/user`;

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
      <strong>{value}</strong>
    </div>
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

function policyKey(policy) {
  return policy?.doc_id || `${policy?.source_table || 'policy'}:${policy?.source_id || policy?.policy_name || 'unknown'}`;
}

function PreparationBoard({ policy, checkedItems, onToggle }) {
  const items = useMemo(() => buildPreparationItems(policy), [policy]);
  const stats = getCompletionStats(items, checkedItems);
  const done = stats.total > 0 && stats.completed === stats.total;
  const keyForPolicy = policyKey(policy);

  return (
    <section className="panel prep-board">
      <p className="card-eyebrow">선택한 정책 준비 보드</p>
      <h2><ClipboardList size={19} /> {displayValue(policy.policy_name, '정책명 확인 필요')}</h2>
      <div className="prep-summary">
        <strong>{stats.completed}/{stats.total} 완료</strong>
        <span>{stats.percent}% 준비 완료</span>
      </div>
      <div className="prep-progress" aria-label={`준비 진행률 ${stats.percent}%`}>
        <div style={{ width: `${stats.percent}%` }} />
      </div>
      <ul className="prep-check-list">
        {items.map((item) => {
          const checked = Boolean(checkedItems?.[item]);
          const itemLink = getPreparationLink(item, policy);
          return (
            <li className={checked ? 'done' : ''} key={item}>
              <label>
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={(event) => onToggle(keyForPolicy, item, event.target.checked)}
                />
                <span className="prep-item-content">
                  <span className="prep-item-text">{item}</span>
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

export default function App() {
  const [userInput, setUserInput] = useState('');
  const [profile, setProfile] = useState(() => {
    const saved = localStorage.getItem(PROFILE_STORAGE_KEY);
    return saved ? sanitizeProfile(JSON.parse(saved)) : null;
  });
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [savingProfile, setSavingProfile] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [seedPolicy, setSeedPolicy] = useState(null);
  // D1: Hero 추천이 만든 대화 세션 + 카드 — 채팅과 공유하는 단일 추천 출처
  const [chatSeed, setChatSeed] = useState(null);
  const [selectedPrepPolicy, setSelectedPrepPolicy] = useState(null);
  const [applyPlan, setApplyPlan] = useState(null);
  const [myApplications, setMyApplications] = useState([]);
  const [myApplicationsLoading, setMyApplicationsLoading] = useState(false);
  const [applyLoading, setApplyLoading] = useState(false);
  const [applyError, setApplyError] = useState('');
  const [checkedPrepByPolicy, setCheckedPrepByPolicy] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem(PREP_STORAGE_KEY) || '{}');
    } catch {
      return {};
    }
  });

  const data = useMemo(() => normalizeResult(result), [result]);
  const selectedPrepPolicyKey = selectedPrepPolicy ? policyKey(selectedPrepPolicy) : '';
  const selectedPrepChecked = selectedPrepPolicyKey ? (checkedPrepByPolicy[selectedPrepPolicyKey] || {}) : {};
  useEffect(() => {
    localStorage.setItem(PREP_STORAGE_KEY, JSON.stringify(checkedPrepByPolicy));
  }, [checkedPrepByPolicy]);

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
    } catch (error) {
      setErrorMessage('사용자 정보를 저장하지 못했습니다. 백엔드 서버가 켜져 있는지 확인해주세요.');
      console.error(error);
    } finally {
      setSavingProfile(false);
    }
  }

  async function handleSubmit(event) {
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
        body: JSON.stringify({ user_input: enrichedInput, user_id: profile?.user_id || null }),
      });
      if (!response.ok) throw new Error(`서버 응답 오류: ${response.status} ${await response.text()}`);
      const nextResult = await response.json();
      setResult(nextResult);
      setErrorMessage(nextResult?.message || '');
      // D1: Hero 추천 세션을 채팅에 시드 (단일 추천 출처)
      setChatSeed(nextResult.session_id ? { sessionId: nextResult.session_id, cards: nextResult.cards || [] } : null);
      setSeedPolicy(null);
      setSelectedPrepPolicy(null);
      setApplyPlan(null);
      setApplyError('');
    } catch (error) {
      setErrorMessage('백엔드 연결에 실패했습니다. VITE_API_URL과 서버 CORS 설정을 확인해주세요.');
      console.error(error);
    } finally {
      setLoading(false);
    }
  }

  function openConverseForPolicy(policy) {
    setSeedPolicy(policy);
    window.requestAnimationFrame(() => {
      document.getElementById('chat-flow-panel')?.scrollIntoView({
        behavior: 'smooth',
        block: 'start',
      });
    });
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

  useEffect(() => {
    refreshMyApplications(profile?.user_id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profile?.user_id]);

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

  // ① ChatFlowPanel의 onApplyPlan 콜백 — 신청 플랜 생성 후 해당 패널로 스크롤
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

  function openPreparationBoard(policy) {
    setSelectedPrepPolicy(policy);
  }

  function togglePreparation(pId, item, checked) {
    setCheckedPrepByPolicy((prev) => togglePreparationItem(prev, pId, item, checked));
  }

  return (
    <main className="page">
      <section className="hero">
        <div className="hero-text">
          <div className="label"><Sparkles size={16} /> 공공 청년 정책 기반</div>
          <h1>청년 맞춤 정책 안내 AI</h1>
          <p>자연어로 상황을 입력하면 적합한 정책을 추천하고, 실행 에이전트가 신청 우선순위와 준비 체크리스트까지 정리합니다.</p>
        </div>
        <form className="hero-card" onSubmit={handleSubmit}>
          <h2>나의 상황 입력</h2>
          <textarea
            value={userInput}
            onChange={(event) => setUserInput(event.target.value)}
            placeholder="예: 서울 마포구에 사는 24세 미취업 청년인데 주거 지원 정책을 찾고 있어"
          />
          <div className="button-row">
            <button className="primary-button" type="submit" disabled={loading}>
              {loading ? <><Loader2 className="spin" size={18} /> 추천 중</> : <><Search size={18} /> 정책 추천받기</>}
            </button>
          </div>
          {errorMessage && <p className="error"><AlertCircle size={16} /> {errorMessage}</p>}
          <p className="hint">현재 연결 주소: <code>{RECOMMEND_URL}</code></p>
        </form>
      </section>

      <section className="result-grid">
        <aside className="left-column">
          <ProfileForm profile={profile} onLogin={handleLogin} saving={savingProfile} />
          <IncomeCalculator />
          <ApplicationAgentPanel recommendations={data.recommendations} />
          <EligibilityGapPanel recommendations={data.recommendations} profile={profile} />
          <MyApplicationsPanel
            applications={myApplications}
            loading={myApplicationsLoading}
            onOpen={openMyApplication}
          />
          {/* ① 신청 플랜 패널 — ChatFlowPanel의 onApplyPlan이 여기로 스크롤 */}
          <div id="apply-plan-anchor">
            {(applyPlan || applyLoading) && (
              <ApplyPanel
                plan={applyPlan}
                loading={applyLoading}
                error={applyError}
                onToggleItem={handleApplyItemToggle}
                onStatusChange={handleApplyStatusChange}
              />
            )}
          </div>
          {selectedPrepPolicy && (
            <PreparationBoard
              policy={selectedPrepPolicy}
              checkedItems={selectedPrepChecked}
              onToggle={togglePreparation}
            />
          )}
        </aside>

        <section className="right-column">
          {/* ① onApplyPlan 주입 — 채팅에서 "신청 준비 시작" 클릭 시 startApplyPlan 호출 */}
          <ChatFlowPanel
            baseUrl={API_BASE_URL}
            userId={profile?.user_id}
            seededPolicy={seedPolicy}
            seededRecommendation={chatSeed}
            onApplyPlan={startApplyPlan}
          />
          {result ? (
            <>
              <div className="section-title">
                <div>
                  <p className="card-eyebrow">추천 결과</p>
                  <h2>현재 신청 가능한 추천 정책 Top {Math.min(data.recommendations.length, 5)}</h2>
                </div>
                <span className="count-badge">{data.recommendations.length}개 정책</span>
              </div>
              {data.recommendations.length === 0 ? (
                <div className="panel">
                  <p className="muted">{data.message || '현재 신청 가능한 추천 정책이 없습니다. 입력을 조금 더 구체적으로 작성해보세요.'}</p>
                </div>
              ) : (
                <div className="policy-list">
                  {data.recommendations.slice(0, 5).map((policy, index) => (
                    <PolicyCard
                      policy={policy}
                      index={index}
                      onChat={openConverseForPolicy}
                      onPrepare={openPreparationBoard}
                      onApply={startApplyPlan}
                      key={`${policy.policy_name}-${index}`}
                    />
                  ))}
                </div>
              )}
            </>
          ) : (
            <div className="panel empty-state">
              <UserRound size={28} />
              <h2>로그인 정보를 저장한 뒤 추천을 받아보세요</h2>
              <p>나이, 성별, 시도, 시군구, 취업 상태가 추천 문장에 함께 반영됩니다.</p>
            </div>
          )}
        </section>
      </section>
    </main>
  );
}
