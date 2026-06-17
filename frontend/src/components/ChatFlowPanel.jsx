import { useEffect, useRef, useState } from 'react';
import { Loader2, MessagesSquare, Send } from 'lucide-react';
import { actionToMessage, sendConverse } from '../converseClient.js';

const GREETING = {
  role: 'assistant',
  text: '왼쪽 "나의 상황 입력"에서 추천받은 정책을 골라 상담을 시작하세요. 예: "정책 2 서류 알려줘", "선택한 정책 신청 방법 알려줘"',
  actions: [],
  cards: [],
};

// 추천 카드(클릭 선택)를 첨부하는 intent: Hero 시드 추천 + 안내(추천 요청/선택 유도)
const CARD_INTENTS = ['recommend', 'need_recommendation', 'need_select'];

function normalizeSeedPolicy(policy = {}) {
  const title = policy.policy_name || policy.title || '정책명 확인 필요';
  return {
    doc_id: policy.doc_id || policy.policy_id || '',
    source_table: policy.source_table || '',
    source_id: policy.source_id || '',
    policy_name: title,
    title,
    category_main: policy.category_main || policy.domain || '',
    domain: policy.domain || policy.category_main || '',
  };
}

function buildAssistantMessage(res) {
  return {
    role: 'assistant',
    text: res.reply,
    actions: res.suggested_actions || [],
    // 추천 카드 첨부 — Hero 시드 추천/선택 유도/추천 안내 시 클릭 선택 가능
    cards: CARD_INTENTS.includes(res.intent) ? (res.cards || []) : [],
  };
}

// ② 추천 카드 리스트 컴포넌트
function ChatCardList({ cards, onSelect, disabled }) {
  if (!cards || cards.length === 0) return null;
  return (
    <div className="chat-card-list">
      {cards.map((card) => (
        <button
          key={card.doc_id || card.rank}
          type="button"
          className="chat-card-item"
          onClick={() => !disabled && onSelect(card)}
          disabled={disabled}
        >
          <span className="chat-card-rank">{card.rank}</span>
          <span className="chat-card-title">{card.title}</span>
          {card.domain && <span className="chat-card-domain">{card.domain}</span>}
        </button>
      ))}
    </div>
  );
}

// onApplyPlan: App이 주입하는 콜백 — 선택된 정책으로 /agent/apply-plan 호출
export default function ChatFlowPanel({ baseUrl, userId, seededPolicy, seededRecommendation, onApplyPlan }) {
  const [messages, setMessages] = useState([GREETING]);
  const [sessionId, setSessionId] = useState(null);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  // 현재 선택된 정책 — create_apply_plan 액션칩 인터셉트에 사용
  const [chatSelectedPolicy, setChatSelectedPolicy] = useState(null);
  const lastSeededDocId = useRef(null);
  const lastSeededSessionId = useRef(null);

  function syncSelectedPolicy(res) {
    if (res.intent === 'recommend') {
      setChatSelectedPolicy(null); // 새 추천 = 이전 선택 해제
    } else if (res.selected_policy) {
      setChatSelectedPolicy(res.selected_policy);
    }
  }

  // 추천 카드에서 정책 직접 선택 (텍스트 입력 불필요)
  async function selectCard(card) {
    const title = card.title || card.policy_name || '정책';
    setMessages((prev) => [
      ...prev,
      { role: 'user', text: `'${title}' 선택`, actions: [], cards: [] },
    ]);
    setLoading(true);
    setError('');
    try {
      const res = await sendConverse(baseUrl, { message: '', sessionId, userId, policy: card });
      setSessionId(res.session_id);
      syncSelectedPolicy(res);
      setMessages((prev) => [...prev, buildAssistantMessage(res)]);
    } catch (err) {
      setError('대화 처리 중 오류가 발생했습니다. 백엔드 서버가 켜져 있는지 확인해주세요.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  // D1: Hero "나의 상황 입력"이 만든 추천 세션/카드를 채팅에 시드한다.
  // 채팅은 별도 추천 목록을 만들지 않고 이 세션을 단일 출처로 이어받는다.
  useEffect(() => {
    const sid = seededRecommendation?.sessionId;
    if (!sid || lastSeededSessionId.current === sid) return;
    lastSeededSessionId.current = sid;
    setSessionId(sid);
    setChatSelectedPolicy(null);
    setError('');
    const cards = seededRecommendation.cards || [];
    const text = cards.length
      ? `회원님 조건으로 신청 가능한 정책 ${cards.length}개예요. 아래 카드를 누르거나 "정책 2 신청할래"처럼 말해 상담을 이어가세요.`
      : '조건에 맞는 정책을 찾지 못했어요. 왼쪽 "나의 상황 입력"에서 조건을 바꿔 다시 찾아보세요.';
    setMessages([
      GREETING,
      {
        role: 'assistant',
        text,
        actions: cards.slice(0, 3).map((card) => ({ label: `${card.rank}번 선택`, intent: 'select', ordinal: card.rank })),
        cards,
      },
    ]);
  }, [seededRecommendation]);

  // 정책 카드에서 "이 정책 자세히 보기" 클릭으로 대화 시작할 때
  useEffect(() => {
    const docId = seededPolicy?.doc_id;
    if (!docId || lastSeededDocId.current === docId) return;

    const policy = normalizeSeedPolicy(seededPolicy);
    lastSeededDocId.current = docId;
    let active = true;

    async function seedConversation() {
      setMessages((prev) => [
        ...prev,
        { role: 'user', text: `'${policy.title}' 선택`, actions: [], cards: [] },
      ]);
      setInput('');
      setLoading(true);
      setError('');
      try {
        const res = await sendConverse(baseUrl, { message: '', sessionId, userId, policy });
        if (!active) return;
        setSessionId(res.session_id);
        syncSelectedPolicy(res);
        setMessages((prev) => [...prev, buildAssistantMessage(res)]);
      } catch (err) {
        if (!active) return;
        lastSeededDocId.current = null;
        setError('대화 처리 중 오류가 발생했습니다. 백엔드 서버가 켜져 있는지 확인해주세요.');
        console.error(err);
      } finally {
        if (active) setLoading(false);
      }
    }

    seedConversation();
    return () => { active = false; };
  }, [baseUrl, seededPolicy, userId]);

  async function send(rawText) {
    const message = (rawText ?? input).trim();
    if (!message || loading) return;
    setMessages((prev) => [
      ...prev,
      { role: 'user', text: message, actions: [], cards: [] },
    ]);
    setInput('');
    setLoading(true);
    setError('');
    try {
      const res = await sendConverse(baseUrl, { message, sessionId, userId });
      setSessionId(res.session_id);
      syncSelectedPolicy(res);
      setMessages((prev) => [...prev, buildAssistantMessage(res)]);
    } catch (err) {
      setError('대화 처리 중 오류가 발생했습니다. 백엔드 서버가 켜져 있는지 확인해주세요.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  // ① create_apply_plan 액션칩 인터셉트 — /agent/converse 대신 onApplyPlan 콜백 호출
  function handleChipClick(action) {
    if ((action.action || action.intent) === 'create_apply_plan') {
      const policy = chatSelectedPolicy;
      if (!policy) {
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            text: '신청 플랜을 만들려면 먼저 정책을 선택해 주세요.',
            actions: [],
            cards: [],
          },
        ]);
        return;
      }
      const title = policy.title || policy.policy_name || '선택한 정책';
      setMessages((prev) => [
        ...prev,
        { role: 'user', text: '신청 준비 시작할게요.', actions: [], cards: [] },
        {
          role: 'assistant',
          text: `'${title}' 신청 플랜을 만들고 있어요. 잠시 후 화면 왼쪽에서 확인하세요.`,
          actions: [],
          cards: [],
        },
      ]);
      onApplyPlan?.(policy);
      return;
    }
    // 그 외 액션칩 → 자연어 발화로 변환 후 전송
    send(actionToMessage(action));
  }

  function handleSubmit(event) {
    event.preventDefault();
    send();
  }

  const lastActions = !loading ? (messages[messages.length - 1]?.actions || []) : [];

  return (
    <section id="chat-flow-panel" className="panel chat-panel">
      <div className="chat-head">
        <div>
          <p className="card-eyebrow">대화형 신청 도우미</p>
          <h2><MessagesSquare size={19} /> 고른 정책 상담·신청</h2>
        </div>
        <span className="count-badge">서류 · 지원금 · 신청 준비</span>
      </div>

      <div className="chat-window">
        {messages.map((message, index) => (
          <div key={`msg-${index}`}>
            <div className={`chat-bubble ${message.role === 'user' ? 'user' : 'assistant'}`}>
              <p style={{ whiteSpace: 'pre-wrap' }}>{message.text}</p>
            </div>
            {/* ② 추천 카드 인라인 렌더링 */}
            <ChatCardList
              cards={message.cards}
              onSelect={selectCard}
              disabled={loading}
            />
          </div>
        ))}
        {loading && (
          <div className="chat-bubble assistant">
            <p><Loader2 className="spin inline-spin" size={16} /> 확인 중입니다.</p>
          </div>
        )}
      </div>

      {lastActions.length > 0 && (
        <div className="suggestion-row">
          {lastActions.map((action, index) => (
            <button
              type="button"
              className="suggestion-chip"
              key={`${action.label}-${index}`}
              onClick={() => handleChipClick(action)}
            >
              {action.label}
            </button>
          ))}
        </div>
      )}

      <form className="chat-form" onSubmit={handleSubmit}>
        <input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder='예: "정책 2 서류 알려줘" 또는 "선택한 정책 신청 방법 알려줘"'
        />
        <button className="primary-button icon-button" type="submit" disabled={loading || !input.trim()}>
          <Send size={17} />
        </button>
      </form>
      {error && <p className="error">{error}</p>}
    </section>
  );
}
