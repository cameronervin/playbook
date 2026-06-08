/* Icon.jsx — Lucide icon set (https://lucide.dev), inlined for reliability.
   Stroke-only, 1.75px, 24x24 viewBox. Inherits currentColor. */
(function () {
  const P = {
    'arrow-right': 'M5 12h14 M12 5l7 7-7 7',
    'arrow-left': 'M19 12H5 M12 19l-7-7 7-7',
    'send': 'M22 2 11 13 M22 2 15 22 11 13 2 9 22 2',
    'plus': 'M5 12h14 M12 5v14',
    'search': 'M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16z M21 21l-4.3-4.3',
    'settings': 'M20 7h-9 M14 17H5 M17 14a3 3 0 1 0 0 6 3 3 0 0 0 0-6z M7 4a3 3 0 1 0 0 6 3 3 0 0 0 0-6z',
    'file-text': 'M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7z M14 2v5h5 M16 13H8 M16 17H8 M10 9H8',
    'database': 'M12 8c4.97 0 9-1.34 9-3s-4.03-3-9-3-9 1.34-9 3 4.03 3 9 3z M3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5 M3 12c0 1.66 4.03 3 9 3s9-1.34 9-3',
    'message-square': 'M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z',
    'users': 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z M22 21v-2a4 4 0 0 0-3-3.87 M16 3.13a4 4 0 0 1 0 7.75',
    'shield': 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z',
    'plane': 'M17.8 19.2 16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.5-.1 1 .3 1.3L9 12l-2 3H4l-1 1 3 2 2 3 1-1v-3l3-2 3.5 5.3c.3.4.8.5 1.3.3l.5-.2c.4-.3.6-.7.5-1.2z',
    'ticket': 'M2 9a3 3 0 0 1 0 6v2a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-2a3 3 0 0 1 0-6V7a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2z M13 5v2 M13 17v2 M13 11v2',
    'chevron-down': 'm6 9 6 6 6-6',
    'chevron-right': 'm9 18 6-6-6-6',
    'chevron-left': 'm15 18-6-6 6-6',
    'check': 'M20 6 9 17l-5-5',
    'check-circle': 'M22 11.08V12a10 10 0 1 1-5.93-9.14 M22 4 12 14.01l-3-3',
    'clock': 'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z M12 6v6l4 2',
    'more-horizontal': 'M12 13a1 1 0 1 0 0-2 1 1 0 0 0 0 2z M19 13a1 1 0 1 0 0-2 1 1 0 0 0 0 2z M5 13a1 1 0 1 0 0-2 1 1 0 0 0 0 2z',
    'panel-right': 'M3 3h18a0 0 0 0 1 0 0v18a0 0 0 0 1 0 0H3a0 0 0 0 1 0 0V3a0 0 0 0 1 0 0z M15 3v18',
    'x': 'M18 6 6 18 M6 6l12 12',
    'paperclip': 'm21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48',
    'trending-up': 'M22 7 13.5 15.5 8.5 10.5 2 17 M16 7h6v6',
    'sliders': 'M4 21v-7 M4 10V3 M12 21v-9 M12 8V3 M20 21v-5 M20 12V3 M2 14h4 M10 8h4 M18 16h4',
    'bell': 'M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9 M10.3 21a1.94 1.94 0 0 0 3.4 0',
    'book-open': 'M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z',
    'zap': 'M13 2 3 14h9l-1 8 10-12h-9l1-8z',
    'home': 'M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z M9 22V12h6v10',
    'sparkle-route': 'M5 19l6-6 4 3 5-7', // playbook route motif
    'user': 'M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2 M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z',
    'log-out': 'M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4 M16 17l5-5-5-5 M21 12H9',
    'mail': 'M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z M22 6l-10 7L2 6',
    'chevrons-up-down': 'm7 15 5 5 5-5 M7 9l5-5 5 5',
    'monitor': 'M20 3H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2z M8 21h8 M12 17v4',
    'moon': 'M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9z',
    'sun': 'M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10z M12 1v2 M12 21v2 M4.2 4.2l1.4 1.4 M18.4 18.4l1.4 1.4 M1 12h2 M21 12h2 M4.2 19.8l1.4-1.4 M18.4 5.6l1.4-1.4',
    'pencil': 'M17 3a2.83 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5z',
    'lock': 'M19 11H5a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7a2 2 0 0 0-2-2z M7 11V7a5 5 0 0 1 10 0v4',
    'circle-help': 'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3 M12 17h.01',
    'globe': 'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z M2 12h20 M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z',
    'camera': 'M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3z M12 17a4 4 0 1 0 0-8 4 4 0 0 0 0 8z',
    'shield-check': 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z M9 12l2 2 4-4',
    'trash': 'M3 6h18 M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6 M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2 M10 11v6 M14 11v6',
    'layout-dashboard': 'M3 3h8v8H3z M13 3h8v5h-8z M13 12h8v9h-8z M3 14h8v7H3z',
    'trending-down': 'M22 17 13.5 8.5 8.5 13.5 2 7 M16 17h6v-6',
    'alert-triangle': 'M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z M12 9v4 M12 17h.01',
    'filter': 'M22 3H2l8 9.46V19l4 2v-8.54z',
    'calendar': 'M8 2v4 M16 2v4 M3 10h18 M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z',
    'refresh-cw': 'M21 12a9 9 0 1 1-2.64-6.36L21 8 M21 3v5h-5',
    'flag': 'M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z M4 22v-7',
    'upload': 'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4 M17 8l-5-5-5 5 M12 3v12',
    'play': 'M6 3 20 12 6 21z',
    'x-circle': 'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z M15 9l-6 6 M9 9l6 6',
    'minus-circle': 'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z M8 12h8',
    'shield-alert': 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z M12 8v4 M12 16h.01',
    'sparkles': 'M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z M19 3v4 M21 5h-4 M5 17v3 M6.5 18.5h-3',
    'bar-chart-2': 'M18 20V10 M12 20V4 M6 20v-6',
    'activity': 'M22 12h-4l-3 9L9 3l-3 9H2',
    'scroll-text': 'M8 21h12a2 2 0 0 0 2-2v-2H10v2a2 2 0 1 1-4 0V5a2 2 0 1 0-4 0v3h4 M19 17V5a2 2 0 0 0-2-2H8 M15 8h-5 M15 12h-5',
    'external-link': 'M15 3h6v6 M10 14 21 3 M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6',
    'maximize-2': 'M15 3h6v6 M9 21H3v-6 M21 3l-7 7 M3 21l7-7',
    'arrow-up-right': 'M7 17 17 7 M7 7h10v10',
    'message-circle': 'M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8z',
    'loader': 'M12 2v4 M12 18v4 M4.93 4.93l2.83 2.83 M16.24 16.24l2.83 2.83 M2 12h4 M18 12h4 M4.93 19.07l2.83-2.83 M16.24 7.76l2.83-2.83',
    'eye': 'M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7z M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z',
    'eye-off': 'M9.88 9.88a3 3 0 0 0 4.24 4.24 M10.73 5.08A11 11 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68 M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61 M2 2l20 20',
    'corner-down-right': 'M15 10l5 5-5 5 M4 4v7a4 4 0 0 0 4 4h12',
    'user-plus': 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z M19 8v6 M22 11h-6',
    'circle-dot': 'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z',
    'help-circle': 'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3 M12 17h.01',
    'robot': 'M5 10h14a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-6a2 2 0 0 1 2-2z M12 10V6 M12 6a1.6 1.6 0 1 0 0-3.2 1.6 1.6 0 0 0 0 3.2z M2 14h1 M21 14h1 M8.5 15h.01 M15.5 15h.01',
  };
  function Icon({ name, size = 18, stroke = 1.75, style, className }) {
    const d = P[name];
    return React.createElement('svg', {
      width: size, height: size, viewBox: '0 0 24 24', fill: 'none',
      stroke: 'currentColor', strokeWidth: stroke, strokeLinecap: 'round',
      strokeLinejoin: 'round', style, className, 'aria-hidden': true,
    }, (d || '').split(' M').map((seg, i) =>
      React.createElement('path', { key: i, d: (i === 0 ? seg : 'M' + seg) })
    ));
  }
  // Brand play-route mark (square caps/joins, orange) for agent avatars + logo
  function Mark({ size = 24, color = '#F6F1E8' }) {
    return React.createElement('svg', { width: size, height: size, viewBox: '0 0 512 512', fill: 'none', 'aria-hidden': true },
      React.createElement('path', { fill: color, d: 'M32 402.84 L100.86 402.84 L169.72 283.38 L377.13 283.38 L480 104.18 L342.28 104.18 L308.27 163.91 L377.13 163.91 L342.28 223.64 L135.70 223.64 Z' }),
      React.createElement('path', { fill: '#FF7300', d: 'M204.56 104.18 L272.59 104.18 L238.58 163.91 L169.72 163.91 Z' }),
      React.createElement('path', { fill: '#FF7300', d: 'M291.67 321.54 L359.70 321.54 L314.90 407.82 L249.36 407.82 Z' })
    );
  }
  window.Icon = Icon;
  window.Mark = Mark;
})();
