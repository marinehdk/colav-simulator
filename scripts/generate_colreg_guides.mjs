import { mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const outputDir = path.join(root, 'web_gui/assets/openbridge');

const guides = [
  {
    file: 'Rule13-guide.svg',
    rule: 'Rule 13',
    title: '追越',
    english: 'Overtaking',
    scene: 'overtaking',
    sceneLabel: '本船从目标船正横后 22.5° 以上方向接近',
    points: [
      '追越船必须始终让清被追越船。',
      '尽早、明显、大幅度采取避让行动。',
      '只有完全驶过并清爽后，追越责任才解除。',
      '被追越船保持航向和航速，并持续监视。',
    ],
    ownRole: ['本船：追越船 / Give-way', '主动避让；优先向右舷大幅转向'],
    targetRole: ['目标船：被追越船 / Stand-on', '保持航向航速；持续监视'],
    thresholds: [['CPA', '≥ 1.0 NM'], ['TCPA', '≥ 12 min'], ['方位', '目标船正横后 > 22.5°']],
    stages: [
      ['识别局面', '确认追越态势', 'observe'],
      ['尽早行动', '右转并建立意图', 'starboard'],
      ['持续让清', '保持安全距离', 'monitor'],
      ['追越准备', '确认不妨碍目标船', 'pass'],
      ['完成追越', '完全驶过并清爽', 'clear'],
      ['恢复航线', '平稳返回计划航向', 'recover'],
    ],
    principles: ['大幅度', '尽早', '明显可见', '持续有效'],
    risks: ['行动过迟或小角度转向', '未完全清爽即返回航线'],
    core: '追越船承担持续让清责任，直至完全驶过并清爽。',
  },
  {
    file: 'Rule14-guide.svg',
    rule: 'Rule 14',
    title: '对头相遇',
    english: 'Head-on Situation',
    scene: 'headon',
    sceneLabel: '两船航向相反或接近相反，互见于正前方',
    points: [
      '两艘机动船均应采取避碰行动。',
      '双方均向右转，形成左舷对左舷通过。',
      '行动应尽早、明显，避免连续小幅修正。',
      '持续验证 CPA 增大；必要时配合减速。',
    ],
    ownRole: ['本船：Give-way', '向右舷转向，形成清晰避让意图'],
    targetRole: ['目标船：Give-way', '预期同样向右舷采取行动'],
    thresholds: [['CPA', '≥ 1.0 NM'], ['TCPA', '≥ 12 min'], ['航向差', '约 180°']],
    stages: [
      ['识别局面', '确认对头几何', 'observe'],
      ['规则判定', '双方承担责任', 'monitor'],
      ['尽早行动', '双方明显右转', 'starboard'],
      ['持续校核', '确认 CPA 增大', 'monitor'],
      ['安全通过', '左舷对左舷通过', 'clear'],
      ['恢复航线', '风险解除后返回', 'recover'],
    ],
    principles: ['双方责任', '右转优先', '尽早明显', '持续监测'],
    risks: ['等待对方先行动', '小角度修正导致意图不清'],
    core: '双方均向右转，使彼此从对方左舷安全通过。',
  },
  {
    file: 'Rule15-guide.svg',
    rule: 'Rule 15',
    title: '交叉相遇',
    english: 'Crossing',
    scene: 'crossing',
    sceneLabel: '目标船位于本船右舷，存在碰撞风险',
    points: [
      '右舷见船的本船为让路船。',
      '让路船尽早、大幅度改变航向或航速。',
      '应避免从直航船船首穿越。',
      '直航船保持航向航速，同时持续监视。',
    ],
    ownRole: ['本船：让路船 / Give-way', '优先向右转，从目标船船尾安全通过'],
    targetRole: ['目标船：直航船 / Stand-on', '保持航向航速；必要时发出提醒'],
    thresholds: [['CPA', '≥ 1.0 NM'], ['TCPA', '≥ 12 min'], ['夹角', '< 112.5°']],
    stages: [
      ['识别局面', '确认右舷来船', 'observe'],
      ['尽早决策', '规划船尾通过', 'monitor'],
      ['明显让路', '大幅向右转向', 'starboard'],
      ['安全通过', '保持目标船船尾', 'pass'],
      ['确认清爽', 'CPA 与 TCPA 安全', 'clear'],
      ['恢复航线', '无二次风险后返回', 'recover'],
    ],
    principles: ['尽早', '大幅度', '连续行动', '避免穿越船首'],
    risks: ['行动过迟或转向幅度不足', '安全通过后过早回切'],
    core: '让路船应采取明确行动，从直航船船尾安全通过。',
  },
  {
    file: 'Multiship-guide.svg',
    rule: 'Rules 16–17',
    title: '多船责任',
    english: 'Multiship Duties',
    scene: 'multiship',
    sceneLabel: '逐目标判责、统一排序，避免单目标动作制造新风险',
    points: [
      'Rule 16：让路船应尽早、大幅度采取行动。',
      'Rule 17：直航船保持航向航速并持续监视。',
      '让路行动不足时，直航船可采取协助避碰行动。',
      '任何动作都必须复核全局目标与二次冲突。',
    ],
    ownRole: ['让路目标：Rule 16', '果断、可见、持续地让清'],
    targetRole: ['直航目标：Rule 17', '保持为主；必要时独立行动'],
    thresholds: [['全局 CPA', '全部目标达标'], ['优先级', 'TCPA / 风险'], ['复核', '无二次冲突']],
    stages: [
      ['逐船识别', '建立责任与风险表', 'observe'],
      ['威胁排序', '锁定优先目标', 'monitor'],
      ['统一规划', '选择兼容避让动作', 'starboard'],
      ['持续监视', '跟踪所有目标趋势', 'monitor'],
      ['独立行动', '必要时协助避碰', 'pass'],
      ['全局恢复', '风险清除后回航线', 'recover'],
    ],
    principles: ['逐目标判责', '全局安全', '动作一致', '持续重评估'],
    risks: ['只处理最近目标', '单次转向制造二次冲突'],
    core: '局部动作必须服从全局安全；每次机动后重新评估全部目标。',
  },
];

const escapeXml = (value) => String(value)
  .replaceAll('&', '&amp;')
  .replaceAll('<', '&lt;')
  .replaceAll('>', '&gt;');

function tspans(lines, x, y, className = 'body', lineHeight = 28) {
  return `<text class="${className}">${lines.map((line, index) => `<tspan x="${x}" y="${y + index * lineHeight}">${escapeXml(line)}</tspan>`).join('')}</text>`;
}

function ship(x, y, color, rotation = 0, scale = 1) {
  return `<g transform="translate(${x} ${y}) rotate(${rotation}) scale(${scale})">
    <path d="M0 -30 C13 -25 17 -8 15 19 L8 32 H-8 L-15 19 C-17 -8 -13 -25 0 -30Z" fill="${color}" stroke="#fff" stroke-width="3"/>
    <rect x="-7" y="-7" width="14" height="18" rx="3" fill="#dceaf6"/>
    <line x1="0" y1="-24" x2="0" y2="24" stroke="#fff" stroke-opacity=".55" stroke-width="2"/>
  </g>`;
}

function scenarioGraphic(kind) {
  const arrow = 'marker-end="url(#arrow-white)"';
  if (kind === 'overtaking') return `
    <path d="M175 262 C180 205 215 145 255 90" class="track" ${arrow}/>
    <path d="M175 262 C110 205 115 120 255 90" class="action" marker-end="url(#arrow-green)"/>
    ${ship(175, 275, '#2f7d32', 0, .9)}${ship(255, 85, '#0b4f94', 0, .9)}
    <path d="M255 85 A98 98 0 0 0 163 151" class="sector"/>
    <text x="62" y="174" class="diagram-label">目标船尾部扇区 112.5°</text>`;
  if (kind === 'headon') return `
    <path d="M145 265 L235 70" class="track" ${arrow}/><path d="M355 265 L265 70" class="track" ${arrow}/>
    <path d="M145 265 C105 185 120 125 195 82" class="action" marker-end="url(#arrow-green)"/>
    <path d="M355 265 C395 185 380 125 305 82" class="action" marker-end="url(#arrow-green)"/>
    ${ship(145, 275, '#0b4f94', 0, .9)}${ship(355, 275, '#2f7d32', 0, .9)}
    <text x="178" y="166" class="diagram-label">双方明显向右转</text>`;
  if (kind === 'crossing') return `
    <path d="M190 276 L190 78" class="track" ${arrow}/><path d="M395 94 L190 94" class="track" ${arrow}/>
    <path d="M190 276 C245 220 305 170 350 116" class="action" marker-end="url(#arrow-green)"/>
    ${ship(190, 285, '#0b4f94', 0, .9)}${ship(400, 94, '#2f7d32', -90, .9)}
    <path d="M190 175 A82 82 0 0 1 270 95" class="sector"/>
    <text x="258" y="182" class="diagram-label">优先从目标船船尾通过</text>`;
  return `
    <path d="M250 285 L250 70" class="track" ${arrow}/><path d="M425 98 L248 98" class="track" ${arrow}/><path d="M75 125 L242 195" class="track" ${arrow}/>
    <path d="M250 285 C315 245 345 190 365 126" class="action" marker-end="url(#arrow-green)"/>
    ${ship(250, 292, '#0b4f94', 0, .85)}${ship(430, 98, '#2f7d32', -90, .78)}${ship(72, 124, '#d98916', 112, .72)}
    <text x="60" y="245" class="diagram-label">逐目标判责 · 全局复核</text>`;
}

function miniGraphic(mode) {
  const action = mode === 'observe'
    ? '<circle cx="121" cy="70" r="24" fill="none" stroke="#82b9e5" stroke-width="3"/><path d="M121 52V88M103 70H139" stroke="#82b9e5" stroke-width="3"/>'
    : mode === 'starboard'
      ? '<path d="M92 132 C95 84 128 60 173 48" class="mini-action" marker-end="url(#arrow-green)"/>'
      : mode === 'recover'
        ? '<path d="M87 132 C130 105 150 77 154 44" class="mini-action" marker-end="url(#arrow-green)"/>'
        : mode === 'clear'
          ? '<path d="M88 132 C113 95 146 74 183 56" class="mini-action" marker-end="url(#arrow-green)"/><circle cx="183" cy="56" r="15" fill="#2f7d32"/><path d="M176 56l5 5 10-13" fill="none" stroke="#fff" stroke-width="4"/>'
          : '<path d="M88 132 C120 106 148 82 175 57" class="mini-action" marker-end="url(#arrow-green)"/>';
  return `<g><path d="M82 138 L178 47" class="mini-track" marker-end="url(#arrow-white)"/>${action}${ship(82, 142, '#0b4f94', 0, .42)}${ship(181, 43, '#2f7d32', 45, .38)}</g>`;
}

function renderGuide(guide) {
  const bullets = guide.points.map((point, index) => `<g transform="translate(566 ${178 + index * 55})"><circle cx="0" cy="-6" r="4" fill="#006bd6"/>${tspans([point], 16, 0, 'body')}</g>`).join('');
  const thresholds = guide.thresholds.map(([label, value], index) => `<g transform="translate(${1080 + index * 156} 360)"><rect width="144" height="54" rx="8" class="metric"/><text x="12" y="20" class="micro muted">${escapeXml(label)}</text><text x="12" y="42" class="metric-value">${escapeXml(value)}</text></g>`).join('');
  const stages = guide.stages.map(([title, detail, mode], index) => {
    const x = 24 + index * 259;
    return `<g transform="translate(${x} 506)"><rect width="242" height="280" rx="10" class="card"/><rect width="242" height="42" rx="10" fill="#dceaf6"/><rect y="32" width="242" height="10" fill="#dceaf6"/><circle cx="24" cy="21" r="13" fill="#003b73"/><text x="24" y="27" text-anchor="middle" class="stage-number">${index + 1}</text><text x="45" y="27" class="stage-title">${escapeXml(title)}</text><g transform="translate(0 38)">${miniGraphic(mode)}</g><line x1="14" y1="210" x2="228" y2="210" class="divider"/><text x="18" y="238" class="small">${escapeXml(detail)}</text><text x="18" y="264" class="micro muted">${index < 5 ? '持续评估 CPA / TCPA' : '确认无新增风险'}</text></g>`;
  }).join('');
  const principles = guide.principles.map((item, index) => `<g transform="translate(${48 + (index % 2) * 226} ${872 + Math.floor(index / 2) * 42})"><circle r="12" fill="#2f7d32"/><path d="M-5 0l4 4 8-9" fill="none" stroke="#fff" stroke-width="3"/><text x="20" y="6" class="body">${escapeXml(item)}</text></g>`).join('');
  const riskLines = guide.risks.map((item, index) => `<text x="1082" y="${866 + index * 29}" class="small"><tspan fill="#c62828">●</tspan> ${escapeXml(item)}</text>`).join('');
  return `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1000" viewBox="0 0 1600 1000" role="img" aria-labelledby="title desc">
  <title id="title">${escapeXml(guide.rule)} ${escapeXml(guide.title)} COLREGs 操作参考</title>
  <desc id="desc">统一版式的高清矢量 COLREGs 规则、责任、操作流程与风险提示图</desc>
  <defs>
    <linearGradient id="header" x1="0" x2="1"><stop stop-color="#002f6c"/><stop offset="1" stop-color="#001f49"/></linearGradient>
    <linearGradient id="ocean" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#0b5b8d"/><stop offset="1" stop-color="#063b68"/></linearGradient>
    <pattern id="waves" width="80" height="28" patternUnits="userSpaceOnUse"><path d="M0 14 Q20 5 40 14 T80 14" fill="none" stroke="#fff" stroke-opacity=".08" stroke-width="2"/></pattern>
    <filter id="shadow" x="-10%" y="-10%" width="120%" height="125%"><feDropShadow dx="0" dy="3" stdDeviation="4" flood-color="#0d2a46" flood-opacity=".15"/></filter>
    <marker id="arrow-white" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0 0L10 5L0 10Z" fill="#fff"/></marker>
    <marker id="arrow-green" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0 0L10 5L0 10Z" fill="#83c44e"/></marker>
    <style>
      text{font-family:Inter,"Noto Sans SC","PingFang SC","Microsoft YaHei",sans-serif;fill:#102a43;text-rendering:geometricPrecision}
      .title{font-size:38px;font-weight:750;fill:#fff;letter-spacing:.2px}.subtitle{font-size:20px;font-weight:650;fill:#dceaf6}.pill{font-size:17px;font-weight:650;fill:#002f6c}
      .panel-title{font-size:20px;font-weight:720;fill:#003b73}.body{font-size:18px;font-weight:520}.small{font-size:16px;font-weight:540}.micro{font-size:14px;font-weight:540}.muted{fill:#52697d}.light{fill:#fff}.diagram-label{font-size:18px;font-weight:700;fill:#ffe44f}
      .card{fill:#fff;stroke:#9fb9d0;stroke-width:1.5;filter:url(#shadow)}.metric{fill:#f3f7fb;stroke:#abc0d3}.metric-value{font-size:16px;font-weight:760;fill:#003b73}
      .track{fill:none;stroke:#fff;stroke-width:3;stroke-dasharray:10 9}.action{fill:none;stroke:#83c44e;stroke-width:7;stroke-linecap:round}.sector{fill:none;stroke:#ffe44f;stroke-width:3;stroke-dasharray:8 6}
      .mini-track{fill:none;stroke:#fff;stroke-width:3;stroke-dasharray:8 7}.mini-action{fill:none;stroke:#83c44e;stroke-width:6;stroke-linecap:round}.stage-number{font-size:15px;font-weight:760;fill:#fff}.stage-title{font-size:17px;font-weight:700;fill:#003b73}.divider{stroke:#d7e1ea}
    </style>
  </defs>
  <rect width="1600" height="1000" fill="#eef3f8"/>
  <rect width="1600" height="88" fill="url(#header)"/>
  <text x="28" y="56" class="title" fill="#fff">${escapeXml(guide.rule)}  ${escapeXml(guide.title)} <tspan class="subtitle" fill="#dceaf6">(${escapeXml(guide.english)}) — COLREGs</tspan></text>
  <g transform="translate(1290 22)"><rect width="282" height="46" rx="8" fill="#fff"/><text x="141" y="30" text-anchor="middle" class="pill">适用 ODD：A 开阔水域</text></g>

  <g transform="translate(24 110)"><rect width="500" height="330" rx="12" fill="url(#ocean)" filter="url(#shadow)"/><rect width="500" height="330" rx="12" fill="url(#waves)"/><rect width="500" height="48" rx="12" fill="#002f6c"/><rect y="38" width="500" height="10" fill="#002f6c"/><text x="22" y="31" class="panel-title" style="fill:#fff">会遇态势示意图</text><rect x="18" y="66" width="464" height="48" rx="8" fill="#001f49" fill-opacity=".78"/><text x="34" y="97" class="small" style="fill:#fff">${escapeXml(guide.sceneLabel)}</text><g transform="translate(45 64) scale(.82)">${scenarioGraphic(guide.scene)}</g></g>

  <g><rect x="540" y="110" width="500" height="330" rx="12" class="card"/><rect x="540" y="110" width="500" height="48" rx="12" fill="#dceaf6"/><rect x="540" y="148" width="500" height="10" fill="#dceaf6"/><text x="566" y="141" class="panel-title">规则要点</text>${bullets}<rect x="564" y="396" width="452" height="28" rx="6" fill="#e8f2fb"/><text x="580" y="416" class="micro" fill="#003b73">相关：Rule 5 / 6 / 7 / 8 与本规则责任条款</text></g>

  <g><rect x="1056" y="110" width="520" height="330" rx="12" class="card"/><rect x="1056" y="110" width="520" height="48" rx="12" fill="#dceaf6"/><rect x="1056" y="148" width="520" height="10" fill="#dceaf6"/><text x="1082" y="141" class="panel-title">责任划分与判定阈值</text>${ship(1107, 210, '#0b4f94', 0, .7)}${tspans(guide.ownRole, 1142, 190, 'body', 31)}<line x1="1080" y1="248" x2="1552" y2="248" class="divider"/>${ship(1107, 298, '#2f7d32', 0, .7)}${tspans(guide.targetRole, 1142, 278, 'body', 31)}${thresholds}</g>

  <g><rect x="24" y="458" width="1552" height="36" rx="8" fill="#002f6c"/><text x="44" y="483" class="panel-title" style="fill:#fff">避碰操作流程 · 从识别到恢复</text>${stages}</g>

  <g><rect x="24" y="810" width="490" height="166" rx="12" class="card"/><rect x="24" y="810" width="490" height="42" rx="12" fill="#dceaf6"/><rect x="24" y="842" width="490" height="10" fill="#dceaf6"/><text x="48" y="838" class="panel-title">推荐行动原则 · Rule 8</text>${principles}</g>
  <g><rect x="530" y="810" width="510" height="166" rx="12" class="card"/><rect x="530" y="810" width="510" height="42" rx="12" fill="#dceaf6"/><rect x="530" y="842" width="510" height="10" fill="#dceaf6"/><text x="554" y="838" class="panel-title">统一评估基线</text><text x="558" y="882" class="body">CPA 安全阈值</text><text x="810" y="882" class="body" font-weight="760">≥ 1.0 NM</text><line x1="554" y1="898" x2="1016" y2="898" class="divider"/><text x="558" y="927" class="body">提前行动参考 TCPA</text><text x="810" y="927" class="body" font-weight="760">≥ 12 min</text><text x="558" y="958" class="micro muted">阈值为 ODD-A 展示基线；实际项目按验证配置执行。</text></g>
  <g><rect x="1056" y="810" width="520" height="166" rx="12" class="card"/><rect x="1056" y="810" width="520" height="42" rx="12" fill="#fff0ef"/><rect x="1056" y="842" width="520" height="10" fill="#fff0ef"/><text x="1082" y="838" class="panel-title" fill="#a5211b">常见风险与核心原则</text>${riskLines}<rect x="1078" y="928" width="476" height="34" rx="7" fill="#e8f5e9"/><text x="1094" y="950" class="micro" fill="#1f6b2c">${escapeXml(guide.core)}</text></g>
</svg>`;
}

await mkdir(outputDir, { recursive: true });
for (const guide of guides) {
  await writeFile(path.join(outputDir, guide.file), renderGuide(guide), 'utf8');
}

console.log(`Generated ${guides.length} COLREG guide SVGs in ${outputDir}`);
