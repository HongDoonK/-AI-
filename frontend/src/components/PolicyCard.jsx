import { ClipboardList, ExternalLink, Search, Send } from 'lucide-react';
import { displayValue, getPossibilityClass } from '../appConfig.js';
import { getScoreMood } from '../scoreMood.js';

export default function PolicyCard({ policy, index, onChat, onPrepare, onApply }) {
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
              <li key={`${item}-${idx}`}><span>{item}</span></li>
            ))}
          </ul>
        </section>
      )}
      <div className="policy-actions">
        <button className="primary-button" type="button" onClick={() => onApply(policy)}><Send size={16} /> 신청 준비하기</button>
        <button className="ghost-button" type="button" onClick={() => onPrepare(policy)}><ClipboardList size={16} /> 준비 체크 시작</button>
        <button className="ghost-button" type="button" onClick={() => onChat(policy)}><Search size={16} /> 이 정책 자세히 보기</button>
        {url && <a className="link-button" href={url} target="_blank" rel="noreferrer">신청/참고 링크 열기 <ExternalLink size={15} /></a>}
      </div>
    </article>
  );
}
