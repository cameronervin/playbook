/* TopBar.jsx — chat header: the conversation title. Conversations span any number
   of knowledge areas, so the thread itself is not labeled by domain. */

function TopBar({ conv, sourcesOpen, onToggleSources, onRename, onDelete }) {
  const [menuOpen, setMenuOpen] = React.useState(false);
  const [editing, setEditing] = React.useState(false);
  const [draft, setDraft] = React.useState('');
  const [titleHover, setTitleHover] = React.useState(false);
  const hasConv = !!conv;
  const title = (conv && conv.messages.length > 0) ? conv.title : 'New chat';

  const startRename = () => { setDraft(conv.title || ''); setEditing(true); setMenuOpen(false); };
  const commit = () => { const t = draft.trim(); if (t && conv) onRename(conv.id, t); setEditing(false); };

  return React.createElement('header', {
    style: {
      height: 64, flex: 'none', borderBottom: '1px solid var(--border)', display: 'flex',
      alignItems: 'center', gap: 13, padding: '0 22px', background: 'var(--bg-base)',
    },
  },
    editing
      ? React.createElement('input', {
          autoFocus: true, value: draft,
          onChange: (e) => setDraft(e.target.value), onBlur: commit,
          onKeyDown: (e) => { if (e.key === 'Enter') { e.preventDefault(); commit(); } if (e.key === 'Escape') setEditing(false); },
          style: { fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 16, letterSpacing: '-0.01em', color: 'var(--fg-1)', background: 'var(--bg-base)', border: '1px solid var(--border-brand)', borderRadius: 'var(--radius-sm)', padding: '5px 9px', outline: 'none', boxShadow: 'var(--shadow-focus)', minWidth: 0, maxWidth: 380, flex: '0 1 380px' },
        })
      : React.createElement('div', {
          onClick: () => { if (hasConv) startRename(); },
          onMouseEnter: () => setTitleHover(true), onMouseLeave: () => setTitleHover(false),
          title: hasConv ? 'Rename chat' : undefined,
          style: { display: 'flex', alignItems: 'center', gap: 8, minWidth: 0, padding: '5px 9px', margin: '0 -9px', borderRadius: 'var(--radius-sm)', cursor: hasConv ? 'pointer' : 'default', background: (titleHover && hasConv) ? 'var(--surface-hover)' : 'transparent', transition: 'background var(--dur-fast)' },
        },
          React.createElement('span', { style: { fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 16, letterSpacing: '-0.01em', color: 'var(--fg-1)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', minWidth: 0 } }, title),
          hasConv && React.createElement(Icon, { name: 'pencil', size: 14, style: { flex: 'none', color: 'var(--fg-3)', opacity: titleHover ? 1 : 0, transition: 'opacity var(--dur-fast)' } })
        ),
    React.createElement('div', { style: { marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8, position: 'relative' } },
      React.createElement(IconBtn, { name: 'more-horizontal', active: menuOpen, onClick: () => { if (hasConv) setMenuOpen(o => !o); } }),
      React.createElement(IconBtn, { name: 'panel-right', active: sourcesOpen, onClick: onToggleSources }),
      menuOpen && React.createElement(React.Fragment, null,
        React.createElement('div', { onClick: () => setMenuOpen(false), style: { position: 'fixed', inset: 0, zIndex: 40 } }),
        React.createElement('div', {
          style: { position: 'absolute', top: 'calc(100% + 6px)', right: 0, zIndex: 41, width: 184, background: 'var(--surface-raised)', border: '1px solid var(--border-strong)', borderRadius: 'var(--radius-md)', boxShadow: 'var(--shadow-lg)', overflow: 'hidden', padding: 6, animation: 'pbmenu var(--dur-med) var(--ease-out) both' },
        },
          React.createElement(TopBarMenuItem, { icon: 'pencil', label: 'Rename chat', onClick: startRename }),
          React.createElement(TopBarMenuItem, { icon: 'trash', label: 'Delete chat', danger: true, onClick: () => { setMenuOpen(false); onDelete(conv.id); } })
        )
      )
    )
  );
}

function TopBarMenuItem({ icon, label, danger, onClick }) {
  const [hover, setHover] = React.useState(false);
  return React.createElement('button', {
    type: 'button', onClick, onMouseEnter: () => setHover(true), onMouseLeave: () => setHover(false),
    style: {
      width: '100%', display: 'flex', alignItems: 'center', gap: 11, padding: '9px 10px',
      border: 0, cursor: 'pointer', borderRadius: 'var(--radius-sm)', textAlign: 'left',
      background: hover ? (danger ? 'var(--danger-bg)' : 'var(--surface-hover)') : 'transparent',
      color: danger ? 'var(--danger)' : (hover ? 'var(--fg-1)' : 'var(--fg-2)'),
      fontFamily: 'var(--font-body)', fontWeight: 500, fontSize: 13.5,
    },
  },
    React.createElement(Icon, { name: icon, size: 17, style: { flex: 'none', color: danger ? 'var(--danger)' : (hover ? 'var(--brand)' : 'var(--fg-3)') } }),
    label
  );
}

function IconBtn({ name, active, onClick }) {
  const [hover, setHover] = React.useState(false);
  return React.createElement('button', {
    onClick, onMouseEnter: () => setHover(true), onMouseLeave: () => setHover(false),
    style: {
      width: 34, height: 34, borderRadius: 'var(--radius-sm)', border: 0, cursor: 'pointer',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: active ? 'var(--brand-soft)' : (hover ? 'var(--surface-hover)' : 'transparent'),
      color: active ? 'var(--brand)' : 'var(--fg-2)',
    },
  }, React.createElement(Icon, { name, size: 18 }));
}

window.TopBar = TopBar;
window.IconBtn = IconBtn;
