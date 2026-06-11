import { CheckCircle2, ClipboardList, ExternalLink, Loader2 } from 'lucide-react';
import {
  formatDeadlineLabel,
  getApplyProgress,
  getChannelLabel,
  getEligibilityBadge,
  getNextStatusActions,
  getStatusLabel,
  groupChecklist,
  isChecklistLocked,
} from '../applyPlan.js';

const GROUP_TITLES = {
  document: '제출 서류',
  eligibility: '자격 확인',
  action: '신청 단계',
};

function ChecklistGroup({ title, items, locked, onToggleItem }) {
  if (!items.length) return null;
  return (
    <section className="mini-section">
      <h4>{title}</h4>
      <ul className="prep-check-list">
        {items.map((item) => (
          <li className={item.checked ? 'done' : ''} key={item.item_id}>
            <label>
              <input
                type="checkbox"
                checked={item.checked}
                disabled={locked}
                onChange={(event) => onToggleItem(item.item_id, event.target.checked)}
              />
              <span className="prep-item-content">
                <span className="prep-item-text">{item.label}</span>
                {item.help_url ? (
                  <a className="prep-resource-link" href={item.help_url} target="_blank" rel="noreferrer">
                    {item.help_label || '바로가기'}
                  </a>
                ) : (
                  item.help_label && <span className="hint">{item.help_label}</span>
                )}
              </span>
            </label>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function ApplyPanel({ plan, loading, error, onToggleItem, onStatusChange }) {
  if (loading) {
    return (
      <section className="panel prep-board">
        <p className="card-eyebrow">신청 도우미</p>
        <p className="muted"><Loader2 className="spin" size={16} /> 신청 플랜을 만드는 중...</p>
      </section>
    );
  }
  if (!plan) return null;

  const progress = getApplyProgress(plan);
  const groups = groupChecklist(plan);
  const eligibility = getEligibilityBadge(plan.eligibility);
  const locked = isChecklistLocked(plan.status);
  const statusActions = getNextStatusActions(plan);

  return (
    <section className="panel prep-board">
      <p className="card-eyebrow">신청 도우미 에이전트</p>
      <h2><ClipboardList size={19} /> {plan.policy_name || '선택한 정책'}</h2>

      <div className="policy-rank-row">
        <span className={eligibility.className}>{eligibility.label}</span>
        <span className="badge blue">{getStatusLabel(plan.status)}</span>
        <span className="badge">{getChannelLabel(plan.apply_channel)}</span>
      </div>
      <div className="policy-meta">
        <span>마감: {formatDeadlineLabel(plan)}</span>
      </div>

      {plan.eligibility_notes?.length > 0 && (
        <ul className="check-list">
          {plan.eligibility_notes.map((note, idx) => (
            <li key={`${note.field}-${idx}`}><span>{note.reason}</span></li>
          ))}
        </ul>
      )}

      <div className="prep-summary">
        <strong>{progress.completed}/{progress.total} 완료</strong>
        <span>{progress.percent}% 준비 완료</span>
      </div>
      <div className="prep-progress" aria-label={`신청 준비 진행률 ${progress.percent}%`}>
        <div style={{ width: `${progress.percent}%` }} />
      </div>

      <ChecklistGroup title={GROUP_TITLES.document} items={groups.document} locked={locked} onToggleItem={onToggleItem} />
      <ChecklistGroup title={GROUP_TITLES.eligibility} items={groups.eligibility} locked={locked} onToggleItem={onToggleItem} />
      <ChecklistGroup title={GROUP_TITLES.action} items={groups.action} locked={locked} onToggleItem={onToggleItem} />

      {plan.draft_answers && Object.keys(plan.draft_answers).length > 0 && (
        <section className="mini-section">
          <h4>신청서 초안 (AI 작성, 제출 전 꼭 수정·확인)</h4>
          {Object.entries(plan.draft_answers).map(([field, text]) => (
            <div key={field} className="prep-item-content" style={{ marginBottom: '8px' }}>
              <strong className="prep-item-text">{field}</strong>
              <p className="muted" style={{ whiteSpace: 'pre-wrap' }}>{text}</p>
              <button
                className="ghost-button"
                type="button"
                onClick={() => navigator.clipboard?.writeText(text)}
              >
                복사
              </button>
            </div>
          ))}
        </section>
      )}

      {plan.next_action && <p className="hint">{plan.next_action}</p>}

      <div className="policy-actions">
        {plan.apply_channel === 'online' && plan.apply_url && (
          <a className="link-button" href={plan.apply_url} target="_blank" rel="noreferrer">
            신청 페이지 열기 <ExternalLink size={15} />
          </a>
        )}
        {statusActions.map((action) => (
          <button
            className="ghost-button"
            type="button"
            key={action.status}
            onClick={() => onStatusChange(action.status)}
          >
            {action.label}
          </button>
        ))}
      </div>

      {plan.status === 'submitted' && (
        <p className="prep-complete"><CheckCircle2 size={16} /> 제출 완료로 표시했습니다. 접수 확인까지 잊지 마세요.</p>
      )}
      {error && <p className="error">{error}</p>}
    </section>
  );
}
