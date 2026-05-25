/**
 * Fetches AgileMood backend using stored JWT token.
 * All errors are thrown so callers can display them.
 */
export async function agilemoodFetch(apiUrl, jwtToken, path, options = {}) {
  const resp = await fetch(`${apiUrl}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${jwtToken}`,
      ...(options.headers || {}),
    },
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`${resp.status} ${resp.statusText}: ${text}`);
  }
  return resp.json();
}
