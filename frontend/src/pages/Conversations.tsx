import { useEffect, useState } from 'react';
import { getConversations, getConversationMessages, getCases } from '../services/api';
import type { Conversation, Message, Case } from '../types';
import { MessageSquare, Users, User, Trash2, ChevronRight } from 'lucide-react';

const APP_BADGE: Record<string, string> = {
  WhatsApp: 'bg-emerald-100 text-emerald-700 border-emerald-200',
  Telegram: 'bg-blue-100 text-blue-700 border-blue-200',
  Signal: 'bg-indigo-100 text-indigo-700 border-indigo-200',
};

function MessageBubble({ msg }: { msg: Message }) {
  const isSent = msg.direction === 'sent';
  const isDeleted = msg.evidence_status === 'DELETED' || msg.evidence_status === 'DELETED_RECOVERED';

  return (
    <div className={`flex ${isSent ? 'justify-end' : 'justify-start'} mb-2`}>
      <div className={`max-w-[70%] rounded-2xl px-4 py-2 text-sm shadow-sm border
        ${isSent
          ? 'bg-slate-900 text-white border-slate-800 rounded-br-sm'
          : 'bg-white text-slate-900 border-slate-200 rounded-bl-sm'}
        ${isDeleted ? 'opacity-60 border-dashed border-rose-300 bg-rose-50 text-rose-900' : ''}`}>
        {!isSent && <p className="text-xs font-semibold mb-0.5 text-slate-500">{msg.sender || 'Unknown'}</p>}
        {isDeleted && (
          <p className="flex items-center gap-1 text-rose-500 text-xs font-semibold mb-1">
            <Trash2 size={11} /> DELETED MESSAGE
          </p>
        )}
        <p className={isDeleted ? 'text-rose-800 italic' : ''}>{msg.message_text || <span className="text-slate-400 italic">[no text]</span>}</p>
        {msg.has_attachment && (
          <p className="text-xs mt-1 text-slate-400">📎 {msg.attachment_name || 'Attachment'}</p>
        )}
        <p className={`text-[10px] mt-1 text-right ${isSent ? 'text-slate-400' : 'text-slate-400'}`}>
          {msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—'}
        </p>
      </div>
    </div>
  );
}

export default function Conversations() {
  const [cases, setCases] = useState<Case[]>([]);
  const [selectedCase, setSelectedCase] = useState('');
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedConv, setSelectedConv] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loadingConvs, setLoadingConvs] = useState(false);
  const [loadingMsgs, setLoadingMsgs] = useState(false);

  useEffect(() => {
    getCases().then(c => {
      setCases(c);
      if (c.length > 0) setSelectedCase(c[0].case_id);
    });
  }, []);

  useEffect(() => {
    if (!selectedCase) return;
    setLoadingConvs(true);
    setSelectedConv(null);
    setMessages([]);
    getConversations(selectedCase)
      .then(setConversations)
      .finally(() => setLoadingConvs(false));
  }, [selectedCase]);

  const loadMessages = async (conv: Conversation) => {
    setSelectedConv(conv);
    setLoadingMsgs(true);
    try {
      const msgs = await getConversationMessages(conv.conv_id, 1, 100);
      setMessages(msgs);
    } finally {
      setLoadingMsgs(false);
    }
  };

  const deletedCount = messages.filter(m => m.evidence_status === 'DELETED' || m.evidence_status === 'DELETED_RECOVERED').length;

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Conversation Reconstruction</h2>
          <p className="text-slate-500 text-xs mt-0.5">Recovered conversations from extracted databases</p>
        </div>
        <select
          className="forensic-input text-sm"
          value={selectedCase}
          onChange={e => setSelectedCase(e.target.value)}
        >
          {cases.length === 0 && <option>No cases found</option>}
          {cases.map(c => <option key={c.case_id} value={c.case_id}>{c.name}</option>)}
        </select>
      </div>

      {cases.length === 0 ? (
        <div className="forensic-panel p-12 text-center">
          <MessageSquare size={40} className="mx-auto text-slate-300 mb-3" />
          <p className="text-slate-600 font-medium">No cases found</p>
          <p className="text-slate-400 text-sm mt-1">Create a case and import evidence first.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 h-[calc(100vh-160px)]">
          {/* Conversation list */}
          <div className="lg:col-span-1 forensic-panel flex flex-col overflow-hidden">
            <div className="forensic-header">{loadingConvs ? 'Loading...' : `${conversations.length} Conversations`}</div>
            <div className="flex-1 overflow-y-auto divide-y divide-slate-100">
              {conversations.length === 0 && !loadingConvs && (
                <div className="p-6 text-center text-slate-400 text-sm">
                  No conversations found. Import a database file in your case.
                </div>
              )}
              {conversations.map(conv => (
                <div
                  key={conv.conv_id}
                  className={`px-3 py-3 cursor-pointer hover:bg-blue-50 transition-colors ${selectedConv?.conv_id === conv.conv_id ? 'bg-blue-50 border-l-2 border-l-blue-500' : ''}`}
                  onClick={() => loadMessages(conv)}
                >
                  <div className="flex items-center gap-2 mb-1">
                    {conv.is_group ? <Users size={12} className="text-slate-400 shrink-0" /> : <User size={12} className="text-slate-400 shrink-0" />}
                    <p className="text-slate-800 font-medium text-sm truncate">{conv.display_name || conv.group_name || conv.conv_id}</p>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className={`text-[10px] px-1.5 py-0.5 rounded border font-semibold ${APP_BADGE[conv.application || ''] || 'bg-slate-100 text-slate-600 border-slate-200'}`}>
                      {conv.application || '?'}
                    </span>
                    <span className="text-slate-400 text-xs">{conv.message_count} msgs</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Messages panel */}
          <div className="lg:col-span-3 forensic-panel flex flex-col overflow-hidden">
            {!selectedConv ? (
              <div className="flex-1 flex items-center justify-center text-slate-400">
                <div className="text-center">
                  <MessageSquare size={36} className="mx-auto mb-3 text-slate-300" />
                  <p className="font-medium">Select a conversation</p>
                </div>
              </div>
            ) : (
              <>
                {/* Chat header */}
                <div className="forensic-header flex items-center gap-3 justify-between">
                  <div className="flex items-center gap-2">
                    {selectedConv.is_group ? <Users size={14} /> : <User size={14} />}
                    <span>{selectedConv.display_name || selectedConv.group_name || selectedConv.conv_id}</span>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded border font-semibold ${APP_BADGE[selectedConv.application || ''] || 'bg-slate-100 text-slate-600 border-slate-200'}`}>
                      {selectedConv.application}
                    </span>
                  </div>
                  {deletedCount > 0 && (
                    <span className="flex items-center gap-1 text-xs text-rose-600 font-semibold bg-rose-50 border border-rose-200 px-2 py-0.5 rounded">
                      <Trash2 size={11} /> {deletedCount} Deleted Found
                    </span>
                  )}
                </div>
                {/* Messages */}
                <div className="flex-1 overflow-y-auto p-4 bg-slate-50">
                  {loadingMsgs ? (
                    <div className="text-slate-400 text-sm animate-pulse text-center pt-12">Loading messages...</div>
                  ) : messages.length === 0 ? (
                    <div className="text-slate-400 text-sm text-center pt-12">No messages found in this conversation.</div>
                  ) : (
                    messages.map(msg => <MessageBubble key={msg.message_id} msg={msg} />)
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
