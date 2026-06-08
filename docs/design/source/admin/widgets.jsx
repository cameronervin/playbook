/* widgets.jsx — admin building blocks: page header, stat cards, charts,
   status/risk/topic pills, filter controls, empty states. */

/* ---------------- icon button (admin-local; Home defines its own) ---------------- */
function IconBtn({ name, active, onClick }) {
  const [hover, setHover] = React.useState(false);
  return (
    <button onClick={onClick} onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{ width: 34, height: 34, borderRadius: 'var(--radius-sm)', border: 0, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: active ? 'var(--brand-soft)' : (hover ? 'var(--surface-hover)' : 'transparent'),
        color: active ? 'var(--brand)' : 'var(--fg-2)' }}>
      <Icon name={name} size={18} />
    </button>
  );
}

/* ---------------- page scaffold ---------------- */
function PageHeader({ icon, title, sub, children }) {
  return (
    <header style={{ position: 'relative', flex: 'none', borderBottom: '1px solid var(--border)', padding: '0 28px', background: 'var(--bg-base)' }}>
      <div className="admin-grid" />
      <div style={{ position: 'relative', minHeight: 68, display: 'flex', alignItems: 'center', gap: 14 }}>
        <div style={{ lineHeight: 1.3, minWidth: 0 }}>
          <div style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 20, letterSpacing: '-0.015em', color: 'var(--fg-1)' }}>{title}</div>
          {sub && <div style={{ fontFamily: 'var(--font-body)', fontSize: 12.5, color: 'var(--fg-3)', marginTop: 2 }}>{sub}</div>}
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10 }}>{children}</div>
      </div>
    </header>
  );
}

function SectionLabel({ children, style }) {
  return <div style={{ fontFamily: 'var(--font-body)', fontSize: 11.5, fontWeight: 700, color: 'var(--fg-3)', letterSpacing: '0.06em', textTransform: 'uppercase', ...style }}>{children}</div>;
}

function Card({ children, style, pad = 18 }) {
  return <div style={{ background: 'var(--surface)', border: '1px solid var(--border-strong)', borderRadius: 'var(--radius-lg)', padding: pad, ...style }}>{children}</div>;
}

/* ---------------- stat card ---------------- */
function StatCard({ label, value, unit, delta, deltaUnit, invert, icon, hint }) {
  const dir = delta == null ? 0 : (delta > 0 ? 1 : (delta < 0 ? -1 : 0));
  const good = invert ? dir < 0 : dir > 0;
  const tone = dir === 0 ? 'var(--fg-3)' : (good ? 'var(--success)' : 'var(--danger)');
  return (
    <Card pad={16} style={{ display: 'flex', flexDirection: 'column', gap: 10, minWidth: 0 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Icon name={icon} size={15} style={{ color: 'var(--fg-3)' }} />
        <span style={{ fontFamily: 'var(--font-body)', fontSize: 12.5, fontWeight: 600, color: 'var(--fg-3)' }}>{label}</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
        <span style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 30, letterSpacing: '-0.02em', color: 'var(--fg-1)', lineHeight: 1 }}>{value}</span>
        {unit && <span style={{ fontFamily: 'var(--font-body)', fontSize: 13, color: 'var(--fg-3)' }}>{unit}</span>}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, minHeight: 16 }}>
        {delta != null && (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, color: tone, fontFamily: 'var(--font-body)', fontWeight: 600, fontSize: 12 }}>
            <Icon name={dir >= 0 ? 'trending-up' : 'trending-down'} size={13} />
            {dir > 0 ? '+' : ''}{delta}{deltaUnit || ''}
          </span>
        )}
        <span style={{ fontFamily: 'var(--font-body)', fontSize: 11.5, color: 'var(--fg-4)' }}>{hint || 'vs prev 7d'}</span>
      </div>
    </Card>
  );
}

/* ---------------- volume bar chart (daily, with unanswered overlay) ---------------- */
function VolumeChart({ series }) {
  const max = Math.max(...series.map(d => d.total), 1);
  const [hi, setHi] = React.useState(null);
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 12, height: 116, padding: '0 2px' }}>
        {series.map((d, i) => {
          const h = Math.round((d.total / max) * 100) + 4;
          const uh = Math.round((d.unanswered / max) * 100);
          const active = hi === i;
          return (
            <div key={i} onMouseEnter={() => setHi(i)} onMouseLeave={() => setHi(null)}
              style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, cursor: 'default' }}>
              <div style={{ position: 'relative', width: '100%', maxWidth: 40, height: h, borderRadius: '4px 4px 2px 2px', overflow: 'hidden', background: active ? 'var(--orange-400)' : 'var(--brand)', transition: 'background var(--dur-fast)' }}>
                {uh > 0 && <div style={{ position: 'absolute', left: 0, right: 0, top: 0, height: uh, background: 'var(--warning)' }} />}
                {active && (
                  <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'flex-start', justifyContent: 'center', paddingTop: 4 }}>
                    <span style={{ fontFamily: 'var(--font-body)', fontWeight: 700, fontSize: 11, color: 'var(--fg-on-brand)' }}>{d.total}</span>
                  </div>
                )}
              </div>
              <span style={{ fontFamily: 'var(--font-body)', fontSize: 11, color: active ? 'var(--fg-1)' : 'var(--fg-4)', fontWeight: active ? 600 : 500 }}>{d.day}</span>
            </div>
          );
        })}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--border)' }}>
        <Legend color="var(--brand)" label="Answered" />
        <Legend color="var(--warning)" label="Unanswered / declined" />
        <span style={{ marginLeft: 'auto', fontFamily: 'var(--font-body)', fontSize: 11.5, color: 'var(--fg-4)' }}>
          {hi != null ? series[hi].date + ' · ' + series[hi].total + ' questions' : 'Hover a day for detail'}
        </span>
      </div>
    </div>
  );
}
function Legend({ color, label }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7, fontFamily: 'var(--font-body)', fontSize: 11.5, color: 'var(--fg-3)' }}>
      <span style={{ width: 9, height: 9, borderRadius: 2, background: color }} />{label}
    </span>
  );
}

/* ---------------- horizontal topic bars ---------------- */
function TopicBars({ items, onPick, activeKey }) {
  const max = Math.max(...items.map(i => i.count), 1);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
      {items.map((it, i) => {
        const active = activeKey && it.key === activeKey;
        return (
          <div key={i} onClick={onPick && it.key ? () => onPick(it.key) : undefined}
            style={{ display: 'grid', gridTemplateColumns: '92px 1fr 34px', alignItems: 'center', gap: 12, cursor: onPick && it.key ? 'pointer' : 'default' }}>
            <span style={{ fontFamily: 'var(--font-body)', fontSize: 12.5, fontWeight: active ? 700 : 500, color: active ? 'var(--brand)' : 'var(--fg-2)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{it.label}</span>
            <span style={{ height: 9, borderRadius: 'var(--radius-pill)', background: 'var(--surface-raised)', overflow: 'hidden' }}>
              <span style={{ display: 'block', height: '100%', width: ((it.count / max) * 100) + '%', borderRadius: 'var(--radius-pill)', background: active ? 'var(--brand)' : 'var(--orange-600)' }} />
            </span>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12.5, color: 'var(--fg-2)', textAlign: 'right' }}>{it.count}</span>
          </div>
        );
      })}
    </div>
  );
}

/* ---------------- labels / pills ---------------- */
const STATUS_META = {
  answered: { tone: 'success', icon: 'check-circle', label: 'Answered' },
  declined: { tone: 'warning', icon: 'minus-circle', label: 'Declined' },
  unsupported: { tone: 'info', icon: 'help-circle', label: 'Unsupported' },
  failed: { tone: 'danger', icon: 'alert-triangle', label: 'Failed' },
  partial: { tone: 'neutral', icon: 'circle-dot', label: 'Partial' },
};
function StatusPill({ status }) {
  const m = STATUS_META[status] || STATUS_META.partial;
  return <Badge tone={m.tone} style={{ paddingLeft: 8 }}><Icon name={m.icon} size={13} />{m.label}</Badge>;
}

const RISK_LABEL = { nil: 'NIL', compliance: 'Compliance', recruiting: 'Recruiting-risk' };
function RiskPill({ risk }) {
  const tone = risk === 'recruiting' ? 'danger' : 'warning';
  return <Badge tone={tone} style={{ paddingLeft: 8 }}><Icon name="flag" size={12} />{RISK_LABEL[risk] || risk}</Badge>;
}

function TopicChip({ label }) {
  return <span style={{ fontFamily: 'var(--font-body)', fontSize: 11.5, fontWeight: 600, color: 'var(--fg-2)', background: 'var(--surface-raised)', border: '1px solid var(--border)', borderRadius: 'var(--radius-pill)', padding: '3px 10px' }}>{label}</span>;
}

const SEV_META = { low: { c: 'var(--success)', label: 'Low' }, medium: { c: 'var(--warning)', label: 'Medium' }, high: { c: 'var(--danger)', label: 'High' } };
function SeverityTag({ severity }) {
  const m = SEV_META[severity] || SEV_META.low;
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontFamily: 'var(--font-body)', fontSize: 11, fontWeight: 700, letterSpacing: '0.04em', textTransform: 'uppercase', color: m.c }}>
      <span style={{ width: 7, height: 7, borderRadius: '50%', background: m.c }} />{m.label}
    </span>
  );
}

/* ---------------- filter controls ---------------- */
function Segmented({ options, value, onChange, size = 'md' }) {
  const pad = size === 'sm' ? '5px 10px' : '7px 13px';
  const fs = size === 'sm' ? 12 : 12.5;
  return (
    <div style={{ display: 'inline-flex', background: 'var(--surface)', border: '1px solid var(--border-strong)', borderRadius: 'var(--radius-md)', padding: 3, gap: 2 }}>
      {options.map(o => {
        const v = typeof o === 'string' ? o : o.value;
        const lbl = typeof o === 'string' ? o : o.label;
        const active = v === value;
        return (
          <button key={v} onClick={() => onChange(v)}
            style={{ border: 0, cursor: 'pointer', padding: pad, borderRadius: 'var(--radius-sm)', fontFamily: 'var(--font-body)', fontWeight: active ? 600 : 500, fontSize: fs, whiteSpace: 'nowrap',
              background: active ? 'var(--brand-soft)' : 'transparent', color: active ? 'var(--brand)' : 'var(--fg-3)', transition: 'background var(--dur-fast), color var(--dur-fast)' }}>
            {lbl}
          </button>
        );
      })}
    </div>
  );
}

function FilterSelect({ icon, label, value, options, onChange }) {
  return (
    <label style={{ display: 'inline-flex', alignItems: 'center', gap: 8, height: 36, padding: '0 11px', background: 'var(--surface)', border: '1px solid var(--border-strong)', borderRadius: 'var(--radius-md)', cursor: 'pointer', position: 'relative' }}>
      {icon && <Icon name={icon} size={15} style={{ color: 'var(--fg-3)', flex: 'none' }} />}
      {label && <span style={{ fontFamily: 'var(--font-body)', fontSize: 12.5, color: 'var(--fg-3)' }}>{label}</span>}
      <select value={value} onChange={(e) => onChange(e.target.value)}
        style={{ appearance: 'none', WebkitAppearance: 'none', border: 0, background: 'transparent', color: 'var(--fg-1)', fontFamily: 'var(--font-body)', fontSize: 12.5, fontWeight: 600, cursor: 'pointer', outline: 'none', paddingRight: 16 }}>
        {options.map(o => <option key={o} value={o} style={{ background: 'var(--surface-raised)', color: 'var(--fg-1)' }}>{o}</option>)}
      </select>
      <Icon name="chevron-down" size={14} style={{ color: 'var(--fg-3)', position: 'absolute', right: 9, pointerEvents: 'none' }} />
    </label>
  );
}

/* ---------------- empty state ---------------- */
function EmptyState({ icon, title, body, children }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center', padding: '56px 24px', gap: 12 }}>
      <div style={{ width: 52, height: 52, borderRadius: 'var(--radius-lg)', background: 'var(--surface)', border: '1px solid var(--border-strong)', color: 'var(--fg-3)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Icon name={icon} size={24} /></div>
      <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 16, color: 'var(--fg-1)' }}>{title}</div>
      <div style={{ fontFamily: 'var(--font-body)', fontSize: 13.5, color: 'var(--fg-3)', maxWidth: 380, lineHeight: 1.55 }}>{body}</div>
      {children}
    </div>
  );
}

/* ---------------- live insight status chip ---------------- */
function RunStatus({ status, size = 'md' }) {
  const map = {
    completed: { tone: 'success', icon: 'check-circle', label: 'Completed' },
    processing: { tone: 'info', icon: 'loader', label: 'Processing', spin: true },
    pending: { tone: 'neutral', icon: 'clock', label: 'Pending' },
    failed: { tone: 'danger', icon: 'alert-triangle', label: 'Failed' },
  };
  const m = map[status] || map.pending;
  return (
    <Badge tone={m.tone} style={{ paddingLeft: 8 }}>
      <Icon name={m.icon} size={13} className={m.spin ? 'pb-spin' : ''} />{m.label}
    </Badge>
  );
}

Object.assign(window, {
  IconBtn, PageHeader, SectionLabel, Card, StatCard, VolumeChart, TopicBars,
  StatusPill, RiskPill, TopicChip, SeverityTag, Segmented, FilterSelect, EmptyState, RunStatus,
  STATUS_META, RISK_LABEL,
});
