import { useEffect, useState } from 'react';
import { getCases, createCase } from '../services/api';
import type { Case } from '../types';
import { Plus, FolderOpen, ChevronRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export default function Cases() {
  const [cases, setCases] = useState<Case[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: '', description: '', investigator: '' });
  const [creating, setCreating] = useState(false);
  const navigate = useNavigate();

  const load = () => getCases().then(setCases).finally(() => setLoading(false));
  useEffect(() => { load(); }, []);

  const handleCreate = async () => {
    if (!form.name.trim()) return;
    setCreating(true);
    try {
      await createCase(form);
      setForm({ name: '', description: '', investigator: '' });
      setShowForm(false);
      load();
    } finally { setCreating(false); }
  };

  const statusColor = (s: string) => s === 'open' ? 'badge-active' : s === 'closed' ? 'badge-deleted' : 'badge-warning';

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Case Management</h2>
          <p className="text-slate-500 text-xs mt-0.5">{cases.length} case{cases.length !== 1 ? 's' : ''} in system</p>
        </div>
        <button className="forensic-btn-primary" onClick={() => setShowForm(!showForm)}>
          <Plus size={16} /> New Case
        </button>
      </div>

      {/* Create form */}
      {showForm && (
        <div className="forensic-panel p-5 space-y-3 border-blue-200 bg-blue-50/30">
          <p className="forensic-header -mx-5 -mt-5 mb-4 rounded-t">Create New Case</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-slate-700 font-semibold mb-1 block">Case Name *</label>
              <input className="forensic-input w-full" placeholder="e.g. Mobile Device Analysis 2026"
                value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />
            </div>
            <div>
              <label className="text-xs text-slate-700 font-semibold mb-1 block">Investigator</label>
              <input className="forensic-input w-full" placeholder="Investigator name"
                value={form.investigator} onChange={e => setForm({ ...form, investigator: e.target.value })} />
            </div>
          </div>
          <div>
            <label className="text-xs text-slate-700 font-semibold mb-1 block">Description</label>
            <textarea className="forensic-input w-full resize-none" rows={3} placeholder="Case description..."
              value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} />
          </div>
          <div className="flex gap-3 pt-1">
            <button className="forensic-btn-primary" onClick={handleCreate} disabled={creating || !form.name.trim()}>
              {creating ? 'Creating...' : 'Create Case'}
            </button>
            <button className="forensic-btn" onClick={() => setShowForm(false)}>Cancel</button>
          </div>
        </div>
      )}

      {/* Cases list */}
      {loading
        ? <div className="text-slate-500 animate-pulse">Loading cases...</div>
        : cases.length === 0
        ? (
          <div className="forensic-panel p-12 text-center">
            <FolderOpen size={40} className="mx-auto text-slate-300 mb-3" />
            <p className="text-slate-500 font-medium">No cases yet</p>
            <p className="text-slate-400 text-sm mt-1">Create your first forensic case to begin analysis.</p>
          </div>
        )
        : (
          <div className="forensic-panel overflow-hidden">
            <table className="forensic-table">
              <thead>
                <tr>
                  <th>Case ID</th>
                  <th>Name</th>
                  <th>Investigator</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {cases.map(c => (
                  <tr key={c.case_id} className="cursor-pointer" onClick={() => navigate(`/cases/${c.case_id}`)}>
                    <td className="text-blue-600 font-mono text-xs font-semibold">{c.case_id}</td>
                    <td className="text-slate-900 font-medium">{c.name}</td>
                    <td className="text-slate-600">{c.investigator || '—'}</td>
                    <td><span className={`badge ${statusColor(c.status)}`}>{c.status}</span></td>
                    <td className="text-slate-500 text-xs">{new Date(c.created_at).toLocaleDateString()}</td>
                    <td><ChevronRight size={14} className="text-slate-400" /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
    </div>
  );
}
