/**
 * MGX API client
 */

import type {
  Session,
  SessionCreate,
  HistoryResponse,
  FileTreeResponse,
  FileResponse,
  FileContent,
  DevContainerResponse,
  ProdContainerResponse,
  ProdBuildResponse,
  CollectionsResponse,
  DatabaseQueryResponse,
} from '../types';

const API_BASE = import.meta.env.VITE_API_BASE || '';

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = localStorage.getItem('access_token');
  
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...options.headers,
  };
  
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    if (response.status === 401) {
      logout();
      window.location.href = '/login';
    }
    const error = await response.text();
    throw new ApiError(response.status, error || response.statusText);
  }
  
  return response.json();
}

// Auth
export async function login(username: string, password: string) {
  const formData = new FormData();
  formData.append('username', username);
  formData.append('password', password);
  
  const response = await fetch(`${API_BASE}/oauth2/token`, {
    method: 'POST',
    body: formData,
  });
  
  if (!response.ok) {
    throw new ApiError(response.status, 'Login failed');
  }
  
  const data = await response.json();
  localStorage.setItem('access_token', data.access_token);
  return data;
}

export function logout() {
  localStorage.removeItem('access_token');
}

export function isAuthenticated(): boolean {
  return !!localStorage.getItem('access_token');
}

// Sessions
export async function listSessions() {
  return request<Session[]>('/api/sessions');
}

export async function createSession(name: string, framework: string) {
  return request<Session>('/api/sessions', {
    method: 'POST',
    body: JSON.stringify({ name, framework } as SessionCreate),
  });
}

export async function getSession(sessionId: string) {
  return request<Session>(`/api/sessions/${sessionId}`);
}

// Workspace files
export async function listFileTree(workspaceId: string, dir?: string) {
  const url =
    dir !== undefined
      ? `/api/workspaces/${workspaceId}/entries?${new URLSearchParams({ dir })}`
      : `/api/workspaces/${workspaceId}/entries`;
  return request<FileTreeResponse>(url);
}

export async function readFile(workspaceId: string, path: string) {
  const params = new URLSearchParams({ path });
  return request<FileResponse>(`/api/workspaces/${workspaceId}/files?${params}`);
}

export async function writeFile(workspaceId: string, path: string, content: string) {
  const params = new URLSearchParams({ path });
  return request<FileResponse>(`/api/workspaces/${workspaceId}/files?${params}`, {
    method: 'PUT',
    body: JSON.stringify({ content } as FileContent),
  });
}

// Dev container
export async function startDev(sessionId: string) {
  return request<DevContainerResponse>(`/api/apps/${sessionId}/dev/start`, { method: 'POST' });
}

export async function stopDev(sessionId: string) {
  return request<DevContainerResponse>(`/api/apps/${sessionId}/dev/stop`, { method: 'POST' });
}

export async function getDevStatus(sessionId: string) {
  return request<DevContainerResponse>(`/api/apps/${sessionId}/dev/status`);
}

export async function getDevServerLogs(sessionId: string, tail: number = 100) {
  const params = new URLSearchParams({ tail: tail.toString() });
  return request<{ status: string; logs: string; tail: number }>(
    `/api/apps/${sessionId}/dev/server/logs?${params}`
  );
}

// Production
export async function buildProd(sessionId: string) {
  return request<ProdBuildResponse>(`/api/apps/${sessionId}/prod/build`, { method: 'POST' });
}

export async function deployProd(sessionId: string) {
  return request<ProdContainerResponse>(`/api/apps/${sessionId}/prod/deploy`, { method: 'POST' });
}

export async function stopProd(sessionId: string) {
  return request<ProdContainerResponse>(`/api/apps/${sessionId}/prod/stop`, { method: 'POST' });
}

export async function getProdStatus(sessionId: string) {
  return request<ProdContainerResponse>(`/api/apps/${sessionId}/prod/status`);
}

// Logs
export async function getLogs(sessionId: string, target: 'dev' | 'prod', tail: number = 100) {
  const params = new URLSearchParams({ target, tail: tail.toString() });
  return request<any>(`/api/apps/${sessionId}/logs?${params}`);
}

// Agent
export async function getHistory(sessionId: string, limit: number = 1000) {
  const params = new URLSearchParams({ limit: limit.toString() });
  return request<HistoryResponse>(`/api/apps/${sessionId}/agent/history?${params}`);
}

export async function triggerAgent(sessionId: string, prompt: string) {
  // This returns a streaming response, handle separately
  return request<any>(`/api/apps/${sessionId}/agent/generate`, {
    method: 'POST',
    body: JSON.stringify({ prompt }),
  });
}

export async function getAgentTaskResult(sessionId: string, taskId: string) {
  return request<any>(`/api/apps/${sessionId}/agent/tasks/${taskId}`);
}

export async function stopAgent(sessionId: string) {
  return request<{ success: boolean }>(`/api/apps/${sessionId}/agent/stop`, {
    method: 'POST',
  });
}

// Database
export async function listCollections(sessionId: string) {
  return request<CollectionsResponse>(`/api/apps/${sessionId}/database/collections`);
}

export async function queryCollection(
  sessionId: string,
  collection: string,
  filter: Record<string, any> = {},
  limit: number = 10,
  skip: number = 0
) {
  return request<DatabaseQueryResponse>(`/api/apps/${sessionId}/database/query`, {
    method: 'POST',
    body: JSON.stringify({ collection, filter, limit, skip }),
  });
}
