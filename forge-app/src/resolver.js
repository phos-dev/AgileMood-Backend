import Resolver from '@forge/resolver';
import { kvs } from '@forge/kvs';
import api, { route, storage } from '@forge/api';

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

resolver.define('getMyTeams', async ({ payload }) => {
  const { jwtToken } = payload;
  const resp = await api.fetch(`${API_URL}/teams/`, {
    headers: { Authorization: `Bearer ${jwtToken}` },
  });
  if (!resp.ok) throw new Error(`${resp.status}`);
  const data = await resp.json();
  return (Array.isArray(data) ? data : data.teams ?? []).map(t => ({ id: t.id, name: t.name }));
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

  const resp = await api.fetch(`${API_URL}/emotion_record/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${jwtToken}` },
    body,
  });
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

resolver.define('getSprintToken', async ({ payload }) => {
  const { teamId, jwtToken } = payload;
  const tokenResp = await api.fetch(`${API_URL}/teams/${teamId}/current-sprint-token`, {
    headers: { Authorization: `Bearer ${jwtToken}` },
  });
  if (tokenResp.status === 401) return { status: 'session_expired' };
  if (tokenResp.status === 404) return { status: 'no_active_sprint' };
  if (!tokenResp.ok) throw new Error(`${tokenResp.status}`);
  const { sprint_token, sprint_number, sprint_name } = await tokenResp.json();

  const stateResp = await api.fetch(`${API_URL}/questionnaire/${sprint_token}`, {
    headers: { Authorization: `Bearer ${jwtToken}` },
  });
  if (stateResp.status === 401) return { status: 'session_expired' };
  if (stateResp.status === 410) return { status: 'expired', sprint_token, sprint_number, sprint_name };
  if (!stateResp.ok) throw new Error(`state: ${stateResp.status}`);
  const state = await stateResp.json();
  return { ...state, sprint_token, sprint_number, sprint_name };
});

resolver.define('submitPsQuestionnaire', async ({ payload }) => {
  const { jwtToken, sprint_token, answers } = payload;
  const resp = await api.fetch(`${API_URL}/questionnaire/submit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${jwtToken}` },
    body: JSON.stringify({ sprint_token, answers }),
  });
  if (!resp.ok) throw new Error(`${resp.status}`);
  return { success: true };
});

resolver.define('getPsReport', async ({ payload }) => {
  const { teamId, jwtToken } = payload;
  const resp = await api.fetch(`${API_URL}/reports/psychological-safety?team_id=${teamId}`, {
    headers: { Authorization: `Bearer ${jwtToken}` },
  });
  if (!resp.ok) throw new Error(`${resp.status}`);
  return await resp.json();
});

async function _getBoardId(projectId) {
  try {
    const resp = await api.asApp().requestJira(route`/rest/agile/1.0/board?projectKeyOrId=${projectId}`);
    console.log('[AgileMood] _getBoardId status:', resp.status, 'projectId:', projectId);
    if (resp.ok) {
      const data = await resp.json();
      console.log('[AgileMood] boards found:', JSON.stringify(data.values?.map(b => ({ id: b.id, name: b.name }))));
      const id = data.values?.[0]?.id;
      if (id) return String(id);
    } else {
      console.error('[AgileMood] _getBoardId error:', resp.status);
    }
  } catch (e) {
    console.error('[AgileMood] _getBoardId exception:', e.message);
  }
  return null;
}

resolver.define('connectProject', async ({ payload, context }) => {
  const { teamId } = payload;
  const projectId = context.extension?.project?.id;
  console.log('[AgileMood] connectProject projectId:', projectId, 'teamId:', teamId);
  const boardId = await _getBoardId(projectId);
  console.log('[AgileMood] connectProject saving boardId:', boardId);
  if (!boardId) return { success: false, error: 'board_not_found' };
  const userKey = `agilemood-board-${boardId}-account-${context.accountId}`;
  await storage.set(userKey, { teamId });
  await storage.set(`agilemood-board-${boardId}`, { teamId }); // used by sprint triggers
  return { success: true, boardId };
});

resolver.define('disconnectJira', async ({ payload, context }) => {
  const { teamId, jwtToken } = payload;

  const projectId = context.extension?.project?.id;
  if (projectId) {
    const boardId = await _getBoardId(projectId);
    if (boardId) {
      await storage.delete(`agilemood-board-${boardId}-account-${context.accountId}`);
    }
  }

  const resp = await api.fetch(`${API_URL}/integrations/jira/disconnect?team_id=${teamId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${jwtToken}` },
  });
  if (!resp.ok && resp.status !== 403 && resp.status !== 404) throw new Error(`${resp.status}`);
  return { success: true };
});

resolver.define('getProjectStatus', async ({ context }) => {
  const projectId = context.extension?.project?.id;
  const boardId = await _getBoardId(projectId);
  if (!boardId) return { connected: false, teamId: null };
  const userKey = `agilemood-board-${boardId}-account-${context.accountId}`;
  const s = await storage.get(userKey);
  return { connected: !!(s?.teamId), teamId: s?.teamId ?? null };
});

export const handler = resolver.getDefinitions();
