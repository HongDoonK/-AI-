import { useMemo, useState } from 'react';
import { Search, Sparkles, MapPin, Phone, ExternalLink, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/recommend';

const mockResult = {
  user_condition: {
    age: 24,
    region: '서울특별시',
    status: '대학생',
    interest: '주거',
    employment_status: '확인 필요',
    housing_status: '월세 또는 주거 지원 관심',
    missing_info: ['소득 기준', '무주택 여부']
  },
  recommendations: [
    {
      policy_name: '청년 월세 지원 관련 정책',
      category: '주거',
      fit_level: '높음',
      application_period: '확인 필요',
      support_content: '청년의 주거비 부담 완화를 위한 월세 또는 주거 관련 지원',
      reason: '사용자의 나이와 지역, 주거 지원 관심 분야가 정책 내용과 관련성이 높습니다.',
      check_points: ['소득 기준 충족 여부', '무주택 여부', '주민등록상 주소지', '신청 기간'],
      checklist: ['신청 기간 확인하기', '소득 기준 확인하기', '무주택 여부 확인하기', '제출서류 확인하기', '신청 또는 참고 링크 접속하기'],
      url: ''
    },
    {
      policy_name: '청년 주거 상담 지원',
      category: '주거 / 상담',
      fit_level: '보통',
      application_period: '상시 또는 별도 문의',
      support_content: '청년 주거 문제 해결을 위한 상담 및 정보 제공',
      reason: '주거 문제 해결을 위한 상담 서비스와 사용자의 관심 분야가 연결됩니다.',
      check_points: ['상담 가능 지역', '운영 시간', '상담 예약 방식'],
      checklist: ['센터 운영 시간 확인하기', '상담 가능 여부 문의하기', '필요한 서류나 정보 준비하기'],
      url: ''
    },
    {
      policy_name: '청년 전월세 관련 지원',
      category: '주거',
      fit_level: '추가 확인 필요',
      application_period: '확인 필요',
      support_content: '전월세 부담 완화와 관련된 청년 지원 정책',
      reason: '전월세 부담 완화 목적의 정책으로 사용자 관심 분야와 관련성이 있습니다.',
      check_points: ['대상 지역', '소득 기준', '신청 가능 기간'],
      checklist: ['정책 상세 페이지 확인하기', '신청 자격 확인하기', '문의처 확인하기'],
      url: ''
    }
  ],
  centers: [
    {
      center_name: '서울청년센터 성북',
      address: '서울특별시 성북구 종암로 5길 7',
      detail_address: '서울청년센터 성북(단독건물)',
      phone: '02-921-5330',
      url: 'https://blog.naver.com/syc_sbyouth'
    },
    {
      center_name: '노원 청년평생교육센터 청년배움',
      address: '서울특별시 노원구 화랑로 419-3',
      detail_address: '태릉입구역이니티움 상가 2층',
      phone: '02-2116-7124',
      url: 'https://www.nowon.kr/nwll/web/orgintro/1001?orgNo=202'
    }
  ]
};

function normalizeResult(data) {
  return {
    user_condition: data?.user_condition || {},
    recommendations: Array.isArray(data?.recommendations) ? data.recommendations : [],
    centers: Array.isArray(data?.centers) ? data.centers : []
  };
}

function getFitClass(fitLevel = '') {
  if (fitLevel.includes('높')) return 'badge green';
  if (fitLevel.includes('보통')) return 'badge blue';
  if (fitLevel.includes('확인') || fitLevel.includes('낮')) return 'badge orange';
  return 'badge gray';
}

function ValuePill({ label, value }) {
  return (
    <div className="pill">
      <span>{label}</span>
      <strong>{value || '확인 필요'}</strong>
    </div>
  );
}

function PolicyCard({ policy, index }) {
  const checkPoints = policy.check_points || policy.checkPoints || [];
  const checklist = policy.checklist || [];

  return (
    <article className="policy-card">
      <div className="policy-head">
        <div>
          <p className="card-eyebrow">추천 정책 {index + 1}</p>
          <h3>{policy.policy_name || policy.plcyNm || '정책명 확인 필요'}</h3>
        </div>
        <span className={getFitClass(policy.fit_level || policy.fitLevel)}>
          {policy.fit_level || policy.fitLevel || '확인 필요'}
        </span>
      </div>

      <div className="policy-meta">
        <span>분야: {policy.category || policy.lclsfNm || '확인 필요'}</span>
        <span>신청기간: {policy.application_period || policy.aplyYmd || '확인 필요'}</span>
      </div>

      <section className="mini-section">
        <h4>추천 이유</h4>
        <p>{policy.reason || '사용자 조건과 정책 데이터의 관련성을 기준으로 추천되었습니다.'}</p>
      </section>

      {policy.support_content && (
        <section className="mini-section">
          <h4>지원 내용</h4>
          <p>{policy.support_content}</p>
        </section>
      )}

      {checkPoints.length > 0 && (
        <section className="mini-section">
          <h4>신청 전 확인사항</h4>
          <ul className="compact-list">
            {checkPoints.map((item, idx) => <li key={idx}>{item}</li>)}
          </ul>
        </section>
      )}

      {checklist.length > 0 && (
        <section className="mini-section checklist-block">
          <h4>행동 체크리스트</h4>
          <ul className="check-list">
            {checklist.map((item, idx) => (
              <li key={idx}><CheckCircle2 size={16} />{item}</li>
            ))}
          </ul>
        </section>
      )}

      {(policy.url || policy.application_url || policy.ref_url) && (
        <a className="link-button" href={policy.url || policy.application_url || policy.ref_url} target="_blank" rel="noreferrer">
          신청/참고 링크 열기 <ExternalLink size={15} />
        </a>
      )}
    </article>
  );
}

function CenterCard({ center }) {
  return (
    <article className="center-card">
      <div className="center-title">
        <MapPin size={18} />
        <h3>{center.center_name || center.cntrNm || '센터명 확인 필요'}</h3>
      </div>
      <p>{center.address || center.cntrAddr || '주소 확인 필요'}</p>
      {(center.detail_address || center.cntrDaddr) && <p className="muted">{center.detail_address || center.cntrDaddr}</p>}
      <p className="phone"><Phone size={15} /> {center.phone || center.cntrTelno || '전화번호 확인 필요'}</p>
      {(center.url || center.cntrUrlAddr) && (
        <a className="link-button secondary" href={center.url || center.cntrUrlAddr} target="_blank" rel="noreferrer">
          센터 홈페이지 <ExternalLink size={15} />
        </a>
      )}
    </article>
  );
}

export default function App() {
  const [userInput, setUserInput] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  const data = useMemo(() => normalizeResult(result), [result]);

  async function handleSubmit() {
    if (!userInput.trim()) {
      setErrorMessage('상황을 먼저 입력해주세요.');
      return;
    }

    setLoading(true);
    setErrorMessage('');

    try {
      const response = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_input: userInput })
      });

      if (!response.ok) {
        throw new Error(`서버 응답 오류: ${response.status}`);
      }

      const responseData = await response.json();
      setResult(responseData);
    } catch (error) {
      setErrorMessage('백엔드 연결에 실패했습니다. 아래 예시 결과 보기로 화면을 확인할 수 있습니다.');
      console.error(error);
    } finally {
      setLoading(false);
    }
  }

  function showMockResult() {
    setErrorMessage('');
    setUserInput('서울 사는 24살 대학생인데 월세 지원 정책 있어?');
    setResult(mockResult);
  }

  return (
    <main className="page">
      <section className="hero">
        <div className="hero-text">
          <div className="label"><Sparkles size={16} /> 온통청년 API 기반</div>
          <h1>청년 맞춤 정책 안내 AI</h1>
          <p>정책명을 몰라도 자신의 상황을 입력하면 AI가 관련 청년정책과 가까운 청년센터를 안내합니다.</p>
        </div>
        <div className="hero-card">
          <h2>나의 상황 입력</h2>
          <textarea
            value={userInput}
            onChange={(event) => setUserInput(event.target.value)}
            placeholder="예: 서울 사는 24살 대학생인데 월세 지원 정책 있어?"
          />
          <div className="button-row">
            <button className="primary-button" onClick={handleSubmit} disabled={loading}>
              {loading ? <><Loader2 className="spin" size={18} /> 추천 중...</> : <><Search size={18} /> 정책 추천받기</>}
            </button>
            <button className="ghost-button" onClick={showMockResult}>예시 결과 보기</button>
          </div>
          {errorMessage && <p className="error"><AlertCircle size={16} /> {errorMessage}</p>}
          <p className="hint">백엔드 주소는 환경변수 <code>VITE_API_URL</code>로 변경할 수 있습니다.</p>
        </div>
      </section>

      {result && (
        <section className="result-grid">
          <aside className="left-column">
            <div className="panel">
              <p className="card-eyebrow">AI 분석 결과</p>
              <h2>사용자 조건</h2>
              <div className="pill-wrap">
                <ValuePill label="나이" value={data.user_condition.age ? `${data.user_condition.age}세` : data.user_condition.age} />
                <ValuePill label="지역" value={data.user_condition.region} />
                <ValuePill label="상태" value={data.user_condition.status} />
                <ValuePill label="관심 분야" value={data.user_condition.interest} />
              </div>
              {(data.user_condition.missing_info || []).length > 0 && (
                <div className="notice-box">
                  <strong>추가 확인 필요</strong>
                  <p>{data.user_condition.missing_info.join(', ')}</p>
                </div>
              )}
            </div>

            <div className="panel blue-panel">
              <p className="card-eyebrow">상담 연결</p>
              <h2>가까운 청년센터</h2>
              {data.centers.length === 0 ? (
                <p className="muted">센터 정보를 찾지 못했습니다.</p>
              ) : (
                <div className="center-list">
                  {data.centers.map((center, index) => <CenterCard center={center} key={index} />)}
                </div>
              )}
            </div>
          </aside>

          <section className="right-column">
            <div className="section-title">
              <div>
                <p className="card-eyebrow">추천 결과</p>
                <h2>추천 정책 Top {Math.min(data.recommendations.length, 5) || 5}</h2>
              </div>
              <span className="count-badge">{data.recommendations.length}개 정책</span>
            </div>

            {data.recommendations.length === 0 ? (
              <div className="panel"><p className="muted">추천 정책이 없습니다. 입력을 더 구체적으로 작성해보세요.</p></div>
            ) : (
              <div className="policy-list">
                {data.recommendations.slice(0, 5).map((policy, index) => (
                  <PolicyCard policy={policy} index={index} key={index} />
                ))}
              </div>
            )}
          </section>
        </section>
      )}
    </main>
  );
}
