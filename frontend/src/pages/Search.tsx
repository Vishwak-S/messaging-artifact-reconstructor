import { useState } from 'react';
import { searchMessages, getCases } from '../services/api';
import type { Message, Case } from '../types';
import { Search as SearchIcon, Trash2, Loader } from 'lucide-react';
import { useEffect } from 'react';

const APP_BADGE: Record<string, string> = {
  WhatsApp: 'bg-emerald-100 text-emerald-700 border-emerald-200',
  Telegram: 'bg-blue-100 text-blue-700 border-blue-200',
  Signal: 'bg-indigo-100 text-indigo-700 border-indigo-200',
};

function highlight(text: string, query: string) {
  if (!query.trim()) return <span>{text}</span>;
  const parts = text.split(new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi'));
  return (
    <span>
      {parts.map((part, i) =>
        part.toLowerCase() === query.toLowerCase()
          ? <mark key={i} className="bg-yellow-200 text-yellow-900 rounded px-0.5">{part}</mark>
          : <span key={i}>{part}</span>
      )}
    </span>
  );
}

export default function GlobalSearch() {
  const [cases, setCases] = useState<Case[]>([]);
  const [query, setQuery] = useState('');
  const [caseFilter, setCaseFilter] = useState('');
  const [appFilter, setAppFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [results, setResults] = useState<Message[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  useEffect(() => { getCases().then(setCases); }, []);

  const doSearch = async () => {
    setLoading(true);
    setSearched(true);
    try {
      const res = await searchMessages({
        q: query || undefined,
        case_id: caseFilter || undefined,
        application: appFilter || undefined,
        message_type: typeFilter || undefined,
        page: 1,
      });
      setResults(res.results);
      setTotal(res.total);
    } catch {
      setResults([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  };

  const handleKey = (e: React.KeyboardEvent) => { if (e.key === 'Enter') doSearch(); };

  return (
    <div className="p-6 space-y-5">
      <div>
        <h2 className="text-xl font-bold text-slate-900">Global Search</h2>
        <p className="text-slate-500 text-xs mt-0.5">Search across all messages in all cases</p>
      </div>

      {/* Search bar */}
      <div className="forensic-panel p-4 space-y-3">
        <div className="flex gap-2">
          <div className="flex-1 relative">
            <SearchIcon size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              className="forensic-input w-full pl-9 text-sm"
              placeholder="Search messages, senders, keywords..."
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={handleKey}
            />
          </div>
          <button className="forensic-btn-primary px-6" onClick={doSearch} disabled={loading}>
            {loading ? <Loader size={15} className="animate-spin" /> : <SearchIcon size={15} />}
            {loading ? 'Searching...' : 'Search'}
          </button>
        </div>
        <div className="flex flex-wrap gap-2">
          <select className="forensic-input text-xs" value={caseFilter} onChange={e => setCaseFilter(e.target.value)}>
            <option value="">All Cases</option>
            {cases.map(c => <option key={c.case_id} value={c.case_id}>{c.name}</option>)}
          </select>
          <select className="forensic-input text-xs" value={appFilter} onChange={e => setAppFilter(e.target.value)}>
            <option value="">All Apps</option>
            <option value="WhatsApp">WhatsApp</option>
            <option value="Telegram">Telegram</option>
            <option value="Signal">Signal</option>
          </select>
          <select className="forensic-input text-xs" value={typeFilter} onChange={e => setTypeFilter(e.target.value)}>
            <option value="">All Types</option>
            <option value="text">Text</option>
            <option value="image">Image</option>
            <option value="audio">Audio</option>
            <option value="video">Video</option>
            <option value="document">Document</option>
          </select>
        </div>
      </div>

      {/* Results */}
      {searched && (
        <div>
          <p className="text-slate-500 text-xs mb-3">
            {loading ? 'Searching...' : `${total.toLocaleString()} result${total !== 1 ? 's' : ''} found${query ? ` for "${query}"` : ''}`}
          </p>
          {!loading && results.length === 0 ? (
            <div className="forensic-panel p-12 text-center">
              <SearchIcon size={36} className="mx-auto text-slate-300 mb-3" />
              <p className="text-slate-600 font-medium">No results found</p>
              <p className="text-slate-400 text-sm mt-1">Try a different keyword or remove filters.</p>
            </div>
          ) : (
            <div className="forensic-panel overflow-hidden">
              <div className="divide-y divide-slate-100">
                {results.map(msg => (
                  <div key={msg.message_id} className={`px-4 py-3 ${msg.evidence_status === 'Deleted' ? 'bg-rose-50' : 'hover:bg-slate-50'} transition-colors`}>
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <span className={`text-[10px] px-1.5 py-0.5 rounded border font-bold ${APP_BADGE[msg.application || ''] || 'bg-slate-100 text-slate-600 border-slate-200'}`}>
                        {msg.application || '?'}
                      </span>
                      <span className="text-slate-700 text-xs font-semibold">{msg.sender || 'Unknown'}</span>
                      {msg.recipient && <span className="text-slate-400 text-xs">→ {msg.recipient}</span>}
                      {msg.evidence_status === 'Deleted' && (
                        <span className="flex items-center gap-0.5 text-[10px] text-rose-700 font-bold bg-rose-100 border border-rose-200 px-1.5 py-0.5 rounded ml-auto">
                          <Trash2 size={10} /> DELETED
                        </span>
                      )}
                      <span className="text-slate-400 text-[10px] ml-auto">
                        {msg.timestamp ? new Date(msg.timestamp).toLocaleString() : '—'}
                      </span>
                    </div>
                    <p className={`text-sm leading-relaxed ${msg.evidence_status === 'Deleted' ? 'text-rose-800 italic' : 'text-slate-800'}`}>
                      {highlight(msg.message_text || '[no text]', query)}
                    </p>
                    {msg.has_attachment && (
                      <p className="text-xs text-slate-500 mt-1">📎 {msg.attachment_name || 'Attachment'}</p>
                    )}
                    <p className="text-slate-400 text-[10px] mt-1 font-mono">{msg.source_database} · {msg.source_table}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {!searched && (
        <div className="forensic-panel p-12 text-center">
          <SearchIcon size={40} className="mx-auto text-slate-300 mb-3" />
          <p className="text-slate-600 font-medium">Enter a keyword to search</p>
          <p className="text-slate-400 text-sm mt-1">Search across all messages, senders, and attachments.</p>
        </div>
      )}
    </div>
  );
}
