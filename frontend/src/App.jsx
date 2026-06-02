import { useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  Bot,
  CheckCircle2,
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
  X,
} from 'lucide-react';

const DEFAULT_API_BASE_URL = 'http://localhost:8000';
const API_BASE_URL = resolveApiBaseUrl(import.meta.env.VITE_API_URL);
const RECOMMEND_URL = `${API_BASE_URL}/recommend`;
const CHAT_URL = `${API_BASE_URL}/chat`;
const USER_URL = `${API_BASE_URL}/user`;
const PROFILE_STORAGE_KEY = 'youth-policy-user-profile';

const REGION_OPTIONS = {
  서울: ['종로구', '중구', '용산구', '성동구', '광진구', '동대문구', '중랑구', '성북구', '강북구', '도봉구', '노원구', '은평구', '서대문구', '마포구', '양천구', '강서구', '구로구', '금천구', '영등포구', '동작구', '관악구', '서초구', '강남구', '송파구', '강동구'],
  부산: ['중구', '서구', '동구', '영도구', '부산진구', '동래구', '남구', '북구', '해운대구', '사하구', '금정구', '강서구', '연제구', '수영구', '사상구', '기장군'],
  대구: ['중구', '동구', '서구', '남구', '북구', '수성구', '달서구', '달성군', '군위군'],
  인천: ['중구', '동구', '미추홀구', '연수구', '남동구', '부평구', '계양구', '서구', '강화군', '옹진군'],
  광주: ['동구', '서구', '남구', '북구', '광산구'],
  대전: ['동구', '중구', '서구', '유성구', '대덕구'],
  울산: ['중구', '남구', '동구', '북구', '울주군'],
  세종: ['세종시'],
  경기: ['수원시', '성남시', '고양시', '용인시', '부천시', '안산시', '안양시', '남양주시', '화성시', '평택시', '의정부시', '시흥시', '파주시', '김포시', '광명시', '광주시', '군포시', '하남시', '오산시', '양주시', '이천시', '구리시', '안성시', '포천시', '의왕시', '여주시', '양평군', '동두천시', '과천시', '가평군', '연천군'],
  강원: ['춘천시', '원주시', '강릉시', '동해시', '태백시', '속초시', '삼척시', '홍천군', '횡성군', '영월군', '평창군', '정선군', '철원군', '화천군', '양구군', '인제군', '고성군', '양양군'],
  충북: ['청주시', '충주시', '제천시', '보은군', '옥천군', '영동군', '증평군', '진천군', '괴산군', '음성군', '단양군'],
  충남: ['천안시', '공주시', '보령시', '아산시', '서산시', '논산시', '계룡시', '당진시', '금산군', '부여군', '서천군', '청양군', '홍성군', '예산군', '태안군'],
  전북: ['전주시', '군산시', '익산시', '정읍시', '남원시', '김제시', '완주군', '진안군', '무주군', '장수군', '임실군', '순창군', '고창군', '부안군'],
  전남: ['목포시', '여수시', '순천시', '나주시', '광양시', '담양군', '곡성군', '구례군', '고흥군', '보성군', '화순군', '장흥군', '강진군', '해남군', '영암군', '무안군', '함평군', '영광군', '장성군', '완도군', '진도군', '신안군'],
  경북: ['포항시', '경주시', '김천시', '안동시', '구미시', '영주시', '영천시', '상주시', '문경시', '경산시', '의성군', '청송군', '영양군', '영덕군', '청도군', '고령군', '성주군', '칠곡군', '예천군', '봉화군', '울진군', '울릉군'],
  경남: ['창원시', '진주시', '통영시', '사천시', '김해시', '밀양시', '거제시', '양산시', '의령군', '함안군', '창녕군', '고성군', '남해군', '하동군', '산청군', '함양군', '거창군', '합천군'],
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

function buildProfileText(profile) {
  if (!profile) return '';
  const parts = [];
  if (profile.region_sido) parts.push(profile.region_sido);
  if (profile.region_sigungu) parts.push(profile.region_sigungu);
  if (profile.age) parts.push(`${profile.age}세`);
  if (profile.gender) parts.push(profile.gender);
  if (profile.status) parts.push(profile.status);
  if (profile.employment_status) parts.push(profile.employment_status);
  if (profile.interest) parts.push(`관심분야 ${profile.interest}`);
  if (profile.income) parts.push(`소득 ${profile.income}`);
  if (profile.housing_status) parts.push(`주거상황 ${profile.housing_status}`);
  return parts.join(' ');
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
    status: profile?.status || '청년',
    interest: profile?.interest || '',
    employment_status: profile?.employment_status || '',
    income: profile?.income || '',
    housing_status: profile?.housing_status || '',
  }));

  const sigunguOptions = REGION_OPTIONS[form.region_sido] || [];

  useEffect(() => {
    if (!profile) return;
    setForm({
      age: profile.age || '',
      gender: profile.gender || '',
      region_sido: profile.region_sido || '',
      region_sigungu: profile.region_sigungu || '',
      status: profile.status || '청년',
      interest: profile.interest || '',
      employment_status: profile.employment_status || '',
      income: profile.income || '',
      housing_status: profile.housing_status || '',
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
    onLogin({ ...form, age: form.age ? Number(form.age) : null });
  }

  return (
    <form className="panel login-panel" onSubmit={submit}>
      <p className="card-eyebrow">사용자 로그인</p>
      <h2>내 조건 저장</h2>
      <div className="form-grid">
        <label>나이<input value={form.age} onChange={(e) => updateField('age', e.target.value)} type="number" min="14" max="49" placeholder="24" /></label>
        <label>성별<select value={form.gender} onChange={(e) => updateField('gender', e.target.value)}><option value="">선택 안 함</option><option value="여성">여성</option><option value="남성">남성</option></select></label>
        <label>시도<select value={form.region_sido} onChange={(e) => updateField('region_sido', e.target.value)}><option value="">선택 안 함</option>{Object.keys(REGION_OPTIONS).map((sido) => <option key={sido} value={sido}>{sido}</option>)}</select></label>
        <label>시군구<select value={form.region_sigungu} onChange={(e) => updateField('region_sigungu', e.target.value)} disabled={!form.region_sido}><option value="">선택 안 함</option>{sigunguOptions.map((sigungu) => <option key={sigungu} value={sigungu}>{sigungu}</option>)}</select></label>
        <label>상태<input value={form.status} onChange={(e) => updateField('status', e.target.value)} placeholder="청년, 대학생, 졸업생" /></label>
        <label>재직 여부<select value={form.employment_status} onChange={(e) => updateField('employment_status', e.target.value)}><option value="">선택 안 함</option><option value="미취업">미취업</option><option value="재직">재직</option><option value="창업">창업자</option><option value="자영업">자영업</option><option value="프리랜서">프리랜서</option></select></label>
        <label>관심 분야<select value={form.interest} onChange={(e) => updateField('interest', e.target.value)}><option value="">선택 안 함</option><option value="주거">주거</option><option value="취업">취업</option><option value="창업">창업</option><option value="교육">교육</option><option value="복지">복지</option><option value="금융">금융</option></select></label>
        <label>주거 상황<input value={form.housing_status} onChange={(e) => updateField('housing_status', e.target.value)} placeholder="월세" /></label>
      </div>
      <label>소득<input value={form.income} onChange={(e) => updateField('income', e.target.value)} placeholder="중위소득 100%" /></label>
      <button className="primary-button full-button" type="submit" disabled={saving}>
        {saving ? <><Loader2 className="spin" size={18} /> 저장 중</> : <><LogIn size={18} /> 로그인/저장</>}
      </button>
      {profile?.user_id && <p className="hint">가입 시점: {displayValue(profile.created_at)} · 사용자 ID: {profile.user_id.slice(0, 8)}</p>}
    </form>
  );
}

function PolicyCard({ policy, index, onOpenChat }) {
  const checklist = Array.isArray(policy.checklist) ? policy.checklist : [];
  const url = policy.application_url || policy.url || policy.ref_url;
  const badges = Array.isArray(policy.match_badges) ? policy.match_badges.filter(Boolean) : [];
  const hasEvidence = badges.length > 0 || policy.region_match || policy.domain_label || policy.source_label || policy.match_score_label;
  return (
    <article className="policy-card" tabIndex="0" onClick={() => onOpenChat(policy)} onKeyDown={(event) => { if (event.key === 'Enter') onOpenChat(policy); }}>
      <div className="policy-head">
        <div><p className="card-eyebrow">추천 정책 {index + 1}</p><h3>{displayValue(policy.policy_name, '정책명 확인 필요')}</h3></div>
        <span className={getPossibilityClass(policy.apply_possibility)}>{displayValue(policy.apply_possibility)}</span>
      </div>
      <div className="policy-meta"><span>신청 기간: {displayValue(policy.application_period)}</span></div>
      {hasEvidence && <section className="evidence-box"><div className="evidence-head"><strong>추천 근거</strong>{policy.match_score_label && <span>{displayValue(policy.match_method, '검색 점수')} {policy.match_score_label}</span>}</div><div className="evidence-grid">{badges.map((badge, idx) => <span key={`${badge}-${idx}`}>{badge}</span>)}</div></section>}
      <section className="mini-section"><h4>추천 이유</h4><p>{displayValue(policy.reason, '입력 조건과 정책 데이터의 관련성을 기준으로 추천했습니다.')}</p></section>
      {policy.support_content && <section className="mini-section"><h4>지원 내용</h4><p>{policy.support_content}</p></section>}
      {checklist.length > 0 && <section className="mini-section checklist-block"><h4>신청 체크리스트</h4><ul className="check-list">{checklist.map((item, idx) => <li key={`${item}-${idx}`}><CheckCircle2 size={16} /><span>{item}</span></li>)}</ul></section>}
      <div className="policy-actions">
        <button className="ghost-button" type="button" onClick={(event) => { event.stopPropagation(); onOpenChat(policy); }}><MessageCircle size={16} /> AI 상담 시작</button>
        {url && <a className="link-button" href={url} target="_blank" rel="noreferrer" onClick={(event) => event.stopPropagation()}>신청/참고 링크 열기 <ExternalLink size={15} /></a>}
      </div>
    </article>
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

function ChatMessageContent({ content }) {
  const lines = String(content || '').split('\n');
  const blocks = [];
  let checklist = [];

  function flushChecklist() {
    if (checklist.length > 0) {
      blocks.push({ type: 'checklist', items: checklist });
      checklist = [];
    }
  }

  lines.forEach((line) => {
    const match = line.match(/^- \[ \]\s*(.+)$/);
    if (match) {
      checklist.push(match[1]);
      return;
    }
    flushChecklist();
    if (line.trim()) blocks.push({ type: 'text', text: line });
  });
  flushChecklist();

  return (
    <>
      {blocks.map((block, index) => {
        if (block.type === 'checklist') {
          return (
            <ul className="chat-checklist" key={`checklist-${index}`}>
              {block.items.map((item, itemIndex) => (
                <li key={`${item}-${itemIndex}`}>
                  <CheckCircle2 size={15} />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          );
        }
        return <p key={`text-${index}`}>{block.text}</p>;
      })}
    </>
  );
}

function ChatPanel({ policy, messages, input, loading, onInputChange, onSend, onClose }) {
  if (!policy) return null;
  return (
    <section className="chat-panel" aria-label="정책 AI 상담">
      <div className="chat-header">
        <div className="chat-title">
          <Bot size={20} />
          <div>
            <p className="card-eyebrow">정책 상담 에이전트</p>
            <h2>{displayValue(policy.policy_name, '선택한 정책')}</h2>
          </div>
        </div>
        <button className="icon-button" type="button" onClick={onClose} aria-label="상담 닫기"><X size={18} /></button>
      </div>
      <div className="chat-messages">
        {messages.map((message, index) => (
          <div className={`chat-message ${message.role}`} key={`${message.role}-${index}`}>
            <ChatMessageContent content={message.content} />
          </div>
        ))}
        {loading && <div className="chat-message assistant"><p><Loader2 className="spin inline-icon" size={15} /> 답변을 생성하고 있습니다.</p></div>}
      </div>
      <form className="chat-form" onSubmit={onSend}>
        <input value={input} onChange={(event) => onInputChange(event.target.value)} placeholder="신청 조건, 준비 서류, 다음 단계 등을 물어보세요" />
        <button className="primary-button icon-submit" type="submit" disabled={loading || !input.trim()} aria-label="메시지 보내기"><Send size={18} /></button>
      </form>
    </section>
  );
}

export default function App() {
  const [userInput, setUserInput] = useState('');
  const [profile, setProfile] = useState(() => {
    const saved = localStorage.getItem(PROFILE_STORAGE_KEY);
    return saved ? JSON.parse(saved) : null;
  });
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [savingProfile, setSavingProfile] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [selectedPolicy, setSelectedPolicy] = useState(null);
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const data = useMemo(() => normalizeResult(result), [result]);

  async function handleLogin(profileInput) {
    setSavingProfile(true);
    setErrorMessage('');
    try {
      const response = await fetch(USER_URL, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(profileInput) });
      if (!response.ok) throw new Error(`사용자 저장 실패: ${response.status}`);
      const savedProfile = await response.json();
      setProfile(savedProfile);
      localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(savedProfile));
    } catch (error) {
      setErrorMessage('사용자 정보를 저장하지 못했습니다. 백엔드가 켜져 있는지 확인해주세요.');
      console.error(error);
    } finally {
      setSavingProfile(false);
    }
  }

  async function handleSubmit(event) {
    event?.preventDefault();
    if (!userInput.trim()) {
      setErrorMessage('상황을 먼저 입력해주세요.');
      return;
    }
    setLoading(true);
    setErrorMessage('');
    const profileText = buildProfileText(profile);
    const enrichedInput = profileText
      ? `질문: ${userInput.trim()}\n저장된 사용자 정보: ${profileText}`
      : userInput.trim();
    try {
      const response = await fetch(RECOMMEND_URL, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ user_input: enrichedInput }) });
      if (!response.ok) throw new Error(`서버 응답 오류: ${response.status} ${await response.text()}`);
      setResult(await response.json());
      setSelectedPolicy(null);
      setChatMessages([]);
      setChatInput('');
    } catch (error) {
      setErrorMessage('백엔드 연결에 실패했습니다. VITE_API_URL과 서버 CORS 설정을 확인해주세요.');
      console.error(error);
    } finally {
      setLoading(false);
    }
  }

  function handleOpenPolicyChat(policy) {
    setSelectedPolicy(policy);
    setChatInput('');
    setChatMessages([
      {
        role: 'assistant',
        content: `${displayValue(policy.policy_name, '선택한 정책')} 상담을 시작할게요. 신청 조건, 준비 서류, 다음 행동 중 궁금한 점을 물어보세요.`,
      },
    ]);
  }

  async function handleSendChat(event) {
    event.preventDefault();
    const message = chatInput.trim();
    if (!message || !selectedPolicy) return;

    const nextMessages = [...chatMessages, { role: 'user', content: message }];
    setChatMessages(nextMessages);
    setChatInput('');
    setChatLoading(true);
    setErrorMessage('');

    try {
      const response = await fetch(CHAT_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          policy: selectedPolicy,
          user_context: data.user_condition,
          messages: nextMessages,
        }),
      });
      if (!response.ok) throw new Error(`챗봇 응답 오류: ${response.status} ${await response.text()}`);
      const chatResult = await response.json();
      setChatMessages([...nextMessages, { role: 'assistant', content: chatResult.answer }]);
    } catch (error) {
      setChatMessages([...nextMessages, { role: 'assistant', content: '답변을 생성하지 못했습니다. 백엔드 연결과 OPENAI_API_KEY 설정을 확인해주세요.' }]);
      console.error(error);
    } finally {
      setChatLoading(false);
    }
  }

  return (
    <main className="page">
      <section className="hero">
        <div className="hero-text"><div className="label"><Sparkles size={16} /> 온통청년 API 기반</div><h1>청년 맞춤 정책 안내 AI</h1><p>질문에 적은 관심 분야를 우선 반영하고, 로그인 정보는 부족한 조건을 보충하는 데 사용합니다.</p></div>
        <form className="hero-card" onSubmit={handleSubmit}>
          <h2>나의 상황 입력</h2>
          <textarea value={userInput} onChange={(event) => setUserInput(event.target.value)} placeholder="예: 복지 혜택 받을 수 있는 정책 추천해줘" />
          <div className="button-row"><button className="primary-button" type="submit" disabled={loading}>{loading ? <><Loader2 className="spin" size={18} /> 추천 중</> : <><Search size={18} /> 정책 추천받기</>}</button></div>
          {errorMessage && <p className="error"><AlertCircle size={16} /> {errorMessage}</p>}
          <p className="hint">현재 연결 주소: <code>{RECOMMEND_URL}</code></p>
        </form>
      </section>

      <section className="result-grid">
        <aside className="left-column">
          <LoginPanel profile={profile} onLogin={handleLogin} saving={savingProfile} />
          {result && <><div className="panel"><p className="card-eyebrow">AI 분석 결과</p><h2>사용자 조건</h2><div className="pill-wrap"><ValuePill label="나이" value={data.user_condition.age ? `${data.user_condition.age}세` : null} /><ValuePill label="성별" value={data.user_condition.gender || profile?.gender} /><ValuePill label="지역" value={data.user_condition.region || profile?.region_sido} /><ValuePill label="상태" value={data.user_condition.status} /><ValuePill label="재직 여부" value={data.user_condition.employment_status} /><ValuePill label="관심 분야" value={data.user_condition.interest} /><ValuePill label="주거 상황" value={data.user_condition.housing_status} /></div></div><div className="panel blue-panel"><p className="card-eyebrow">상담 연결</p><h2>가까운 청년센터</h2>{data.centers.length === 0 ? <p className="muted">지역 조건에 맞는 센터 정보가 아직 없습니다.</p> : <div className="center-list">{data.centers.slice(0, 5).map((center, index) => <CenterCard center={center} key={`${center.center_name || center.cntrNm}-${index}`} />)}</div>}</div></>}
        </aside>

        <section className="right-column">
          {result ? <><div className="section-title"><div><p className="card-eyebrow">추천 결과</p><h2>현재 신청 가능한 추천 정책 Top {Math.min(data.recommendations.length, 5)}</h2></div><span className="count-badge">{data.recommendations.length}개 정책</span></div>{data.recommendations.length === 0 ? <div className="panel"><p className="muted">현재 신청 가능한 추천 정책이 없습니다. 입력을 조금 더 구체적으로 작성해보세요.</p></div> : <div className="policy-list">{data.recommendations.slice(0, 5).map((policy, index) => <PolicyCard policy={policy} index={index} onOpenChat={handleOpenPolicyChat} key={`${policy.policy_name}-${index}`} />)}</div>}</> : <div className="panel empty-state"><UserRound size={28} /><h2>로그인 정보를 저장한 뒤 추천을 받아보세요</h2><p>나이, 성별, 지역, 관심 분야가 추천 문장에 함께 반영됩니다.</p></div>}
        </section>
      </section>
      <ChatPanel
        policy={selectedPolicy}
        messages={chatMessages}
        input={chatInput}
        loading={chatLoading}
        onInputChange={setChatInput}
        onSend={handleSendChat}
        onClose={() => setSelectedPolicy(null)}
      />
    </main>
  );
}
