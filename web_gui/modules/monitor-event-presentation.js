/** Shared Deployment/Replay operational event presentation. */

export const ENCOUNTER_LABELS = {
  head_on: 'Rule 14 Head-on',
  overtaking: 'Rule 13 Overtaking',
  overtaken: 'Rule 13 Overtaken',
  crossing_give_way: 'Rule 15 Give-way (16)',
  crossing_stand_on: 'Rule 15 Stand-on (17)',
  clear: 'Clear',
};

export function eventDisplayContent(event) {
  const details = event.details || {};
  const target = details.targetLabel || (details.target_id !== undefined ? `TS${details.target_id}` : '');
  const contextLabel = (value) => String(value || '').replaceAll('_', ' ');
  const reasonLabel = (value) => String(value || '').replaceAll('_', ' ');
  const transitionLabel = (from, to) => [from, to].filter(Boolean).map(contextLabel).join(' → ');
  const lifecycleStateLabel = (value, displayClass) => {
    const state = String(value || '');
    if (state.includes('PAST_CLEAR')) return 'CLEARING';
    if (state.includes('RELEASED')) return 'RELEASED';
    if (state.includes('ACTIVE') || state.includes('COMMITTED')) {
      if (displayClass === 'HIGH') return 'AVOIDING';
      return displayClass === 'LOW' ? 'MONITOR' : 'COMMITTED';
    }
    if (state.includes('CANDIDATE') || state.includes('MONITORING')) return 'MONITOR';
    if (state.includes('CLEAR')) return 'SAFE';
    return contextLabel(state);
  };
  const riskEvidence = () => [
    Number.isFinite(details.dcpa_m) ? `DCPA ${details.dcpa_m.toFixed(1)} m` : '',
    Number.isFinite(details.tcpa_s) ? `TCPA ${details.tcpa_s.toFixed(1)} s` : '',
  ].filter(Boolean).join(' · ');
  const withEvidence = (...parts) => [...parts.filter(Boolean), riskEvidence()].filter(Boolean).join(' · ');
  const content = ({ eventType, status = '', subject = '', detail = '', cardTone = 'info', statusTone = cardTone }) => ({
    title: [eventType, status].filter(Boolean).join(' '),
    description: [subject, detail].filter(Boolean).join('  '),
    eventType,
    status,
    subject,
    detail,
    cardTone,
    statusTone,
  });
  switch (event.type) {
    case 'planner_solved':
      return content({
        eventType: 'Planner solution',
        status: details.status || '',
        subject: `#${details.solve_id ?? '—'}`,
        detail: typeof details.feasible === 'boolean' ? (details.feasible ? 'feasible' : 'infeasible') : '',
      });
    case 'colregs_change': {
      const from = details.from ? (ENCOUNTER_LABELS[details.from] || details.from) : 'Clear';
      const to = details.to ? (ENCOUNTER_LABELS[details.to] || details.to) : 'Clear';
      const cleared = details.to === 'clear';
      return content({
        eventType: 'COLREGs',
        status: cleared ? 'Clear' : 'Hold',
        subject: target,
        detail: cleared ? `${from} → Clear` : to,
        cardTone: 'info',
        statusTone: cleared ? 'safe' : 'warning',
      });
    }
    case 'dcpa_level_change': {
      const status = String(details.level || 'unknown').toUpperCase();
      return content({
        eventType: 'DCPA',
        status,
        subject: target,
        detail: Number.isFinite(details.dcpaM) ? `${details.dcpaM.toFixed(1)} m closest approach` : 'Closest approach updated',
        cardTone: 'info',
        statusTone: status === 'DANGER' ? 'danger' : status === 'WARN' ? 'warning' : 'safe',
      });
    }
    case 'threat_entered':
      return content({
        eventType: 'Threat',
        status: contextLabel(details.to_context || 'ENTERED'),
        subject: target,
        detail: withEvidence(reasonLabel(details.reason)),
        cardTone: details.to_context === 'CURRENT_PRIMARY' ? 'danger' : 'warning',
      });
    case 'threat_escalated':
      return content({
        eventType: 'Threat',
        status: 'ESCALATED',
        subject: target,
        detail: withEvidence(transitionLabel(details.from_context, details.to_context) || reasonLabel(details.reason)),
        cardTone: 'warning',
      });
    case 'threat_clearing':
      return content({
        eventType: 'Threat',
        status: 'CLEARING',
        subject: target,
        detail: transitionLabel(details.from_context, details.to_context),
        cardTone: 'safe',
      });
    case 'threat_released':
      return content({
        eventType: 'Threat',
        status: 'RELEASED',
        subject: target,
        detail: withEvidence(reasonLabel(details.reason)),
        cardTone: 'safe',
      });
    case 'primary_switched': {
      const from = details.from_target_id === undefined ? '--' : `TS${details.from_target_id}`;
      const to = details.to_target_id === undefined ? (target || '--') : `TS${details.to_target_id}`;
      return content({
        eventType: 'Primary',
        status: 'SWITCHED',
        subject: `${from} → ${to}`,
        detail: withEvidence(reasonLabel(details.reason)),
        cardTone: 'warning',
      });
    }
    case 'schedule_reorder':
      return content({
        eventType: 'Threat schedule',
        status: contextLabel(details.to_context || 'UPDATED'),
        subject: target,
        detail: transitionLabel(details.from_context, details.to_context) || reasonLabel(details.reason),
      });
    case 'target_transition': {
      const toState = String(details.to_state || '');
      const fromSummary = lifecycleStateLabel(details.from_state, details.from_display_class);
      const toSummary = lifecycleStateLabel(toState, details.display_class);
      const sameSummaryChanged = fromSummary && fromSummary === toSummary && details.from_state !== details.to_state;
      const stateTransition = sameSummaryChanged
        ? transitionLabel(
          String(details.from_state || '').replaceAll('/', ' · '),
          String(details.to_state || '').replaceAll('/', ' · '),
        )
        : fromSummary ? `${fromSummary} → ${toSummary}` : '';
      return content({
        eventType: 'Risk state',
        status: toSummary || 'UPDATED',
        subject: target,
        detail: withEvidence(stateTransition),
        cardTone: toSummary === 'AVOIDING' ? 'danger' : ['CLEARING', 'RELEASED', 'SAFE'].includes(toSummary) ? 'safe' : 'warning',
      });
    }
    case 'risk_level_changed': {
      const to = String(details.to_display_class || details.display_class || 'UNKNOWN').toUpperCase();
      return content({
        eventType: 'Risk',
        status: to,
        subject: target,
        detail: withEvidence(transitionLabel(details.from_display_class, details.to_display_class)),
        cardTone: to === 'HIGH' ? 'danger' : to === 'CLEAR' ? 'safe' : 'warning',
      });
    }
    case 'colregs_changed':
      return content({
        eventType: 'COLREGs',
        status: 'UPDATED',
        subject: target,
        detail: transitionLabel(details.from_encounter, details.to_encounter),
        cardTone: details.to_encounter === 'CLEAR' ? 'safe' : 'warning',
      });
    case 'observation_degraded':
      return content({
        eventType: 'Observation',
        status: contextLabel(details.to_health || 'DEGRADED'),
        subject: target,
        detail: transitionLabel(details.from_health, details.to_health),
        cardTone: details.to_health === 'UNUSABLE' ? 'danger' : 'warning',
      });
    case 'observation_recovered':
      return content({
        eventType: 'Observation',
        status: 'RECOVERED',
        subject: target,
        detail: transitionLabel(details.from_health, details.to_health),
        cardTone: 'safe',
      });
    case 'avoidance_action_started':
      return content({
        eventType: 'Avoidance',
        status: 'ACTIVE',
        subject: target,
        detail: withEvidence([contextLabel(details.encounter), contextLabel(details.role)].filter(Boolean).join(' · ')),
        cardTone: 'danger',
      });
    case 'avoidance_action_ended':
      return content({
        eventType: 'Avoidance',
        status: 'RECOVERY',
        subject: target,
        detail: 'Collision-avoidance action released',
        cardTone: 'safe',
      });
    case 'threat_lifecycle_active':
      return content({
        eventType: 'Threat lifecycle',
        status: 'ACTIVE',
        subject: target,
        detail: 'Canonical avoidance duty active',
        cardTone: 'danger',
      });
    case 'algorithm_handoff':
      return content({
        eventType: 'Algorithm handoff',
        status: 'ACTIVE',
        detail: reasonLabel(details.trigger || 'Lifecycle active'),
        cardTone: 'warning',
      });
    case 'historical_recovery_complete':
      return content({ eventType: 'Historical recovery', status: 'COMPLETE', detail: reasonLabel(details.reason), cardTone: 'safe' });
    case 'historical_handoff_not_triggered':
      return content({ eventType: 'Algorithm handoff', status: 'NOT TRIGGERED', detail: reasonLabel(details.reason), cardTone: 'warning' });
    case 'planner_failed':
      return content({
        eventType: 'Planner',
        status: 'FAILED',
        subject: `#${details.solve_id ?? '—'}`,
        detail: details.failure_code || details.reason || details.status || 'Plan unavailable',
        cardTone: 'danger',
      });
    case 'planner_recovered':
      return content({
        eventType: 'Planner',
        status: 'RECOVERED',
        subject: `#${details.solve_id ?? '—'}`,
        detail: details.status || 'Feasible plan restored',
        cardTone: 'safe',
      });
    case 'collision':
      return content({
        eventType: 'Collision',
        status: 'DANGER',
        subject: target || `Ship ${details.ship_id ?? '—'}`,
        detail: 'Collision detected',
        cardTone: 'danger',
        statusTone: 'danger',
      });
    case 'grounding':
      return content({
        eventType: 'Grounding',
        status: 'DANGER',
        subject: `Ship ${details.ship_id ?? '—'}`,
        detail: 'Grounding detected',
        cardTone: 'danger',
        statusTone: 'danger',
      });
    case 'time_limit':
      return content({ eventType: 'Simulation', status: 'Time limit', detail: 'Run stopped at configured duration' });
    case 'goal_reached':
      return content({
        eventType: 'Avoidance',
        status: 'Complete',
        subject: `Ship ${details.ship_id ?? '—'}`,
        detail: 'Mission route reached',
        cardTone: 'safe',
        statusTone: 'safe',
      });
    case 'session_started':
      return content({ eventType: 'Simulation', status: 'Started', detail: 'Session is ready for monitoring' });
    case 'session_resumed':
      return content({ eventType: 'Simulation', status: 'Resumed', detail: 'Execution resumed' });
    case 'session_paused':
      return content({ eventType: 'Simulation', status: 'Paused', detail: 'Manual pause' });
    case 'session_reset':
      return content({ eventType: 'Simulation', status: 'Reset', detail: 'New session created from immutable Run Specification' });
    case 'session_replayed':
      return content({ eventType: 'Simulation', status: 'Replay', detail: 'Replay session created from source run' });
    case 'session_finished':
      return content({ eventType: 'Simulation', status: 'Finished', detail: 'Session completed' });
    case 'session_failed':
      return content({
        eventType: 'Simulation',
        status: 'Failed',
        detail: details.reason || 'Runtime failure',
        cardTone: 'danger',
        statusTone: 'danger',
      });
    default:
      return content({
        eventType: String(event.type || 'simulation_event').replaceAll('_', ' ').replace(/^./, (letter) => letter.toUpperCase()),
        subject: target || (details.ship_id !== undefined ? `Ship ${details.ship_id}` : ''),
        detail: 'Simulation event',
      });
  }
}

const MONITOR_HIDDEN_EVENT_TYPES = new Set(['planner_solved']);

export function visibleMonitorEvents(events) {
  return (Array.isArray(events) ? events : []).filter((event) => (
    !MONITOR_HIDDEN_EVENT_TYPES.has(event?.type)
    && event?.type !== 'primary_challenger'
    && !(event?.type === 'schedule_reorder'
      && event?.details?.reason === 'deterministic_track_key_order_changed')
  ));
}

function monitorEventTone(event) {
  return eventDisplayContent(event).cardTone;
}

function monitorToneColor(tone) {
  return tone === 'danger'
    ? 'var(--alert-alarm-color, #d82828)'
    : tone === 'warning'
      ? 'var(--alert-warning-color, #b87800)'
      : tone === 'safe'
        ? 'var(--alert-success-color, #16804b)'
        : 'var(--ob-accent-mid, #5d8fd5)';
}

function decorateMonitorEventItems(eventList, events, documentRef) {
  const eventItems = [...(eventList.shadowRoot?.querySelectorAll('obc-event-item') || [])];
  eventItems.forEach((item, index) => {
    const event = events[index];
    const presentation = event ? eventDisplayContent(event) : null;
    const tone = event ? monitorEventTone(event) : 'info';
    const statusTone = presentation?.statusTone || 'info';
    const accent = monitorToneColor(tone);
    const statusAccent = monitorToneColor(statusTone);
    const background = `color-mix(in srgb, ${accent} 8%, var(--ob-surface, #ffffff))`;
    const border = `color-mix(in srgb, ${accent} 38%, var(--ob-border, #dddddd))`;
    item.dataset.eventTone = tone;
    item.dataset.eventStatusTone = statusTone;
    item.style.setProperty('--flat-enabled-background-color', background);
    item.style.setProperty('--flat-enabled-border-color', border);
    item.style.setProperty('--flat-hover-background-color', background);
    item.style.setProperty('--flat-hover-border-color', border);
    const shadow = item.shadowRoot;
    const wrapper = shadow?.querySelector('.wrapper');
    const visibleWrapper = shadow?.querySelector('.visible-wrapper');
    const content = shadow?.querySelector('.event-content');
    const title = shadow?.querySelector('.title');
    const description = shadow?.querySelector('.description');
    if (wrapper) wrapper.classList.remove('type-color-coded');
    if (visibleWrapper) {
      visibleWrapper.style.background = background;
      visibleWrapper.style.borderColor = border;
      visibleWrapper.style.borderLeft = `3px solid ${accent}`;
      visibleWrapper.style.padding = '8px 10px 6px';
      visibleWrapper.style.minHeight = '64px';
    }
    if (content) content.style.justifyContent = 'space-between';
    if (title) {
      title.style.color = 'var(--ob-text, #1f1f1f)';
      title.style.fontSize = '12px';
      title.style.fontWeight = '650';
      title.style.lineHeight = '17px';
      title.style.whiteSpace = 'normal';
      title.style.overflow = 'visible';
      title.style.textOverflow = 'clip';
      title.style.display = 'block';
      if (presentation) {
        const header = documentRef.createElement('span');
        header.className = 'event-title-line';
        header.style.display = 'block';
        header.style.whiteSpace = 'nowrap';
        const eventType = documentRef.createElement('span');
        eventType.className = 'event-type';
        eventType.textContent = presentation.eventType;
        header.append(eventType);
        if (presentation.status) {
          const status = documentRef.createElement('span');
          status.className = 'event-status';
          status.textContent = ` ${presentation.status}`;
          status.style.color = statusAccent;
          status.style.fontWeight = '750';
          header.append(status);
        }
        const body = documentRef.createElement('span');
        body.className = 'event-body-line';
        body.style.display = 'flex';
        body.style.flexWrap = 'wrap';
        body.style.columnGap = '10px';
        body.style.rowGap = '2px';
        body.style.marginTop = '3px';
        body.style.fontSize = '11px';
        body.style.fontWeight = '500';
        body.style.lineHeight = '15px';
        if (presentation.subject) {
          const subject = documentRef.createElement('span');
          subject.className = 'event-subject';
          subject.textContent = presentation.subject;
          subject.style.fontWeight = '700';
          body.append(subject);
        }
        if (presentation.detail) {
          const detail = documentRef.createElement('span');
          detail.className = 'event-detail';
          detail.textContent = presentation.detail;
          body.append(detail);
        }
        title.replaceChildren(header, body);
      }
    }
    if (description) {
      description.style.color = 'var(--ob-subtle, #707070)';
      description.style.fontFamily = 'var(--font-mono)';
      description.style.fontSize = '9px';
      description.style.lineHeight = '13px';
      description.style.textAlign = 'right';
      description.style.whiteSpace = 'nowrap';
    }
  });
}

export function renderMonitorEventItems(eventList, events, formatDuration, documentRef = document, emptyTitle = 'Waiting for simulation events') {
  const visibleEvents = visibleMonitorEvents(events).slice().reverse();
  if (!eventList) return visibleEvents.length;
  eventList.showHeader = false;
  eventList.events = visibleEvents.length
    ? visibleEvents.map((event) => {
        const content = eventDisplayContent(event);
        const startTime = Number.isFinite(event.simTime) ? formatDuration(event.simTime) : '--:--:--';
        return {
          title: [content.title, content.description].filter(Boolean).join(' · '),
          description: startTime,
          startTime,
          endTime: '',
          eventItemType: 'doubleLine',
          hasTime: false,
          hasEndTime: false,
          hasArrow: false,
          colorCoded: false,
        };
      })
    : [{
        title: emptyTitle,
        description: '--:--:--',
        startTime: '--:--:--',
        endTime: '',
        eventItemType: 'doubleLine',
        hasTime: false,
        hasEndTime: false,
        hasArrow: false,
        colorCoded: false,
        disabled: true,
      }];
  const decorate = () => decorateMonitorEventItems(eventList, visibleEvents, documentRef);
  decorate();
  eventList.updateComplete?.then(() => {
    const itemUpdates = [...(eventList.shadowRoot?.querySelectorAll('obc-event-item') || [])]
      .map((item) => item.updateComplete)
      .filter(Boolean);
    Promise.all(itemUpdates).then(decorate);
  });
  return visibleEvents.length;
}
