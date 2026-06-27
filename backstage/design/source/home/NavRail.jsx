/* NavRail.jsx — left rail: brand, new chat, searchable conversation history,
   footer nav, and the account block that opens the profile menu. */

function NavRail({ conversations, activeConvId, view, user, onNewChat, onSelectConv, onKnowledge, onOpenSettings, onSignOut }) {
  const [query, setQuery] = React.useState('');
  const [menuOpen, setMenuOpen] = React.useState(false);
  const isAdmin = /admin/i.test(user.role || '');

  const q = query.trim().toLowerCase();
  const filtered = q ? conversations.filter(c => c.title.toLowerCase().includes(q)) : conversations;
  const groups = [];
  filtered.forEach(c => { if (!groups.includes(c.group)) groups.push(c.group); });

  return (
    <nav style={{ width: 264, flex: 'none', background: 'var(--bg-void)', borderRight: '1px solid var(--border)', display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* brand */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '18px 18px 12px' }}>
        <Mark size={26} />
        <div style={{ fontFamily: 'var(--font-display)', fontWeight: 900, fontSize: 20, letterSpacing: '-0.02em', textTransform: 'uppercase', color: 'var(--fg-1)', lineHeight: 1 }}>Playbook</div>
      </div>

      {/* new chat */}
      <div style={{ padding: '4px 12px 8px' }}>
        <NewChatBtn onClick={onNewChat} />
      </div>

      {/* search */}
      <div style={{ padding: '0 12px 6px' }}>
        <SearchBox value={query} onChange={setQuery} />
      </div>

      {/* history */}
      <div style={{ padding: '4px 12px', flex: 1, overflowY: 'auto' }}>
        {groups.length === 0 ? (
          <div style={{ padding: '18px 11px', fontFamily: 'var(--font-body)', fontSize: 13, color: 'var(--fg-4)' }}>No matching chats.</div>
        ) : groups.map(g => (
          <React.Fragment key={g}>
            <div style={{ padding: '12px 11px 6px', fontFamily: 'var(--font-body)', fontSize: 11.5, fontWeight: 600, color: 'var(--fg-3)', letterSpacing: '0.02em' }}>{g}</div>
            {filtered.filter(c => c.group === g).map(c => (
              <ConvRow key={c.id} conv={c} active={view === 'chat' && c.id === activeConvId} onClick={() => onSelectConv(c.id)} />
            ))}
          </React.Fragment>
        ))}
      </div>

      {/* account block — opens profile menu (settings, knowledge base, sign out live here) */}
      <div style={{ position: 'relative', padding: '10px 12px 14px', borderTop: '1px solid var(--border)' }}>
        {menuOpen && (
          <ProfileMenu user={user} isAdmin={isAdmin} onClose={() => setMenuOpen(false)}
            onOpenSettings={onOpenSettings} onKnowledge={onKnowledge} onSignOut={onSignOut} />
        )}
        <AccountButton user={user} open={menuOpen} onClick={() => setMenuOpen(o => !o)} />
      </div>
    </nav>
  );
}

function NewChatBtn({ onClick }) {
  const [hover, setHover] = React.useState(false);
  return (
    <button onClick={onClick} onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 9, padding: '10px 12px', cursor: 'pointer',
        borderRadius: 'var(--radius-md)', border: '1px solid var(--border-strong)',
        background: hover ? 'var(--surface-hover)' : 'transparent', color: 'var(--fg-1)',
        fontFamily: 'var(--font-body)', fontWeight: 600, fontSize: 14 }}>
      <Icon name="plus" size={17} style={{ color: 'var(--brand)' }} />
      <span style={{ flex: 1, textAlign: 'left' }}>New chat</span>
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10.5, color: 'var(--fg-4)' }}>⌘N</span>
    </button>
  );
}

function SearchBox({ value, onChange }) {
  const [focus, setFocus] = React.useState(false);
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '0 10px', height: 34,
      background: 'var(--surface)', borderRadius: 'var(--radius-md)',
      border: '1px solid ' + (focus ? 'var(--border-brand)' : 'var(--border)'),
      boxShadow: focus ? 'var(--shadow-focus)' : 'none', transition: 'border-color var(--dur-fast), box-shadow var(--dur-fast)' }}>
      <Icon name="search" size={15} style={{ color: 'var(--fg-4)', flex: 'none' }} />
      <input value={value} onChange={(e) => onChange(e.target.value)} placeholder="Search chats"
        onFocus={() => setFocus(true)} onBlur={() => setFocus(false)}
        style={{ flex: 1, minWidth: 0, border: 0, outline: 'none', background: 'transparent', color: 'var(--fg-1)', fontFamily: 'var(--font-body)', fontSize: 13 }} />
      {value && <button onClick={() => onChange('')} style={{ border: 0, background: 'transparent', cursor: 'pointer', color: 'var(--fg-4)', display: 'flex', padding: 0 }}><Icon name="x" size={14} /></button>}
    </div>
  );
}

function ConvRow({ conv, active, onClick }) {
  const [hover, setHover] = React.useState(false);
  return (
    <div onClick={onClick} onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{ position: 'relative', display: 'flex', alignItems: 'center', padding: '8px 11px', borderRadius: 'var(--radius-sm)', cursor: 'pointer', marginBottom: 1,
        background: active ? 'var(--brand-soft)' : (hover ? 'var(--surface-hover)' : 'transparent'),
        color: active ? 'var(--brand)' : 'var(--fg-2)' }}>
      {active && <span style={{ position: 'absolute', left: 0, top: '50%', transform: 'translateY(-50%)', width: 3, height: 15, borderRadius: '0 2px 2px 0', background: 'var(--brand)' }} />}
      <span style={{ fontFamily: 'var(--font-body)', fontWeight: active ? 600 : 500, fontSize: 13.5, flex: 1, minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{conv.title}</span>
    </div>
  );
}

function RailItem({ icon, label, active, onClick }) {
  const [hover, setHover] = React.useState(false);
  return (
    <div onClick={onClick} onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{ display: 'flex', alignItems: 'center', gap: 11, padding: '9px 11px', borderRadius: 'var(--radius-sm)', cursor: 'pointer', marginBottom: 2,
        background: active ? 'var(--brand-soft)' : (hover ? 'var(--surface-hover)' : 'transparent'),
        color: active ? 'var(--brand)' : 'var(--fg-2)' }}>
      <Icon name={icon} size={18} />
      <span style={{ fontFamily: 'var(--font-body)', fontWeight: active ? 600 : 500, fontSize: 14, flex: 1 }}>{label}</span>
    </div>
  );
}

function AccountButton({ user, open, onClick }) {
  const [hover, setHover] = React.useState(false);
  return (
    <button onClick={onClick} onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px', cursor: 'pointer',
        borderRadius: 'var(--radius-md)', border: '1px solid ' + (open ? 'var(--border-strong)' : 'transparent'),
        background: (open || hover) ? 'var(--surface-hover)' : 'transparent', textAlign: 'left' }}>
      <div style={{ position: 'relative', flex: 'none' }}>
        <div style={{ width: 32, height: 32, borderRadius: 'var(--radius-md)', background: 'var(--brand)', color: 'var(--fg-on-brand)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 13 }}>{user.initials}</div>
        <span style={{ position: 'absolute', right: -2, bottom: -2, width: 10, height: 10, borderRadius: '50%', background: 'var(--success)', border: '2px solid var(--bg-void)' }} />
      </div>
      <div style={{ lineHeight: 1.25, minWidth: 0, flex: 1 }}>
        <div style={{ fontFamily: 'var(--font-body)', fontWeight: 600, fontSize: 13, color: 'var(--fg-1)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{user.name}</div>
        <div style={{ fontFamily: 'var(--font-body)', fontSize: 11.5, color: 'var(--fg-3)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{user.org}</div>
      </div>
      <Icon name="chevrons-up-down" size={16} style={{ flex: 'none', color: 'var(--fg-4)' }} />
    </button>
  );
}

window.NavRail = NavRail;
