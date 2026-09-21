import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import { LayoutDashboard, FolderKanban, Database, MessageSquare, Clock, Search, FileText, Shield } from 'lucide-react';
import Dashboard from './pages/Dashboard';
import Cases from './pages/Cases';
import CaseDetail from './pages/CaseDetail';
import Evidence from './pages/Evidence';
import Conversations from './pages/Conversations';
import Timeline from './pages/Timeline';
import GlobalSearch from './pages/Search';
import Reports from './pages/Reports';
import AuditLog from './pages/AuditLog';

function Sidebar() {
  const location = useLocation();
  const navItems = [
    { name: 'Dashboard', path: '/', icon: <LayoutDashboard size={18} /> },
    { name: 'Cases', path: '/cases', icon: <FolderKanban size={18} /> },
    { name: 'Evidence', path: '/evidence', icon: <Database size={18} /> },
    { name: 'Conversations', path: '/conversations', icon: <MessageSquare size={18} /> },
    { name: 'Timeline', path: '/timeline', icon: <Clock size={18} /> },
    { name: 'Search', path: '/search', icon: <Search size={18} /> },
    { name: 'Reports', path: '/reports', icon: <FileText size={18} /> },
    { name: 'Audit Log', path: '/audit', icon: <Shield size={18} /> },
  ];

  return (
    <div className="w-64 bg-white border-r border-slate-200 flex flex-col shrink-0">
      <div className="p-4 border-b border-slate-200">
        <h1 className="text-blue-600 font-bold tracking-tighter leading-tight text-sm">
          MESSAGING ARTIFACT<br />
          <span className="text-slate-900 text-base">RECONSTRUCTOR</span>
        </h1>
        <p className="text-slate-400 text-[10px] mt-1 uppercase tracking-wider">Forensic Analysis Platform</p>
      </div>
      <nav className="flex-1 overflow-y-auto py-3">
        <ul className="space-y-0.5 px-2">
          {navItems.map((item) => (
            <li key={item.path}>
              <Link
                to={item.path}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors text-sm ${
                  location.pathname === item.path || (item.path !== '/' && location.pathname.startsWith(item.path))
                    ? 'bg-blue-50 text-blue-700 font-semibold border border-blue-100'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                }`}
              >
                {item.icon}
                {item.name}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
      <div className="p-4 border-t border-slate-200 text-xs text-slate-400">
        <p className="font-semibold text-slate-500">v1.0.0</p>
        <p>Forensic Analysis Platform</p>
        <p className="mt-1 text-[10px] leading-relaxed">For authorized use only</p>
      </div>
    </div>
  );
}

function MainLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        {children}
      </main>
    </div>
  );
}

function App() {
  return (
    <Router>
      <MainLayout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/cases" element={<Cases />} />
          <Route path="/cases/:caseId" element={<CaseDetail />} />
          <Route path="/evidence" element={<Evidence />} />
          <Route path="/conversations" element={<Conversations />} />
          <Route path="/timeline" element={<Timeline />} />
          <Route path="/search" element={<GlobalSearch />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/audit" element={<AuditLog />} />
        </Routes>
      </MainLayout>
    </Router>
  );
}

export default App;
