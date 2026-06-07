/* ui.jsx — Playbook primitives: Button, Badge, AgentAvatar, Pulse, Kbd */

function PBButton({ variant = 'primary', size = 'md', icon, iconRight, children, onClick, style, disabled }) {
  const base = {
    fontFamily: 'var(--font-body)', fontWeight: 600, cursor: disabled ? 'not-allowed' : 'pointer',
    border: '1px solid transparent', borderRadius: 'var(--radius-md)', display: 'inline-flex',
    alignItems: 'center', gap: 8, lineHeight: 1, transition: 'background var(--dur-fast), border-color var(--dur-fast)',
    whiteSpace: 'nowrap',
  };
  const sizes = {
    sm: { fontSize: 13, padding: '7px 12px' },
    md: { fontSize: 14, padding: '10px 16px' },
    lg: { fontSize: 15, padding: '13px 22px' },
  };
  const variants = {
    primary: { background: 'var(--brand)', color: 'var(--fg-on-brand)' },
    secondary: { background: 'transparent', color: 'var(--fg-1)', borderColor: 'var(--border-strong)' },
    ghost: { background: 'transparent', color: 'var(--fg-2)' },
    danger: { background: 'var(--danger-bg)', color: 'var(--danger)' },
  };
  const dis = disabled ? { background: 'var(--surface-raised)', color: 'var(--fg-4)', borderColor: 'transparent' } : {};
  const [hover, setHover] = React.useState(false);
  const hoverStyle = (!disabled && hover) ? ({
    primary: { background: 'var(--brand-hover)' },
    secondary: { background: 'var(--surface-hover)' },
    ghost: { background: 'var(--surface-hover)', color: 'var(--fg-1)' },
    danger: { background: 'rgba(240,86,63,0.22)' },
  })[variant] : {};
  const sz = sizes[size];
  return React.createElement('button', {
    onClick: disabled ? undefined : onClick, disabled,
    onMouseEnter: () => setHover(true), onMouseLeave: () => setHover(false),
    style: { ...base, ...sz, ...variants[variant], ...dis, ...hoverStyle, ...style },
  },
    icon && (icon === 'mark'
      ? React.createElement(Mark, { size: size === 'sm' ? 17 : 19, color: 'currentColor' })
      : React.createElement(Icon, { name: icon, size: size === 'sm' ? 15 : 17 })),
    children,
    iconRight && React.createElement(Icon, { name: iconRight, size: size === 'sm' ? 15 : 17 })
  );
}

function Badge({ tone = 'neutral', children, dot, pulse, style }) {
  const tones = {
    neutral: { bg: 'var(--surface-raised)', fg: 'var(--fg-2)', bd: 'var(--border-strong)' },
    brand: { bg: 'var(--brand-soft)', fg: 'var(--brand)', bd: 'transparent' },
    info: { bg: 'var(--info-bg)', fg: 'var(--info)', bd: 'transparent' },
    success: { bg: 'var(--success-bg)', fg: 'var(--success)', bd: 'transparent' },
    warning: { bg: 'var(--warning-bg)', fg: 'var(--warning)', bd: 'transparent' },
    danger: { bg: 'var(--danger-bg)', fg: 'var(--danger)', bd: 'transparent' },
  };
  const t = tones[tone];
  return React.createElement('span', {
    style: {
      display: 'inline-flex', alignItems: 'center', gap: 7, fontFamily: 'var(--font-body)',
      fontWeight: 600, fontSize: 12, padding: '4px 10px', borderRadius: 'var(--radius-pill)',
      background: t.bg, color: t.fg, border: `1px solid ${t.bd}`, ...style,
    },
  },
    dot && React.createElement(Pulse, { color: t.fg, active: pulse }),
    children
  );
}

function Pulse({ color = 'var(--brand)', size = 7, active = true }) {
  return React.createElement('span', {
    className: active ? 'pb-pulse' : '',
    style: { width: size, height: size, borderRadius: '50%', background: color, flex: 'none', '--pulse-color': color },
  });
}

function AgentAvatar({ size = 34, tone = 'brand', icon }) {
  const bg = tone === 'brand' ? 'var(--brand)' : 'var(--surface-hover)';
  const fg = tone === 'brand' ? 'var(--fg-on-brand)' : 'var(--fg-2)';
  return React.createElement('div', {
    style: { width: size, height: size, borderRadius: 'var(--radius-md)', background: bg, color: fg,
      display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 'none' },
  }, icon
    ? React.createElement(Icon, { name: icon, size: Math.round(size * 0.52) })
    : React.createElement(Mark, { size: Math.round(size * 0.62), color: 'var(--fg-on-brand)' })
  );
}

Object.assign(window, { PBButton, Badge, Pulse, AgentAvatar });
