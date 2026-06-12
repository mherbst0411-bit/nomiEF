// Thin client for the Nomi Music API.
const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function req(path, opts = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "content-type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch {}
    throw new Error(detail);
  }
  return res.status === 204 ? null : res.json();
}

export const api = {
  createUser: (handle) =>
    req("/v1/users", {
      method: "POST",
      body: JSON.stringify({ handle, accept_terms: true }),
    }),
  onboard: (userId, body) =>
    req(`/v1/users/${userId}/onboarding`, {
      method: "POST", body: JSON.stringify(body),
    }),
  profile: (userId) => req(`/v1/users/${userId}/profile`),
  generate: (userId, body) =>
    req(`/v1/users/${userId}/generate`, {
      method: "POST", body: JSON.stringify(body),
    }),
  tracks: (userId) => req(`/v1/users/${userId}/tracks`),
  track: (userId, trackId) => req(`/v1/users/${userId}/tracks/${trackId}`),
  feedback: (userId, trackId, event_type) =>
    req(`/v1/users/${userId}/tracks/${trackId}/feedback`, {
      method: "POST", body: JSON.stringify({ event_type }),
    }),
  audioUrl: (userId, trackId) =>
    `${BASE}/v1/users/${userId}/tracks/${trackId}/audio`,
  exportData: (userId) => req(`/v1/users/${userId}/export`),
  deleteUser: (userId) =>
    req(`/v1/users/${userId}`, { method: "DELETE" }),
};

export const session = {
  get: () =>
    typeof window === "undefined" ? null : localStorage.getItem("nomi_user"),
  set: (id) => localStorage.setItem("nomi_user", id),
  clear: () => localStorage.removeItem("nomi_user"),
};
