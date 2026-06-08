/* Composer.jsx — message input at bottom of the thread. */

function Composer({ onSend, disabled, maxWidth = 720, enterToSend = true }) {
  const [val, setVal] = React.useState('');
  const [focus, setFocus] = React.useState(false);
  const taRef = React.useRef(null);
  const submit = () => {
    const t = val.trim();
    if (!t || disabled) return;
    onSend(t);
    setVal('');
    if (taRef.current) taRef.current.style.height = 'auto';
  };
  const grow = (e) => {
    setVal(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = Math.min(e.target.scrollHeight, 160) + 'px';
  };
  return React.createElement('div', { style: { flex: 'none', padding: '14px 28px 22px', display: 'flex', justifyContent: 'center', background: 'var(--bg-base)' } },
    React.createElement('div', { style: { width: '100%', maxWidth: maxWidth } },
      React.createElement('div', {
        style: {
          background: 'var(--surface)', border: `1px solid ${focus ? 'var(--border-brand)' : 'var(--border-solid)'}`,
          borderRadius: 'var(--radius-lg)', padding: 12, boxShadow: focus ? 'var(--shadow-focus)' : 'var(--shadow-sm)',
          transition: 'border-color var(--dur-fast), box-shadow var(--dur-fast)',
        },
      },
        React.createElement('textarea', {
          ref: taRef, value: val, rows: 1,
          onChange: grow, onFocus: () => setFocus(true), onBlur: () => setFocus(false),
          onKeyDown: (e) => { const send = enterToSend ? (e.key === 'Enter' && !e.shiftKey) : (e.key === 'Enter' && (e.metaKey || e.ctrlKey)); if (send) { e.preventDefault(); submit(); } },
          placeholder: 'Ask Playbook a question…',
          style: {
            width: '100%', boxSizing: 'border-box', resize: 'none', border: 0, outline: 'none', background: 'transparent',
            color: 'var(--fg-1)', fontFamily: 'var(--font-body)', fontSize: 15, lineHeight: 1.5, padding: '4px 4px 10px',
          },
        }),
        React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 10 } },
          React.createElement(IconBtn, { name: 'paperclip' }),
          React.createElement('div', { style: { marginLeft: 'auto' } },
            React.createElement(PBButton, { variant: 'primary', size: 'sm', iconRight: 'send', onClick: submit, disabled: !val.trim() || disabled }, 'Ask')
          )
        )
      ),
      React.createElement('div', { style: { textAlign: 'center', marginTop: 9, fontFamily: 'var(--font-body)', fontSize: 11, color: 'var(--fg-4)' } }, 'Responses are AI generated. Review to confirm accuracy.')
    )
  );
}

window.Composer = Composer;
