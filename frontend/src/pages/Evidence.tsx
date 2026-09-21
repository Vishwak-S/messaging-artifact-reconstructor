import { useEffect, useState } from 'react';
import { getDatabases } from '../services/api';
import type { ForensicDatabase } from '../types';
import { Database, CheckCircle, XCircle, ChevronRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const APP_COLORS: Record<string, string> = {
  WhatsApp: 'text-emerald-600 bg-emerald-50 border-emerald-200',
  Telegram: 'text-blue-600 bg-blue-50 border-blue-200',
  Signal: 'text-indigo-600 bg-indigo-50 border-indigo-200',
  Unknown: 'text-slate-600 bg-slate-50 border-slate-200',
};

export default function EvidencePage() {
  const [databases, setDatabases] = useState<ForensicDatabase[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<ForensicDatabase | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    getDatabases()
      .then(setDatabases)
      .finally(() => setLoading(false));
  }, []);

  const appGroups = databases.reduce<Record<string, ForensicDatabase[]>>((acc, db) => {
    const app = db.app_detected || 'Unknown';
    if (!acc[app]) acc[app] = [];
    acc[app].push(db);
    return acc;
  }, {});

  return (
    <div className="p-6 space-y-5">
      <div>
        <h2 className="text-xl font-bold text-slate-900">Evidence Explorer</h2>
        <p className="text-slate-500 text-xs mt-0.5">{databases.length} database{databases.length !== 1 ? 's' : ''} across all cases</p>
      </div>

      {loading ? (
        <div className="text-slate-500 animate-pulse text-sm">Loading evidence...</div>
      ) : databases.length === 0 ? (
        <div className="forensic-panel p-12 text-center">
          <Database size={40} className="mx-auto text-slate-300 mb-3" />
          <p className="text-slate-600 font-medium">No evidence imported yet</p>
          <p className="text-slate-500 text-sm mt-1">Go to <button className="text-blue-600 underline" onClick={() => navigate('/cases')}>Cases</button> to import evidence files.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          {/* Left: database list */}
          <div className="lg:col-span-1 space-y-4">
            {Object.entries(appGroups).map(([app, dbs]) => (
              <div key={app} className="forensic-panel">
                <div className="forensic-header flex items-center gap-2">
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold border ${APP_COLORS[app]}`}>{app}</span>
                  <span className="text-slate-600">{dbs.length} DB{dbs.length !== 1 ? 's' : ''}</span>
                </div>
                <ul>
                  {dbs.map(db => (
                    <li
                      key={db.db_id}
                      className={`px-4 py-3 cursor-pointer border-b border-slate-100 last:border-0 flex items-center justify-between hover:bg-blue-50 transition-colors ${selected?.db_id === db.db_id ? 'bg-blue-50 border-l-2 border-l-blue-500' : ''}`}
                      onClick={() => setSelected(db)}
                    >
                      <div>
                        <p className="text-slate-800 font-medium text-sm truncate max-w-[160px]">{db.db_filename}</p>
                        <p className="text-slate-500 text-xs">{db.total_records?.toLocaleString() ?? 0} records</p>
                      </div>
                      <ChevronRight size={14} className="text-slate-400 shrink-0" />
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          {/* Right: database detail */}
          <div className="lg:col-span-2">
            {!selected ? (
              <div className="forensic-panel h-full flex items-center justify-center p-12 text-center text-slate-400">
                <div>
                  <Database size={32} className="mx-auto mb-3 text-slate-300" />
                  <p className="font-medium">Select a database to inspect</p>
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                {/* Header */}
                <div className="forensic-panel p-5">
                  <div className="flex items-start justify-between mb-3">
                    <div>
                      <p className="text-slate-500 text-xs font-mono">{selected.db_id}</p>
                      <h3 className="text-lg font-bold text-slate-900">{selected.db_filename}</h3>
                    </div>
                    <span className={`px-2 py-0.5 text-xs rounded border font-semibold ${APP_COLORS[selected.app_detected || 'Unknown']}`}>
                      {selected.app_detected || 'Unknown'}
                    </span>
                  </div>
                  <div className="grid grid-cols-3 gap-4">
                    {[
                      { label: 'Tables', value: selected.table_count ?? '—' },
                      { label: 'Total Records', value: selected.total_records?.toLocaleString() ?? '—' },
                      { label: 'App Match Confidence', value: selected.detection_confidence ?? '—' },
                    ].map(item => (
                      <div key={item.label} className="bg-slate-50 rounded p-3">
                        <p className="text-slate-500 text-xs uppercase tracking-wider">{item.label}</p>
                        <p className="text-slate-900 font-bold text-lg mt-0.5">{item.value}</p>
                      </div>
                    ))}
                  </div>
                  <div className="flex gap-4 mt-3 text-xs text-slate-600 pt-3 border-t border-slate-100">
                    <span className="flex items-center gap-1">
                      {selected.sqlite_valid ? <CheckCircle size={12} className="text-emerald-500" /> : <XCircle size={12} className="text-rose-500" />}
                      SQLite Valid
                    </span>
                    <span className="flex items-center gap-1">
                      {selected.wal_detected ? <CheckCircle size={12} className="text-amber-500" /> : <XCircle size={12} className="text-slate-400" />}
                      WAL File
                    </span>
                    <span className="flex items-center gap-1">
                      {selected.shm_detected ? <CheckCircle size={12} className="text-amber-500" /> : <XCircle size={12} className="text-slate-400" />}
                      SHM File
                    </span>
                  </div>
                </div>

                {/* Schema info */}
                {selected.schema_info && Object.keys(selected.schema_info).length > 0 && (
                  <div className="forensic-panel">
                    <div className="forensic-header">Database Schema ({Object.keys(selected.schema_info).length} tables)</div>
                    <div className="divide-y divide-slate-100">
                      {Object.entries(selected.schema_info).map(([table, cols]) => (
                        <div key={table} className="px-4 py-3">
                          <p className="font-mono font-semibold text-slate-800 text-sm mb-1">{table}</p>
                          <p className="text-slate-500 text-xs font-mono">{(cols as string[]).join(' · ')}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
