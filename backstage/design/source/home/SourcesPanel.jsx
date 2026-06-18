/* SourcesPanel.jsx — right context panel: the documents Playbook grounded the
   answer in. Selecting a source reveals the exact passage the answer drew from. */

const EXCERPTS = {
  'NIL_POLICY_2025.PDF': { page: 'p. 4 · §2.1', html: 'Student-athletes must disclose any name, image, and likeness agreement valued at <mark>$600 or more</mark> to the compliance office within <mark>72 hours</mark> of execution. Agreements that reference university marks, facilities, or uniforms require an additional brand-use review prior to finalization.' },
  'NCAA_BYLAW_13.PDF': { page: 'p. 11 · §13.1', html: 'Recruiting contact may not occur during a <mark>dead period</mark>. Permissible activities are limited to those expressly authorized under Bylaw 13.1, and all in-person contact must be logged within two business days.' },
  'ELIGIBILITY_CHECKLIST.DOCX': { page: 'p. 1', html: 'Confirm amateurism certification, academic progress, and a current physical on file before the first date of competition.' },
  'TRANSFER_PORTAL_SOP.PDF': { page: 'p. 2', html: 'An athlete\u2019s name is entered into the transfer portal within <mark>two business days</mark> of a written transfer request submitted to the compliance office.' },
  'PER_DIEM_RATES.XLSX': { page: 'Sheet: 2025 rates', html: 'Daily meal per diem: <mark>$65.00</mark> \u2014 Breakfast $15 / Lunch $20 / Dinner $30. Provided team meals are deducted from the corresponding daily allotment.' },
  'TRAVEL_POLICY_2025.PDF': { page: 'p. 9 · §4', html: 'Per diem is issued for each full day of authorized team travel. Partial travel days are prorated by meal, and receipts are not required for per-diem disbursement.' },
  'CHARTER_VENDORS.PDF': { page: 'p. 1', html: 'Only vendors on the approved charter list may be booked for team ground transportation. New vendors require Operations approval.' },
  'GAMEDAY_FAQ.PDF': { page: 'p. 3', html: 'Students enter through <mark>Gate 3</mark> with a valid student ID and a mobile ticket claimed in the app. The student section opens <mark>90 minutes</mark> before kickoff on a first-come, first-served basis.' },
  'TICKET_TRANSFER_GUIDE.PDF': { page: 'p. 2', html: 'Tickets transfer through the official app; screenshots are not valid for entry. Transfers close 60 minutes after kickoff.' },
  'STUDY_HALL_POLICY.PDF': { page: 'p. 5', html: 'Any student-athlete carrying below a <mark>2.3 cumulative GPA</mark> is placed on a structured study-hall plan and must petition Academic Services for travel eligibility.' },
  'TUTORING_GUIDE.DOCX': { page: 'p. 2', html: 'Request a tutor through the Student Services portal at least 48 hours before the intended session.' },
  'FACILITY_HOURS.PDF': { page: 'p. 1', html: 'The indoor practice field may be reserved up to <mark>14 days</mark> in advance through the Operations portal. In-season teams hold scheduling priority; open slots release each Monday at 8:00 a.m.' },
  'EQUIPMENT_SOP.PDF': { page: 'p. 3', html: 'All issued equipment is checked out against the athlete\u2019s roster ID and returned at season end. Lost items are billed to the team account.' },
  'COWBOY_CLUB_LEVELS.PDF': { page: 'p. 2', html: 'Membership begins at the Posse level (<mark>$100/yr</mark>) and scales through Brand Champion (<mark>$25,000+</mark>). Each tier accrues priority points applied to seating and parking selection.' },
  'SUITE_BENEFITS.PDF': { page: 'p. 1', html: 'Suite holders receive premium parking, in-suite catering, and early gate entry 30 minutes ahead of general admission.' },
};

function SourcesPanel({ scope, highlight, onSelect, onClose }) {
  const activeFile = highlight && highlight.file;
  const excerpt = activeFile ? EXCERPTS[activeFile] : null;
  return React.createElement('aside', {
    style: { width: 320, flex: 'none', borderLeft: '1px solid var(--border)', background: 'var(--bg-page)', display: 'flex', flexDirection: 'column', height: '100%' },
  },
    React.createElement('div', { style: { height: 64, flex: 'none', display: 'flex', alignItems: 'center', padding: '0 18px', borderBottom: '1px solid var(--border)' } },
      React.createElement('div', { style: { fontFamily: 'var(--font-body)', fontSize: 14, fontWeight: 700, color: 'var(--fg-1)' } }, 'Sources'),
      React.createElement('div', { style: { marginLeft: 'auto' } }, React.createElement(IconBtn, { name: 'x', onClick: onClose }))
    ),
    React.createElement('div', { style: { padding: '14px 14px 18px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: 9 } },
      // selected-document excerpt — the passage the answer is grounded in
      excerpt && React.createElement(Excerpt, { file: activeFile, data: excerpt }),
      // list of grounding documents (click to read its passage)
      React.createElement('div', { style: { fontFamily: 'var(--font-body)', fontSize: 11.5, fontWeight: 600, color: 'var(--fg-3)', padding: '2px 4px 2px' } },
        excerpt ? 'All sources' : 'Grounding documents'),
      scope.docs.map((d, i) => React.createElement(SourceItem, {
        key: i, doc: d, active: activeFile === d.file, onClick: () => onSelect && onSelect(d.file),
      }))
    )
  );
}

function Excerpt({ file, data }) {
  return React.createElement('div', {
    style: { border: '1px solid var(--border-brand)', borderRadius: 'var(--radius-md)', background: 'var(--surface)', padding: '13px 14px', marginBottom: 4 },
  },
    React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 } },
      React.createElement(Icon, { name: 'file-text', size: 14, style: { color: 'var(--brand)', flex: 'none' } }),
      React.createElement('div', { style: { fontFamily: 'var(--font-mono)', fontSize: 11.5, color: 'var(--fg-1)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', flex: 1, minWidth: 0 } }, file),
      React.createElement('span', { style: { fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--fg-3)', flex: 'none' } }, data.page)
    ),
    React.createElement('div', {
      style: { borderLeft: '2px solid var(--brand)', paddingLeft: 12, fontFamily: 'var(--font-body)', fontSize: 13, lineHeight: 1.6, color: 'var(--fg-2)' },
      dangerouslySetInnerHTML: { __html: data.html },
    })
  );
}

function SourceItem({ doc, active, onClick }) {
  const [hover, setHover] = React.useState(false);
  return React.createElement('div', {
    onClick, onMouseEnter: () => setHover(true), onMouseLeave: () => setHover(false),
    style: {
      display: 'flex', gap: 11, padding: '11px 12px', borderRadius: 'var(--radius-md)',
      border: `1px solid ${active ? 'var(--border-brand)' : 'var(--border)'}`,
      background: active ? 'var(--brand-soft)' : (hover ? 'var(--surface-raised)' : 'var(--surface)'),
      cursor: 'pointer', transition: 'background var(--dur-fast), border-color var(--dur-fast)',
    },
  },
    React.createElement('div', { style: { width: 30, height: 30, flex: 'none', borderRadius: 'var(--radius-sm)', background: 'var(--surface-hover)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: active ? 'var(--brand)' : 'var(--fg-3)' } },
      React.createElement(Icon, { name: 'file-text', size: 16 })),
    React.createElement('div', { style: { minWidth: 0, flex: 1 } },
      React.createElement('div', { style: { fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--fg-1)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' } }, doc.file),
      React.createElement('div', { style: { fontFamily: 'var(--font-body)', fontSize: 11.5, color: 'var(--fg-3)', marginTop: 2 } }, doc.meta)
    )
  );
}

window.SourcesPanel = SourcesPanel;
