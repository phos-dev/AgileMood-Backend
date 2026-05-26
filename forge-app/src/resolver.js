import Resolver from '@forge/resolver';
import { kvs } from '@forge/kvs';
import api from '@forge/api';

const API_URL = 'https://agilemood-backend-v2.vercel.app';
const resolver = new Resolver();

resolver.define('getSettings', async () => {
  return await kvs.get('agilemood-settings');
});

resolver.define('saveSettings', async ({ payload }) => {
  await kvs.set('agilemood-settings', payload);
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
  return await resp.json();
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

resolver.define('registerEmotion', async ({ payload }) => {
  const { emotionId, intensity, notes, teamId, jwtToken } = payload;
  const resp = await api.fetch(`${API_URL}/emotion_record/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${jwtToken}`,
    },
    body: JSON.stringify({
      emotion_id: parseInt(emotionId, 10),
      intensity,
      notes,
      team_id: teamId,
      is_anonymous: true,
    }),
  });
  if (!resp.ok) throw new Error(`${resp.status}`);
  return { success: true };
});

resolver.define('getMessages', async ({ payload }) => {
  const { teamId, jwtToken } = payload;
  const resp = await api.fetch(`${API_URL}/feedback/?team_id=${teamId}`, {
    headers: { Authorization: `Bearer ${jwtToken}` },
  });
  if (!resp.ok) throw new Error(`${resp.status}`);
  const data = await resp.json();
  return Array.isArray(data) ? data : data.feedbacks || [];
});

export const handler = resolver.getDefinitions();
