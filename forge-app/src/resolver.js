import Resolver from '@forge/resolver';
import { kvs } from '@forge/kvs';
import api from '@forge/api';

const API_URL = 'https://agilemood-backend-v2.vercel.app';
const resolver = new Resolver();

resolver.define('getSettings', async ({ context }) => {
  return await kvs.get(`settings-${context.accountId}`);
});

resolver.define('saveSettings', async ({ payload, context }) => {
  await kvs.set(`settings-${context.accountId}`, payload);
  return { success: true };
});

resolver.define('login', async ({ payload }) => {
  const { email, password } = payload;
  const resp = await api.fetch(`${API_URL}/user/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ username: email, password }).toString(),
  });
  if (!resp.ok) throw new Error(`${resp.status}`);
  const { access_token } = await resp.json();

  const meResp = await api.fetch(`${API_URL}/user/logged`, {
    headers: { Authorization: `Bearer ${access_token}` },
  });
  if (!meResp.ok) throw new Error(`me: ${meResp.status}`);
  const me = await meResp.json();

  return { access_token, role: me.role, teamId: me.team_id, name: me.name, email: me.email };
});

resolver.define('getMoodSummary', async ({ payload }) => {
  const { teamId, jwtToken, startDate, endDate } = payload;
  const params = new URLSearchParams();
  if (startDate) params.set('start_date', startDate);
  if (endDate) params.set('end_date', endDate);
  const qs = params.toString() ? `?${params}` : '';
  const headers = { Authorization: `Bearer ${jwtToken}` };

  const [distResp, intensityResp] = await Promise.all([
    api.fetch(`${API_URL}/reports/emoji-distribution/${teamId}${qs}`, { headers }),
    api.fetch(`${API_URL}/reports/average-intensity/${teamId}${qs}`, { headers }),
  ]);
  if (!distResp.ok) throw new Error(`emoji-distribution: ${distResp.status}`);
  if (!intensityResp.ok) throw new Error(`average-intensity: ${intensityResp.status}`);

  const [dist, intensity] = await Promise.all([distResp.json(), intensityResp.json()]);
  return { dist, intensity };
});

resolver.define('getMyTeam', async ({ payload }) => {
  const { jwtToken } = payload;
  const resp = await api.fetch(`${API_URL}/teams/`, {
    headers: { Authorization: `Bearer ${jwtToken}` },
  });
  if (!resp.ok) throw new Error(`${resp.status}`);
  const data = await resp.json();
  const teams = Array.isArray(data) ? data : data.teams ?? [];
  if (teams.length === 0) return null;
  return { teamId: teams[0].id, teamName: teams[0].name };
});

resolver.define('getEmotions', async ({ payload }) => {
  const { teamId } = payload;
  const resp = await api.fetch(`${API_URL}/emotions/public?team_id=${teamId}`);
  if (!resp.ok) throw new Error(`${resp.status}`);
  const data = await resp.json();
  return data.emotions ?? [];
});

resolver.define('registerEmotion', async ({ payload }) => {
  const { emotionId, intensity, notes, teamId, jwtToken, isAnonymous } = payload;
  const body = JSON.stringify({
    emotion_id: parseInt(emotionId, 10),
    intensity,
    notes,
    is_anonymous: isAnonymous,
  });

  let resp;
  if (isAnonymous) {
    resp = await api.fetch(`${API_URL}/emotion_record/public?team_id=${teamId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
    });
  } else {
    resp = await api.fetch(`${API_URL}/emotion_record/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${jwtToken}` },
      body,
    });
  }
  if (!resp.ok) throw new Error(`${resp.status}`);
  return { success: true };
});

resolver.define('getMessages', async ({ payload }) => {
  const { jwtToken } = payload;
  const resp = await api.fetch(`${API_URL}/feedback/`, {
    headers: { Authorization: `Bearer ${jwtToken}` },
  });
  if (!resp.ok) throw new Error(`${resp.status}`);
  const data = await resp.json();
  return Array.isArray(data) ? data : data.feedbacks || [];
});

export const handler = resolver.getDefinitions();
