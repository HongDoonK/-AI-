import { useEffect, useRef, useState } from 'react';
import { Loader2, MessagesSquare, Send } from 'lucide-react';
import { actionToMessage, sendConverse } from '../converseClient.js';

const GREETING = {
  role: 'assistant',
  text: '어떤 상황인지 한 문장으로 알려 주세요. 예: "서울 26살 직장인인데 목돈 마련하고 싶어"',
  actions: [],
};

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

// 한 대화창에서 추천 → 정책 선택 → 서류 → 지원금이 자연스럽게 이어지는 패널.
// 자체 세션 상태(session_id)를 들고 /agent/converse만 호출한다 (App 상태와 독립).
export default function ChatFlowPanel({ baseUrl, userId, seededPolicy }) {
  const [messages, setMessages] = useState([GREETING]);
  const [sessionId, setSessionId] = useState(null);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const lastSeededDocId = useRef(null);

  useEffect(() => {
    const docId = seededPolicy?.doc_id;
    if (!docId || lastSeededDocId.current === docId) return;

    const policy = normalizeSeedPolicy(seededPolicy);
    lastSeededDocId.current = docId;
    let active = true;

    async function seedConversation() {
      setMessages((prev) => [...prev, { role: 'user', text: `'${policy.title}' 선택` }]);
      setInput('');
      setLoading(true);
      setError('');
      try {
        const res = await sendConverse(baseUrl, { message: '', sessionId, userId, policy });
        if (!active) return;
        setSessionId(res.session_id);
        setMessages((prev) => [
          ...prev,
          { role: 'assistant', text: res.reply, actions: res.suggested_actions || [] },
        ]);
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
    return () => {
      active = false;
    };
  }, [baseUrl, seededPolicy, userId]);

  async function send(rawText) {
    const message = (rawText ?? input).trim();
    if (!message || loading) return;
    setMessages((prev) => [...prev, { role: 'user', text: message }]);
    setInput('');
    setLoading(true);
    setError('');
    try {
      const res = await sendConverse(baseUrl, { message, sessionId, userId });
      setSessionId(res.session_id);
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', text: res.reply, actions: res.suggested_actions || [] },
      ]);
    } catch (err) {
      setError('대화 처리 중 오류가 발생했습니다. 백엔드 서버가 켜져 있는지 확인해주세요.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(event) {
    event.preventDefault();
    send();
  }

  const lastActions = !loading ? messages[messages.length - 1]?.actions || [] : [];

  return (
    <section id="chat-flow-panel" className="panel chat-panel">
      <div className="chat-head">
        <div>
          <p className="card-eyebrow">대화형 신청 도우미</p>
          <h2><MessagesSquare size={19} /> 한 번에 물어보기</h2>
        </div>
        <span className="count-badge">추천 · 서류 · 지원금</span>
      </div>

      <div className="chat-window">
        {messages.map((message, index) => (
          <div
            className={`chat-bubble ${message.role === 'user' ? 'user' : 'assistant'}`}
            key={`${message.role}-${index}`}
          >
            <p style={{ whiteSpace: 'pre-wrap' }}>{message.text}</p>
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
              onClick={() => send(actionToMessage(action))}
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
          placeholder='예: "정책 2 신청할래" 또는 "얼마나 받을 수 있어?"'
        />
        <button className="primary-button icon-button" type="submit" disabled={loading || !input.trim()}>
          <Send size={17} />
        </button>
      </form>
      {error && <p className="error">{error}</p>}
    </section>
  );
}
