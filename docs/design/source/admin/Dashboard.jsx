/* Dashboard.jsx — the admin Insights page. A simplified analytics view with the
   AI summary baked in: query volume, common topics, risk flags, and the
   generated insight. Controls (window, generate, ask) live in the body. */

function Dashboard({ summary, insight, timeWindow, onTimeWindow, onGenerate, onOpenChat, insightStatus }) {
  const s = summary;
  const generating = insightStatus === 'processing' || insightStatus === 'pending';
  const winLabel = { '7d': 'Last 7 days', '30d': 'Last 30 days', 'custom': 'Custom range' };
  const winKey = { 'Last 7 days': '7d', 'Last 30 days': '30d', 'Custom range': 'custom' };
  const riskSev = Object.fromEntries(insight.risk_breakdown.map(r => [r.label.replace('-risk', ''), r.severity]));

  const riskRows = [
    { label: 'NIL', count: s.risk_counts.nil, sev: 'medium' },
    { label: 'Compliance', count: s.risk_counts.compliance, sev: 'medium' },
    { label: 'Recruiting-risk', count: s.risk_counts.recruiting, sev: 'high' },
  ];

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, background: 'var(--bg-base)' }}>
      <PageHeader title="Insights" sub="AI generated insights from user queries">
        <FilterSelect value={winLabel[timeWindow]} options={['Last 7 days', 'Last 30 days', 'Custom range']} onChange={(v) => onTimeWindow(winKey[v])} />
        <PBButton variant="secondary" size="sm" icon="refresh-cw" onClick={() => onGenerate(timeWindow)} disabled={generating}>{generating ? 'Regenerating…' : 'Regenerate'}</PBButton>
        <PBButton variant="primary" size="sm" icon="zap" onClick={onOpenChat}>Explore with AI</PBButton>
      </PageHeader>

      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 28px 20px' }}>
        <div style={{ maxWidth: 1000, margin: '0 auto' }}>

          {/* AI summary hero */}
          <AISummary insight={insight} generating={generating} />

          {/* common topics + risk */}
          <div style={{ display: 'grid', gridTemplateColumns: '1.55fr 1fr', gap: 16, marginTop: 14 }}>
            <Card>
              <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 15, color: 'var(--fg-1)', marginBottom: 12 }}>Common topics</div>
              <TopicBars items={s.top_topics} />
            </Card>

            <Card>
              <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 15, color: 'var(--fg-1)', marginBottom: 12 }}>Risk flags</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                {riskRows.map((r, i) => {
                  const c = r.sev === 'high' ? 'var(--danger)' : 'var(--warning)';
                  return (
                    <div key={r.label} style={{ display: 'flex', alignItems: 'center', gap: 11, padding: '13px 4px', borderBottom: i < riskRows.length - 1 ? '1px solid var(--border)' : 'none' }}>
                      <span style={{ width: 8, height: 8, borderRadius: '50%', background: c, flex: 'none' }} />
                      <span style={{ fontFamily: 'var(--font-body)', fontSize: 13.5, color: 'var(--fg-1)', flex: 1 }}>{r.label}</span>
                      <span style={{ fontFamily: 'var(--font-body)', fontSize: 10.5, fontWeight: 700, letterSpacing: '0.04em', textTransform: 'uppercase', color: c }}>{r.sev}</span>
                      <span style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 19, color: 'var(--fg-1)', width: 30, textAlign: 'right' }}>{r.count}</span>
                    </div>
                  );
                })}
              </div>
            </Card>
          </div>

          {/* query volume */}
          <Card style={{ marginTop: 14 }}>
            <div style={{ display: 'flex', alignItems: 'baseline', marginBottom: 12 }}>
              <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 15, color: 'var(--fg-1)' }}>Query volume</div>
              <span style={{ marginLeft: 'auto', fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--fg-3)' }}>{s.query_volume} this week</span>
            </div>
            <VolumeChart series={s.volume_series} />
          </Card>

        </div>
      </div>
    </div>
  );
}

/* AI summary — executive summary + the 3 KPIs the agent surfaced. Details
   (findings + recommended focus) expand on demand. */
function AISummary({ insight, generating }) {
  const [open, setOpen] = React.useState(false);
  return (
    <Card style={{ borderColor: 'var(--border-brand)', background: 'linear-gradient(180deg, rgba(255,115,0,0.06), transparent 52%), var(--surface)', padding: 18 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
          <Icon name="sparkles" size={16} style={{ color: 'var(--brand)' }} />
          <span style={{ fontFamily: 'var(--font-body)', fontSize: 12, fontWeight: 700, color: 'var(--brand)', letterSpacing: '0.02em' }}>AI summary</span>
        </span>
        <span style={{ marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: 8, fontFamily: 'var(--font-body)', fontSize: 11.5, color: 'var(--fg-3)' }}>
          {generating
            ? <React.Fragment><Icon name="loader" size={13} className="pb-spin" style={{ color: 'var(--info)' }} />Generating…</React.Fragment>
            : <React.Fragment><span className="pb-pulse" style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--success)', '--pulse-color': 'rgba(63,182,139,0.4)' }} />Updated {insight.generated_at} · {insight.window_label}</React.Fragment>}
        </span>
      </div>

      {generating ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
          {[92, 100, 70].map((w, i) => <span key={i} style={{ height: 13, width: w + '%', borderRadius: 'var(--radius-pill)', background: 'var(--surface-raised)' }} />)}
        </div>
      ) : (
        <React.Fragment>
          <p style={{ margin: 0, fontFamily: 'var(--font-body)', fontSize: 14.5, lineHeight: 1.65, color: 'var(--fg-1)', textWrap: 'pretty' }}>{insight.summary}</p>

          {/* agent-picked KPIs — shown by default */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', marginTop: 14, paddingTop: 13, borderTop: '1px solid var(--border)' }}>
            {insight.kpis.map((k, i) => (
              <div key={i} style={{ paddingLeft: i > 0 ? 22 : 0, borderLeft: i > 0 ? '1px solid var(--border)' : 'none' }}>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                  <span style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 26, letterSpacing: '-0.02em', color: 'var(--fg-1)', lineHeight: 1 }}>{k.value}</span>
                  <span style={{ fontFamily: 'var(--font-body)', fontSize: 12.5, fontWeight: 600, color: 'var(--fg-2)' }}>{k.label}</span>
                </div>
                <div style={{ fontFamily: 'var(--font-body)', fontSize: 11.5, color: 'var(--fg-4)', marginTop: 5 }}>{k.sub}</div>
              </div>
            ))}
          </div>

          {/* expand toggle */}
          <button onClick={() => setOpen(o => !o)}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6, marginTop: 12, padding: 0, border: 0, background: 'transparent', color: 'var(--brand)', fontFamily: 'var(--font-body)', fontWeight: 600, fontSize: 12.5, cursor: 'pointer' }}>
            {open ? 'Hide details' : 'Show details'}
            <Icon name="chevron-down" size={15} style={{ transform: open ? 'rotate(180deg)' : 'none', transition: 'transform var(--dur-fast)' }} />
          </button>

          {open && (
            <div style={{ animation: 'pbfade var(--dur-med) var(--ease-out) both' }}>
              {/* headline findings */}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 16 }}>
                {insight.headline_cards.map((c, i) => {
                  const col = c.severity === 'high' ? 'var(--danger)' : c.severity === 'medium' ? 'var(--warning)' : 'var(--success)';
                  return (
                    <span key={i} style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '7px 12px', background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: 'var(--radius-pill)' }}>
                      <span style={{ width: 7, height: 7, borderRadius: '50%', background: col, flex: 'none' }} />
                      <span style={{ fontFamily: 'var(--font-body)', fontSize: 12.5, fontWeight: 600, color: 'var(--fg-1)' }}>{c.title}</span>
                      <span style={{ fontFamily: 'var(--font-body)', fontSize: 12, color: 'var(--fg-3)' }}>{c.value}</span>
                    </span>
                  );
                })}
              </div>
              {/* recommended focus */}
              <div style={{ marginTop: 18, paddingTop: 16, borderTop: '1px solid var(--border)' }}>
                <div style={{ fontFamily: 'var(--font-body)', fontSize: 11.5, fontWeight: 700, color: 'var(--fg-3)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 11 }}>Recommended focus</div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '11px 22px' }}>
                  {insight.recommended_attention_areas.map((a, i) => (
                    <div key={i} style={{ display: 'flex', gap: 11, alignItems: 'flex-start' }}>
                      <span style={{ flex: 'none', width: 20, height: 20, borderRadius: 'var(--radius-sm)', background: 'var(--brand-soft)', color: 'var(--brand)', fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 11, display: 'flex', alignItems: 'center', justifyContent: 'center', marginTop: 1 }}>{i + 1}</span>
                      <span style={{ fontFamily: 'var(--font-body)', fontSize: 13, lineHeight: 1.5, color: 'var(--fg-2)', textWrap: 'pretty' }}>{a}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </React.Fragment>
      )}
    </Card>
  );
}

window.Dashboard = Dashboard;
