const SVG_NS = 'http://www.w3.org/2000/svg';
const VIEWBOX = { width: 300, height: 190 };
const PLOT = { left: 48, top: 18, right: 286, bottom: 146 };
const TICK_COUNT = 5;

function svgNode(name, attributes = {}) {
  const node = document.createElementNS(SVG_NS, name);
  Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, String(value)));
  return node;
}

function formatTick(value) {
  const magnitude = Math.abs(value);
  if (magnitude >= 1000 || (magnitude > 0 && magnitude < 0.01)) return value.toExponential(1);
  if (magnitude >= 100) return value.toFixed(0);
  if (magnitude >= 10) return value.toFixed(1);
  return value.toFixed(2).replace(/\.00$/, '').replace(/(\.\d)0$/, '$1');
}

class ColavLineGraph extends HTMLElement {
  static get observedAttributes() {
    return ['caption', 'x-label', 'y-label', 'legend', 'unit'];
  }

  constructor() {
    super();
    this._values = [];
    this._xValues = [];
    this.attachShadow({ mode: 'open' });
    this.shadowRoot.innerHTML = `
      <style>
        :host { min-width: 0; color: var(--ob-text, #16201d); font-family: var(--font-ui, sans-serif); }
        figure { height: 100%; margin: 0; display: grid; grid-template-rows: auto minmax(0, 1fr) auto; border: 1px solid var(--ob-border, #c7cecb); border-radius: var(--radius, 4px); background: var(--ob-surface, #fff); overflow: hidden; }
        figcaption { min-height: 28px; display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 0 10px; border-bottom: 1px solid var(--ob-border, #c7cecb); }
        .caption { font-size: 10px; font-weight: 650; }
        .summary { color: var(--ob-subtle, #65736f); font: 500 9px/14px var(--font-mono, monospace); white-space: nowrap; }
        svg { display: block; width: 100%; height: 100%; min-height: 0; }
        .axis { stroke: var(--ob-muted, #82918c); stroke-width: 1; vector-effect: non-scaling-stroke; }
        .grid { stroke: var(--ob-border, #c7cecb); stroke-width: 1; opacity: .65; vector-effect: non-scaling-stroke; }
        .series { fill: none; stroke: var(--ob-accent, #1e5aa8); stroke-width: 2; vector-effect: non-scaling-stroke; }
        .marker { fill: var(--ob-accent, #1e5aa8); }
        text { fill: var(--ob-subtle, #65736f); font: 8px var(--font-mono, monospace); }
        .axis-label { fill: var(--ob-muted, #4d5d58); font-size: 8px; font-weight: 600; }
        .empty { font-size: 10px; }
        .legend { min-height: 24px; display: flex; align-items: center; gap: 6px; padding: 0 10px; border-top: 1px solid var(--ob-border, #c7cecb); color: var(--ob-subtle, #65736f); font-size: 9px; }
        .legend i { width: 16px; height: 2px; background: var(--ob-accent, #1e5aa8); }
      </style>
      <figure>
        <figcaption><span class="caption"></span><span class="summary">Waiting for data</span></figcaption>
        <svg viewBox="0 0 300 190" role="img">
          <g class="grid-lines"></g>
          <line class="axis" x1="48" y1="18" x2="48" y2="146"></line>
          <line class="axis" x1="48" y1="146" x2="286" y2="146"></line>
          <g class="tick-labels"></g>
          <polyline class="series"></polyline>
          <circle class="marker" r="2.5" display="none"></circle>
          <text class="empty" x="167" y="82" text-anchor="middle">Waiting for data</text>
          <text class="axis-label x-label" x="167" y="181" text-anchor="middle"></text>
          <text class="axis-label y-label" transform="translate(10 82) rotate(-90)" text-anchor="middle"></text>
        </svg>
        <div class="legend"><i></i><span></span></div>
      </figure>
    `;
  }

  connectedCallback() {
    this._render();
  }

  attributeChangedCallback() {
    if (this.isConnected) this._render();
  }

  setSeries(values, xValues = null) {
    this._values = Array.from(values || [], Number).filter(Number.isFinite);
    const suppliedX = Array.from(xValues || [], Number);
    this._xValues = suppliedX.length === this._values.length && suppliedX.every(Number.isFinite)
      ? suppliedX
      : this._values.map((_, index) => index + 1);
    this._render();
  }

  _render() {
    if (!this.shadowRoot) return;
    const caption = this.getAttribute('caption') || 'Graph';
    const legend = this.getAttribute('legend') || caption;
    const unit = this.getAttribute('unit') || '';
    this.shadowRoot.querySelector('.caption').textContent = caption;
    this.shadowRoot.querySelector('.legend span').textContent = legend;
    this.shadowRoot.querySelector('.x-label').textContent = this.getAttribute('x-label') || 'Sample';
    this.shadowRoot.querySelector('.y-label').textContent = this.getAttribute('y-label') || 'Value';
    this.shadowRoot.querySelector('svg').setAttribute('aria-label', `${caption} graph`);

    const empty = this.shadowRoot.querySelector('.empty');
    const series = this.shadowRoot.querySelector('.series');
    const marker = this.shadowRoot.querySelector('.marker');
    const grid = this.shadowRoot.querySelector('.grid-lines');
    const labels = this.shadowRoot.querySelector('.tick-labels');
    grid.replaceChildren();
    labels.replaceChildren();

    if (!this._values.length) {
      empty.removeAttribute('display');
      marker.setAttribute('display', 'none');
      series.setAttribute('points', '');
      this.shadowRoot.querySelector('.summary').textContent = 'Waiting for data';
      return;
    }

    empty.setAttribute('display', 'none');
    const rawMin = Math.min(...this._values);
    const rawMax = Math.max(...this._values);
    const yMin = Math.min(0, rawMin);
    const yMax = rawMax === yMin ? yMin + Math.max(1, Math.abs(yMin) * 0.1) : rawMax;
    const xMin = Math.min(...this._xValues);
    const xMax = Math.max(...this._xValues);
    const hasXRange = xMax !== xMin;
    const xSpan = Math.max(1, xMax - xMin);
    const ySpan = Math.max(1e-9, yMax - yMin);
    const xAt = value => hasXRange
      ? PLOT.left + (value - xMin) / xSpan * (PLOT.right - PLOT.left)
      : (PLOT.left + PLOT.right) / 2;
    const yAt = value => PLOT.bottom - (value - yMin) / ySpan * (PLOT.bottom - PLOT.top);

    for (let index = 0; index < TICK_COUNT; index += 1) {
      const ratio = index / (TICK_COUNT - 1);
      const x = PLOT.left + ratio * (PLOT.right - PLOT.left);
      const y = PLOT.bottom - ratio * (PLOT.bottom - PLOT.top);
      grid.append(
        svgNode('line', { class: 'grid', x1: x, y1: PLOT.top, x2: x, y2: PLOT.bottom }),
        svgNode('line', { class: 'grid', x1: PLOT.left, y1: y, x2: PLOT.right, y2: y }),
      );
      const xText = svgNode('text', { x, y: PLOT.bottom + 13, 'text-anchor': 'middle' });
      xText.textContent = hasXRange ? formatTick(xMin + ratio * (xMax - xMin)) : (index === 2 ? formatTick(xMin) : '');
      const yText = svgNode('text', { x: PLOT.left - 5, y: y + 3, 'text-anchor': 'end' });
      yText.textContent = formatTick(yMin + ratio * ySpan);
      labels.append(xText, yText);
    }

    series.setAttribute('points', this._values.map((value, index) =>
      `${xAt(this._xValues[index]).toFixed(2)},${yAt(value).toFixed(2)}`).join(' '));
    marker.removeAttribute('display');
    marker.setAttribute('cx', xAt(this._xValues.at(-1)).toFixed(2));
    marker.setAttribute('cy', yAt(this._values.at(-1)).toFixed(2));
    const suffix = unit ? ` ${unit}` : '';
    this.shadowRoot.querySelector('.summary').textContent =
      `Latest ${formatTick(this._values.at(-1))}${suffix} · Max ${formatTick(rawMax)}${suffix}`;
  }
}

if (!customElements.get('colav-line-graph')) {
  customElements.define('colav-line-graph', ColavLineGraph);
}

export { ColavLineGraph, formatTick };
