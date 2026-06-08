/* AdminNav.jsx — admin console left rail. Brand, a short nav (Insights,
   Knowledge base, and Users & roles for super admins), and the account block. */

function AdminNav({ active, onNavigate, user, isSuperAdmin, counts, onOpenSettings, onChatWorkspace, onSignOut }) {
  const items = [
    { id: 'insights', icon: 'layout-dashboard', label: 'Insights' },
    { id: 'kb', icon: 'database', label: 'Knowledge base', badge: counts.failedDocs, badgeTone: 'danger' },
  ];
  if (isSuperAdmin) items.push({ id: 'users', icon: 'users', label: 'Users & roles' });

  return (
    <nav style={{ width: 244, flex: 'none', background: 'var(--bg-void)', borderRight: '1px solid var(--border)', display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* brand */}
      <div style={{ padding: '20px 18px 16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Mark size={24} />
          <div style={{ fontFamily: 'var(--font-display)', fontWeight: 900, fontSize: 19, letterSpacing: '-0.02em', textTransform: 'uppercase', color: 'var(--fg-1)', lineHeight: 1 }}>Playbook</div>
          <span style={{ marginLeft: 'auto', fontFamily: 'var(--font-body)', fontSize: 10.5, fontWeight: 700, color: 'var(--fg-3)', letterSpacing: '0.08em', textTransform: 'uppercase' }}>Admin</span>
        </div>
      </div>

      {/* nav */}
      <div style={{ padding: '2px 12px', flex: 1, overflowY: 'auto' }}>
        {items.map(it => (
          <NavItem key={it.id} item={it} active={active === it.id} onClick={() => onNavigate(it.id)} />
        ))}
      </div>

      {/* account */}
      <AdminAccount user={user} isSuperAdmin={isSuperAdmin} onOpenSettings={onOpenSettings} onChatWorkspace={onChatWorkspace} onSignOut={onSignOut} />
    </nav>
  );
}

function NavItem({ item, active, onClick }) {
  const [hover, setHover] = React.useState(false);
  const badgeTone = item.badgeTone === 'danger' ? 'var(--danger)' : 'var(--fg-3)';
  const badgeBg = item.badgeTone === 'danger' ? 'var(--danger-bg)' : 'var(--surface-raised)';
  return (
    <div onClick={onClick} onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{ position: 'relative', display: 'flex', alignItems: 'center', gap: 11, padding: '10px 11px', borderRadius: 'var(--radius-sm)', cursor: 'pointer', marginBottom: 2,
        background: active ? 'var(--brand-soft)' : (hover ? 'var(--surface-hover)' : 'transparent'),
        color: active ? 'var(--brand)' : 'var(--fg-2)' }}>
      {active && <span style={{ position: 'absolute', left: 0, top: '50%', transform: 'translateY(-50%)', width: 3, height: 16, borderRadius: '0 2px 2px 0', background: 'var(--brand)' }} />}
      <Icon name={item.icon} size={18} style={{ flex: 'none' }} />
      <span style={{ fontFamily: 'var(--font-body)', fontWeight: active ? 600 : 500, fontSize: 13.5, flex: 1 }}>{item.label}</span>
      {item.badge != null && item.badge > 0 && (
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10.5, fontWeight: 700, color: badgeTone, background: badgeBg, borderRadius: 'var(--radius-pill)', padding: '1px 7px', minWidth: 20, textAlign: 'center' }}>{item.badge}</span>
      )}
    </div>
  );
}

function AdminAccount({ user, isSuperAdmin, onOpenSettings, onChatWorkspace, onSignOut }) {
  const [open, setOpen] = React.useState(false);
  React.useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, []);
  return (
    <div style={{ position: 'relative', padding: '10px 12px 14px', borderTop: '1px solid var(--border)' }}>
      {open && (
        <React.Fragment>
          <div onClick={() => setOpen(false)} style={{ position: 'fixed', inset: 0, zIndex: 40 }} />
          <div role="menu" style={{ position: 'absolute', left: 12, right: 12, bottom: 'calc(100% + 8px)', zIndex: 41, background: 'var(--surface-raised)', border: '1px solid var(--border-strong)', borderRadius: 'var(--radius-lg)', boxShadow: 'var(--shadow-lg)', overflow: 'hidden', animation: 'pbmenu var(--dur-med) var(--ease-out) both' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 11, padding: '13px 14px', borderBottom: '1px solid var(--border)' }}>
              <div style={{ width: 38, height: 38, flex: 'none', borderRadius: 'var(--radius-md)', background: 'var(--brand)', color: 'var(--fg-on-brand)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 15 }}>{user.initials}</div>
              <div style={{ minWidth: 0, lineHeight: 1.3 }}>
                <div style={{ fontFamily: 'var(--font-body)', fontWeight: 700, fontSize: 13.5, color: 'var(--fg-1)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{user.name}</div>
                <div style={{ fontFamily: 'var(--font-body)', fontSize: 11.5, color: 'var(--fg-3)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{user.email}</div>
              </div>
            </div>
            <div style={{ padding: 6 }}>
              <AcctMenuItem icon="settings" label="Settings" onClick={() => { setOpen(false); onOpenSettings('profile'); }} />
              <AcctMenuItem icon="message-circle" label="Chat workspace" onClick={() => { setOpen(false); onChatWorkspace(); }} />
            </div>
            <div style={{ padding: 6, borderTop: '1px solid var(--border)' }}>
              <AcctMenuItem icon="log-out" label="Sign out" danger onClick={() => { setOpen(false); onSignOut(); }} />
            </div>
          </div>
        </React.Fragment>
      )}
      <button onClick={() => setOpen(o => !o)}
        style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px', cursor: 'pointer', borderRadius: 'var(--radius-md)', border: '1px solid ' + (open ? 'var(--border-strong)' : 'transparent'), background: open ? 'var(--surface-hover)' : 'transparent', textAlign: 'left' }}
        onMouseEnter={(e) => { if (!open) e.currentTarget.style.background = 'var(--surface-hover)'; }}
        onMouseLeave={(e) => { if (!open) e.currentTarget.style.background = 'transparent'; }}>
        <div style={{ position: 'relative', flex: 'none' }}>
          <div style={{ width: 32, height: 32, borderRadius: 'var(--radius-md)', background: 'var(--brand)', color: 'var(--fg-on-brand)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 13 }}>{user.initials}</div>
          <span style={{ position: 'absolute', right: -2, bottom: -2, width: 10, height: 10, borderRadius: '50%', background: 'var(--success)', border: '2px solid var(--bg-void)' }} />
        </div>
        <div style={{ lineHeight: 1.25, minWidth: 0, flex: 1 }}>
          <div style={{ fontFamily: 'var(--font-body)', fontWeight: 600, fontSize: 13, color: 'var(--fg-1)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{user.name}</div>
          <div style={{ fontFamily: 'var(--font-body)', fontSize: 11.5, color: 'var(--fg-3)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{isSuperAdmin ? 'Super admin' : 'Department admin'}</div>
        </div>
        <Icon name="chevrons-up-down" size={16} style={{ flex: 'none', color: 'var(--fg-4)' }} />
      </button>
    </div>
  );
}

function AcctMenuItem({ icon, label, danger, onClick }) {
  const [hover, setHover] = React.useState(false);
  return (
    <button type="button" onClick={onClick} onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 11, padding: '9px 10px', border: 0, cursor: 'pointer', borderRadius: 'var(--radius-sm)', textAlign: 'left',
        background: hover ? (danger ? 'var(--danger-bg)' : 'var(--surface-hover)') : 'transparent',
        color: danger ? 'var(--danger)' : (hover ? 'var(--fg-1)' : 'var(--fg-2)'), fontFamily: 'var(--font-body)', fontWeight: 500, fontSize: 13.5 }}>
      <Icon name={icon} size={17} style={{ flex: 'none', color: danger ? 'var(--danger)' : (hover ? 'var(--brand)' : 'var(--fg-3)') }} />{label}
    </button>
  );
}

window.AdminNav = AdminNav;
