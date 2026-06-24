import { parsePolicyDeadline } from './agentPlanner.js';

export const FREE_SAVED_LIMIT = 5;
export const PRO_SAVED_LIMIT = 999;

export const PRO_FEATURES = [
  '정책함 무제한 저장',
  '마감 캘린더 자동 등록',
  'D-7 / D-3 / D-1 / 당일 알림',
  'ICS 캘린더 내보내기',
];

export function classifyDeadline(deadline, today = new Date()) {
  if (!deadline) return { status: 'needs_date_check', daysLeft: null };
  const todayUtc = Date.UTC(today.getFullYear(), today.getMonth(), today.getDate());
  const deadlineUtc = Date.UTC(deadline.getUTCFullYear(), deadline.getUTCMonth(), deadline.getUTCDate());
  const daysLeft = Math.ceil((deadlineUtc - todayUtc) / (1000 * 60 * 60 * 24));
  if (daysLeft < 0) return { status: 'expired', daysLeft };
  if (daysLeft <= 7) return { status: 'urgent', daysLeft };
  return { status: 'open', daysLeft };
}

export function buildSavedCalendarEvents(policies, today = new Date()) {
  return (Array.isArray(policies) ? policies : []).map((policy) => {
    const deadline = parsePolicyDeadline(policy.application_period || policy.apply_period);
    const { status, daysLeft } = classifyDeadline(deadline, today);
    return {
      policyKey: policy.doc_id || `${policy.source_table || 'policy'}:${policy.source_id || policy.policy_name || 'unknown'}`,
      policyName: policy.policy_name || '정책명 확인 필요',
      applicationPeriod: policy.application_period || policy.apply_period || '',
      deadlineAt: deadline ? deadline.toISOString().slice(0, 10) : null,
      deadlineStatus: status,
      daysLeft,
      applicationUrl: policy.application_url || policy.url || policy.ref_url || '',
    };
  }).sort((a, b) => {
    if (!a.deadlineAt && !b.deadlineAt) return 0;
    if (!a.deadlineAt) return 1;
    if (!b.deadlineAt) return -1;
    return a.deadlineAt.localeCompare(b.deadlineAt);
  });
}

export function formatDeadlineLabel(daysLeft, status) {
  if (status === 'needs_date_check') return '날짜 확인 필요';
  if (status === 'expired') return '신청 종료';
  if (daysLeft === 0) return '오늘 마감';
  if (daysLeft === 1) return '내일 마감';
  return `${daysLeft}일 남음`;
}

export function buildIcsCalendar(events, calendarName = '충북 청년정책 마감 일정', settings = null) {
  const stamp = new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z');
  const alarmRules = [
    { key: 'notify_d7', trigger: '-P7D', label: 'D-7' },
    { key: 'notify_d3', trigger: '-P3D', label: 'D-3' },
    { key: 'notify_d1', trigger: '-P1D', label: 'D-1' },
    { key: 'notify_d0', trigger: 'PT0S', label: '당일' },
  ].filter((rule) => !settings || settings[rule.key] !== false);

  const lines = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//Chungbuk Youth Policy//Saved Policies//KO',
    'CALSCALE:GREGORIAN',
    'METHOD:PUBLISH',
    `X-WR-CALNAME:${calendarName}`,
  ];

  for (const event of events) {
    if (!event.deadlineAt) continue;
    const dateValue = event.deadlineAt.replace(/-/g, '');
    const uid = `${event.policyKey}-${dateValue}@chungbuk-youth-policy`;
    const summary = `[마감] ${event.policyName}`;
    const description = [event.applicationPeriod, event.applicationUrl].filter(Boolean).join('\\n');
    lines.push(
      'BEGIN:VEVENT',
      `UID:${uid}`,
      `DTSTAMP:${stamp}`,
      `DTSTART:${dateValue}T090000Z`,
      `SUMMARY:${summary}`,
      `DESCRIPTION:${description || '신청 기간 확인 필요'}`,
    );
    for (const rule of alarmRules) {
      lines.push(
        'BEGIN:VALARM',
        'ACTION:DISPLAY',
        `TRIGGER:${rule.trigger}`,
        `DESCRIPTION:${rule.label} ${event.policyName}`,
        'END:VALARM',
      );
    }
    lines.push('END:VEVENT');
  }

  lines.push('END:VCALENDAR');
  return `${lines.join('\r\n')}\r\n`;
}

export function downloadIcsFile(events, filename = 'chungbuk-youth-policy-deadlines.ics', settings = null) {
  const blob = new Blob([buildIcsCalendar(events, undefined, settings)], { type: 'text/calendar;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function defaultNotificationSettings() {
  return {
    enabled: false,
    notify_d7: true,
    notify_d3: true,
    notify_d1: true,
    notify_d0: true,
    plan_tier: 'free',
  };
}

export function canUseProFeature(planTier, feature) {
  if (planTier === 'pro') return true;
  return feature === 'list';
}

const ALERT_RULES = [
  { key: 'notify_d7', daysLeft: 7, label: 'D-7' },
  { key: 'notify_d3', daysLeft: 3, label: 'D-3' },
  { key: 'notify_d1', daysLeft: 1, label: 'D-1' },
  { key: 'notify_d0', daysLeft: 0, label: '당일' },
];

export function getDeadlineAlerts(events, settings, today = new Date()) {
  if (!settings?.enabled) return [];
  const calendarEvents = Array.isArray(events) ? events : buildSavedCalendarEvents(events, today);

  return calendarEvents.flatMap((event) => {
    if (event.daysLeft == null || event.deadlineStatus === 'expired') return [];
    return ALERT_RULES.filter((rule) => settings[rule.key] !== false && event.daysLeft === rule.daysLeft).map(
      (rule) => ({
        ...event,
        alertLabel: rule.label,
      }),
    );
  });
}

export function buildDemoAlarmPolicies(today = new Date()) {
  const base = new Date(Date.UTC(today.getFullYear(), today.getMonth(), today.getDate()));

  function periodForDaysLeft(daysLeft) {
    const deadline = new Date(base);
    deadline.setUTCDate(deadline.getUTCDate() + daysLeft);
    const iso = deadline.toISOString().slice(0, 10);
    return `2026-01-01 ~ ${iso}`;
  }

  return [
    { doc_id: 'demo-alarm-d7', policy_name: '[시연] D-7 알림 테스트', application_period: periodForDaysLeft(7) },
    { doc_id: 'demo-alarm-d3', policy_name: '[시연] D-3 알림 테스트', application_period: periodForDaysLeft(3) },
    { doc_id: 'demo-alarm-d1', policy_name: '[시연] D-1 알림 테스트', application_period: periodForDaysLeft(1) },
    { doc_id: 'demo-alarm-d0', policy_name: '[시연] 당일 마감 테스트', application_period: periodForDaysLeft(0) },
  ];
}

export function isDemoAlarmPolicy(policy) {
  const key = String(policy?.doc_id || policy?.policy_key || '');
  return key.startsWith('demo-alarm-');
}

export function hasDemoAlarmPolicies(policies) {
  return (Array.isArray(policies) ? policies : []).some(isDemoAlarmPolicy);
}

export async function requestNotificationPermission() {
  if (typeof Notification === 'undefined') return 'unsupported';
  if (Notification.permission === 'granted') return 'granted';
  if (Notification.permission === 'denied') return 'denied';
  return Notification.requestPermission();
}

export function showDeadlineNotification(alert) {
  if (typeof Notification === 'undefined' || Notification.permission !== 'granted') return false;
  new Notification(`[${alert.alertLabel}] ${alert.policyName}`, {
    body: alert.applicationPeriod || `마감일 ${alert.deadlineAt || '확인 필요'}`,
    tag: `${alert.policyKey}-${alert.alertLabel}`,
  });
  return true;
}

export async function runDemoAlarmTest(events, settings) {
  const permission = await requestNotificationPermission();
  if (permission === 'unsupported') {
    return { ok: false, message: '이 브라우저는 알림을 지원하지 않습니다.' };
  }
  if (permission === 'denied') {
    return { ok: false, message: '브라우저 설정에서 알림을 허용해 주세요.' };
  }

  const alerts = getDeadlineAlerts(events, settings);
  if (alerts.length === 0) {
    return { ok: false, message: '오늘 울릴 알림이 없습니다. 「시연용 마감 정책 추가」를 먼저 눌러 주세요.' };
  }

  alerts.forEach((alert, index) => {
    window.setTimeout(() => showDeadlineNotification(alert), index * 700);
  });

  return { ok: true, message: `${alerts.length}건의 알림을 보냈습니다.` };
}
