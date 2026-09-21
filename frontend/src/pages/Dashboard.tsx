import { useEffect, useState } from 'react';
import { getStats } from '../services/api';
import type { Stats } from '../types';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { Database, MessageSquare, FolderKanban, Paperclip, Shield, Activity } from 'lucide-react';

const APP_COLORS: Record<string, string> = {
  WhatsApp: '#25D366',
  Telegram: '#2AABEE',
  Signal: '#3A76F0',
};

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    getStats()
      .then(setStats)
      .catch(() => setError('Cannot connect to backend. Is the server running?'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-8 text-slate-500 animate-pulse">Loading forensic dashboard...</div>;

  if (error) return (
    <div className="p-8">
      <div className="forensic-panel p-6 border-rose-200 bg-rose-50">
        <p className="text-rose-600 font-semibold mb-2">⚠ Backend Connection Error</p>
        <p className="text-slate-600 text-sm">{error}</p>
        <p className="text-slate-500 text-xs mt-2">Make sure the FastAPI backend is running on port 8000.</p>
      </div>
    </div>
  );

  const appData = stats ? Object.entries(stats.applications).map(([name, count]) => ({ name, count })) : [];
  const pieData = appData.filter(d => d.count > 0);

  const statCards = [
    { label: 'Cases', value: stats?.total_cases ?? 0, icon: <FolderKanban size={20} />, color: 'text-blue-600' },
    { label: 'Evidence Files', value: stats?.total_evidence ?? 0, icon: <Database size={20} />, color: 'text-violet-600' },
    { label: 'Databases', value: stats?.total_databases ?? 0, icon: <Database size={20} />, color: 'text-cyan-600' },
    { label: 'Messages', value: (stats?.total_messages ?? 0).toLocaleString(), icon: <MessageSquare size={20} />, color: 'text-emerald-600' },
    { label: 'Conversations', value: stats?.total_conversations ?? 0, icon: <Activity size={20} />, color: 'text-amber-600' },
    { label: 'Attachments', value: stats?.total_attachments ?? 0, icon: <Paperclip size={20} />, color: 'text-rose-600' },
  ];

  return (
    <div className="p-6 space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-900 mb-1">Forensic Analysis Dashboard</h2>
        <p className="text-slate-500 text-xs">Evidence summary across all active cases</p>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {statCards.map(card => (
          <div key={card.label} className="forensic-panel p-4 flex flex-col gap-2">
            <div className={`${card.color}`}>{card.icon}</div>
            <div className="text-2xl font-bold text-slate-900">{card.value}</div>
            <div className="text-slate-500 text-xs uppercase tracking-wider">{card.label}</div>
          </div>
        ))}
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* App distribution bar */}
        <div className="forensic-panel">
          <div className="forensic-header">Application Distribution</div>
          <div className="p-4 h-48">
            {appData.every(d => d.count === 0)
              ? <p className="text-slate-500 text-center pt-12 text-sm">No messages extracted yet. Import evidence to begin.</p>
              : (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={appData} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
                    <XAxis dataKey="name" tick={{ fill: '#64748b', fontSize: 11 }} />
                    <YAxis tick={{ fill: '#64748b', fontSize: 10 }} />
                    <Tooltip contentStyle={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 6, fontSize: 12 }} />
                    <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                      {appData.map(d => (
                        <Cell key={d.name} fill={APP_COLORS[d.name] || '#6366f1'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
          </div>
        </div>

        {/* Pie chart */}
        <div className="forensic-panel">
          <div className="forensic-header">Message Type Share</div>
          <div className="p-4 h-48 flex items-center justify-center gap-6">
            {pieData.length === 0
              ? <p className="text-slate-500 text-sm">No data yet.</p>
              : (
                <>
                  <ResponsiveContainer width={150} height={150}>
                    <PieChart>
                      <Pie data={pieData} dataKey="count" nameKey="name" cx="50%" cy="50%" outerRadius={60} innerRadius={30}>
                        {pieData.map(d => (
                          <Cell key={d.name} fill={APP_COLORS[d.name] || '#6366f1'} />
                        ))}
                      </Pie>
                      <Tooltip contentStyle={{ background: '#ffffff', border: '1px solid #e2e8f0', fontSize: 12 }} />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="space-y-2">
                    {pieData.map(d => (
                      <div key={d.name} className="flex items-center gap-2 text-xs">
                        <div className="w-3 h-3 rounded-full" style={{ background: APP_COLORS[d.name] || '#6366f1' }} />
                        <span className="text-slate-700">{d.name}</span>
                        <span className="text-slate-500">{d.count.toLocaleString()}</span>
                      </div>
                    ))}
                  </div>
                </>
              )}
          </div>
        </div>
      </div>

      {/* Forensic notice */}
      <div className="forensic-panel p-4 border-l-4 border-l-blue-500 bg-blue-50/50">
        <div className="flex items-start gap-3">
          <Shield size={16} className="text-blue-600 mt-0.5 shrink-0" />
          <div>
            <p className="text-blue-800 text-xs font-semibold uppercase tracking-wider mb-1">Forensic Platform Notice</p>
            <p className="text-slate-700 text-xs leading-relaxed">
              This platform is designed for <strong className="text-slate-900">authorized forensic analysis only</strong>. 
              All evidence is preserved read-only. Original files are never modified. 
              Analysis actions are recorded in the chain-of-custody log.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
