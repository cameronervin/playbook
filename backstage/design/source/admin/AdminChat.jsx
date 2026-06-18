/* AdminChat.jsx — analytics chat side panel. Asks natural-language questions
   about analytics + insights, cites the metric/insight/query behind each
   answer, never reveals athlete identity, and declines out-of-scope or
   action requests. Session history persists across open/close. */

const REF_META = {
  metric: { icon: 'bar-chart-2', label: 'Metric' },
  dashboard_insight: { icon: 'sparkles', label: 'Insight' },
  query: { icon: 'message-square', label: 'Query' },
};

function AdminChat({ open, messages, onSend, onClose, busy }) {
  const [draft, setDraft] = React.useState('');
  const scrollRef = React.useRef(null);
  React.useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, busy]);

  const submit = (text) => { const v = (text != null ? text : draft).trim(); if (!v || busy) return; onSend(v); setDraft(''); };
  if (!open) return null;

  return (
    <aside style={{ width: 384, flex: 'none', borderLeft: '1px solid var(--border-strong)', background: 'var(--bg-page)', display: 'flex', flexDirection: 'column', height: '100%', animation: 'pbpanel var(--dur-med) var(--ease-out) both' }}>
      {/* header */}
      <div style={{ height: 60, flex: 'none', display: 'flex', alignItems: 'center', gap: 11, padding: '0 16px', borderBottom: '1px solid var(--border)' }}>
        <div style={{ position: 'relative', flex: 'none' }}>
          <AgentAvatar size={32} icon="zap" />
        </div>
        <div style={{ minWidth: 0, lineHeight: 1.25 }}>
          <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 14.5, color: 'var(--fg-1)' }}>Analytics AI Agent</div>
        </div>
        <div style={{ marginLeft: 'auto' }}><IconBtn name="x" onClick={onClose} /></div>
      </div>

      {/* thread */}
      <div ref={scrollRef} style={{ flex: 1, overflowY: 'auto', padding: '16px', display: 'flex', flexDirection: 'column', gap: 16 }}>
        {messages.length === 0 ? (
          <div style={{ marginTop: 4 }}>
            <p style={{ margin: '0 0 18px', fontFamily: 'var(--font-body)', fontSize: 13.5, lineHeight: 1.6, color: 'var(--fg-2)' }}>Ask an AI agent about query patterns, support gaps, risk trends, and more.</p>
            <SectionLabel style={{ marginBottom: 10, paddingLeft: 2 }}>Try asking</SectionLabel>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {ADMIN_CHAT_SUGGESTIONS.map((s, i) => (
                <button key={i} onClick={() => submit(s)}
                  style={{ display: 'flex', alignItems: 'center', gap: 10, textAlign: 'left', padding: '11px 13px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-strong)', background: 'var(--surface)', color: 'var(--fg-1)', cursor: 'pointer', fontFamily: 'var(--font-body)', fontSize: 13, transition: 'background var(--dur-fast), border-color var(--dur-fast)' }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--surface-raised)'; e.currentTarget.style.borderColor = 'var(--border-brand)'; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = 'var(--surface)'; e.currentTarget.style.borderColor = 'var(--border-strong)'; }}>
                  <Icon name="corner-down-right" size={15} style={{ color: 'var(--brand)', flex: 'none' }} />
                  <span style={{ flex: 1 }}>{s}</span>
                </button>
              ))}
            </div>
          </div>
        ) : messages.map((m, i) => <ChatMsg key={i} msg={m} />)}
        {busy && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 11 }}>
            <span style={{ display: 'inline-flex' }}><Mark size={26} /></span>
            <span className="pb-think" style={{ fontFamily: 'var(--font-body)', fontSize: 13, color: 'var(--fg-3)' }}>Thinking…</span>
          </div>
        )}
      </div>

      {/* composer */}
      <div style={{ flex: 'none', padding: '12px 16px 16px', borderTop: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8, padding: '8px 8px 8px 13px', background: 'var(--surface)', border: '1px solid var(--border-strong)', borderRadius: 'var(--radius-lg)' }}>
          <textarea value={draft} onChange={(e) => setDraft(e.target.value)} rows={1} placeholder="Ask about the analytics…"
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); } }}
            style={{ flex: 1, resize: 'none', border: 0, outline: 'none', background: 'transparent', color: 'var(--fg-1)', fontFamily: 'var(--font-body)', fontSize: 13.5, lineHeight: 1.5, maxHeight: 120, padding: '4px 0' }} />
          <button onClick={() => submit()} disabled={!draft.trim() || busy}
            style={{ width: 34, height: 34, flex: 'none', borderRadius: 'var(--radius-md)', border: 0, cursor: draft.trim() && !busy ? 'pointer' : 'not-allowed', background: draft.trim() && !busy ? 'var(--brand)' : 'var(--surface-hover)', color: draft.trim() && !busy ? 'var(--fg-on-brand)' : 'var(--fg-4)', display: 'flex', alignItems: 'center', justifyContent: 'center', transition: 'background var(--dur-fast)' }}>
            <Icon name="send" size={16} />
          </button>
        </div>
        <div style={{ marginTop: 8, fontFamily: 'var(--font-body)', fontSize: 11, color: 'var(--fg-4)', textAlign: 'center' }}>Responses are AI generated. Review to confirm accuracy.</div>
      </div>
    </aside>
  );
}

function ChatMsg({ msg }) {
  if (msg.role === 'user') {
    return (
      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <div style={{ maxWidth: '86%', padding: '10px 14px', borderRadius: 'var(--radius-lg) var(--radius-lg) var(--radius-xs) var(--radius-lg)', background: 'var(--brand-soft)', border: '1px solid var(--border-brand)', fontFamily: 'var(--font-body)', fontSize: 13.5, lineHeight: 1.5, color: 'var(--fg-1)', textWrap: 'pretty' }}>{msg.text}</div>
      </div>
    );
  }
  const declined = msg.answer_type === 'declined';
  const stream = useStreamText(msg.answer || '', !!msg.stream);
  return (
    <div style={{ display: 'flex', gap: 11 }}>
      <AgentAvatar size={30} icon="zap" />
      <div style={{ flex: 1, minWidth: 0 }}>
        <p className={stream.done ? null : 'pb-streaming'} style={{ margin: 0, fontFamily: 'var(--font-body)', fontSize: 13.5, lineHeight: 1.6, color: declined ? 'var(--fg-3)' : 'var(--fg-2)', textWrap: 'pretty' }}>{stream.shown}</p>
        {stream.done && msg.refs && msg.refs.length > 0 && <SourcesDisclosure refs={msg.refs} />}
      </div>
    </div>
  );
}

// Word-by-word reveal of a plain-text answer.
function useStreamText(text, enabled) {
  const [shown, setShown] = React.useState(enabled ? '' : text);
  const [done, setDone] = React.useState(!enabled);
  React.useEffect(() => {
    const reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (!enabled || reduce) { setShown(text); setDone(true); return; }
    const parts = text.match(/\s+|\S+/g) || [];
    let i = 0, acc = '';
    setShown(''); setDone(false);
    const id = setInterval(() => {
      while (i < parts.length) { const p = parts[i]; acc += p; i++; if (!/^\s+$/.test(p)) break; }
      while (i < parts.length && /^\s+$/.test(parts[i])) { acc += parts[i]; i++; }
      setShown(acc);
      if (i >= parts.length) { clearInterval(id); setDone(true); }
    }, 26);
    return () => clearInterval(id);
  }, [text, enabled]);
  return { shown, done };
}

function SourcesDisclosure({ refs }) {
  const [open, setOpen] = React.useState(false);
  return (
    <div style={{ marginTop: 10 }}>
      <button onClick={() => setOpen((o) => !o)}
        style={{ display: 'inline-flex', alignItems: 'center', gap: 7, padding: '4px 9px 4px 8px', borderRadius: 'var(--radius-pill)', border: '1px solid var(--border-strong)', background: open ? 'var(--surface-raised)' : 'var(--surface)', color: 'var(--fg-2)', cursor: 'pointer', fontFamily: 'var(--font-body)', fontSize: 11.5, fontWeight: 600, transition: 'background var(--dur-fast), border-color var(--dur-fast)' }}
        onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'var(--border-brand)'; }}
        onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border-strong)'; }}>
        <Icon name="file-text" size={13} style={{ color: 'var(--brand)', flex: 'none' }} />
        <span>Sources</span>
        <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--fg-3)' }}>{refs.length}</span>
        <Icon name="chevron-down" size={13} style={{ color: 'var(--fg-3)', flex: 'none', transform: open ? 'rotate(180deg)' : 'none', transition: 'transform var(--dur-fast)' }} />
      </button>
      {open && (
        <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {refs.map((r, i) => {
            const meta = REF_META[r.type] || { icon: 'circle-dot', label: r.type };
            return (
              <span key={i} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontFamily: 'var(--font-body)', fontSize: 11, fontWeight: 600, color: 'var(--fg-2)', background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-pill)', padding: '3px 9px 3px 7px' }}>
                <Icon name={meta.icon} size={12} style={{ color: 'var(--brand)' }} />
                <span style={{ color: 'var(--fg-3)' }}>{meta.label}</span>
                <span style={{ fontFamily: 'var(--font-mono)' }}>{r.id}</span>
              </span>
            );
          })}
        </div>
      )}
    </div>
  );
}

window.AdminChat = AdminChat;
