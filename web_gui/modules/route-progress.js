export function routeLegs(waypoints) {
  const [norths, easts] = Array.isArray(waypoints) ? waypoints : [[], []];
  if (!Array.isArray(norths) || !Array.isArray(easts) || norths.length < 2 || easts.length !== norths.length) {
    return [];
  }
  return norths.slice(0, -1).map((_, index) => ({
    from: { n: norths[index], e: easts[index] },
    to: { n: norths[index + 1], e: easts[index + 1] },
  }));
}

export function routeProgress(legs, pos) {
  // Active leg: the first leg the ownship has not fully passed; if all are
  // passed the ownship is on the final approach (remaining distance 0).
  for (let index = 0; index < legs.length; index += 1) {
    const leg = legs[index];
    const dn = leg.to.n - leg.from.n;
    const de = leg.to.e - leg.from.e;
    const length = Math.hypot(dn, de);
    if (length === 0) continue;
    const t = ((pos.n - leg.from.n) * dn + (pos.e - leg.from.e) * de) / (length * length);
    if (t < 1 || index === legs.length - 1) {
      const remaining = Math.max(0, (1 - Math.max(t, 0))) * length;
      const later = legs.slice(index + 1).reduce(
        (sum, item) => sum + Math.hypot(item.to.n - item.from.n, item.to.e - item.from.e),
        0,
      );
      return {
        index,
        leg,
        nextLeg: legs[index + 1] ?? null,
        remaining,
        total: remaining + later,
        t,
      };
    }
  }
  return null;
}
