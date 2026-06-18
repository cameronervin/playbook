/* ChatThread.jsx — conversation with Playbook. One agent voice; messages can
   note which knowledge area grounded the answer. Empty state surfaces the
   knowledge areas as scope chips (the "roster" lives inside the app). */

function ChatThread({ messages, topic, topics, onCite, onPickTopic, onPrompt, maxWidth = 720, gap = 24 }) {
  const endRef = React.useRef(null);
  React.useEffect(() => { if (endRef.current) endRef.current.scrollTop = endRef.current.scrollHeight; }, [messages]);
  return React.createElement('div', {
    ref: endRef,
    style: { flex: 1, overflowY: 'auto', padding: '28px 0', display: 'flex', justifyContent: 'center' },
  },
    React.createElement('div', { style: { width: '100%', maxWidth: maxWidth, padding: '0 28px', display: 'flex', flexDirection: 'column', gap: gap } },
      messages.length === 0
        ? React.createElement(EmptyState, null)
        : messages.map((m, i) => m.role === 'user'
          ? React.createElement(UserMsg, { key: i, msg: m })
          : React.createElement(AgentMsg, { key: i, msg: m, topic, onCite })
        )
    )
  );
}

function EmptyState() {
  return React.createElement('div', { style: { padding: '13vh 0 16px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 } },
    React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 14 } },
      React.createElement(Mark, { size: 36 }),
      React.createElement('h2', { style: { fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 30, letterSpacing: '-0.02em', color: 'var(--fg-1)', margin: 0, textAlign: 'center' } },
        'Ask PlaybookAI')
    ),
    React.createElement('p', { style: { fontFamily: 'var(--font-body)', fontSize: 15, color: 'var(--fg-3)', width: 'fit-content', maxWidth: '100%', margin: 0, lineHeight: 1.55, textAlign: 'center', textWrap: 'balance' } },
      'Get answers to your athletics questions,',
      React.createElement('br'),
      'PlaybookAI is your coach off the field.'
    )
  );
}

function UserMsg({ msg }) {
  return React.createElement('div', { style: { display: 'flex', justifyContent: 'flex-end' } },
    React.createElement('div', {
      style: { maxWidth: '78%', background: 'var(--surface-hover)', border: '1px solid var(--border)', color: 'var(--fg-1)',
        borderRadius: 'var(--radius-lg)', borderTopRightRadius: 4, padding: '12px 15px', fontFamily: 'var(--font-body)', fontSize: 14.5, lineHeight: 1.55 },
    }, msg.text)
  );
}

function AgentMsg({ msg, topic, onCite }) {
  var stream = useStreamHtml(msg.html || '', !!msg.stream);
  return React.createElement('div', { style: { display: 'flex' } },
    React.createElement('div', { style: { flex: 1, minWidth: 0 } },
      React.createElement('div', { style: { fontFamily: 'var(--font-body)', fontSize: 12.5, color: 'var(--fg-3)', marginBottom: 8 } },
        React.createElement('b', { style: { color: 'var(--fg-1)', fontWeight: 600 } }, 'PlaybookAI')),
      msg.thinking
        ? React.createElement(Thinking, null)
        : React.createElement(React.Fragment, null,
            React.createElement('div', {
              className: stream.done ? null : 'pb-streaming',
              style: { fontFamily: 'var(--font-body)', fontSize: 14.5, lineHeight: 1.62, color: 'var(--fg-1)' },
              dangerouslySetInnerHTML: { __html: stream.shown },
            }),
            stream.done && msg.cites && msg.cites.length > 0 && React.createElement('div', { style: { display: 'flex', gap: 8, marginTop: 14, flexWrap: 'wrap' } },
              msg.cites.map((c, i) => React.createElement('button', {
                key: i, onClick: () => onCite && onCite(c),
                style: { display: 'inline-flex', alignItems: 'center', gap: 7, background: 'var(--surface)', border: '1px solid var(--border-strong)', borderRadius: 'var(--radius-sm)', padding: '6px 10px', fontFamily: 'var(--font-mono)', fontSize: 10.5, color: 'var(--fg-2)', cursor: 'pointer' },
              },
                React.createElement(Icon, { name: 'file-text', size: 13, style: { color: 'var(--brand)' } }), c.file
              ))
            ),
            React.createElement('div', { style: { fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--fg-3)', marginTop: 12 } },
              stream.done ? 'Checked ' + msg.checked + ' sources · ' + msg.time : null)
          )
    )
  );
}

// Stream an HTML string in word-by-word, keeping tags atomic so markup never breaks mid-reveal.
function tokenizeHtml(html) {
  var tokens = [], re = /(<[^>]+>)|([^<]+)/g, m;
  while ((m = re.exec(html))) {
    if (m[1]) { tokens.push(m[1]); }
    else { var parts = m[2].match(/\s+|\S+/g) || []; for (var i = 0; i < parts.length; i++) tokens.push(parts[i]); }
  }
  return tokens;
}
function useStreamHtml(html, enabled) {
  var s = React.useState(enabled ? '' : html), shown = s[0], setShown = s[1];
  var d = React.useState(!enabled), done = d[0], setDone = d[1];
  React.useEffect(function () {
    var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (!enabled || reduce) { setShown(html); setDone(true); return; }
    var tokens = tokenizeHtml(html), i = 0, acc = '';
    setShown(''); setDone(false);
    var id = setInterval(function () {
      // reveal one word, plus any trailing whitespace/tags so closing tags attach cleanly
      while (i < tokens.length) { var tk = tokens[i]; acc += tk; i++; if (!/^(<[^>]+>|\s+)$/.test(tk)) break; }
      while (i < tokens.length && /^(<[^>]+>|\s+)$/.test(tokens[i])) { acc += tokens[i]; i++; }
      setShown(acc);
      if (i >= tokens.length) { clearInterval(id); setDone(true); }
    }, 26);
    return function () { clearInterval(id); };
  }, [html, enabled]);
  return { shown: shown, done: done };
}

function Thinking() {
  return React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 11, padding: '4px 0' } },
    React.createElement('div', { style: { display: 'inline-flex' } }, React.createElement(Mark, { size: 22 })),
    React.createElement('span', { className: 'pb-think', style: { fontFamily: 'var(--font-body)', fontSize: 13.5, color: 'var(--fg-3)' } }, 'Thinking…')
  );
}

window.ChatThread = ChatThread;
