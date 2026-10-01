import spiceCards from './spice_cards.json';

const sheetsContainer = document.getElementById('sheetsContainer');
const filterControls = document.getElementById('filterControls');
const qtyMultiplier = document.getElementById('qtyMultiplier');

let currentFilter = 'all';

const EVENT_ICONS = {
  sacred_well: "⛲",
  forgotten_passage: "🚪",
  dead_scouts_map: "🗺️",
  ruined_watchtower: "🏰",
  wandering_hermit: "🧙",
  runic_monolith: "🔮",
  abandoned_hearth: "🔥",
  masters_forge: "⚒️",
  wandering_peddler: "🎒",
  trappers_cache: "📦",
  alchemists_alembic: "🧪",
  monstrous_clutch: "🥚",
  couriers_satchel: "✉️"
};

function renderPortraitEventCard(data) {
  const icon = EVENT_ICONS[data.id] || "✨";
  return `
    <div class="spice-card-portrait">
      <div class="p-header">
        <div class="p-tier-badge">${data.tier}</div>
        <div class="p-title">${data.name}</div>
      </div>
      <div class="p-subtitle-bar">
        <span>${data.subtitle || "Adventure Discovery"}</span>
        <span>Zone Level Scaling</span>
      </div>
      <div class="p-art-zone">
        <div class="p-icon-vignette">${icon}</div>
      </div>
      <div class="p-body">
        <div class="p-flavor">
          "${data.flavor || ''}"
        </div>
        <div class="p-choices-container">
          ${data.choices.map((c, idx) => `
            <div class="p-choice-card">
              <div class="p-choice-hdr">
                <span class="p-choice-title">${c.title}</span>
                <span class="p-choice-tag">${idx === 0 ? 'Choice 1' : 'Choice 2'}</span>
              </div>
              <div class="p-choice-desc">${c.desc}</div>
            </div>
          `).join('')}
        </div>
      </div>
      <div class="p-footer">
        <span>QUEST SPICE DECK</span>
        <span>${data.id.replace(/_/g, ' ')}</span>
      </div>
    </div>
  `;
}

function renderLandscapeCombatCard(data) {
  const nameLen = (data.name || '').length;
  const spineClass = nameLen >= 19 ? 'l-spine-name' : 'l-spine-name';
  const hdrStyle = nameLen > 18 ? 'font-size: 9.8pt; letter-spacing: 0.2px;' : '';

  return `
    <div class="spice-card-landscape">
      <div class="l-spine">
        <div class="l-spine-content">
          <div class="${spineClass}">${data.name}</div>
          <div class="l-spine-sub">
            <span class="l-spine-role">${data.spine_icon || '⚔️'} ${data.spine_role}</span>
            <span class="l-spine-hp">HP ${data.hp}</span>
          </div>
        </div>
      </div>
      <div class="l-main">
        <div class="l-header">
          <div class="l-title">${data.name}</div>
        </div>
        <div class="l-hp-badge">
          <div class="l-hp-badge-lbl">HP</div>
          <div class="l-hp-badge-val">${data.hp}</div>
        </div>
        <div class="l-sub-hdr">
          <span>Wilderness Combat</span>
          <span>${data.note || ''}</span>
        </div>
        <div class="l-body">
          ${data.ability ? `
            <div class="l-ability-box">
              ${data.ability}
            </div>
          ` : ''}
          <div class="l-rounds">
            ${data.pattern.map((r, i) => `
              <div class="l-round-box">
                <div class="l-round-num">ROUND ${i + 1}</div>
                <div class="l-round-stats">
                  <div class="l-stat-val l-dmg">🗡️ ${r[0]}</div>
                  <div class="l-stat-val l-blk">🛡️ ${r[1]}</div>
                </div>
              </div>
            `).join('')}
          </div>
          <div class="l-reward-box">
            <strong>REWARD:</strong> ${data.reward}
          </div>
        </div>
      </div>
    </div>
  `;
}

function renderCards() {
  sheetsContainer.innerHTML = '';
  const multiplier = parseInt(qtyMultiplier.value) || 1;

  const eventCards = spiceCards.filter(c => c.type === 'event');
  const combatCards = spiceCards.filter(c => c.type === 'combat');

  // 1. Render Portrait Events (3x3 grid = 9 cards per sheet)
  if (currentFilter === 'all' || currentFilter === 'event') {
    const allEvents = [];
    for (let m = 0; m < multiplier; m++) {
      allEvents.push(...eventCards);
    }

    const btnEvent = document.querySelector('[data-type="event"]');
    const btnCombat = document.querySelector('[data-type="combat"]');
    if (btnEvent) btnEvent.textContent = `Adventure Events (${eventCards.length})`;
    if (btnCombat) btnCombat.textContent = `Wilderness Combats (${combatCards.length})`;

    if (currentFilter === 'all') {
      const title = document.createElement('div');
      title.className = 'sheet-section-title';
      title.textContent = `${eventCards.length} Adventure Events (Portrait 2.5" × 3.5")`;
      sheetsContainer.appendChild(title);
    }

    let currentSheet = null;
    let count = 0;
    allEvents.forEach(data => {
      if (count % 9 === 0) {
        currentSheet = document.createElement('div');
        currentSheet.className = 'sheet-portrait';
        sheetsContainer.appendChild(currentSheet);
      }
      currentSheet.insertAdjacentHTML('beforeend', renderPortraitEventCard(data));
      count++;
    });

    if (currentSheet && count % 9 !== 0) {
      const rem = 9 - (count % 9);
      for (let i = 0; i < rem; i++) {
        currentSheet.insertAdjacentHTML('beforeend', '<div class="card-empty-portrait"></div>');
      }
    }
  }

  // 2. Render Landscape Combat Cards (2x4 grid = 8 cards per sheet)
  if (currentFilter === 'all' || currentFilter === 'combat') {
    const allCombat = [];
    for (let m = 0; m < multiplier; m++) {
      allCombat.push(...combatCards);
    }

    if (currentFilter === 'all') {
      const title = document.createElement('div');
      title.className = 'sheet-section-title';
      title.textContent = `${combatCards.length} Wilderness Combats (Landscape 3.5" × 2.5" with 46pt Spine)`;
      sheetsContainer.appendChild(title);
    }

    let currentSheet = null;
    let count = 0;
    allCombat.forEach(data => {
      if (count % 8 === 0) {
        currentSheet = document.createElement('div');
        currentSheet.className = 'sheet-landscape';
        sheetsContainer.appendChild(currentSheet);
      }
      currentSheet.insertAdjacentHTML('beforeend', renderLandscapeCombatCard(data));
      count++;
    });

    if (currentSheet && count % 8 !== 0) {
      const rem = 8 - (count % 8);
      for (let i = 0; i < rem; i++) {
        currentSheet.insertAdjacentHTML('beforeend', '<div class="card-empty-landscape"></div>');
      }
    }
  }
}

filterControls.addEventListener('click', (e) => {
  if (e.target.classList.contains('btn-filter')) {
    document.querySelectorAll('.btn-filter').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
    currentFilter = e.target.dataset.type;
    renderCards();
  }
});

qtyMultiplier.addEventListener('change', renderCards);

renderCards();
