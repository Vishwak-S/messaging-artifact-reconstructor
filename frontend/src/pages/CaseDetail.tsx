import { useEffect, useState, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { getCase, getDatabases, getEvidenceStatus, uploadEvidence, verifyHash, autoAcquire, decryptCrypt14, getAnalysisRuns } from '../services/api';
import type { Case, ForensicDatabase } from '../types';
import { Upload, CheckCircle, XCircle, Clock, ChevronRight, RefreshCw, HardDrive, KeyRound, ShieldAlert } from 'lucide-react';

const APP_COLORS: Record<string, string> = { WhatsApp: 'text-emerald-600', Telegram: 'text-blue-600', Signal: 'text-indigo-600', Unknown: 'text-slate-500' };
const CONF_COLORS: Record<string, string> = { High: 'badge-active', Medium: 'badge-warning', Low: 'badge-deleted' };

function PipelineLog({ log }: { log: Array<{ step: string; status: string; detail: string }> }) {
  return (
    <div className="space-y-1 font-mono text-xs mt-3 bg-slate-50 border border-slate-200 rounded p-3">
      {log.map((entry, i) => (
        <div key={i} className="flex items-start gap-2">
          {entry.status === 'OK' ? <CheckCircle size={12} className="text-emerald-500 mt-0.5 shrink-0" />
            : entry.status === 'ERROR' ? <XCircle size={12} className="text-rose-500 mt-0.5 shrink-0" />
            : <Clock size={12} className="text-amber-500 mt-0.5 shrink-0" />}
          <span className="text-slate-600 w-32 shrink-0">{entry.step}</span>
          <span className="text-slate-800 truncate">{entry.detail}</span>
        </div>
      ))}
    </div>
  );
}

export default function CaseDetail() {
  const { caseId } = useParams<{ caseId: string }>();
  const [caseData, setCaseData] = useState<Case | null>(null);
  const [databases, setDatabases] = useState<ForensicDatabase[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<Record<string, { status: string; pipeline?: Array<{ step: string; status: string; detail: string }> }>>({});
  const [hashResults, setHashResults] = useState<Record<string, { match: boolean; current_hash: string }>>({});
  const [scanResult, setScanResult] = useState<{ found: boolean; count: number; message: string; scanned_paths: string[] } | null>(null);
  const [scanning, setScanning] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const keyRef = useRef<HTMLInputElement>(null);
  const [crypt14Target, setCrypt14Target] = useState<string | null>(null);
  const [decrypting, setDecrypting] = useState(false);

  const [analysisRuns, setAnalysisRuns] = useState<any[]>([]);

  const loadData = async () => {
    if (!caseId) return;
    const [c, dbs, runs] = await Promise.all([
      getCase(caseId),
      getDatabases(caseId),
      getAnalysisRuns(caseId),
    ]);
    setCaseData(c);
    setDatabases(dbs);
    setAnalysisRuns(runs);
  };

  useEffect(() => { loadData(); }, [caseId]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !caseId) return;
    setUploading(true);
    try {
      const ev = await uploadEvidence(caseId, file);
      setUploadStatus(prev => ({ ...prev, [ev.evidence_id]: { status: 'analyzing' } }));
      pollForCompletion(ev.evidence_id);
    } catch (err: any) {
      alert(err.message);
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const handleAutoAcquire = async () => {
    if (!caseId) return;
    setScanning(true);
    setScanResult(null);
    try {
      const res = await autoAcquire(caseId);
      setScanResult({
        found: res.found,
        count: res.count,
        message: res.message,
        scanned_paths: res.scanned_paths || [],
      });
      if (res.count > 0) {
        res.evidence_ids.forEach((evId: string) => {
          setUploadStatus(prev => ({ ...prev, [evId]: { status: 'analyzing' } }));
          pollForCompletion(evId);
        });
        loadData();
      }
    } catch (err: any) {
      setScanResult({ found: false, count: 0, message: `Scan error: ${err.message}`, scanned_paths: [] });
    } finally {
      setScanning(false);
    }
  };

  const pollForCompletion = (evidenceId: string) => {
    const poll = setInterval(async () => {
      const s = await getEvidenceStatus(evidenceId);
      if (s.latest_run?.status === 'completed' || s.latest_run?.status === 'error') {
        clearInterval(poll);
        setUploadStatus(prev => ({
          ...prev,
          [evidenceId]: {
            status: s.status,
            pipeline: s.latest_run?.pipeline_log || [],
          },
        }));
        loadData();
      }
    }, 2000);
  };

  const handleVerify = async (evidenceId: string) => {
    try {
      const r = await verifyHash(evidenceId);
      setHashResults(prev => ({ ...prev, [evidenceId]: { match: r.match, current_hash: r.current_hash } }));
    } catch (err: any) { alert(err.message); }
  };

  const handleKeySelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const keyFile = e.target.files?.[0];
    if (!keyFile || !crypt14Target) return;
    setDecrypting(true);
    try {
      const derived = await decryptCrypt14(crypt14Target, keyFile);
      setUploadStatus(prev => ({ ...prev, [derived.evidence_id]: { status: 'analyzing' } }));
      pollForCompletion(derived.evidence_id);
      setCrypt14Target(null);
      loadData();
    } catch (err: any) {
      alert(err.message);
    } finally {
      setDecrypting(false);
      if (keyRef.current) keyRef.current.value = '';
    }
  };

  if (!caseData) return <div className="p-8 text-slate-500 animate-pulse">Loading case...</div>;

  return (
    <div className="p-6 space-y-5">
      <input ref={keyRef} type="file" onChange={handleKeySelected} className="hidden" />
      {/* Case header */}
      <div className="forensic-panel p-5">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-blue-600 font-mono text-xs mb-1 font-semibold">{caseData.case_id}</p>
            <h2 className="text-xl font-bold text-slate-900">{caseData.name}</h2>
            <p className="text-slate-600 text-sm mt-1">{caseData.description || 'No description.'}</p>
          </div>
          <span className={`badge ${caseData.status === 'open' ? 'badge-active' : 'badge-warning'}`}>{caseData.status}</span>
        </div>
        <div className="mt-3 flex gap-6 text-xs text-slate-600 border-t border-slate-100 pt-3">
          <span>Investigator: <span className="text-slate-900 font-medium">{caseData.investigator || '—'}</span></span>
          <span>Created: <span className="text-slate-900 font-medium">{new Date(caseData.created_at).toLocaleString()}</span></span>
          <span>Databases: <span className="text-slate-900 font-medium">{databases.length}</span></span>
        </div>
      </div>

      {/* Evidence Upload */}
      {(databases.length === 0 && analysisRuns.length === 0) || showImport ? (
        <div className="forensic-panel">
          <div className="forensic-header flex justify-between items-center py-1.5">
            <span>Import Evidence</span>
            <div className="flex gap-2">
              {(databases.length > 0 || analysisRuns.length > 0) && (
                <button 
                  className="px-3 py-1 text-xs text-slate-500 hover:text-slate-800 font-medium"
                  onClick={() => setShowImport(false)}
                >
                  Cancel
                </button>
              )}
              <button 
                className="forensic-btn py-1 px-3 text-xs bg-slate-900 text-white hover:bg-slate-800 disabled:opacity-50"
                onClick={handleAutoAcquire}
                disabled={scanning || uploading}
              >
                <HardDrive size={14} /> {scanning ? 'Scanning...' : 'Scan Local PC'}
              </button>
            </div>
          </div>

          {/* Scan result panel */}
          {scanResult && (
            <div className={`mx-4 mt-3 rounded-lg border p-4 text-sm ${
              scanResult.found
                ? 'bg-emerald-50 border-emerald-300 text-emerald-900'
                : 'bg-amber-50 border-amber-300 text-amber-900'
            }`}>
              <div className="flex items-start gap-2 mb-2">
                {scanResult.found
                  ? <CheckCircle size={16} className="text-emerald-600 mt-0.5 shrink-0" />
                  : <XCircle size={16} className="text-amber-600 mt-0.5 shrink-0" />}
                <p className="font-medium">{scanResult.message}</p>
              </div>
              <details className="mt-2">
                <summary className="cursor-pointer text-xs opacity-70 hover:opacity-100 font-mono">
                  View scanned paths ({scanResult.scanned_paths.length})
                </summary>
                <ul className="mt-2 space-y-0.5">
                  {scanResult.scanned_paths.map((p, i) => (
                    <li key={i} className="font-mono text-xs opacity-80 break-all">• {p}</li>
                  ))}
                </ul>
              </details>
            </div>
          )}

          <div className="p-4 bg-slate-50/50">
            <div
              className="bg-white border-2 border-dashed border-slate-300 hover:border-blue-500 hover:bg-blue-50/30 rounded-lg p-8 text-center cursor-pointer transition-colors"
              onClick={() => fileRef.current?.click()}
            >
              <Upload size={24} className="mx-auto text-slate-400 mb-2" />
              <p className="text-slate-700 text-sm font-medium">Or manually upload an evidence file</p>
              <p className="text-slate-500 text-xs mt-1">Accepted: valid SQLite, WhatsApp .crypt14, or Telegram Desktop export JSON</p>
              {uploading && <p className="text-blue-600 text-xs mt-3 animate-pulse font-semibold">Uploading and starting analysis...</p>}
            </div>
            <input ref={fileRef} type="file" accept=".db,.sqlite,.sqlite3,.db3,.crypt14,.json" onChange={handleFileUpload} className="hidden" />
          </div>
        </div>
      ) : (
        <div className="flex justify-end">
          <button 
            className="forensic-btn py-1.5 px-4 text-sm bg-blue-600 text-white hover:bg-blue-700"
            onClick={() => setShowImport(true)}
          >
            <Upload size={16} /> Add More Evidence
          </button>
        </div>
      )}

      {/* Analysis status cards */}
      {Object.entries(uploadStatus).map(([evId, info]) => (
        <div key={evId} className="forensic-panel p-4 border-l-4 border-l-blue-500 bg-blue-50/30">
          <div className="flex items-center gap-2 mb-2">
            <RefreshCw size={14} className="text-blue-600 animate-spin" />
            <span className="text-blue-800 text-xs font-semibold uppercase tracking-wider">Analysis Pipeline: {evId}</span>
          </div>
          {info.pipeline && <PipelineLog log={info.pipeline} />}
        </div>
      ))}

      {/* Databases */}
      <div className="forensic-panel">
        <div className="forensic-header">Detected Databases ({databases.length})</div>
        {databases.length === 0
          ? <div className="p-8 text-center text-slate-500 text-sm">No databases analysed yet. Upload a .db file above.</div>
          : (
            <table className="forensic-table">
              <thead>
                <tr>
                  <th>Database</th>
                  <th>Application</th>
                  <th>App Match Confidence</th>
                  <th>Tables</th>
                  <th>Records</th>
                  <th>SQLite</th>
                  <th>WAL</th>
                  <th>Hash / encrypted backup</th>
                </tr>
              </thead>
              <tbody>
                {databases.map(db => (
                  <tr key={db.db_id}>
                    <td className="font-mono text-xs text-slate-600 font-semibold">{db.db_filename}</td>
                    <td className={`font-semibold text-xs ${APP_COLORS[db.app_detected || 'Unknown']}`}>{db.app_detected || 'Unknown'}</td>
                    <td><span className={`badge ${CONF_COLORS[db.detection_confidence || ''] || 'badge-warning'}`}>{db.detection_confidence || 'N/A'}</span></td>
                    <td className="text-slate-700">{db.table_count ?? '—'}</td>
                    <td className="text-slate-700 font-mono text-xs">{db.total_records?.toLocaleString() ?? '—'}</td>
                    <td>{db.sqlite_valid ? <CheckCircle size={14} className="text-emerald-500" /> : <XCircle size={14} className="text-rose-500" />}</td>
                    <td>{db.wal_detected ? <span className="badge badge-warning">YES</span> : <span className="text-slate-400 text-xs">NO</span>}</td>
                    <td>
                      <button
                        className="text-blue-600 hover:text-blue-700 text-xs underline font-medium"
                        onClick={() => handleVerify(db.evidence_id)}
                      >
                        Verify
                      </button>
                      {hashResults[db.evidence_id] && (
                        <span className={`ml-2 badge ${hashResults[db.evidence_id].match ? 'badge-active' : 'badge-deleted'}`}>
                          {hashResults[db.evidence_id].match ? '✓ MATCH' : '✗ MISMATCH'}
                        </span>
                      )}
                      {db.db_filename.toLowerCase().endsWith('.crypt14') && (
                        <button
                          className="ml-3 inline-flex items-center gap-1 text-violet-700 hover:text-violet-900 text-xs underline font-medium disabled:opacity-50"
                          disabled={decrypting}
                          onClick={() => { setCrypt14Target(db.evidence_id); keyRef.current?.click(); }}
                        >
                          <KeyRound size={13} /> {decrypting && crypt14Target === db.evidence_id ? 'Decrypting…' : 'Provide key & decrypt'}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </div>

      {databases.some(db => db.db_filename.toLowerCase().endsWith('.crypt14')) && (
        <div className="rounded-lg border border-violet-200 bg-violet-50 p-4 text-sm text-violet-950">
          <div className="flex gap-2">
            <ShieldAlert size={18} className="mt-0.5 shrink-0 text-violet-700" />
            <div>
              <p className="font-semibold">Encrypted WhatsApp backup detected</p>
              <p className="mt-1 text-violet-900">A <code>.crypt14</code> file is encrypted and cannot yield trustworthy deleted-message results until it is decrypted. Choose “Provide key &amp; decrypt” and select an authorized matching key file. The key is used in memory only and is never saved.</p>
              <p className="mt-2 text-xs text-violet-800">This app does not retrieve keys from phones, WhatsApp accounts, or protected device storage. On older Android versions the key is commonly under <code>/data/data/com.whatsapp/files/key</code>, which normal file browsers cannot access. Obtain it only through the device owner or an authorized mobile-forensics process.</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
