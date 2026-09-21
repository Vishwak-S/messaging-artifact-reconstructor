import { useEffect, useState } from 'react';
import { getAuditLog, getAnalysisRuns, getCases } from '../services/api';
import type { AuditEvent, AnalysisRun, Case } from '../types';
import { Shield, CheckCircle, XCircle, Clock, RefreshCw, Activity } from 'lucide-react';

const ACTION_COLORS: Record<string, string> = {
  EVIDENCE_IMPORTED: 'text-blue-600 bg-blue-50 border-blue-200',
  HASH_CALCULATED: 'text-slate-600 bg-slate-50 border-slate-200',
  HASH_VERIFIED: 'text-emerald-600 bg-emerald-50 border-emerald-200',
  APPLICATION_IDENTIFIED: 'text-indigo-600 bg-indigo-50 border-indigo-200',
  ANALYSIS_STARTED: 'text-amber-600 bg-amber-50 border-amber-200',
  ANALYSIS_COMPLETED: 'text-emerald-600 bg-emerald-50 border-emerald-200',
  ANALYSIS_FAILED: 'text-rose-600 bg-rose-50 border-rose-200',
  REPORT_GENERATED: 'text-purple-600 bg-purple-50 border-purple-200',
};

function StatusBadge({ status }: { status: string }) {
  if (status === 'completed') return <span className="flex items-center gap-1 text-emerald-600 text-xs font-semibold"><CheckCircle size={12} />Completed</span>;
  if (status === 'failed' || status === 'error') return <span className="flex items-center gap-1 text-rose-600 text-xs font-semibold"><XCircle size={12} />Failed</span>;
  return <span className="flex items-center gap-1 text-amber-600 text-xs font-semibold"><Clock size={12} />{status}</span>;
}

export default function AuditLog() {
  const [cases, setCases] = useState<Case[]>([]);
  const [selectedCase, setSelectedCase] = useState('');
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [runs, setRuns] = useState<AnalysisRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'audit' | 'runs'>('audit');

  const load = (caseId: string) => {
    setLoading(true);
    Promise.all([getAuditLog(caseId || undefined), getAnalysisRuns(caseId || undefined)])
      .then(([a, r]) => { setAudit(a); setRuns(r); })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    getCases().then(c => {
      setCases(c);
      const id = c[0]?.case_id || '';
      setSelectedCase(id);
      load(id);
    });
  }, []);

  const handleCaseChange = (id: string) => {
    setSelectedCase(id);
    load(id);
  };

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Chain of Custody</h2>
          <p className="text-slate-500 text-xs mt-0.5">Immutable audit log and analysis run history</p>
        </div>
        <div className="flex items-center gap-2">
          <select className="forensic-input text-sm" value={selectedCase} onChange={e => handleCaseChange(e.target.value)}>
            <option value="">All Cases</option>
            {cases.map(c => <option key={c.case_id} value={c.case_id}>{c.name}</option>)}
          </select>
          <button className="forensic-btn" onClick={() => load(selectedCase)}>
            <RefreshCw size={14} />
          </button>
          <button 
            className="forensic-btn text-rose-600 border-rose-200 hover:bg-rose-50" 
            onClick={() => { setAudit([]); setRuns([]); }}
          >
            Clear Display
          </button>
        </div>
      </div>

      {/* Tab switcher */}
      <div className="flex border-b border-slate-200">
        {[
          { id: 'audit', label: 'Audit Events', icon: <Shield size={14} />, count: audit.length },
          { id: 'runs', label: 'Analysis Runs', icon: <Activity size={14} />, count: runs.length },
        ].map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id as any)}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              tab === t.id ? 'border-blue-500 text-blue-600' : 'border-transparent text-slate-600 hover:text-slate-900'
            }`}
          >
            {t.icon}
            {t.label}
            <span className="text-[10px] bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded font-bold">{t.count}</span>
          </button>
        ))}
      </div>

      {loading ? (
        <div className="text-slate-500 animate-pulse text-sm py-8 text-center">Loading audit trail...</div>
      ) : tab === 'audit' ? (
        <div className="forensic-panel overflow-hidden">
          {audit.length === 0 ? (
            <div className="p-12 text-center">
              <Shield size={40} className="mx-auto text-slate-300 mb-3" />
              <p className="text-slate-600 font-medium">No audit events</p>
              <p className="text-slate-400 text-sm mt-1">Events are recorded when you import and analyze evidence.</p>
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {[...audit].reverse().map(ev => (
                <div key={ev.id} className="p-4 hover:bg-slate-50 transition-colors">
                  <div className="flex items-start gap-3">
                    <span className={`text-[10px] px-1.5 py-0.5 rounded border font-bold shrink-0 mt-0.5 ${ACTION_COLORS[ev.action] || 'text-slate-600 bg-slate-50 border-slate-200'}`}>
                      {ev.action.replace(/_/g, ' ')}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-slate-800 text-sm">{ev.description || '—'}</p>
                      <div className="flex gap-3 mt-1 text-[10px] text-slate-400 font-mono">
                        <span>{new Date(ev.timestamp).toLocaleString()}</span>
                        {ev.case_id && <span>Case: {ev.case_id}</span>}
                        {ev.evidence_id && <span>Evidence: {ev.evidence_id}</span>}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        /* Analysis Runs */
        <div className="forensic-panel overflow-hidden">
          {runs.length === 0 ? (
            <div className="p-12 text-center">
              <Activity size={40} className="mx-auto text-slate-300 mb-3" />
              <p className="text-slate-600 font-medium">No analysis runs yet</p>
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {[...runs].reverse().map(run => (
                <div key={run.run_id} className="p-4 hover:bg-slate-50 transition-colors">
                  <div className="flex items-center justify-between mb-2">
                    <div>
                      <p className="font-mono text-xs text-slate-500">{run.run_id}</p>
                      <p className="text-slate-800 font-semibold text-sm mt-0.5">Evidence: {run.evidence_id}</p>
                    </div>
                    <StatusBadge status={run.status} />
                  </div>
                  <div className="grid grid-cols-3 gap-3 text-xs">
                    {[
                      { label: 'Messages', value: run.messages_extracted },
                      { label: 'Conversations', value: run.conversations_found },
                      { label: 'Attachments', value: run.attachments_found },
                    ].map(s => (
                      <div key={s.label} className="bg-slate-50 rounded p-2 border border-slate-100">
                        <p className="text-slate-400 uppercase tracking-wider text-[10px]">{s.label}</p>
                        <p className="text-slate-900 font-bold text-base">{s.value}</p>
                      </div>
                    ))}
                  </div>
                  {run.pipeline_log && run.pipeline_log.length > 0 && (
                    <div className="mt-3 space-y-1 font-mono text-[11px] bg-slate-50 rounded border border-slate-100 p-2">
                      {run.pipeline_log.map((step, i) => (
                        <div key={i} className="flex items-center gap-2">
                          {step.status === 'OK' ? <CheckCircle size={11} className="text-emerald-500 shrink-0" /> : <XCircle size={11} className="text-rose-500 shrink-0" />}
                          <span className="text-slate-500 w-28 shrink-0">{step.step}</span>
                          <span className="text-slate-700 truncate">{step.detail}</span>
                        </div>
                      ))}
                    </div>
                  )}
                  <p className="text-slate-400 text-[10px] mt-2">
                    Started: {new Date(run.start_time).toLocaleString()}
                    {run.end_time && ` · Ended: ${new Date(run.end_time).toLocaleString()}`}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
