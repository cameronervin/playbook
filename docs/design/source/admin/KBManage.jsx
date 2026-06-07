/* KBManage.jsx — admin knowledge base in the collections format: see how
   documents are divided across collections, open one to manage its documents.
   Status only surfaces while a document is processing or has failed; ready
   documents read clean. Create/delete gated to super admin; metadata edits
   available to all admins. */

function KBManage({ collections, docs, canManage, onUpload, onRetry, onDelete, onToggleOfficial, onSaveMeta, onCreateCollection }) {
  const [openId, setOpenId] = React.useState(null);
  const [editId, setEditId] = React.useState(null);

  const docsFor = (cid) => docs.filter(d => d.collId === cid);
  const open = openId ? collections.find(c => c.id === openId) : null;
  const editing = editId ? docs.find(d => d.id === editId) : null;

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, background: 'var(--bg-base)' }}>
      {open
        ? <CollectionDetail coll={open} docs={docsFor(open.id)} canManage={canManage}
            onBack={() => setOpenId(null)} onUpload={() => onUpload(open.id)}
            onEdit={setEditId} onRetry={onRetry} onDelete={onDelete} onToggleOfficial={onToggleOfficial} />
        : <CollectionGrid collections={collections} docsFor={docsFor} canManage={canManage}
            onOpen={setOpenId} onCreate={() => setOpenId(onCreateCollection())} />}

      {editing && (
        <MetaDrawer doc={editing} canManage={canManage} onClose={() => setEditId(null)}
          onSave={(patch) => { onSaveMeta(editing.id, patch); setEditId(null); }}
          onRetry={() => { onRetry(editing.id); setEditId(null); }}
          onDelete={() => { onDelete(editing.id); setEditId(null); }} />
      )}
    </div>
  );
}

/* ---- collections grid ---- */
function CollectionGrid({ collections, docsFor, canManage, onOpen, onCreate }) {
  const total = collections.reduce((n, c) => n + docsFor(c.id).length, 0);
  return (
    <React.Fragment>
      <PageHeader title="Knowledge base" sub={total + ' documents across ' + collections.length + ' collections'}>
        {canManage
          ? <PBButton variant="secondary" size="sm" icon="plus" onClick={onCreate}>New collection</PBButton>
          : <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7, fontFamily: 'var(--font-body)', fontSize: 12, color: 'var(--fg-3)' }}><Icon name="lock" size={14} />Managed by super admins</span>}
      </PageHeader>
      <div style={{ flex: 1, overflowY: 'auto', padding: '24px 28px 40px' }}>
        <div style={{ maxWidth: 1000, margin: '0 auto', display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 16 }}>
          {collections.map(c => <CollectionCard key={c.id} coll={c} docs={docsFor(c.id)} onClick={() => onOpen(c.id)} />)}
        </div>
      </div>
    </React.Fragment>
  );
}

function CollectionCard({ coll, docs, onClick }) {
  const [hover, setHover] = React.useState(false);
  const failed = docs.filter(d => d.status === 'failed').length;
  const loading = docs.filter(d => d.status === 'processing' || d.status === 'uploaded').length;
  let foot;
  if (failed > 0) foot = <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: 'var(--danger)' }}><Icon name="alert-triangle" size={13} />{failed} {failed === 1 ? 'needs' : 'need'} attention</span>;
  else if (loading > 0) foot = <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: 'var(--info)' }}><Icon name="loader" size={13} className="pb-spin" />{loading} processing</span>;
  else foot = <span style={{ color: 'var(--fg-3)' }}>{docs.length === 0 ? 'No documents yet' : 'All ready'}</span>;
  return (
    <div onClick={onClick} onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{ padding: 18, borderRadius: 'var(--radius-lg)', cursor: 'pointer',
        background: hover ? 'var(--surface-raised)' : 'var(--surface)',
        border: '1px solid ' + (hover ? 'var(--border-brand)' : 'var(--border-strong)'), transition: 'background var(--dur-fast), border-color var(--dur-fast)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 11, marginBottom: 12 }}>
        <div style={{ width: 38, height: 38, flex: 'none', borderRadius: 'var(--radius-md)', background: 'var(--brand-soft)', color: 'var(--brand)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Icon name={coll.icon} size={19} /></div>
        <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 15.5, color: 'var(--fg-1)', flex: 1, minWidth: 0 }}>{coll.name}</div>
        <Icon name="chevron-right" size={18} style={{ flex: 'none', color: hover ? 'var(--brand)' : 'var(--fg-4)' }} />
      </div>
      <div style={{ fontFamily: 'var(--font-body)', fontSize: 13, color: 'var(--fg-3)', lineHeight: 1.5, minHeight: 58 }}>{coll.blurb}</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--border)', fontFamily: 'var(--font-body)', fontSize: 12, color: 'var(--fg-2)' }}>
        <span style={{ fontWeight: 600 }}>{docs.length} {docs.length === 1 ? 'document' : 'documents'}</span>
        <span style={{ color: 'var(--fg-4)' }}>·</span>
        {foot}
      </div>
    </div>
  );
}

/* ---- collection detail: documents within ---- */
function CollectionDetail({ coll, docs, canManage, onBack, onUpload, onEdit, onRetry, onDelete, onToggleOfficial }) {
  return (
    <React.Fragment>
      <PageHeader title={coll.name} sub={docs.length + ' ' + (docs.length === 1 ? 'document' : 'documents') + ' · grounds athlete answers'}>
        <PBButton variant="secondary" size="sm" icon="arrow-left" onClick={onBack}>All collections</PBButton>
        {canManage && <PBButton variant="primary" size="sm" icon="upload" onClick={onUpload}>Upload document</PBButton>}
      </PageHeader>
      <div style={{ flex: 1, overflowY: 'auto', padding: '22px 28px 40px' }}>
        <div style={{ maxWidth: 760, margin: '0 auto' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 11, marginBottom: 16, padding: '12px 14px', background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)' }}>
            <div style={{ width: 32, height: 32, flex: 'none', borderRadius: 'var(--radius-sm)', background: 'var(--brand-soft)', color: 'var(--brand)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Icon name={coll.icon} size={17} /></div>
            <span style={{ fontFamily: 'var(--font-body)', fontSize: 13, color: 'var(--fg-3)', lineHeight: 1.5 }}>{coll.blurb}</span>
          </div>
          {docs.length === 0 ? (
            <EmptyState icon="database" title="No documents yet" body={canManage ? 'Upload department documents to start grounding answers from this collection.' : 'A super admin hasn\u2019t added documents to this collection yet.'}>
              {canManage && <PBButton variant="secondary" size="sm" icon="upload" onClick={onUpload}>Upload document</PBButton>}
            </EmptyState>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
              {docs.map(d => <DocItem key={d.id} doc={d} canManage={canManage}
                onEdit={() => onEdit(d.id)} onRetry={() => onRetry(d.id)} onDelete={() => onDelete(d.id)} onToggleOfficial={() => onToggleOfficial(d.id)} />)}
            </div>
          )}
        </div>
      </div>
    </React.Fragment>
  );
}

function DocItem({ doc, canManage, onEdit, onRetry, onDelete, onToggleOfficial }) {
  const [hover, setHover] = React.useState(false);
  const [menu, setMenu] = React.useState(false);
  const ext = (doc.title.split('.').pop() || '').toLowerCase();
  const loading = doc.status === 'processing' || doc.status === 'uploaded';
  const failed = doc.status === 'failed';
  return (
    <div onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{ borderRadius: 'var(--radius-md)', background: hover ? 'var(--surface-raised)' : 'var(--surface)', border: '1px solid ' + (failed ? 'rgba(240,86,63,0.3)' : (hover ? 'var(--border-strong)' : 'var(--border)')), transition: 'background var(--dur-fast)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 13, padding: '12px 14px' }}>
        <div style={{ width: 34, height: 34, flex: 'none', borderRadius: 'var(--radius-sm)', background: 'var(--surface-hover)', color: failed ? 'var(--danger)' : 'var(--fg-2)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Icon name="file-text" size={17} /></div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, fontSize: 13, color: 'var(--fg-1)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 280 }}>{doc.title}</span>
            {doc.official && <Icon name="shield-check" size={14} style={{ color: 'var(--success)', flex: 'none' }} title="Official" />}
          </div>
          <div style={{ fontFamily: 'var(--font-body)', fontSize: 12, color: 'var(--fg-3)', marginTop: 2 }}>{doc.size} · {doc.uploaded} · {doc.uploader}{doc.priority === 'High' ? ' · High priority' : ''}</div>
        </div>

        {/* tags */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 5, flex: 'none' }}>
          {doc.tags.slice(0, 2).map(t => <TopicChip key={t} label={t} />)}
        </div>

        {/* status — only while loading or failed */}
        {loading && <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontFamily: 'var(--font-body)', fontSize: 12, fontWeight: 600, color: 'var(--info)', flex: 'none' }}><Icon name="loader" size={14} className="pb-spin" />Processing</span>}
        {failed && <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontFamily: 'var(--font-body)', fontSize: 12, fontWeight: 600, color: 'var(--danger)', flex: 'none' }}><Icon name="alert-triangle" size={14} />Failed</span>}
        {!loading && !failed && <span style={{ flex: 'none', fontFamily: 'var(--font-mono)', fontSize: 10.5, fontWeight: 600, color: 'var(--fg-3)', background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: 'var(--radius-xs)', padding: '3px 7px', textTransform: 'uppercase' }}>{ext}</span>}

        {/* actions */}
        <div style={{ position: 'relative', flex: 'none' }}>
          <button onClick={() => setMenu(m => !m)} style={{ width: 30, height: 30, borderRadius: 'var(--radius-sm)', border: 0, cursor: 'pointer', background: menu ? 'var(--surface-hover)' : 'transparent', color: 'var(--fg-2)', display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: (hover || menu) ? 1 : 0.4 }}>
            <Icon name="more-horizontal" size={18} />
          </button>
          {menu && (
            <React.Fragment>
              <div onClick={() => setMenu(false)} style={{ position: 'fixed', inset: 0, zIndex: 40 }} />
              <div style={{ position: 'absolute', top: 'calc(100% + 4px)', right: 0, zIndex: 41, width: 192, background: 'var(--surface-raised)', border: '1px solid var(--border-strong)', borderRadius: 'var(--radius-md)', boxShadow: 'var(--shadow-lg)', overflow: 'hidden', padding: 6, animation: 'pbmenu var(--dur-med) var(--ease-out) both' }}>
                <RowMenuItem icon="pencil" label="Edit metadata" onClick={() => { setMenu(false); onEdit(); }} />
                <RowMenuItem icon="shield-check" label={doc.official ? 'Remove official flag' : 'Mark official'} onClick={() => { setMenu(false); onToggleOfficial(); }} />
                {failed && canManage && <RowMenuItem icon="refresh-cw" label="Retry processing" onClick={() => { setMenu(false); onRetry(); }} />}
                {canManage && <RowMenuItem icon="trash" label="Delete / archive" danger onClick={() => { setMenu(false); onDelete(); }} />}
              </div>
            </React.Fragment>
          )}
        </div>
      </div>
      {failed && doc.reason && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 9, margin: '0 14px 12px 61px', padding: '9px 12px', background: 'var(--danger-bg)', border: '1px solid rgba(240,86,63,0.3)', borderRadius: 'var(--radius-sm)' }}>
          <Icon name="alert-triangle" size={14} style={{ color: 'var(--danger)', flex: 'none' }} />
          <span style={{ fontFamily: 'var(--font-body)', fontSize: 12, color: 'var(--fg-2)', flex: 1 }}>{doc.reason}</span>
          {canManage && <button onClick={onRetry} style={{ display: 'inline-flex', alignItems: 'center', gap: 5, border: 0, background: 'transparent', color: 'var(--danger)', fontFamily: 'var(--font-body)', fontWeight: 600, fontSize: 12, cursor: 'pointer' }}><Icon name="refresh-cw" size={13} />Retry</button>}
        </div>
      )}
    </div>
  );
}

function RowMenuItem({ icon, label, danger, onClick }) {
  const [hover, setHover] = React.useState(false);
  return (
    <button type="button" onClick={onClick} onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 10, padding: '8px 9px', border: 0, cursor: 'pointer', borderRadius: 'var(--radius-sm)', textAlign: 'left',
        background: hover ? (danger ? 'var(--danger-bg)' : 'var(--surface-hover)') : 'transparent',
        color: danger ? 'var(--danger)' : (hover ? 'var(--fg-1)' : 'var(--fg-2)'), fontFamily: 'var(--font-body)', fontWeight: 500, fontSize: 13 }}>
      <Icon name={icon} size={16} style={{ flex: 'none', color: danger ? 'var(--danger)' : (hover ? 'var(--brand)' : 'var(--fg-3)') }} />{label}
    </button>
  );
}

/* ---- metadata edit drawer ---- */
function MetaDrawer({ doc, canManage, onClose, onSave, onRetry, onDelete }) {
  const [tags, setTags] = React.useState(doc.tags.join(', '));
  const [official, setOfficial] = React.useState(doc.official);
  const [priority, setPriority] = React.useState(doc.priority);
  const [sourceDate, setSourceDate] = React.useState(doc.source_date === '—' ? '' : doc.source_date);
  const [visibility, setVisibility] = React.useState(doc.visibility);

  const save = () => onSave({ tags: tags.split(',').map(s => s.trim()).filter(Boolean), official, priority, source_date: sourceDate || '—', visibility });

  return (
    <React.Fragment>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, zIndex: 60, background: 'rgba(8,7,5,0.55)', animation: 'pbfade var(--dur-med) var(--ease-out) both' }} />
      <aside style={{ position: 'fixed', top: 0, right: 0, bottom: 0, width: 400, zIndex: 61, background: 'var(--bg-page)', borderLeft: '1px solid var(--border-strong)', boxShadow: 'var(--shadow-lg)', display: 'flex', flexDirection: 'column', animation: 'pbpanel var(--dur-med) var(--ease-out) both' }}>
        <div style={{ height: 60, flex: 'none', display: 'flex', alignItems: 'center', gap: 11, padding: '0 18px', borderBottom: '1px solid var(--border)' }}>
          <Icon name="pencil" size={17} style={{ color: 'var(--brand)' }} />
          <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 15, color: 'var(--fg-1)' }}>Edit metadata</div>
          <div style={{ marginLeft: 'auto' }}><IconBtn name="x" onClick={onClose} /></div>
        </div>
        <div style={{ flex: 1, overflowY: 'auto', padding: '18px 18px 24px', display: 'flex', flexDirection: 'column', gap: 18 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 11, padding: '12px 13px', background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)' }}>
            <div style={{ width: 32, height: 32, flex: 'none', borderRadius: 'var(--radius-sm)', background: 'var(--surface-hover)', color: 'var(--brand)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Icon name="file-text" size={16} /></div>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12.5, color: 'var(--fg-1)', fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{doc.title}</div>
              <div style={{ fontFamily: 'var(--font-body)', fontSize: 11.5, color: 'var(--fg-3)', marginTop: 1 }}>{doc.type} · {doc.size} · {doc.uploaded}</div>
            </div>
          </div>

          <Field label="Metadata tags" hint="Helps retrieval prefer the right sources">
            <input value={tags} onChange={(e) => setTags(e.target.value)} placeholder="NIL, Compliance" style={inputStyle} />
          </Field>

          <Field label="Priority" hint="Higher priority is preferred at retrieval">
            <Segmented options={['Low', 'Normal', 'High']} value={priority} onChange={setPriority} size="sm" />
          </Field>

          <Field label="Source date">
            <input value={sourceDate} onChange={(e) => setSourceDate(e.target.value)} placeholder="e.g. Mar 2026" style={inputStyle} />
          </Field>

          <Field label="Visibility">
            <div style={{ display: 'inline-block' }}>
              <FilterSelect value={visibility} options={['All athletes', 'Compliance staff', 'Coaches only']} onChange={setVisibility} />
            </div>
          </Field>

          <div onClick={() => setOfficial(o => !o)} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '13px 14px', background: 'var(--surface)', border: '1px solid ' + (official ? 'var(--border-brand)' : 'var(--border)'), borderRadius: 'var(--radius-md)', cursor: 'pointer' }}>
            <Icon name="shield-check" size={17} style={{ color: official ? 'var(--success)' : 'var(--fg-4)', flex: 'none' }} />
            <div style={{ flex: 1 }}>
              <div style={{ fontFamily: 'var(--font-body)', fontSize: 13, fontWeight: 600, color: 'var(--fg-1)' }}>Official source</div>
              <div style={{ fontFamily: 'var(--font-body)', fontSize: 11.5, color: 'var(--fg-3)' }}>Prefer this document when answers conflict</div>
            </div>
            <span style={{ width: 38, height: 22, borderRadius: 'var(--radius-pill)', background: official ? 'var(--brand)' : 'var(--surface-hover)', position: 'relative', flex: 'none', transition: 'background var(--dur-fast)' }}>
              <span style={{ position: 'absolute', top: 2, left: official ? 18 : 2, width: 18, height: 18, borderRadius: '50%', background: official ? 'var(--fg-on-brand)' : 'var(--fg-3)', transition: 'left var(--dur-fast)' }} />
            </span>
          </div>

          {doc.status === 'failed' && canManage && (
            <PBButton variant="secondary" size="md" icon="refresh-cw" onClick={onRetry} style={{ justifyContent: 'center' }}>Retry processing</PBButton>
          )}
        </div>
        <div style={{ flex: 'none', padding: '14px 18px', borderTop: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 10 }}>
          {canManage && <button onClick={onDelete} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, border: 0, background: 'transparent', color: 'var(--danger)', fontFamily: 'var(--font-body)', fontWeight: 600, fontSize: 13, cursor: 'pointer' }}><Icon name="trash" size={15} />Delete</button>}
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
            <PBButton variant="secondary" size="sm" onClick={onClose}>Cancel</PBButton>
            <PBButton variant="primary" size="sm" onClick={save}>Save changes</PBButton>
          </div>
        </div>
      </aside>
    </React.Fragment>
  );
}

const inputStyle = { width: '100%', padding: '9px 12px', background: 'var(--surface)', border: '1px solid var(--border-strong)', borderRadius: 'var(--radius-md)', color: 'var(--fg-1)', fontFamily: 'var(--font-body)', fontSize: 13, outline: 'none' };
function Field({ label, hint, children }) {
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 8 }}>
        <SectionLabel>{label}</SectionLabel>
        {hint && <span style={{ fontFamily: 'var(--font-body)', fontSize: 11, color: 'var(--fg-4)' }}>{hint}</span>}
      </div>
      {children}
    </div>
  );
}

window.KBManage = KBManage;
