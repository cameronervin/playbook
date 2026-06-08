/* SettingsModal.jsx — centered overlay card (echoes the Login card system:
   raised surface, strong hairline, radius-lg, low warm shadow). Left sub-nav,
   scrollable content, sticky save bar. Appearance reuses the Login bg fields. */

const SETTINGS_NAV = [
  { id: 'profile', icon: 'user', label: 'Profile' },
  { id: 'security', icon: 'shield-check', label: 'Security & SSO' },
];

function SettingsModal({ section, onSection, settings, onChange, onClose }) {
  const [dirty, setDirty] = React.useState(false);
  React.useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  const patch = (group, key, val) => { onChange(group, key, val); setDirty(true); };
  const active = SETTINGS_NAV.find(s => s.id === section) || SETTINGS_NAV[0];
  const showSave = section === 'profile';

  return (
    <div onMouseDown={onClose}
      style={{ position: 'fixed', inset: 0, zIndex: 60, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24,
        background: 'rgba(8,7,5,0.62)', backdropFilter: 'blur(3px)', WebkitBackdropFilter: 'blur(3px)', animation: 'pbfade var(--dur-med) var(--ease-out) both' }}>
      <div onMouseDown={(e) => e.stopPropagation()} role="dialog" aria-modal="true"
        style={{ width: 'min(880px, 100%)', height: 'min(86vh, 660px)', display: 'flex',
          background: 'var(--surface-raised)', border: '1px solid var(--border-strong)', borderRadius: 'var(--radius-lg)',
          boxShadow: 'var(--shadow-lg)', overflow: 'hidden', animation: 'pbrise var(--dur-med) var(--ease-out) both' }}>

        {/* sub-nav */}
        <div style={{ width: 218, flex: 'none', background: 'var(--bg-page)', borderRight: '1px solid var(--border)', display: 'flex', flexDirection: 'column', padding: '18px 12px' }}>
          <div style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 17, color: 'var(--fg-1)', padding: '4px 10px 14px', letterSpacing: '-0.01em' }}>Settings</div>
          {SETTINGS_NAV.map(s => (
            <SettingsTab key={s.id} item={s} active={s.id === section} onClick={() => onSection(s.id)} />
          ))}
        </div>

        {/* content */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
          <div style={{ height: 60, flex: 'none', display: 'flex', alignItems: 'center', padding: '0 22px', borderBottom: '1px solid var(--border)' }}>
            <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 16, color: 'var(--fg-1)' }}>{active.label}</div>
            <button onClick={onClose} style={{ marginLeft: 'auto', width: 34, height: 34, borderRadius: 'var(--radius-sm)', border: 0, cursor: 'pointer', background: 'transparent', color: 'var(--fg-3)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
              onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--surface-hover)'; e.currentTarget.style.color = 'var(--fg-1)'; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--fg-3)'; }}>
              <Icon name="x" size={18} />
            </button>
          </div>

          <div style={{ flex: 1, overflowY: 'auto', padding: '22px 24px 26px' }}>
            {section === 'profile' && <ProfilePane s={settings.profile} patch={(k, v) => patch('profile', k, v)} />}
            {section === 'security' && <SecurityPane user={settings.profile} />}
          </div>

          {showSave && (
            <div style={{ flex: 'none', display: 'flex', alignItems: 'center', gap: 10, padding: '12px 22px', borderTop: '1px solid var(--border)', background: 'var(--surface)' }}>
              <div style={{ fontFamily: 'var(--font-body)', fontSize: 12.5, color: dirty ? 'var(--fg-2)' : 'var(--fg-4)', display: 'flex', alignItems: 'center', gap: 7 }}>
                {dirty ? <React.Fragment><Pulse color="var(--warning)" size={6} /> Unsaved changes</React.Fragment> : 'All changes saved'}
              </div>
              <div style={{ marginLeft: 'auto', display: 'flex', gap: 9 }}>
                <PBButton variant="secondary" size="sm" onClick={onClose}>Cancel</PBButton>
                <PBButton variant="primary" size="sm" icon="check" onClick={() => { setDirty(false); }}>Save changes</PBButton>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function SettingsTab({ item, active, onClick }) {
  const [hover, setHover] = React.useState(false);
  return (
    <button onClick={onClick} onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{ display: 'flex', alignItems: 'center', gap: 11, padding: '10px 11px', marginBottom: 1, width: '100%', textAlign: 'left',
        border: 0, cursor: 'pointer', borderRadius: 'var(--radius-sm)',
        background: active ? 'var(--brand-soft)' : (hover ? 'var(--surface-hover)' : 'transparent'),
        color: active ? 'var(--brand)' : 'var(--fg-2)', fontFamily: 'var(--font-body)', fontWeight: active ? 600 : 500, fontSize: 13.5 }}>
      <Icon name={item.icon} size={17} style={{ flex: 'none', color: active ? 'var(--brand)' : 'var(--fg-3)' }} />
      {item.label}
    </button>
  );
}

/* ---------- shared field primitives ---------- */

function Group({ title, desc, children }) {
  return (
    <div style={{ marginBottom: 26 }}>
      {title && <div style={{ fontFamily: 'var(--font-body)', fontWeight: 700, fontSize: 13.5, color: 'var(--fg-1)', marginBottom: desc ? 3 : 12 }}>{title}</div>}
      {desc && <div style={{ fontFamily: 'var(--font-body)', fontSize: 12.5, color: 'var(--fg-3)', marginBottom: 14, lineHeight: 1.5, maxWidth: 460 }}>{desc}</div>}
      {children}
    </div>
  );
}

function Field({ label, hint, children }) {
  return (
    <label style={{ display: 'block', marginBottom: 14 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 6 }}>
        <span style={{ fontFamily: 'var(--font-body)', fontWeight: 600, fontSize: 12.5, color: 'var(--fg-2)' }}>{label}</span>
        {hint && <span style={{ fontFamily: 'var(--font-body)', fontSize: 11.5, color: 'var(--fg-4)' }}>{hint}</span>}
      </div>
      {children}
    </label>
  );
}

function TextInput({ value, onChange, placeholder, readOnly, icon, type = 'text' }) {
  const [focus, setFocus] = React.useState(false);
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '0 12px', height: 40,
      background: readOnly ? 'var(--surface)' : 'var(--bg-base)',
      border: '1px solid ' + (focus ? 'var(--border-brand)' : 'var(--border-solid)'), borderRadius: 'var(--radius-md)',
      boxShadow: focus ? 'var(--shadow-focus)' : 'none', transition: 'border-color var(--dur-fast), box-shadow var(--dur-fast)' }}>
      {icon && <Icon name={icon} size={16} style={{ color: 'var(--fg-4)', flex: 'none' }} />}
      <input type={type} value={value} placeholder={placeholder} readOnly={readOnly}
        onChange={(e) => onChange && onChange(e.target.value)} onFocus={() => setFocus(true)} onBlur={() => setFocus(false)}
        style={{ flex: 1, minWidth: 0, border: 0, outline: 'none', background: 'transparent', color: readOnly ? 'var(--fg-3)' : 'var(--fg-1)', fontFamily: 'var(--font-body)', fontSize: 14 }} />
      {readOnly && <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontFamily: 'var(--font-body)', fontSize: 11, color: 'var(--fg-4)', flex: 'none' }}><Icon name="lock" size={12} /> SSO</span>}
    </div>
  );
}

function SelectInput({ value, options, onChange }) {
  return (
    <div style={{ position: 'relative' }}>
      <select value={value} onChange={(e) => onChange(e.target.value)}
        style={{ appearance: 'none', WebkitAppearance: 'none', width: '100%', height: 40, padding: '0 36px 0 12px',
          background: 'var(--bg-base)', border: '1px solid var(--border-solid)', borderRadius: 'var(--radius-md)',
          color: 'var(--fg-1)', fontFamily: 'var(--font-body)', fontSize: 14, cursor: 'pointer', outline: 'none' }}>
        {options.map(o => <option key={o} value={o} style={{ background: 'var(--surface-raised)' }}>{o}</option>)}
      </select>
      <span style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none', color: 'var(--fg-3)', display: 'flex' }}>
        <Icon name="chevron-down" size={16} />
      </span>
    </div>
  );
}

function Segmented({ value, options, onChange }) {
  return (
    <div style={{ display: 'inline-flex', background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', padding: 3, gap: 3 }}>
      {options.map(o => (
        <button key={o} onClick={() => onChange(o)}
          style={{ fontFamily: 'var(--font-body)', fontWeight: 600, fontSize: 12.5, border: 0, cursor: 'pointer', padding: '7px 14px', borderRadius: 5,
            background: value === o ? 'var(--brand)' : 'transparent', color: value === o ? 'var(--fg-on-brand)' : 'var(--fg-3)', transition: 'background var(--dur-fast)' }}>{o}</button>
      ))}
    </div>
  );
}

function ToggleRow({ label, desc, value, onChange }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '13px 0', borderBottom: '1px solid var(--border)' }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontFamily: 'var(--font-body)', fontWeight: 600, fontSize: 13.5, color: 'var(--fg-1)' }}>{label}</div>
        {desc && <div style={{ fontFamily: 'var(--font-body)', fontSize: 12.5, color: 'var(--fg-3)', marginTop: 2, lineHeight: 1.45 }}>{desc}</div>}
      </div>
      <Switch value={value} onChange={onChange} />
    </div>
  );
}

function Switch({ value, onChange }) {
  return (
    <button role="switch" aria-checked={!!value} onClick={() => onChange(!value)}
      style={{ position: 'relative', width: 40, height: 23, flex: 'none', border: 0, borderRadius: 'var(--radius-pill)', cursor: 'pointer', padding: 0,
        background: value ? 'var(--brand)' : 'var(--ink-700)', transition: 'background var(--dur-fast)' }}>
      <span style={{ position: 'absolute', top: 2, left: value ? 19 : 2, width: 19, height: 19, borderRadius: '50%', background: value ? 'var(--fg-on-brand)' : 'var(--fg-2)', transition: 'left var(--dur-fast) var(--ease-out)' }} />
    </button>
  );
}

/* ---------- panes ---------- */

function ProfilePane({ s, patch }) {
  return (
    <div>
      <Group title="Details">
        <Field label="Full name"><TextInput value={s.name} onChange={(v) => patch('name', v)} /></Field>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <Field label="Job title"><TextInput value={s.title} onChange={(v) => patch('title', v)} /></Field>
          <Field label="Department"><TextInput value={s.dept} onChange={(v) => patch('dept', v)} /></Field>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <Field label="Email"><TextInput value={s.email} readOnly icon="mail" /></Field>
          <Field label="Role"><TextInput value={s.role} readOnly /></Field>
        </div>
      </Group>
    </div>
  );
}

function SecurityPane({ user }) {
  const providers = [
    { name: 'Microsoft', logo: 'ms', sub: user.email, connected: true },
    { name: 'Google', logo: 'google', sub: 'Not connected', connected: false },
  ];
  return (
    <div>
      <Group title="Single sign-on" desc="Playbook uses SSO only — there's no password to manage. Your administrator controls which providers are available.">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {providers.map(p => <ProviderRow key={p.name} p={p} />)}
        </div>
      </Group>
      <Group title="Active session">
        <div style={{ display: 'flex', alignItems: 'center', gap: 13, padding: '14px 15px', background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)' }}>
          <div style={{ width: 36, height: 36, flex: 'none', borderRadius: 'var(--radius-md)', background: 'var(--surface-hover)', color: 'var(--fg-2)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Icon name="monitor" size={18} /></div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontFamily: 'var(--font-body)', fontWeight: 600, fontSize: 13.5, color: 'var(--fg-1)' }}>This device · Stillwater, OK</div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5, color: 'var(--fg-3)', marginTop: 2 }}>Chrome · last active just now</div>
          </div>
          <Badge tone="success" dot pulse>Active</Badge>
        </div>
        <div style={{ marginTop: 14 }}>
          <PBButton variant="danger" size="sm" icon="log-out">Sign out of all other sessions</PBButton>
        </div>
      </Group>
    </div>
  );
}

function ProviderRow({ p }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 13, padding: '13px 15px', background: 'var(--bg-base)', border: '1px solid ' + (p.connected ? 'var(--border-strong)' : 'var(--border)'), borderRadius: 'var(--radius-md)' }}>
      <div style={{ width: 34, height: 34, flex: 'none', borderRadius: 'var(--radius-sm)', background: 'var(--surface-raised)', border: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {p.logo === 'ms' ? <MsLogo /> : <GgLogo />}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontFamily: 'var(--font-body)', fontWeight: 600, fontSize: 13.5, color: 'var(--fg-1)' }}>{p.name}</div>
        <div style={{ fontFamily: 'var(--font-body)', fontSize: 12, color: 'var(--fg-3)', marginTop: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{p.sub}</div>
      </div>
      {p.connected
        ? <Badge tone="success" dot>Connected</Badge>
        : <PBButton variant="secondary" size="sm">Connect</PBButton>}
    </div>
  );
}

function MsLogo() {
  return (
    <svg width="17" height="17" viewBox="0 0 23 23" aria-hidden="true">
      <rect x="1" y="1" width="10" height="10" fill="#F25022" />
      <rect x="12" y="1" width="10" height="10" fill="#7FBA00" />
      <rect x="1" y="12" width="10" height="10" fill="#00A4EF" />
      <rect x="12" y="12" width="10" height="10" fill="#FFB900" />
    </svg>
  );
}
function GgLogo() {
  return (
    <svg width="17" height="17" viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#FFC107" d="M43.611 20.083H42V20H24v8h11.303c-1.649 4.657-6.08 8-11.303 8-6.627 0-12-5.373-12-12s5.373-12 12-12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 12.955 4 4 12.955 4 24s8.955 20 20 20 20-8.955 20-20c0-1.341-.138-2.65-.389-3.917z" />
      <path fill="#FF3D00" d="M6.306 14.691l6.571 4.819C14.655 15.108 18.961 12 24 12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 16.318 4 9.656 8.337 6.306 14.691z" />
      <path fill="#4CAF50" d="M24 44c5.166 0 9.86-1.977 13.409-5.192l-6.19-5.238A11.91 11.91 0 0 1 24 36c-5.202 0-9.619-3.317-11.283-7.946l-6.522 5.025C9.505 39.556 16.227 44 24 44z" />
      <path fill="#1976D2" d="M43.611 20.083H42V20H24v8h11.303a12.04 12.04 0 0 1-4.087 5.571l.003-.002 6.19 5.238C36.971 39.205 44 34 44 24c0-1.341-.138-2.65-.389-3.917z" />
    </svg>
  );
}

window.SettingsModal = SettingsModal;
