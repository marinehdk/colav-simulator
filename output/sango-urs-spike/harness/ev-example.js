(() => { const s = window.__ursStats; const r = window.__ursDcRttMs || [];
  const sorted = [...r].sort((a,b)=>a-b);
  return { stats: s, dcRttCount: r.length, dcRttMin: sorted[0], dcRttMedian: sorted[Math.floor(sorted.length/2)], dcRttMax: sorted[sorted.length-1] }; })()
