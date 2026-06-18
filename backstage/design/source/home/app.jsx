/* app.jsx — Playbook home (post-login). Chat-first: searchable history on the
   left, conversation in the center, grounding sources on the right, and the
   account/settings surface reachable from the rail. Canned replies — cosmetic. */

/* ---------------- knowledge areas + canned grounding ---------------- */
const TOPICS = [
  { id: 'compliance', name: 'Compliance & NIL', icon: 'shield', sources: 24, updated: '2d ago', answered: 412,
    blurb: 'NIL, eligibility, and recruiting rules — kept current with OSU and NCAA policy.',
    prompts: ["What's the NIL disclosure window?", 'Can a recruit attend a scrimmage?', 'Summer eligibility checklist'],
    docs: [ { file: 'NIL_POLICY_2025.PDF', meta: 'Updated Mar 2025 · 18 pp' }, { file: 'NCAA_BYLAW_13.PDF', meta: 'Recruiting · 44 pp' }, { file: 'ELIGIBILITY_CHECKLIST.DOCX', meta: 'Compliance office · 6 pp' }, { file: 'TRANSFER_PORTAL_SOP.PDF', meta: 'Updated Jan 2025 · 9 pp' } ] },
  { id: 'travel', name: 'Team Travel', icon: 'plane', sources: 16, updated: '5d ago', answered: 263,
    blurb: 'Per-diem rates, charter logistics, and team hotel policy for every sport.',
    prompts: ['What is the meal per diem?', 'Charter bus vendor list', 'Hotel booking deadline'],
    docs: [ { file: 'TRAVEL_POLICY_2025.PDF', meta: 'Athletics ops · 22 pp' }, { file: 'PER_DIEM_RATES.XLSX', meta: 'Finance · updated weekly' }, { file: 'CHARTER_VENDORS.PDF', meta: 'Approved list · 4 pp' } ] },
  { id: 'ticketing', name: 'Ticketing & Fans', icon: 'ticket', sources: 11, updated: '1d ago', answered: 388,
    blurb: 'Season tickets, will-call, student entry, and gameday answers for fans and partners.',
    prompts: ['Student section entry rules', 'How do I transfer a ticket?', 'Parking pass options'],
    docs: [ { file: 'GAMEDAY_FAQ.PDF', meta: 'Fan services · 12 pp' }, { file: 'TICKET_TRANSFER_GUIDE.PDF', meta: 'Updated Aug 2024 · 5 pp' } ] },
  { id: 'academics', name: 'Academic Services', icon: 'book-open', sources: 19, updated: '3d ago', answered: 174,
    blurb: 'Study-hall rules, tutoring, and academic eligibility support for student-athletes.',
    prompts: ['Study hall hours', 'How to request a tutor', 'Minimum GPA to travel'],
    docs: [ { file: 'STUDY_HALL_POLICY.PDF', meta: 'Academics · 7 pp' }, { file: 'TUTORING_GUIDE.DOCX', meta: 'Student services · 4 pp' } ] },
  { id: 'facilities', name: 'Facilities', icon: 'database', sources: 14, updated: '6d ago', answered: 96,
    blurb: 'Weight room hours, field access, and equipment checkout procedures.',
    prompts: ['Weight room hours', 'How to reserve the indoor field', 'Equipment checkout'],
    docs: [ { file: 'FACILITY_HOURS.PDF', meta: 'Operations · 3 pp' }, { file: 'EQUIPMENT_SOP.PDF', meta: 'Equipment room · 8 pp' } ] },
  { id: 'donor', name: 'Donor Relations', icon: 'users', sources: 9, updated: '8d ago', answered: 51,
    blurb: 'Giving levels, suite benefits, and Cowboy Club answers for boosters and partners.',
    prompts: ['Cowboy Club giving levels', 'Suite holder benefits', 'Tax receipt timing'],
    docs: [ { file: 'COWBOY_CLUB_LEVELS.PDF', meta: 'Development · 6 pp' }, { file: 'SUITE_BENEFITS.PDF', meta: 'Premium seating · 5 pp' } ] },
];
const TOPIC_BY_ID = Object.fromEntries(TOPICS.map(t => [t.id, t]));
const PLAYBOOK_ALL = { id: 'all', name: 'your knowledge base', sources: TOPICS.reduce((n, t) => n + t.sources, 0), docs: TOPICS.map(t => t.docs[0]) };

const REPLIES = {
  compliance: { html: 'Athletes must disclose any NIL agreement valued over <b style="color:var(--brand)">$600</b> within <b style="color:var(--brand)">72 hours</b> of signing, using the OSU compliance portal. Deals involving university marks also require a brand-use review before the agreement is finalized.', cites: [{ file: 'NIL_POLICY_2025.PDF' }, { file: 'NCAA_BYLAW_13.PDF' }], checked: 4, time: '1.8s' },
  travel: { html: 'The current meal per diem for team travel is <b style="color:var(--brand)">$65/day</b>, split $15 / $20 / $30 across breakfast, lunch, and dinner. Provided team meals are deducted from the daily rate.', cites: [{ file: 'PER_DIEM_RATES.XLSX' }, { file: 'TRAVEL_POLICY_2025.PDF' }], checked: 3, time: '1.4s' },
  ticketing: { html: 'Students enter through <b style="color:var(--brand)">Gate 3</b> with a valid student ID and a mobile ticket claimed in the app. The student section opens <b style="color:var(--brand)">90 minutes</b> before kickoff and is first-come, first-served.', cites: [{ file: 'GAMEDAY_FAQ.PDF' }], checked: 2, time: '1.1s' },
  academics: { html: 'Student-athletes must hold a <b style="color:var(--brand)">2.3 GPA</b> to be eligible for team travel. Anyone below the line can petition through Academic Services with an approved study-hall plan.', cites: [{ file: 'STUDY_HALL_POLICY.PDF' }], checked: 2, time: '1.2s' },
  facilities: { html: 'The indoor field can be reserved up to <b style="color:var(--brand)">14 days</b> ahead through the Operations portal. In-season teams get priority, and any open slots release every Monday at 8:00am.', cites: [{ file: 'FACILITY_HOURS.PDF' }], checked: 2, time: '1.0s' },
  donor: { html: 'Cowboy Club giving starts at <b style="color:var(--brand)">$100/yr</b> (Posse) and scales to <b style="color:var(--brand)">$25,000+</b> (Brand Champion). Each tier adds priority points toward seating and parking selection.', cites: [{ file: 'COWBOY_CLUB_LEVELS.PDF' }], checked: 3, time: '1.3s' },
  _default: { html: 'Here\u2019s what I found across your knowledge base. I\u2019ve cited the source documents below — open one to see the exact passage this answer is grounded in.', cites: [], checked: 2, time: '1.3s' },
};
function routeTopic(text) {
  const s = text.toLowerCase();
  if (/nil|eligib|recruit|complian|transfer|bylaw/.test(s)) return 'compliance';
  if (/per ?diem|travel|charter|hotel|road|flight/.test(s)) return 'travel';
  if (/ticket|gate|student section|fan|parking|will.?call/.test(s)) return 'ticketing';
  if (/gpa|study hall|tutor|academic|class/.test(s)) return 'academics';
  if (/field|weight room|facilit|equipment|reserve/.test(s)) return 'facilities';
  if (/donor|cowboy club|giving|suite|booster|tax receipt/.test(s)) return 'donor';
  return null;
}
const reply = (id) => REPLIES[id] || REPLIES._default;
const seedThread = (q, id) => { const r = reply(id); return [{ role: 'user', text: q }, { role: 'agent', html: r.html, cites: r.cites, checked: r.checked, time: r.time }]; };

const INITIAL_CONVERSATIONS = [
  { id: 'c1', title: 'NIL disclosure window', topicId: 'compliance', group: 'Today', messages: seedThread("What's the NIL disclosure window for athletes?", 'compliance') },
  { id: 'c2', title: 'Meal per diem on road trips', topicId: 'travel', group: 'Today', messages: seedThread("What's the meal per diem on road trips?", 'travel') },
  { id: 'c3', title: 'Student section entry rules', topicId: 'ticketing', group: 'Yesterday', messages: seedThread('What are the student section entry rules?', 'ticketing') },
  { id: 'c4', title: 'Minimum GPA to travel', topicId: 'academics', group: 'Yesterday', messages: seedThread("What's the minimum GPA to travel with the team?", 'academics') },
  { id: 'c5', title: 'Reserving the indoor field', topicId: 'facilities', group: 'Previous 7 days', messages: seedThread('How do I reserve the indoor field?', 'facilities') },
  { id: 'c6', title: 'Cowboy Club giving levels', topicId: 'donor', group: 'Previous 7 days', messages: seedThread('What are the Cowboy Club giving levels?', 'donor') },
];

/* ---------------- account ---------------- */
const USER_PROFILE = { name: 'Jordan Mitchell', initials: 'JM', email: 'j.mitchell@okstate.edu', org: 'OSU Athletics', role: 'Department admin', title: 'Director of Operations', dept: 'Athletics Administration', timezone: 'Central (CT)' };
const DEFAULT_PREFS = { scope: 'Entire knowledge base', language: 'English (US)', enterToSend: true };
const DEFAULT_NOTIFY = { digest: true, newSources: true, weekly: false, mentions: true, lowConfidence: true };

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "bg": "horizon",
  "motion": true,
  "density": "Comfortable",
  "sourcesDefault": true,
  "role": "Super admin"
}/*EDITMODE-END*/;

let convSeq = 100;
let kbSeq = 0;

function App() {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const [conversations, setConversations] = React.useState(INITIAL_CONVERSATIONS);
  const [topics, setTopics] = React.useState(TOPICS);
  const [activeId, setActiveId] = React.useState('c1');
  const [view, setView] = React.useState('chat');            // chat | knowledge
  const [sourcesOpen, setSourcesOpen] = React.useState(t.sourcesDefault);
  const [highlight, setHighlight] = React.useState({ file: 'NIL_POLICY_2025.PDF' });
  const [settingsSection, setSettingsSection] = React.useState(null);   // null | section id
  const [profile, setProfile] = React.useState(USER_PROFILE);
  const [prefs, setPrefs] = React.useState(DEFAULT_PREFS);
  const [notify, setNotify] = React.useState(DEFAULT_NOTIFY);

  const viewer = { ...profile, role: t.role };
  const isSuperAdmin = /super/i.test(t.role);

  const conv = conversations.find(c => c.id === activeId) || null;
  const topic = conv && conv.topicId ? TOPIC_BY_ID[conv.topicId] : null;
  const scope = topic || PLAYBOOK_ALL;
  const messages = conv ? conv.messages : [];
  const dense = t.density === 'Compact';
  const maxW = dense ? 680 : 760;

  const newChat = React.useCallback(() => {
    const id = 'n' + (++convSeq);
    setConversations(prev => [{ id, title: 'New chat', topicId: null, group: 'Today', messages: [] }, ...prev]);
    setActiveId(id); setView('chat'); setHighlight(null);
  }, []);

  React.useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'n') { e.preventDefault(); newChat(); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [newChat]);

  const openConv = (id) => { setActiveId(id); setView('chat'); setHighlight(null); };
  const renameConv = (id, title) => setConversations(prev => prev.map(c => c.id === id ? { ...c, title } : c));
  const deleteConv = (id) => {
    setConversations(prev => {
      let next = prev.filter(c => c.id !== id);
      if (id === activeId) {
        if (next.length === 0) {
          const nid = 'n' + (++convSeq);
          next = [{ id: nid, title: 'New chat', topicId: null, group: 'Today', messages: [] }];
          setActiveId(nid);
        } else {
          setActiveId(next[0].id);
        }
        setHighlight(null); setView('chat');
      }
      return next;
    });
  };
  const scopeTo = (topicId) => setConversations(prev => prev.map(c => c.id === activeId ? { ...c, topicId } : c));
  const createKB = () => {
    const id = 'kb' + (++kbSeq);
    const kb = { id, name: 'New knowledge base', icon: 'database', sources: 0, updated: 'just now', blurb: 'Add documents to start grounding answers from this knowledge base.', prompts: [], docs: [] };
    setTopics(prev => [...prev, kb]);
    return id;
  };
  const addDoc = (topicId) => setTopics(prev => prev.map(tp => tp.id === topicId
    ? { ...tp, sources: tp.sources + 1, updated: 'just now', docs: [...tp.docs, { file: 'NEW_DOCUMENT_' + (tp.docs.length + 1) + '.PDF', meta: 'Uploaded just now' }] }
    : tp));
  const removeDoc = (topicId, file) => setTopics(prev => prev.map(tp => tp.id === topicId
    ? { ...tp, sources: Math.max(0, tp.sources - 1), updated: 'just now', docs: tp.docs.filter(d => d.file !== file) }
    : tp));

  const send = (text) => {
    const id = activeId;
    const routed = (conv && conv.topicId) || routeTopic(text);
    setConversations(prev => prev.map(c => c.id === id ? {
      ...c, title: c.messages.length === 0 ? text.slice(0, 42) : c.title, topicId: c.topicId || routed,
      messages: [...c.messages, { role: 'user', text }, { role: 'agent', thinking: true }],
    } : c));
    if (t.sourcesDefault) setSourcesOpen(true);
    setTimeout(() => {
      const r = reply(routed);
      setConversations(prev => prev.map(c => {
        if (c.id !== id) return c;
        const arr = [...c.messages];
        arr[arr.length - 1] = { role: 'agent', html: r.html, cites: r.cites, checked: r.checked, time: r.time, stream: true };
        return { ...c, messages: arr };
      }));
      if (r.cites && r.cites[0]) setHighlight(r.cites[0]);
    }, 850);
  };

  // unified settings view for the modal
  const settings = {
    profile: viewer,
    prefs: { scope: prefs.scope, language: prefs.language, enterToSend: prefs.enterToSend, autoSources: t.sourcesDefault },
    notify,
    appearance: { bg: t.bg, motion: t.motion, density: t.density },
  };
  const changeSetting = (group, key, val) => {
    if (group === 'profile') setProfile(p => ({ ...p, [key]: val }));
    else if (group === 'notify') setNotify(n => ({ ...n, [key]: val }));
    else if (group === 'appearance') setTweak(key, val);
    else if (group === 'prefs') {
      if (key === 'autoSources') { setTweak('sourcesDefault', val); setSourcesOpen(val); }
      else setPrefs(p => ({ ...p, [key]: val }));
    }
  };
  const signOut = () => { window.location.href = 'Login.html'; };

  return (
    <div data-density={t.density} style={{ display: 'flex', height: '100%', width: '100%', background: 'var(--bg-base)' }}>
      <NavRail
        conversations={conversations} activeConvId={activeId} view={view} user={viewer}
        onNewChat={newChat} onSelectConv={openConv}
        onKnowledge={() => { window.location.href = 'Admin.html'; }}
        onOpenSettings={(sec) => setSettingsSection(sec)}
        onSignOut={signOut} />

      {view === 'knowledge'
        ? <KnowledgeView topics={topics} canManage={isSuperAdmin} onCreateKB={createKB} onAddDoc={addDoc} onRemoveDoc={removeDoc} onClose={() => setView('chat')} />
        : <div style={{ flex: 1, display: 'flex', minWidth: 0 }}>
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, position: 'relative' }}>
              <div className="bg-layer" aria-hidden="true">
                <BgField field={t.bg} motion={t.motion} />
              </div>
              <div style={{ position: 'relative', zIndex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, flex: 1 }}>
                {messages.length > 0 && <TopBar conv={conv} topic={topic} scope={scope} sourcesOpen={sourcesOpen} onToggleSources={() => setSourcesOpen(o => !o)} onRename={renameConv} onDelete={deleteConv} />}
                <ChatThread
                  messages={messages} topic={topic} topics={TOPICS} maxWidth={maxW} gap={dense ? 16 : 24}
                  onCite={(c) => { setHighlight(c); setSourcesOpen(true); }} onPickTopic={scopeTo} onPrompt={send} />
                <Composer onSend={send} maxWidth={maxW} enterToSend={prefs.enterToSend} />
              </div>
            </div>
            {sourcesOpen && <SourcesPanel scope={scope} highlight={highlight} onSelect={(file) => setHighlight({ file })} onClose={() => setSourcesOpen(false)} />}
          </div>}

      {settingsSection && (
        <SettingsModal section={settingsSection} onSection={setSettingsSection}
          settings={settings} onChange={changeSetting} onClose={() => setSettingsSection(null)} />
      )}

      <TweaksPanel>
        <TweakSection label="Ambient background" />
        <TweakRadio label="Field" value={t.bg} options={['plain', 'horizon', 'aurora', 'ember', 'grid']} onChange={(v) => setTweak('bg', v)} />
        <TweakToggle label="Background motion" value={t.motion} onChange={(v) => setTweak('motion', v)} />
        <TweakSection label="Workspace" />
        <TweakRadio label="Density" value={t.density} options={['Compact', 'Comfortable']} onChange={(v) => setTweak('density', v)} />
        <TweakToggle label="Sources panel by default" value={t.sourcesDefault} onChange={(v) => { setTweak('sourcesDefault', v); setSourcesOpen(v); }} />
        <TweakSection label="Permissions" />
        <TweakRadio label="Your role" value={t.role} options={['Department admin', 'Super admin']} onChange={(v) => setTweak('role', v)} />
      </TweaksPanel>
    </div>
  );
}

/* ---------------- knowledge base view ---------------- */
function KnowledgeView({ topics, canManage, onCreateKB, onAddDoc, onRemoveDoc, onClose }) {
  const [openId, setOpenId] = React.useState(null);
  const total = topics.reduce((n, t) => n + t.sources, 0);
  const open = openId ? topics.find(tp => tp.id === openId) : null;

  if (open) {
    return <KnowledgeDetail topic={open} canManage={canManage}
      onAddDoc={() => onAddDoc(open.id)} onRemoveDoc={(f) => onRemoveDoc(open.id, f)}
      onBack={() => setOpenId(null)} onClose={onClose} />;
  }

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, background: 'var(--bg-base)' }}>
      <header style={{ height: 64, flex: 'none', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 13, padding: '0 22px' }}>
        <div style={{ width: 34, height: 34, borderRadius: 'var(--radius-md)', background: 'var(--surface-hover)', color: 'var(--brand)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Icon name="database" size={18} /></div>
        <div style={{ lineHeight: 1.3 }}>
          <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 16, color: 'var(--fg-1)' }}>Knowledge base</div>
          <div style={{ fontFamily: 'var(--font-body)', fontSize: 12.5, color: 'var(--fg-3)' }}>{total} sources across {topics.length} areas</div>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10 }}>
          {canManage && <PBButton variant="primary" size="sm" icon="plus" onClick={() => setOpenId(onCreateKB())}>New knowledge base</PBButton>}
          <IconBtn name="x" onClick={onClose} />
        </div>
      </header>
      <div style={{ flex: 1, overflowY: 'auto', padding: '28px' }}>
        <div style={{ maxWidth: 960, margin: '0 auto' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 16 }}>
            {topics.map(tp => <KnowledgeCard key={tp.id} topic={tp} onClick={() => setOpenId(tp.id)} />)}
          </div>
        </div>
      </div>
    </div>
  );
}

function KnowledgeCard({ topic, onClick }) {
  const [hover, setHover] = React.useState(false);
  return (
    <div onClick={onClick} onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{ padding: 18, borderRadius: 'var(--radius-lg)', cursor: 'pointer',
        background: hover ? 'var(--surface-raised)' : 'var(--surface)',
        border: '1px solid ' + (hover ? 'var(--border-brand)' : 'var(--border-strong)'), transition: 'background var(--dur-fast), border-color var(--dur-fast)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 11, marginBottom: 12 }}>
        <div style={{ width: 38, height: 38, flex: 'none', borderRadius: 'var(--radius-md)', background: 'var(--brand-soft)', color: 'var(--brand)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Icon name={topic.icon} size={19} /></div>
        <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 15.5, color: 'var(--fg-1)', flex: 1, minWidth: 0 }}>{topic.name}</div>
        <Icon name="chevron-right" size={18} style={{ flex: 'none', color: hover ? 'var(--brand)' : 'var(--fg-4)' }} />
      </div>
      <div style={{ fontFamily: 'var(--font-body)', fontSize: 13, color: 'var(--fg-3)', lineHeight: 1.5, minHeight: 58 }}>{topic.blurb}</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--border)', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--fg-3)' }}>
        <span>{topic.sources} {topic.sources === 1 ? 'source' : 'sources'}</span>
        <span style={{ color: 'var(--fg-4)' }}>·</span>
        <span>updated {topic.updated}</span>
      </div>
    </div>
  );
}

function KnowledgeDetail({ topic, canManage, onAddDoc, onRemoveDoc, onBack, onClose }) {
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, background: 'var(--bg-base)' }}>
      <header style={{ height: 64, flex: 'none', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 12, padding: '0 22px' }}>
        <button onClick={onBack} title="Back to knowledge base"
          style={{ width: 34, height: 34, flex: 'none', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)', background: 'transparent', color: 'var(--fg-2)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--surface-hover)'; e.currentTarget.style.color = 'var(--fg-1)'; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--fg-2)'; }}>
          <Icon name="arrow-left" size={18} />
        </button>
        <div style={{ width: 34, height: 34, flex: 'none', borderRadius: 'var(--radius-md)', background: 'var(--brand-soft)', color: 'var(--brand)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Icon name={topic.icon} size={18} /></div>
        <div style={{ lineHeight: 1.3, minWidth: 0 }}>
          <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 16, color: 'var(--fg-1)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{topic.name}</div>
          <div style={{ fontFamily: 'var(--font-body)', fontSize: 12.5, color: 'var(--fg-3)' }}>{topic.sources} {topic.sources === 1 ? 'document' : 'documents'} · updated {topic.updated}</div>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10 }}>
          {canManage && <PBButton variant="primary" size="sm" icon="plus" onClick={onAddDoc}>Add document</PBButton>}
          <IconBtn name="x" onClick={onClose} />
        </div>
      </header>
      <div style={{ flex: 1, overflowY: 'auto', padding: '24px 28px' }}>
        <div style={{ maxWidth: 760, margin: '0 auto' }}>
          <div style={{ fontFamily: 'var(--font-body)', fontSize: 13, color: 'var(--fg-3)', lineHeight: 1.55, marginBottom: 18, maxWidth: 560 }}>{topic.blurb}</div>
          <div style={{ fontFamily: 'var(--font-body)', fontSize: 11.5, fontWeight: 600, color: 'var(--fg-3)', letterSpacing: '0.04em', textTransform: 'uppercase', marginBottom: 10 }}>Documents</div>
          {topic.docs.length === 0 ? (
            <div style={{ padding: '40px 0', textAlign: 'center', fontFamily: 'var(--font-body)', fontSize: 13.5, color: 'var(--fg-4)' }}>
              No documents yet.{canManage ? ' Add one to start grounding answers here.' : ''}
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {topic.docs.map(d => <DocRow key={d.file} doc={d} canManage={canManage} onRemove={() => onRemoveDoc(d.file)} />)}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function DocRow({ doc, canManage, onRemove }) {
  const [hover, setHover] = React.useState(false);
  const ext = (doc.file.split('.').pop() || '').toLowerCase();
  return (
    <div onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{ display: 'flex', alignItems: 'center', gap: 13, padding: '12px 14px', borderRadius: 'var(--radius-md)',
        background: hover ? 'var(--surface-raised)' : 'var(--surface)', border: '1px solid ' + (hover ? 'var(--border-strong)' : 'var(--border)'), transition: 'background var(--dur-fast)' }}>
      <div style={{ width: 34, height: 34, flex: 'none', borderRadius: 'var(--radius-sm)', background: 'var(--surface-hover)', color: 'var(--fg-2)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Icon name="file-text" size={17} /></div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontFamily: 'var(--font-body)', fontWeight: 600, fontSize: 13.5, color: 'var(--fg-1)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{doc.file}</div>
        <div style={{ fontFamily: 'var(--font-body)', fontSize: 12, color: 'var(--fg-3)', marginTop: 1 }}>{doc.meta}</div>
      </div>
      <span style={{ flex: 'none', fontFamily: 'var(--font-mono)', fontSize: 10.5, fontWeight: 600, color: 'var(--fg-3)', background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: 'var(--radius-xs)', padding: '3px 7px', textTransform: 'uppercase' }}>{ext}</span>
      {canManage && (
        <button onClick={onRemove} title="Remove document"
          style={{ width: 30, height: 30, flex: 'none', borderRadius: 'var(--radius-sm)', border: 0, cursor: 'pointer', background: 'transparent', color: 'var(--fg-4)', display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: hover ? 1 : 0, transition: 'opacity var(--dur-fast)' }}
          onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--danger-bg)'; e.currentTarget.style.color = 'var(--danger)'; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--fg-4)'; }}>
          <Icon name="trash" size={16} />
        </button>
      )}
    </div>
  );
}

function mount() {
  if (typeof useTweaks === 'undefined' || typeof TweaksPanel === 'undefined' || typeof NavRail === 'undefined' || typeof ChatThread === 'undefined' || typeof SettingsModal === 'undefined') {
    return setTimeout(mount, 25);
  }
  ReactDOM.createRoot(document.getElementById('root')).render(<App />);
}
mount();
