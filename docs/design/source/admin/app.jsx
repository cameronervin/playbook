/* app.jsx — Playbook admin console. Admin-only surface: an Insights dashboard
   (analytics + AI summary), knowledge-base management, and super-admin users
   & roles. Athlete role is hard-gated out. Cosmetic data only. */

const ADMIN_USER = { name: 'Jordan Mitchell', initials: 'JM', email: 'j.mitchell@okstate.edu', org: 'OSU Athletics' };

const ADMIN_TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "role": "Super admin",
  "chatDefault": false
}/*EDITMODE-END*/;

const WINDOW_LABEL = { '7d': 'May 27 – Jun 3', '30d': 'May 4 – Jun 3', 'custom': 'Custom range' };
let docSeq = 0;

function AdminApp() {
  const [t, setTweak] = useTweaks(ADMIN_TWEAK_DEFAULTS);
  const role = t.role;
  const isAthlete = /athlete/i.test(role);
  const isSuperAdmin = /super/i.test(role);

  const [route, setRoute] = React.useState('insights');
  const [timeWindow, setTimeWindow] = React.useState('7d');
  const [chatOpen, setChatOpen] = React.useState(t.chatDefault);
  const [chatMsgs, setChatMsgs] = React.useState([]);
  const [chatBusy, setChatBusy] = React.useState(false);

  const [insight, setInsight] = React.useState(ADMIN_INSIGHT);
  const [insightStatus, setInsightStatus] = React.useState('idle');

  const [docs, setDocs] = React.useState(ADMIN_DOCS);
  const [collections, setCollections] = React.useState(ADMIN_KB_COLLECTIONS);
  const [users, setUsers] = React.useState(ADMIN_USERS);
  const [settingsSection, setSettingsSection] = React.useState(null);
  const [profile, setProfile] = React.useState({ name: ADMIN_USER.name, title: 'Director of Operations', dept: 'Athletics Administration', email: ADMIN_USER.email });

  const failedDocs = docs.filter(d => d.status === 'failed').length;

  // guard super-admin-only route if role drops
  React.useEffect(() => {
    if (!isSuperAdmin && route === 'users') setRoute('insights');
  }, [isSuperAdmin, route]);

  /* ----- admin chat ----- */
  const sendChat = (text) => {
    setChatMsgs(prev => [...prev, { role: 'user', text }]);
    setChatBusy(true);
    setTimeout(() => {
      const r = adminChatReply(text);
      setChatMsgs(prev => [...prev, { role: 'agent', answer: r.answer, refs: r.refs, answer_type: r.answer_type, stream: true }]);
      setChatBusy(false);
    }, 750);
  };
  const openChat = () => setChatOpen(true);

  /* ----- insight generation ----- */
  const generateInsight = (win) => {
    if (insightStatus === 'processing') return;
    setInsightStatus('processing');
    setTimeout(() => {
      setInsight(prev => ({ ...prev, generated_at: 'Just now', window_label: (WINDOW_LABEL[win] || 'May 27 – Jun 3') + (win === '30d' ? ' (30 days)' : ' (7 days)') }));
      setInsightStatus('idle');
    }, 2200);
  };

  /* ----- KB mutations ----- */
  const retryDoc = (id) => {
    setDocs(prev => prev.map(d => d.id === id ? { ...d, status: 'processing', reason: null } : d));
    setTimeout(() => setDocs(prev => prev.map(d => d.id === id ? { ...d, status: 'ready' } : d)), 2200);
  };
  const deleteDoc = (id) => setDocs(prev => prev.filter(d => d.id !== id));
  const toggleOfficial = (id) => setDocs(prev => prev.map(d => d.id === id ? { ...d, official: !d.official } : d));
  const saveMeta = (id, patch) => setDocs(prev => prev.map(d => d.id === id ? { ...d, ...patch } : d));
  const uploadDoc = (collId) => {
    const id = 'doc_up_' + (++docSeq);
    const title = 'NEW_UPLOAD_' + docSeq + '.PDF';
    const nd = { id, collId, title, type: 'PDF', size: '0.9 MB', status: 'processing', uploaded: 'Just now', uploader: 'You', tags: [], official: false, priority: 'Normal', source_date: '—', visibility: 'All athletes', reason: null };
    setDocs(prev => [nd, ...prev]);
    setTimeout(() => setDocs(prev => prev.map(d => d.id === id ? { ...d, status: 'ready' } : d)), 2600);
  };
  const createCollection = () => {
    const id = 'coll_' + (++docSeq);
    setCollections(prev => [...prev, { id, name: 'New collection', icon: 'database', blurb: 'Add documents to start grounding answers from this collection.' }]);
    return id;
  };

  /* ----- role mutations ----- */
  const changeRole = (id, newRole) => setUsers(prev => prev.map(x => x.id === id ? { ...x, role: newRole } : x));

  const signOut = () => { window.location.href = 'Login.html'; };
  const chatWorkspace = () => { window.location.href = 'Home.html'; };

  const settings = { profile: { ...profile, role: isSuperAdmin ? 'Super admin' : 'Department admin' } };
  const changeSetting = (group, key, val) => { if (group === 'profile') setProfile(p => ({ ...p, [key]: val })); };

  if (isAthlete) return <AccessDenied />;

  const counts = { failedDocs };

  let main = null;
  if (route === 'insights') main = <Dashboard summary={ADMIN_SUMMARY} insight={insight} timeWindow={timeWindow} onTimeWindow={setTimeWindow} onGenerate={generateInsight} onOpenChat={openChat} insightStatus={insightStatus} />;
  else if (route === 'kb') main = <KBManage collections={collections} docs={docs} canManage={isSuperAdmin} onUpload={uploadDoc} onRetry={retryDoc} onDelete={deleteDoc} onToggleOfficial={toggleOfficial} onSaveMeta={saveMeta} onCreateCollection={createCollection} />;
  else if (route === 'users') main = <UsersView users={users} onChangeRole={changeRole} />;

  return (
    <div style={{ display: 'flex', height: '100%', width: '100%', background: 'var(--bg-base)' }}>
      <AdminNav active={route} onNavigate={setRoute} user={ADMIN_USER} isSuperAdmin={isSuperAdmin} counts={counts} onOpenSettings={(sec) => setSettingsSection(sec)} onChatWorkspace={chatWorkspace} onSignOut={signOut} />
      <div style={{ flex: 1, display: 'flex', minWidth: 0 }}>
        {main}
        <AdminChat open={chatOpen} messages={chatMsgs} onSend={sendChat} onClose={() => setChatOpen(false)} busy={chatBusy} />
      </div>

      {settingsSection && (
        <SettingsModal section={settingsSection} onSection={setSettingsSection}
          settings={settings} onChange={changeSetting} onClose={() => setSettingsSection(null)} />
      )}

      <TweaksPanel>
        <TweakSection label="Access" />
        <TweakRadio label="Your role" value={t.role} options={['Athlete', 'Department admin', 'Super admin']} onChange={(v) => setTweak('role', v)} />
        <TweakSection label="Workspace" />
        <TweakToggle label="Analytics chat open by default" value={t.chatDefault} onChange={(v) => { setTweak('chatDefault', v); setChatOpen(v); }} />
      </TweaksPanel>
    </div>
  );
}

function AccessDenied() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', width: '100%', background: 'var(--bg-base)', textAlign: 'center', padding: 24, position: 'relative' }}>
      <div className="admin-grid" style={{ opacity: 0.5 }} />
      <div style={{ position: 'relative', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16, maxWidth: 420 }}>
        <div style={{ width: 60, height: 60, borderRadius: 'var(--radius-lg)', background: 'var(--surface)', border: '1px solid var(--border-strong)', color: 'var(--fg-3)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Icon name="lock" size={26} /></div>
        <div style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 24, letterSpacing: '-0.01em', color: 'var(--fg-1)', textTransform: 'uppercase' }}>Admins only</div>
        <p style={{ margin: 0, fontFamily: 'var(--font-body)', fontSize: 14.5, lineHeight: 1.6, color: 'var(--fg-3)' }}>The admin console is restricted to department admins. Your account doesn’t have access to insights, analytics, or knowledge-base management.</p>
        <PBButton variant="secondary" size="md" icon="message-circle" onClick={() => { window.location.href = 'Home.html'; }}>Back to chat workspace</PBButton>
        <div style={{ marginTop: 4, fontFamily: 'var(--font-body)', fontSize: 12, color: 'var(--fg-4)' }}>Switch role in Tweaks to preview the admin views.</div>
      </div>
    </div>
  );
}

function mountAdmin() {
  if (typeof useTweaks === 'undefined' || typeof TweaksPanel === 'undefined' || typeof AdminNav === 'undefined' ||
      typeof Dashboard === 'undefined' || typeof KBManage === 'undefined' || typeof UsersView === 'undefined' ||
      typeof AdminChat === 'undefined' || typeof PBButton === 'undefined' || typeof Card === 'undefined' || typeof SettingsModal === 'undefined') {
    return setTimeout(mountAdmin, 25);
  }
  ReactDOM.createRoot(document.getElementById('root')).render(<AdminApp />);
}
mountAdmin();
