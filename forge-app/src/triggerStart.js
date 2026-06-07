import { storage } from '@forge/api';

export async function handler(event) {
  const sprint = event.sprint;
  if (!sprint) return;

  const boardId = sprint.originBoardId?.toString() ?? 'default';
  const settings = await storage.get(`agilemood-board-${boardId}`);
  if (!settings?.teamId) {
    console.log('[AgileMood] Sprint-start: project not configured. Skipping.');
    return;
  }

  const sprintId = sprint.id?.toString();
  if (!sprintId) return;

  await storage.set(`agilemood-sprint-${sprintId}-start`, {
    startDate: sprint.startDate ?? new Date().toISOString(),
  });
  console.log(`[AgileMood] Sprint ${sprintId} start date stored: ${sprint.startDate}`);
}
