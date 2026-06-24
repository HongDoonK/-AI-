import assert from 'node:assert/strict';
import { getScoreMood } from './scoreMood.js';

assert.deepEqual(getScoreMood({ match_score: 0.7 }), {
  emoji: '😄',
  label: '추천 점수 높음',
  className: 'score-mood score-mood-excellent',
});

assert.deepEqual(getScoreMood({ match_score_label: '0.58' }), {
  emoji: '🙂',
  label: '추천 점수 양호',
  className: 'score-mood score-mood-good',
});

assert.deepEqual(getScoreMood({ match_score: 0.48 }), {
  emoji: '😐',
  label: '추천 점수 보통',
  className: 'score-mood score-mood-fair',
});

assert.deepEqual(getScoreMood({ match_score_label: '0.39' }), {
  emoji: '😟',
  label: '추천 점수 낮음',
  className: 'score-mood score-mood-low',
});

assert.deepEqual(getScoreMood({ match_score: 0.2 }), {
  emoji: '☹️',
  label: '추천 점수 매우 낮음',
  className: 'score-mood score-mood-poor',
});

assert.equal(getScoreMood({}), null);
