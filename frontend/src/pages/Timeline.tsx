import { useEffect, useState } from 'react';
import { getTimeline, getCases } from '../services/api';
import type { TimelineEntry, Case } from '../types';
import { Clock, Trash2, Filter } from 'lucide-react';

const APP_DOT: Record<string, string> = {
  WhatsApp: 'bg-emerald-500',
  Telegram: 'bg-blue-500',
  Signal: 'bg-indigo-500',
};
const APP_LINE: Record<string, string> = {
  WhatsApp: 'border-emerald-300',
  Telegram: 'border-blue-300',
  Signal: 'border-indigo-300',
};

function groupByDate(entries: TimelineEntry[]) {
  const groups: Record<string, TimelineEntry[]> = {};
  entries.forEach(e => {
    const date = e.timestamp ? new Date(e.timestamp).toLocaleDateString('en-GB', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' }) : 'Unknown Date';
    if (!groups[date]) groups[date] = [];
    groups[date].push(e);
  });
  return groups;
}

export default function Timeline() {
  const [cases, setCases] = useState<Case[]>([]);
  const [selectedCase, setSelectedCase] = useState('');
  const [appFilter, setAppFilter] = useState('');
  const [entries, setEntries] = useState<TimelineEntry[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getCases().then(c => {
      setCases(c);
      if (c.length > 0) setSelectedCase(c[0].case_id);
    });
  }, []);

  useEffect(() => {
    if (!selectedCase) return;
    setLoading(true);
    getTimeline({ case_id: selectedCase, application: appFilter || undefined, page: 1 })
      .then(setEntries)
      .finally(() => setLoading(false));
  }, [selectedCase, appFilter]);

  const grouped = groupByDate(entries);
  const deletedCount = entries.filter(e => e.evidence_status === 'Deleted').length;

  return (
    <div className="p-6 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Cross-App Timeline</h2>
          <p className="text-slate-500 text-xs mt-0.5">
            {entries.length} events
            {deletedCount > 0 && <span className="ml-2 text-rose-600 font-semibold">· {deletedCount} deleted recovered</span>}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Filter size={14} className="text-slate-400" />
          <select className="forensic-input text-sm" value={selectedCase} onChange={e => setSelectedCase(e.target.value)}>
            {cases.map(c => <option key={c.case_id} value={c.case_id}>{c.name}</option>)}
          </select>
          <select className="forensic-input text-sm" value={appFilter} onChange={e => setAppFilter(e.target.value)}>
            <option value="">All Apps</option>
            <option value="WhatsApp">WhatsApp</option>
            <option value="Telegram">Telegram</option>
            <option value="Signal">Signal</option>
          </select>
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4">
        {['WhatsApp', 'Telegram', 'Signal'].map(app => (
          <div key={app} className="flex items-center gap-1.5 text-xs text-slate-600">
            <div className={`w-2.5 h-2.5 rounded-full ${APP_DOT[app]}`} />
            {app}
          </div>
        ))}
        <div className="flex items-center gap-1.5 text-xs text-rose-600 ml-2">
          <Trash2 size={12} />
          Deleted
        </div>
      </div>

      {loading ? (
        <div className="text-slate-500 animate-pulse text-sm py-8 text-center">Building timeline...</div>
      ) : entries.length === 0 ? (
        <div className="forensic-panel p-12 text-center">
          <Clock size={40} className="mx-auto text-slate-300 mb-3" />
          <p className="text-slate-600 font-medium">No timeline events</p>
          <p className="text-slate-400 text-sm mt-1">Import evidence and run analysis to build the timeline.</p>
        </div>
      ) : (
        <div className="space-y-6">
          {Object.entries(grouped).map(([date, dayEntries]) => (
            <div key={date}>
              {/* Date separator */}
              <div className="flex items-center gap-3 mb-3">
                <div className="h-px flex-1 bg-slate-200" />
                <span className="text-xs font-semibold text-slate-500 bg-slate-100 px-3 py-1 rounded-full border border-slate-200">{date}</span>
                <div className="h-px flex-1 bg-slate-200" />
              </div>

              {/* Events */}
              <div className="relative ml-4">
                <div className="absolute left-2 top-0 bottom-0 w-px bg-slate-200" />
                <div className="space-y-1">
                  {dayEntries.map((entry, i) => {
                    const isDeleted = entry.evidence_status === 'Deleted';
                    const dot = APP_DOT[entry.application || ''] || 'bg-slate-400';
                    const line = APP_LINE[entry.application || ''] || 'border-slate-200';
                    return (
                      <div key={`${entry.message_id}-${i}`} className={`relative flex gap-4 pl-8 py-2 rounded-lg ${isDeleted ? 'bg-rose-50 border border-rose-100' : 'hover:bg-slate-50'} transition-colors`}>
                        {/* Dot on timeline */}
                        <div className={`absolute left-0 top-3 w-4 h-4 rounded-full border-2 border-white ${dot} shadow-sm`} />
                        {/* Time */}
                        <div className="shrink-0 w-16 text-right">
                          <span className="text-slate-400 text-xs font-mono">
                            {entry.timestamp ? new Date(entry.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—'}
                          </span>
                        </div>
                        {/* Content */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-0.5">
                            <span className="text-xs font-semibold text-slate-600">{entry.sender || 'Unknown'}</span>
                            {isDeleted && <span className="flex items-center gap-0.5 text-[10px] text-rose-600 font-bold"><Trash2 size={10} />DELETED</span>}
                            <span className={`text-[10px] px-1 py-0.5 rounded border font-semibold ml-auto
                              ${entry.application === 'WhatsApp' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' :
                                entry.application === 'Telegram' ? 'bg-blue-50 text-blue-700 border-blue-200' :
                                'bg-indigo-50 text-indigo-700 border-indigo-200'}`}>
                              {entry.application || '?'}
                            </span>
                          </div>
                          <p className={`text-sm truncate ${isDeleted ? 'text-rose-700 italic' : 'text-slate-800'}`}>
                            {entry.message_text || <span className="text-slate-400 italic">[{entry.message_type}]</span>}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
