/* ProfileMenu.jsx — account popover that rises from the nav-rail user block.
   The single entry point to edit profile, open settings, and sign out. */

function ProfileMenu({ user, isAdmin, onClose, onOpenSettings, onKnowledge, onSignOut }) {
  const ref = React.useRef(null);
  React.useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <React.Fragment>
      <div onClick={onClose}
        style={{ position: 'fixed', inset: 0, zIndex: 40 }} />
      <div ref={ref} role="menu"
        style={{
          position: 'absolute', left: 12, right: 12, bottom: 'calc(100% + 8px)', zIndex: 41,
          background: 'var(--surface-raised)', border: '1px solid var(--border-strong)',
          borderRadius: 'var(--radius-lg)', boxShadow: 'var(--shadow-lg)', overflow: 'hidden',
          animation: 'pbmenu var(--dur-med) var(--ease-out) both',
        }}>
        {/* identity header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 11, padding: '14px 14px 13px', borderBottom: '1px solid var(--border)' }}>
          <div style={{ position: 'relative', flex: 'none' }}>
            <div style={{ width: 40, height: 40, borderRadius: 'var(--radius-md)', background: 'var(--brand)', color: 'var(--fg-on-brand)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 16 }}>{user.initials}</div>
            <span style={{ position: 'absolute', right: -2, bottom: -2, width: 11, height: 11, borderRadius: '50%', background: 'var(--success)', border: '2px solid var(--surface-raised)' }} />
          </div>
          <div style={{ minWidth: 0, lineHeight: 1.3 }}>
            <div style={{ fontFamily: 'var(--font-body)', fontWeight: 700, fontSize: 14, color: 'var(--fg-1)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{user.name}</div>
            <div style={{ fontFamily: 'var(--font-body)', fontSize: 12, color: 'var(--fg-3)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{user.email}</div>
          </div>
        </div>
        <div style={{ padding: '7px 14px 9px', borderBottom: '1px solid var(--border)' }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7, background: 'var(--brand-soft)', color: 'var(--brand)', fontFamily: 'var(--font-body)', fontWeight: 600, fontSize: 11.5, padding: '4px 9px', borderRadius: 'var(--radius-pill)' }}>
            <Icon name="shield" size={13} />{user.role}
          </span>
        </div>

        {/* actions */}
        <div style={{ padding: 6 }}>
          <MenuItem icon="settings" label="Settings"
            onClick={() => { onClose(); onOpenSettings('profile'); }} />
          {isAdmin && (
            <MenuItem icon="layout-dashboard" label="Admin dashboard"
              onClick={() => { onClose(); onKnowledge(); }} />
          )}
        </div>
        <div style={{ padding: 6, borderTop: '1px solid var(--border)' }}>
          <MenuItem icon="log-out" label="Sign out" danger
            onClick={() => { onClose(); onSignOut(); }} />
        </div>
      </div>
    </React.Fragment>
  );
}

function MenuItem({ icon, label, danger, onClick }) {
  const [hover, setHover] = React.useState(false);
  return (
    <button type="button" role="menuitem" onClick={onClick}
      onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{
        width: '100%', display: 'flex', alignItems: 'center', gap: 11, padding: '9px 10px',
        border: 0, cursor: 'pointer', borderRadius: 'var(--radius-sm)', textAlign: 'left',
        background: hover ? (danger ? 'var(--danger-bg)' : 'var(--surface-hover)') : 'transparent',
        color: danger ? 'var(--danger)' : (hover ? 'var(--fg-1)' : 'var(--fg-2)'),
        fontFamily: 'var(--font-body)', fontWeight: 500, fontSize: 13.5,
      }}>
      <Icon name={icon} size={17} style={{ flex: 'none', color: danger ? 'var(--danger)' : (hover ? 'var(--brand)' : 'var(--fg-3)') }} />
      {label}
    </button>
  );
}

window.ProfileMenu = ProfileMenu;
