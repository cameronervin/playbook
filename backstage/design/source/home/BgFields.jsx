/* BgFields.jsx — ambient background fields, lifted from Login.html so the home
   shell reuses the exact same visual language. All low-contrast, reduced-motion
   aware. Rendered behind the chat column; surfaces stay solid on top. */

function Ambient({ anim }) {
  return (
    <div className={'ambient' + (anim ? '' : ' still')} aria-hidden="true">
      <div className="bloom bloom-a" />
      <div className="bloom bloom-b" />
      <div className="bloom bloom-c" />
      <div className="dots" />
    </div>
  );
}

function HorizonGrid({ anim }) {
  const ref = React.useRef(null);
  React.useEffect(() => {
    const canvas = ref.current, ctx = canvas.getContext('2d');
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches || !anim;
    let w = 0, h = 0, raf = 0, t = 0;
    const COLS = 22, ROWS = 22, STEP = 1, NEAR = 2.0, WAMP = 0.2, WF = 0.95, ZF = 0.5, TSPD = 0.9;
    function resize() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = canvas.clientWidth; h = canvas.clientHeight;
      canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    function draw() {
      ctx.clearRect(0, 0, w, h);
      const horizonY = h * 0.6, cx = w / 2, focal = h * 0.92, camH = 1.0;
      const off = (t * 0.45) % STEP;
      function proj(wx, z) {
        const ps = focal / z;
        const elev = WAMP * Math.sin(wx * WF + z * ZF + t * TSPD);
        return [cx + wx * ps, horizonY + (camH - elev) * ps];
      }
      for (let c = -COLS; c <= COLS; c++) {
        ctx.strokeStyle = 'rgba(255,120,10,0.10)';
        ctx.lineWidth = 1; ctx.beginPath();
        let first = true;
        for (let r = 0; r < ROWS; r++) {
          const z = NEAR + r * STEP - off; if (z <= 0.25) continue;
          const p = proj(c * 0.5, z);
          if (first) { ctx.moveTo(p[0], p[1]); first = false; } else ctx.lineTo(p[0], p[1]);
        }
        ctx.stroke();
      }
      for (let r = 0; r < ROWS; r++) {
        const z = NEAR + r * STEP - off; if (z <= 0.25) continue;
        const fade = Math.max(0, 1 - (z - NEAR) / (ROWS * STEP));
        ctx.strokeStyle = 'rgba(255,120,10,' + (0.55 * fade * fade).toFixed(3) + ')';
        ctx.lineWidth = 1; ctx.beginPath();
        for (let c = -COLS; c <= COLS; c++) {
          const p = proj(c * 0.5, z);
          if (c === -COLS) ctx.moveTo(p[0], p[1]); else ctx.lineTo(p[0], p[1]);
        }
        ctx.stroke();
      }
      if (!reduce) { t += 0.016; raf = requestAnimationFrame(draw); }
    }
    resize(); draw();
    const onR = () => { resize(); if (reduce) draw(); };
    window.addEventListener('resize', onR);
    return () => { cancelAnimationFrame(raf); window.removeEventListener('resize', onR); };
  }, [anim]);
  return <canvas ref={ref} className="fx fx-horizon" />;
}

function Ember({ anim }) {
  const ref = React.useRef(null);
  React.useEffect(() => {
    const canvas = ref.current, ctx = canvas.getContext('2d');
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches || !anim;
    let w = 0, h = 0, raf = 0, tt = 0, ps = [];
    function build() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = canvas.clientWidth; h = canvas.clientHeight;
      canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const n = Math.max(26, Math.min(84, Math.round(w * h / 15000)));
      ps = [];
      for (let i = 0; i < n; i++) ps.push({ x: Math.random() * w, y: Math.random() * h, vy: 0.12 + Math.random() * 0.32, ph: Math.random() * 6.28, sp: 0.4 + Math.random() * 0.6, r: 0.6 + Math.random() * 1.4, hot: Math.random() < 0.5 });
    }
    function frame() {
      tt += 0.016;
      ctx.clearRect(0, 0, w, h);
      ctx.globalCompositeOperation = 'lighter';
      for (const p of ps) {
        p.y -= p.vy; p.x += Math.sin(tt * p.sp + p.ph) * 0.22;
        if (p.y < -6) { p.y = h + 6; p.x = Math.random() * w; }
        const tw = 0.4 + 0.6 * (0.5 + 0.5 * Math.sin(tt * 1.5 * p.sp + p.ph));
        ctx.fillStyle = p.hot ? 'rgba(255,140,52,' + (0.5 * tw).toFixed(3) + ')' : 'rgba(246,241,232,' + (0.3 * tw).toFixed(3) + ')';
        ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, 6.283); ctx.fill();
      }
      ctx.globalCompositeOperation = 'source-over';
      if (!reduce) raf = requestAnimationFrame(frame);
    }
    build(); frame();
    const onR = () => { build(); if (reduce) frame(); };
    window.addEventListener('resize', onR);
    return () => { cancelAnimationFrame(raf); window.removeEventListener('resize', onR); };
  }, [anim]);
  return <canvas ref={ref} className="fx fx-ember" />;
}

// One switch the shell renders behind the chat column.
function BgField({ field, motion }) {
  if (field === 'aurora') return <Ambient anim={motion} />;
  if (field === 'horizon') return <HorizonGrid anim={motion} />;
  if (field === 'ember') return <Ember anim={motion} />;
  if (field === 'grid') return <div className="grid" />;
  return null;
}

Object.assign(window, { Ambient, HorizonGrid, Ember, BgField });
