function parseScore(policy) {
  const rawScore = policy?.match_score;
  if (typeof rawScore === 'number' && Number.isFinite(rawScore)) return rawScore;

  const labelScore = Number.parseFloat(policy?.match_score_label);
  return Number.isFinite(labelScore) ? labelScore : null;
}

export function getScoreMood(policy) {
  const score = parseScore(policy);
  if (score === null) return null;

  if (score >= 0.65) {
    return {
      emoji: '😄',
      label: '추천 점수 높음',
      className: 'score-mood score-mood-excellent',
    };
  }
  if (score >= 0.55) {
    return {
      emoji: '🙂',
      label: '추천 점수 양호',
      className: 'score-mood score-mood-good',
    };
  }
  if (score >= 0.45) {
    return {
      emoji: '😐',
      label: '추천 점수 보통',
      className: 'score-mood score-mood-fair',
    };
  }
  if (score >= 0.35) {
    return {
      emoji: '😟',
      label: '추천 점수 낮음',
      className: 'score-mood score-mood-low',
    };
  }
  return {
    emoji: '☹️',
    label: '추천 점수 매우 낮음',
    className: 'score-mood score-mood-poor',
  };
}
