import trackerData from './tracker_boards.json';

function init() {
  render();
}

function render() {
  const container = document.getElementById('sheetsContainer');
  container.innerHTML = '';
  Object.entries(trackerData.classes).forEach(([className, data]) => {
    container.appendChild(renderBoard(className, data));
  });
}

function hpTrackHtml(maxHp) {
  const perRow = 10;
  let rows = '';
  for (let start = 1; start <= maxHp; start += perRow) {
    let boxes = '';
    for (let n = start; n <= Math.min(start + perRow - 1, maxHp); n++) {
      boxes += `<div class="hp-box">${n}</div>`;
    }
    rows += `<div class="hp-row">${boxes}</div>`;
  }
  return rows;
}

function matchupBlockHtml(label, m) {
  return `
    <div class="matchup-block">
      <div class="matchup-label">${label}</div>
      <div class="matchup-row matchup-best">
        <strong>Comfortable:</strong> ${m.best_1} (${m.best_1_cost}%), ${m.best_2} (${m.best_2_cost}%)
      </div>
      <div class="matchup-row matchup-worst">
        <strong>Struggles:</strong> ${m.worst_1} (${m.worst_1_cost}%), ${m.worst_2} (${m.worst_2_cost}%)
      </div>
    </div>
  `;
}

function renderBoard(className, data) {
  const sheet = document.createElement('div');
  sheet.className = 'tracker-sheet';
  sheet.innerHTML = `
    <div class="tracker-safe-zone">
      <div class="tracker-header">
        <div class="tracker-title">${className}</div>
        <div class="tracker-subtitle">Hero Tracker Board</div>
      </div>

      <div class="tracker-section">
        <div class="section-hdr">HP (${data.max_hp} max)</div>
        <div class="hp-track">${hpTrackHtml(data.max_hp)}</div>
        <div class="hp-hint">Place a token on your current HP. Starts full.</div>
      </div>

      <div class="tracker-resources">
        <div class="resource-box"><div class="resource-label">Gold</div><div class="resource-fill"></div></div>
        <div class="resource-box"><div class="resource-label">XP</div><div class="resource-fill"></div></div>
        <div class="resource-box"><div class="resource-label">Turn</div><div class="resource-fill"></div></div>
      </div>

      <div class="tracker-section">
        <div class="section-hdr">Class Guide</div>
        <div class="matchup-columns">
          ${matchupBlockHtml('Level 1', data.matchup_l1)}
          ${matchupBlockHtml('Level 2', data.matchup_l2)}
        </div>
      </div>

      <div class="tracker-section">
        <div class="section-hdr">Active Quests (place quest cards below)</div>
        <div class="quest-slots">
          <div class="quest-slot slot-red"><span>Quest Slot</span></div>
          <div class="quest-slot slot-green"><span>Quest Slot</span></div>
          <div class="quest-slot slot-blue"><span>Quest Slot</span></div>
        </div>
      </div>
    </div>
  `;
  return sheet;
}

init();
