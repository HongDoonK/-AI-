import assert from 'node:assert/strict';
import {
  buildDemoAlarmPolicies,
  buildIcsCalendar,
  buildSavedCalendarEvents,
  classifyDeadline,
  formatDeadlineLabel,
  FREE_SAVED_LIMIT,
  getDeadlineAlerts,
  hasDemoAlarmPolicies,
  isDemoAlarmPolicy,
} from './policyCalendar.js';

const events = buildSavedCalendarEvents(
  [
    { doc_id: 'a', policy_name: 'Soon', application_period: '2026-06-01 ~ 2026-06-12' },
    { doc_id: 'b', policy_name: 'Later', application_period: '2026-06-01 ~ 2026-07-20' },
    { doc_id: 'c', policy_name: 'Unknown', application_period: '상시' },
  ],
  new Date(Date.UTC(2026, 5, 8)),
);

assert.equal(events.length, 3);
assert.equal(events[0].policyName, 'Soon');
assert.equal(events[0].deadlineStatus, 'urgent');
assert.equal(formatDeadlineLabel(events[0].daysLeft, events[0].deadlineStatus), '4일 남음');

const open = classifyDeadline(new Date(Date.UTC(2026, 6, 1)), new Date(Date.UTC(2026, 5, 8)));
assert.equal(open.status, 'open');

const ics = buildIcsCalendar(events, undefined, { notify_d7: true, notify_d3: true, notify_d1: true, notify_d0: true });
assert.match(ics, /BEGIN:VCALENDAR/);
assert.match(ics, /\[마감\] Soon/);
assert.match(ics, /BEGIN:VALARM/);
assert.equal(FREE_SAVED_LIMIT, 5);

const demoAlerts = getDeadlineAlerts(
  buildSavedCalendarEvents(
    [{ doc_id: 'x', policy_name: 'D7', application_period: '2026-06-01 ~ 2026-06-12' }],
    new Date(Date.UTC(2026, 5, 5)),
  ),
  { enabled: true, notify_d7: true, notify_d3: true, notify_d1: true, notify_d0: true },
);
assert.equal(demoAlerts.some((alert) => alert.alertLabel === 'D-7'), true);

const demoPolicies = buildDemoAlarmPolicies(new Date(Date.UTC(2026, 5, 21)));
assert.equal(hasDemoAlarmPolicies(demoPolicies), true);
assert.equal(isDemoAlarmPolicy(demoPolicies[0]), true);
