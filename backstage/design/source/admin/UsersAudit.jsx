/* UsersAudit.jsx — super-admin only. UsersView: registered users + role
   management (audited). AuditView: immutable action log. */

const ROLE_META = {
  super_admin: { label: 'Super admin', tone: 'brand', icon: 'shield' },
  admin: { label: 'Admin', tone: 'info', icon: 'shield-check' },
  athlete: { label: 'Athlete', tone: 'neutral', icon: 'user' },
};

function UsersView({ users, onChangeRole }) {
  const [q, setQ] = React.useState('');
  const filtered = users.filter(u => !q || u.name.toLowerCase().includes(q.toLowerCase()) || u.email.toLowerCase().includes(q.toLowerCase()));
  const adminCount = users.filter(u => u.role === 'admin' || u.role === 'super_admin').length;

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, background: 'var(--bg-base)' }}>
      <PageHeader title="Users & roles" sub={users.length + ' users · ' + adminCount + ' with admin access'} />

      <div style={{ flex: 'none', padding: '12px 26px', borderBottom: '1px solid var(--border)', background: 'var(--bg-base)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '0 11px', height: 36, width: 260, background: 'var(--surface)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-strong)' }}>
          <Icon name="search" size={15} style={{ color: 'var(--fg-4)', flex: 'none' }} />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search users…"
            style={{ flex: 1, minWidth: 0, border: 0, outline: 'none', background: 'transparent', color: 'var(--fg-1)', fontFamily: 'var(--font-body)', fontSize: 13 }} />
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '18px 26px 40px' }}>
        <div style={{ maxWidth: 880, margin: '0 auto', border: '1px solid var(--border-strong)', borderRadius: 'var(--radius-lg)', overflow: 'hidden', background: 'var(--surface)' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1.2fr 150px', gap: 14, padding: '11px 16px', borderBottom: '1px solid var(--border)', background: 'var(--bg-base)' }}>
            {['User', 'Role', ''].map((h, i) => <span key={i} style={{ fontFamily: 'var(--font-body)', fontSize: 10.5, fontWeight: 700, color: 'var(--fg-4)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>{h}</span>)}
          </div>
          {filtered.map((u, i) => <UserRow key={u.id} user={u} last={i === filtered.length - 1} onChangeRole={(r) => onChangeRole(u.id, r)} />)}
        </div>
      </div>
    </div>
  );
}

function UserRow({ user, last, onChangeRole }) {
  const [menu, setMenu] = React.useState(false);
  const m = ROLE_META[user.role];
  const roleOptions = [
    { role: 'athlete', label: 'Set as athlete' },
    { role: 'admin', label: 'Promote to admin' },
    { role: 'super_admin', label: 'Promote to super admin' },
  ];
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '2fr 1.2fr 150px', gap: 14, padding: '13px 16px', alignItems: 'center', borderBottom: last ? 'none' : '1px solid var(--border)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0 }}>
        <div style={{ width: 34, height: 34, flex: 'none', borderRadius: 'var(--radius-md)', background: user.you ? 'var(--brand)' : 'var(--surface-hover)', color: user.you ? 'var(--fg-on-brand)' : 'var(--fg-2)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 13 }}>{user.name.split(' ').map(w => w[0]).slice(0, 2).join('')}</div>
        <div style={{ minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <span style={{ fontFamily: 'var(--font-body)', fontSize: 13.5, fontWeight: 600, color: 'var(--fg-1)' }}>{user.name}</span>
            {user.you && <span style={{ fontFamily: 'var(--font-body)', fontSize: 10, fontWeight: 700, color: 'var(--fg-3)', background: 'var(--surface-raised)', borderRadius: 'var(--radius-pill)', padding: '1px 7px' }}>YOU</span>}
          </div>
          <div style={{ fontFamily: 'var(--font-body)', fontSize: 12, color: 'var(--fg-3)' }}>{user.email}</div>
        </div>
      </div>
      <div><Badge tone={m.tone} style={{ paddingLeft: 8 }}><Icon name={m.icon} size={12} />{m.label}</Badge></div>
      <div style={{ position: 'relative', justifySelf: 'end' }}>
        {user.you ? (
          <span style={{ fontFamily: 'var(--font-body)', fontSize: 12, color: 'var(--fg-4)', display: 'inline-flex', alignItems: 'center', gap: 6 }}><Icon name="lock" size={13} />Locked</span>
        ) : (
          <React.Fragment>
            <button onClick={() => setMenu(v => !v)} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '6px 11px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-strong)', background: menu ? 'var(--surface-hover)' : 'var(--surface)', color: 'var(--fg-1)', cursor: 'pointer', fontFamily: 'var(--font-body)', fontWeight: 600, fontSize: 12.5 }}>
              Change role<Icon name="chevron-down" size={13} />
            </button>
            {menu && (
              <React.Fragment>
                <div onClick={() => setMenu(false)} style={{ position: 'fixed', inset: 0, zIndex: 40 }} />
                <div style={{ position: 'absolute', top: 'calc(100% + 4px)', right: 0, zIndex: 41, width: 210, background: 'var(--surface-raised)', border: '1px solid var(--border-strong)', borderRadius: 'var(--radius-md)', boxShadow: 'var(--shadow-lg)', overflow: 'hidden', padding: 6, animation: 'pbmenu var(--dur-med) var(--ease-out) both' }}>
                  {roleOptions.map(o => (
                    <button key={o.role} disabled={o.role === user.role} onClick={() => { setMenu(false); if (o.role !== user.role) onChangeRole(o.role); }}
                      style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 10, padding: '8px 9px', border: 0, cursor: o.role === user.role ? 'default' : 'pointer', borderRadius: 'var(--radius-sm)', textAlign: 'left', background: 'transparent', color: o.role === user.role ? 'var(--fg-4)' : 'var(--fg-2)', fontFamily: 'var(--font-body)', fontWeight: 500, fontSize: 13 }}
                      onMouseEnter={(e) => { if (o.role !== user.role) e.currentTarget.style.background = 'var(--surface-hover)'; }}
                      onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}>
                      <Icon name={ROLE_META[o.role].icon} size={15} style={{ flex: 'none', color: o.role === user.role ? 'var(--fg-4)' : 'var(--fg-3)' }} />
                      {o.label}{o.role === user.role && <Icon name="check" size={14} style={{ marginLeft: 'auto', color: 'var(--brand)' }} />}
                    </button>
                  ))}
                </div>
              </React.Fragment>
            )}
          </React.Fragment>
        )}
      </div>
    </div>
  );
}

/* ---------------- audit log ---------------- */
const AUDIT_FILTERS = ['All actions', 'KB documents', 'Roles', 'Insights'];
const ACTION_ICON = { 'kb.upload': 'upload', 'kb.retry': 'refresh-cw', 'kb.metadata': 'pencil', 'kb.delete': 'trash', 'role.change': 'users', 'insight.trigger': 'sparkles' };
const ACTION_GROUP = { 'kb.upload': 'KB documents', 'kb.retry': 'KB documents', 'kb.metadata': 'KB documents', 'kb.delete': 'KB documents', 'role.change': 'Roles', 'insight.trigger': 'Insights' };

function AuditView({ events }) {
  const [filter, setFilter] = React.useState('All actions');
  const filtered = events.filter(e => filter === 'All actions' || ACTION_GROUP[e.action] === filter);
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, background: 'var(--bg-base)' }}>
      <PageHeader icon="scroll-text" title="Audit log" sub="Immutable record of administrative actions">
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7, fontFamily: 'var(--font-body)', fontSize: 11.5, color: 'var(--fg-3)' }}><Icon name="lock" size={14} />Read-only · cannot be edited</span>
      </PageHeader>

      <div style={{ flex: 'none', padding: '12px 26px', borderBottom: '1px solid var(--border)', background: 'var(--bg-base)' }}>
        <Segmented options={AUDIT_FILTERS} value={filter} onChange={setFilter} size="sm" />
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '20px 26px 40px' }}>
        <div style={{ maxWidth: 820, margin: '0 auto' }}>
          {filtered.map((e, i) => (
            <div key={e.id} style={{ display: 'flex', gap: 14, paddingBottom: i < filtered.length - 1 ? 18 : 0 }}>
              {/* timeline */}
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flex: 'none' }}>
                <div style={{ width: 34, height: 34, borderRadius: 'var(--radius-md)', background: 'var(--surface)', border: '1px solid var(--border-strong)', color: 'var(--fg-2)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Icon name={ACTION_ICON[e.action] || 'circle-dot'} size={16} /></div>
                {i < filtered.length - 1 && <div style={{ width: 1, flex: 1, background: 'var(--border)', marginTop: 4 }} />}
              </div>
              <div style={{ flex: 1, minWidth: 0, paddingBottom: 2 }}>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
                  <span style={{ fontFamily: 'var(--font-body)', fontSize: 13.5, color: 'var(--fg-1)' }}><b style={{ fontWeight: 600 }}>{e.actor}</b> · {e.label.toLowerCase()}</span>
                  <span style={{ marginLeft: 'auto', fontFamily: 'var(--font-body)', fontSize: 11.5, color: 'var(--fg-4)' }}>{e.when}</span>
                </div>
                <div style={{ marginTop: 7, display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--fg-3)', background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-xs)', padding: '2px 7px' }}>{e.action}</span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--fg-3)' }}>{e.target_type}:{e.target_id}</span>
                </div>
                <div style={{ marginTop: 7, fontFamily: 'var(--font-body)', fontSize: 12.5, color: 'var(--fg-3)' }}>{e.meta}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { UsersView, AuditView });
