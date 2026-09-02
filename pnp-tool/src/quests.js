import itemsData from './quests_items.json';

let currentTab = 'quests';
let multiplier = 1;

function init() {
  document.querySelectorAll('.btn-filter').forEach(btn => {
    btn.addEventListener('click', (e) => {
      document.querySelectorAll('.btn-filter').forEach(b => b.classList.remove('active'));
      e.target.classList.add('active');
      currentTab = e.target.getAttribute('data-tab');
      render();
    });
  });

  const multInput = document.getElementById('qtyMultiplier');
  multInput.addEventListener('change', (e) => {
    multiplier = parseInt(e.target.value) || 1;
    render();
  });

  render();
}

function render() {
  const container = document.getElementById('sheetsContainer');
  container.innerHTML = '';
  
  let cards = [];
  
  if (currentTab === 'quests') {
    Object.entries(itemsData.quests).forEach(([name, q]) => {
      for (let i = 0; i < multiplier; i++) {
        cards.push(renderQuestCard(name, q));
      }
    });
    paginate(cards, 9, container); // 3x3 poker cards per 8.5x11 page
  } else if (currentTab === 'loot') {
    Object.entries(itemsData.loot).forEach(([name, l]) => {
      for (let i = 0; i < multiplier; i++) {
        cards.push(renderLootCard(name, l));
      }
    });
    paginate(cards, 16, container); // 4x4 mini cards per page (approx)
  } else if (currentTab === 'consumables') {
    Object.entries(itemsData.consumables).forEach(([name, c]) => {
      for (let i = 0; i < multiplier; i++) {
        cards.push(renderConsumableCard(name, c));
      }
    });
    paginate(cards, 16, container); 
  }
}

function paginate(htmlArray, perPage, container) {
  for (let i = 0; i < htmlArray.length; i += perPage) {
    const chunk = htmlArray.slice(i, i + perPage);
    const sheet = document.createElement('div');
    sheet.className = 'sheet';
    sheet.innerHTML = chunk.join('');
    container.appendChild(sheet);
  }
}

function renderQuestCard(name, q) {
  let ladderHtml = '';
  const stages = ["Fresh (0)", "Decay (1)", "Decay (2)", "Dead (3)"];
  q.gold_ladder.forEach((g, i) => {
    ladderHtml += `
      <div class="ladder-row">
        <span>${stages[i]}</span>
        <strong>${g}G</strong>
      </div>
    `;
  });

  return `
    <div class="card-poker">
      <div class="safe-zone">
        <div class="quest-header">
          <div class="quest-title">${name}</div>
          <div class="quest-tier">${q.tier}</div>
        </div>
        <div class="quest-body">
          <div style="font-size: 10pt; margin-bottom: 4px;">REQUIRES</div>
          <div class="req-circle">${q.required}</div>
          <div style="font-size: 10pt;">Loot</div>
          <div class="ladder-box">
            ${ladderHtml}
          </div>
        </div>
        <div class="quest-footer">
          Reward: ${q.base_xp} XP
        </div>
      </div>
    </div>
  `;
}

function renderLootCard(name, l) {
  return `
    <div class="card-mini">
      <div class="safe-zone" style="border-color: ${l.color};">
        <div class="mini-header" style="background: ${l.color};">
          ${name.toUpperCase()}
        </div>
        <div class="mini-body" style="color: ${l.color}; font-weight: bold; font-size: 10pt;">
          ★<br><br>${l.desc}
        </div>
      </div>
    </div>
  `;
}

function renderConsumableCard(name, c) {
  const effectHtml = c.effect.replace(/\n/g, '<br>');
  return `
    <div class="card-mini">
      <div class="safe-zone">
        <div class="mini-cost">${c.cost}</div>
        <div class="mini-header" style="background: #34495e;">
          ${name}
        </div>
        <div class="mini-body">
          ${effectHtml}
        </div>
      </div>
    </div>
  `;
}

init();
