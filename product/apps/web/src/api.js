const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();

  if (!response.ok) {
    const error = new Error(
      typeof payload === "object" && payload?.detail ? payload.detail : `Request failed with ${response.status}`,
    );
    error.status = response.status;
    error.payload = payload;
    throw error;
  }

  return payload;
}

export const api = {
  baseUrl: API_BASE_URL,
  listProjects: () => request("/api/projects"),
  createProject: (payload) =>
    request("/api/projects", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getProject: (projectId) => request(`/api/projects/${projectId}`),
  updateProject: (projectId, payload) =>
    request(`/api/projects/${projectId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  deleteProject: (projectId) =>
    request(`/api/projects/${projectId}`, {
      method: "DELETE",
    }),
  deployProject: (projectId, payload) =>
    request(`/api/projects/${projectId}/deployments`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  listProjectDeployments: (projectId) => request(`/api/projects/${projectId}/deployments`),
  getDeploymentLogs: (deploymentId) => request(`/api/deployments/${deploymentId}/logs`),
  listReleases: (projectId) => request(`/api/projects/${projectId}/releases`),
  rollbackProject: (projectId, payload) =>
    request(`/api/projects/${projectId}/rollback`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getProviderStatus: () => request("/api/providers/status"),
  validateRepo: (payload) =>
    request("/api/providers/validate-repo", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  registerProjectWebhook: (projectId) =>
    request(`/api/projects/${projectId}/webhook-registration`, {
      method: "POST",
    }),
};
