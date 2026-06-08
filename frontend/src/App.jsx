import { useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  Bell,
  CheckCircle2,
  ClipboardList,
  ExternalLink,
  Loader2,
  LogIn,
  MapPin,
  MessageCircle,
  Phone,
  Search,
  Send,
  Sparkles,
  UserRound,
} from 'lucide-react';
import { buildAgentReport } from './agentPlanner.js';
import {
  buildPreparationItems,
  getPreparationLink,
  getCompletionStats,
  togglePreparationItem,
} from './prepTracker.js';

const DEFAULT_API_BASE_URL = 'http://localhost:8000';
const API_BASE_URL = resolveApiBaseUrl(import.meta.env.VITE_API_URL);
const RECOMMEND_URL = `${API_BASE_URL}/recommend`;
const USER_URL = `${API_BASE_URL}/user`;
const CHAT_URL = `${API_BASE_URL}/chat`;
const PROFILE_STORAGE_KEY = 'youth-policy-user-profile';
const PREP_STORAGE_KEY = 'youth-policy-prep-checks';
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
  const raw = (value || DEFAULT_API_BASE_URL).replace(/\/$/, '');
  return raw.endsWith('/recommend') ? raw.slice(0, -'/recommend'.length) : raw;
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
  return 'badge blue';
}

function displayValue(value, fallback = '확인 필요') {
  if (value === null || value === undefined || value === '') return fallback;
  return value;
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
  }));

  const sigunguOptions = REGION_OPTIONS[form.region_sido] || [];

  useEffect(() => {
    if (!profile) return;
    setForm({
      age: profile.age || '',
      gender: profile.gender || '',
      region_sido: profile.region_sido || '',
      region_sigungu: profile.region_sigungu || '',
      employment_status: profile.employment_status || '',
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
      </div>
      <button className="primary-button full-button" type="submit" disabled={saving}>
        {saving ? <><Loader2 className="spin" size={18} /> 저장 중</> : <><LogIn size={18} /> 프로필 저장</>}
      </button>
      {profile?.user_id && <p className="hint">저장 시점: {displayValue(profile.created_at)} · 사용자 ID: {profile.user_id.slice(0, 8)}</p>}
    </form>
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

function PreparationBoard({ policy, checkedItems, onToggle }) {
  const policyId = policyKey(policy);
  const items = useMemo(() => buildPreparationItems(policy), [policy]);
  const stats = getCompletionStats(items, checkedItems);
  const done = stats.total > 0 && stats.completed === stats.total;

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
                  onChange={(event) => onToggle(policyId, item, event.target.checked)}
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
            {policy.match_score_label && <span>{displayValue(policy.match_method, '검색 점수')} {policy.match_score_label}</span>}
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
    <section className="panel chat-panel">
      <div className="chat-head">
        <div>
          <p className="card-eyebrow">정책별 상담</p>
          <h2>{displayValue(policy.policy_name, '선택한 정책')}</h2>
        </div>
        <span className="count-badge">{displayValue(policy.source_label || policy.domain_label, '정책 DB')}</span>
      </div>
      <div className="chat-window">
        {messages.length === 0 ? (
          <div className="chat-empty">
            <MessageCircle size={24} />
            <p>이 정책에서 필요한 서류, 신청 방법, 자격 조건을 물어볼 수 있어요.</p>
          </div>
        ) : messages.map((message, index) => (
          <div className={`chat-bubble ${message.role === 'user' ? 'user' : 'assistant'}`} key={`${message.role}-${index}`}>
            <p>{message.content}</p>
          </div>
        ))}
        {loading && <div className="chat-bubble assistant"><p><Loader2 className="spin inline-spin" size={16} /> 확인 중입니다.</p></div>}
      </div>
      {suggestions.length > 0 && (
        <div className="suggestion-row">
          {suggestions.slice(0, 3).map((suggestion) => (
            <button type="button" className="suggestion-chip" key={suggestion} onClick={() => onUseSuggestion(suggestion)}>{suggestion}</button>
          ))}
        </div>
      )}
      <form className="chat-form" onSubmit={onSend}>
        <input value={input} onChange={(event) => onInput(event.target.value)} placeholder="이 정책에서 필요한 건 뭐야?" />
        <button className="primary-button icon-button" type="submit" disabled={loading || !input.trim()}><Send size={17} /></button>
      </form>
    </section>
  );
}

function CenterCard({ center }) {
  const name = center.center_name || center.cntrNm;
  const address = center.center_addr || center.cntrAddr;
  const detailAddress = center.center_daddr || center.cntrDaddr;
  const phone = center.center_tel || center.cntrTelno;
  const url = center.center_url || center.cntrUrlAddr;
  return (
    <article className="center-card">
      <div className="center-title"><MapPin size={18} /><h3>{displayValue(name, '센터명 확인 필요')}</h3></div>
      <p>{displayValue(address, '주소 확인 필요')}</p>
      {detailAddress && <p className="muted">{detailAddress}</p>}
      <p className="phone"><Phone size={15} /> {displayValue(phone, '전화번호 확인 필요')}</p>
      {url && <a className="link-button secondary" href={url} target="_blank" rel="noreferrer">센터 홈페이지 <ExternalLink size={15} /></a>}
    </article>
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
  const [activePolicy, setActivePolicy] = useState(null);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [chatByPolicy, setChatByPolicy] = useState({});
  const [chatSuggestions, setChatSuggestions] = useState([]);
  const [selectedPrepPolicy, setSelectedPrepPolicy] = useState(null);
  const [checkedPrepByPolicy, setCheckedPrepByPolicy] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem(PREP_STORAGE_KEY) || '{}');
    } catch {
      return {};
    }
  });

  const data = useMemo(() => normalizeResult(result), [result]);
  const activePolicyKey = activePolicy ? policyKey(activePolicy) : '';
  const activeMessages = activePolicyKey ? (chatByPolicy[activePolicyKey] || []) : [];
  const selectedPrepPolicyKey = selectedPrepPolicy ? policyKey(selectedPrepPolicy) : '';
  const selectedPrepChecked = selectedPrepPolicyKey ? (checkedPrepByPolicy[selectedPrepPolicyKey] || {}) : {};
  const displayedCondition = useMemo(() => {
    const condition = data.user_condition || {};
    return {
      age: condition.age ?? profile?.age ?? null,
      gender: condition.gender || profile?.gender || '',
      region_sido: condition.region_sido || profile?.region_sido || '',
      region_sigungu: condition.region_sigungu || profile?.region_sigungu || '',
      employment_status: condition.employment_status || profile?.employment_status || '',
    };
  }, [data.user_condition, profile]);

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
      const savedProfile = sanitizeProfile(await response.json());
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
        body: JSON.stringify({ user_input: enrichedInput }),
      });
      if (!response.ok) throw new Error(`서버 응답 오류: ${response.status} ${await response.text()}`);
      const nextResult = await response.json();
      setResult(nextResult);
      setErrorMessage(nextResult?.message || '');
      setActivePolicy(null);
      setSelectedPrepPolicy(null);
      setChatInput('');
      setChatSuggestions([]);
    } catch (error) {
      setErrorMessage('백엔드 연결에 실패했습니다. VITE_API_URL과 서버 CORS 설정을 확인해주세요.');
      console.error(error);
    } finally {
      setLoading(false);
    }
  }

  function openPolicyChat(policy) {
    setActivePolicy(policy);
    setChatInput('');
    setChatSuggestions([
      '이 정책에서 필요한 서류는 뭐야?',
      '내가 신청 가능할까?',
      '신청 순서를 알려줘',
    ]);
  }

  function openPreparationBoard(policy) {
    setSelectedPrepPolicy(policy);
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
        [key]: [...nextMessages, { role: 'assistant', content: '챗봇 연결에 실패했습니다. 백엔드 서버와 /chat 설정을 확인해주세요.' }],
      }));
      console.error(error);
    } finally {
      setChatLoading(false);
    }
  }

  function useChatSuggestion(suggestion) {
    sendChatMessage(null, suggestion);
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
          <LoginPanel profile={profile} onLogin={handleLogin} saving={savingProfile} />
          <ApplicationAgentPanel recommendations={data.recommendations} />
          {selectedPrepPolicy && (
            <PreparationBoard
              policy={selectedPrepPolicy}
              checkedItems={selectedPrepChecked}
              onToggle={togglePreparation}
            />
          )}
          {result && (
            <>
              <div className="panel">
                <p className="card-eyebrow">AI 분석 결과</p>
                <h2>사용자 조건</h2>
                <div className="pill-wrap">
                  <ValuePill label="나이" value={displayedCondition.age ? `${displayedCondition.age}세` : null} />
                  <ValuePill label="성별" value={displayedCondition.gender} />
                  <ValuePill label="시도" value={displayedCondition.region_sido} />
                  <ValuePill label="시군구" value={displayedCondition.region_sigungu} />
                  <ValuePill label="취업 상태" value={displayedCondition.employment_status} />
                </div>
              </div>
              <div className="panel blue-panel">
                <p className="card-eyebrow">상담 연결</p>
                <h2>가까운 청년센터</h2>
                {data.centers.length === 0 ? (
                  <p className="muted">지역 조건에 맞는 센터 정보가 아직 없습니다.</p>
                ) : (
                  <div className="center-list">
                    {data.centers.slice(0, 5).map((center, index) => (
                      <CenterCard center={center} key={`${center.center_name || center.cntrNm}-${index}`} />
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </aside>

        <section className="right-column">
          {activePolicy && (
            <ChatPanel
              policy={activePolicy}
              messages={activeMessages}
              input={chatInput}
              loading={chatLoading}
              suggestions={chatSuggestions}
              onInput={setChatInput}
              onSend={sendChatMessage}
              onUseSuggestion={useChatSuggestion}
            />
          )}
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
                      onChat={openPolicyChat}
                      onPrepare={openPreparationBoard}
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
