// Centralized API client — all requests go through /api (proxied by Vite → backend)
import type {
  Case, Evidence, ForensicDatabase, Conversation, Message,
  TimelineEntry, SearchResult, AnalysisRun, AuditEvent, Report, Stats, TableRowsResponse
} from '../types';

const BASE = '/api';

async function req<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, options);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Request failed');
  }
  return res.json();
}

// ── Stats ──────────────────────────────────────────────────────────────────
export const getStats = () => req<Stats>('/stats');

// ── Cases ──────────────────────────────────────────────────────────────────
export const getCases = () => req<Case[]>('/cases');
export const getCase = (id: string) => req<Case>(`/cases/${id}`);
export const createCase = (data: { name: string; description?: string; investigator?: string }) =>
  req<Case>('/cases', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });

// ── Evidence ───────────────────────────────────────────────────────────────
export const uploadEvidence = (caseId: string, file: File) => {
  const form = new FormData();
  form.append('file', file);
  return req<Evidence>(`/cases/${caseId}/evidence`, { method: 'POST', body: form });
};
export const autoAcquire = (caseId: string) => 
  req<{ message: string; evidence_ids: string[]; count: number; found: boolean; scanned_paths: string[] }>(`/cases/${caseId}/auto-acquire`, { method: 'POST' });
export const getEvidence = (id: string) => req<Evidence>(`/evidence/${id}`);
export const getEvidenceStatus = (id: string) => req<{ evidence_id: string; status: string; app_detected?: string; sha256?: string; latest_run?: AnalysisRun | null }>(`/evidence/${id}/status`);
export const verifyHash = (id: string) => req<{ evidence_id: string; original_hash: string; current_hash: string; match: boolean; verified_at: string }>(`/evidence/${id}/verify-hash`);
export const analyzeEvidence = (id: string) => req<{ message: string }>(`/evidence/${id}/analyze`, { method: 'POST' });
export const getAnalysisRuns = (caseId?: string) => req<AnalysisRun[]>(`/analysis-runs${caseId ? `?case_id=${caseId}` : ''}`);
export const decryptCrypt14 = (id: string, keyFile: File) => {
  const form = new FormData();
  form.append('key_file', keyFile);
  return req<Evidence>(`/evidence/${id}/decrypt-crypt14`, { method: 'POST', body: form });
};

// ── Databases ──────────────────────────────────────────────────────────────
export const getDatabases = (caseId?: string) =>
  req<ForensicDatabase[]>(`/databases${caseId ? `?case_id=${caseId}` : ''}`);
export const getDatabase = (dbId: string) => req<ForensicDatabase>(`/databases/${dbId}`);
export const getTableRows = (dbId: string, table: string, page = 1, pageSize = 50) =>
  req<TableRowsResponse>(`/databases/${dbId}/tables/${table}/rows?page=${page}&page_size=${pageSize}`);

// ── Conversations ──────────────────────────────────────────────────────────
export const getConversations = (caseId?: string, app?: string) => {
  const params = new URLSearchParams();
  if (caseId) params.set('case_id', caseId);
  if (app) params.set('application', app);
  return req<Conversation[]>(`/conversations?${params}`);
};
export const getConversation = (id: string) => req<Conversation>(`/conversations/${id}`);
export const getConversationMessages = (id: string, page = 1, pageSize = 50) =>
  req<Message[]>(`/conversations/${id}/messages?page=${page}&page_size=${pageSize}`);

// ── Messages ───────────────────────────────────────────────────────────────
export const getMessageEvidence = (id: string) => req<Message>(`/messages/${id}/evidence`);

// ── Timeline ───────────────────────────────────────────────────────────────
export const getTimeline = (params: { case_id?: string; application?: string; from_date?: string; to_date?: string; page?: number }) => {
  const p = new URLSearchParams();
  if (params.case_id) p.set('case_id', params.case_id);
  if (params.application) p.set('application', params.application);
  if (params.from_date) p.set('from_date', params.from_date);
  if (params.to_date) p.set('to_date', params.to_date);
  p.set('page', String(params.page || 1));
  return req<TimelineEntry[]>(`/timeline?${p}`);
};

// ── Search ─────────────────────────────────────────────────────────────────
export const searchMessages = (params: { q?: string; application?: string; case_id?: string; from_date?: string; to_date?: string; message_type?: string; page?: number }) => {
  const p = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v) p.set(k, String(v)); });
  return req<SearchResult>(`/search?${p}`);
};

// ── Reports ────────────────────────────────────────────────────────────────
export const getReports = () => req<Report[]>('/reports');
export const generateReport = (caseId: string, format: string, includeRaw = false) =>
  req<Report>('/reports/generate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ case_id: caseId, format, include_raw_records: includeRaw }) });
export const downloadReport = (reportId: string) => `${BASE}/reports/${reportId}/download`;

// ── Audit ──────────────────────────────────────────────────────────────────
export const getAuditLog = (caseId?: string) => req<AuditEvent[]>(`/audit-log${caseId ? `?case_id=${caseId}` : ''}`);
