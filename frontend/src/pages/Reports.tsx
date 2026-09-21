import { useEffect, useState } from 'react';
import { getReports, generateReport, downloadReport, getCases } from '../services/api';
import type { Report, Case } from '../types';
import { FileText, Download, Plus, Loader, RefreshCw } from 'lucide-react';

export default function Reports() {
  const [cases, setCases] = useState<Case[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [selectedCase, setSelectedCase] = useState('');
  const [format, setFormat] = useState('json');
  const [includeRaw, setIncludeRaw] = useState(false);

  const load = () =>
    Promise.all([getCases(), getReports()])
      .then(([c, r]) => {
        setCases(c);
        setReports(r);
        if (c.length > 0 && !selectedCase) setSelectedCase(c[0].case_id);
      })
      .finally(() => setLoading(false));

  useEffect(() => { load(); }, []);

  const handleGenerate = async () => {
    if (!selectedCase) return;
    setGenerating(true);
    try {
      await generateReport(selectedCase, format, includeRaw);
      load();
    } catch (err: any) {
      alert(err.message);
    } finally {
      setGenerating(false);
    }
  };

  const fmtSize = (bytes?: number) => {
    if (!bytes) return '—';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  };

  const FORMAT_ICONS: Record<string, string> = { json: '{}', pdf: '📄', csv: '📊' };

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Report Generation</h2>
          <p className="text-slate-500 text-xs mt-0.5">Generate forensic reports for chain-of-custody documentation</p>
        </div>
        <button className="forensic-btn" onClick={load}>
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {/* Generate form */}
      <div className="forensic-panel">
        <div className="forensic-header">Generate New Report</div>
        <div className="p-5 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="text-xs text-slate-700 font-semibold mb-1 block">Case</label>
              <select className="forensic-input w-full text-sm" value={selectedCase} onChange={e => setSelectedCase(e.target.value)}>
                {cases.length === 0 && <option>No cases available</option>}
                {cases.map(c => <option key={c.case_id} value={c.case_id}>{c.name}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs text-slate-700 font-semibold mb-1 block">Report Format</label>
              <select className="forensic-input w-full text-sm" value={format} onChange={e => setFormat(e.target.value)}>
                <option value="json">JSON — Machine Readable</option>
                <option value="pdf">PDF — Human Readable</option>
                <option value="csv">CSV — Spreadsheet</option>
              </select>
            </div>
            <div className="flex items-end">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={includeRaw}
                  onChange={e => setIncludeRaw(e.target.checked)}
                  className="rounded border-slate-300 text-blue-600"
                />
                <span className="text-sm text-slate-700">Include raw records</span>
              </label>
            </div>
          </div>
          <button
            className="forensic-btn-primary"
            onClick={handleGenerate}
            disabled={generating || cases.length === 0}
          >
            {generating ? <><Loader size={15} className="animate-spin" /> Generating...</> : <><Plus size={15} /> Generate Report</>}
          </button>
        </div>
      </div>

      {/* Report history */}
      <div className="forensic-panel">
        <div className="forensic-header">Report History ({reports.length})</div>
        {loading ? (
          <div className="p-8 text-center text-slate-500 animate-pulse text-sm">Loading...</div>
        ) : reports.length === 0 ? (
          <div className="p-12 text-center">
            <FileText size={40} className="mx-auto text-slate-300 mb-3" />
            <p className="text-slate-600 font-medium">No reports generated yet</p>
            <p className="text-slate-400 text-sm mt-1">Generate your first report above.</p>
          </div>
        ) : (
          <table className="forensic-table">
            <thead>
              <tr>
                <th>Format</th>
                <th>Report ID</th>
                <th>Case</th>
                <th>Generated</th>
                <th>Size</th>
                <th>Download</th>
              </tr>
            </thead>
            <tbody>
              {reports.map(r => (
                <tr key={r.report_id}>
                  <td>
                    <span className="text-lg">{FORMAT_ICONS[r.format] || '📄'}</span>
                    <span className="ml-2 text-xs font-bold uppercase text-slate-600">{r.format}</span>
                  </td>
                  <td className="font-mono text-xs text-slate-500">{r.report_id}</td>
                  <td className="text-slate-700 text-xs">{r.case_id}</td>
                  <td className="text-slate-500 text-xs">{new Date(r.generated_at).toLocaleString()}</td>
                  <td className="text-slate-600 text-xs">{fmtSize(r.file_size_bytes)}</td>
                  <td>
                    <a
                      href={downloadReport(r.report_id)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 text-blue-600 hover:text-blue-700 text-xs font-semibold"
                    >
                      <Download size={13} /> Download
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
