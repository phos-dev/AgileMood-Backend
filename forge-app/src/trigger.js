import { kvs } from '@forge/kvs';
import api from '@forge/api';

/**
 * Fires on avi:jira:updated:sprint. Skips unless sprint moved to 'closed'.
 * Calls AgileMood backend webhook with HMAC-SHA256 signature.
 */
export async function handler(event) {
  const sprint = event.sprint || event.payload?.sprint;
  if (!sprint || sprint.state?.toLowerCase() !== 'closed') {
    return;
  }

  const API_URL = 'https://agilemood-backend-v2.vercel.app';
  const settings = await kvs.get('agilemood-settings');
  if (!settings?.jwtToken || !settings?.teamId) {
    console.log('[AgileMood] Forge trigger not configured. Skipping sprint-end reminder.');
    return;
  }

  const body = JSON.stringify({
    webhookEvent: 'jira:sprint_closed',
    sprint: { id: sprint.id, name: sprint.name, state: sprint.state },
  });

  const headers = { 'Content-Type': 'application/json' };

  const secret = process.env.JIRA_WEBHOOK_SECRET || '';
  if (secret) {
    const sig = await _hmacSha256(secret, body);
    headers['X-Jira-Signature'] = sig;
  }

  const url = `${API_URL}/webhooks/jira/sprint-end?team_id=${settings.teamId}`;

  try {
    const resp = await api.fetch(url, { method: 'POST', headers, body });
    if (!resp.ok) {
      console.error(`[AgileMood] Webhook call failed: ${resp.status} ${resp.statusText}`);
    } else {
      console.log('[AgileMood] Sprint-end reminder queued successfully.');
    }
  } catch (err) {
    console.error('[AgileMood] Webhook call error:', err.message);
  }
}

async function _hmacSha256(secret, message) {
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey(
    'raw',
    enc.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign'],
  );
  const sigBuffer = await crypto.subtle.sign('HMAC', key, enc.encode(message));
  const hex = Array.from(new Uint8Array(sigBuffer))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
  return `sha256=${hex}`;
}
