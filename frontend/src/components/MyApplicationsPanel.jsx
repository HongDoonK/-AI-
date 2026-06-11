import { ClipboardList, Loader2 } from 'lucide-react';
import { getApplyProgress, getDeadlineUrgency, getStatusLabel } from '../applyPlan.js';

export default function MyApplicationsPanel({ applications, loading, onOpen }) {
  if (!loading && (!applications || applications.length === 0)) return null;

  return (
    <section className="panel">
      <p className="card-eyebrow">내 신청 현황</p>
      <h2><ClipboardList size={19} /> 진행 중인 신청 {applications?.length || 0}건</h2>
      {loading && <p className="muted"><Loader2 className="spin" size={14} /> 불러오는 중...</p>}
      <ul className="check-list">
        {(applications || []).map((item) => {
          const urgency = getDeadlineUrgency(item.days_left);
          const progress = item.progress?.total
            ? `${item.progress.completed}/${item.progress.total}`
            : getApplyProgress(item).total
              ? `${getApplyProgress(item).completed}/${getApplyProgress(item).total}`
              : '';
          return (
            <li key={item.application_id}>
              <button
                className="ghost-button"
                type="button"
                onClick={() => onOpen(item.application_id)}
                style={{ width: '100%', textAlign: 'left' }}
              >
                <span className="prep-item-content">
                  <span className="prep-item-text">{item.policy_name || item.doc_id}</span>
                  <span>
                    <span className={urgency.className}>{urgency.label}</span>{' '}
                    <span className="badge blue">{getStatusLabel(item.status)}</span>
                    {progress && <span className="hint"> {progress} 완료</span>}
                  </span>
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
