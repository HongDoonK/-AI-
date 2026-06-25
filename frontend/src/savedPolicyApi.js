const SAVED_POLICIES_URL = (userId) => `${API_BASE}/saved-policies/${encodeURIComponent(userId)}`;

function getApiBase() {
  if (typeof window !== 'undefined') {
    const { hostname, protocol } = window.location;
    if (hostname !== 'localhost' && hostname !== '127.0.0.1') {
      return `${protocol}//${hostname}:8000`;
    }
  }
  const raw = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');
  return raw.endsWith('/recommend') ? raw.slice(0, -'/recommend'.length) : raw;
}

const API_BASE = getApiBase();

export async function syncSavedPolicies(userId, policies) {
  const response = await fetch(`${SAVED_POLICIES_URL(userId)}/sync`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ policies }),
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

export async function fetchNotificationSettings(userId) {
  const response = await fetch(`${SAVED_POLICIES_URL(userId)}/notification-settings`);
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

export async function saveNotificationSettings(userId, settings) {
  const response = await fetch(`${SAVED_POLICIES_URL(userId)}/notification-settings`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings),
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

export function getServerCalendarIcsUrl(userId) {
  return `${SAVED_POLICIES_URL(userId)}/calendar.ics`;
}
