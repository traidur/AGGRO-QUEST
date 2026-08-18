import mobData from './mobs_text.json';

const sheetsContainer = document.getElementById('sheetsContainer');
const filterControls = document.getElementById('filterControls');
const qtyStandard = document.getElementById('qtyStandard');
const qtyElite = document.getElementById('qtyElite');
let currentFilter = 'all';

function renderCards() {
  sheetsContainer.innerHTML = '';
  
  let filteredMobs = [];
  
  if (currentFilter === 'all' || currentFilter === 'Standard') {
    const stdMultiplier = parseInt(qtyStandard.value) || 0;
    const stdMobs = mobData.filter(m => m.tier === "Standard");
    for (let i = 0; i < stdMultiplier; i++) {
      filteredMobs.push(...stdMobs);
    }
  }
  
  if (currentFilter === 'all' || currentFilter === 'Elite') {
    const eliteMultiplier = parseInt(qtyElite.value) || 0;
    const eliteMobs = mobData.filter(m => m.tier === "Elite");
    for (let i = 0; i < eliteMultiplier; i++) {
      filteredMobs.push(...eliteMobs);
    }
  }
  
  // Build exactly 8 cards per sheet (Landscape fits 2x4)
  let currentSheet = null;
  let cardCount = 0;
  
  filteredMobs.forEach(data => {
    if (cardCount % 8 === 0) {
      currentSheet = document.createElement('div');
      currentSheet.className = 'sheet';
      sheetsContainer.appendChild(currentSheet);
    }
    
    // Determine colors/layout based on tier/type
    const isElite = data.tier === "Elite";
    const bgGradient = isElite 
      ? 'linear-gradient(180deg, #4a0000 0%, #1a0000 100%)' 
      : 'linear-gradient(180deg, #2a2a2a 0%, #111111 100%)';
    const borderCol = isElite ? '#ff3333' : '#666';

    const cardHtml = `
      <div class="mob-card" style="border-color: ${borderCol};">
        <div class="mob-hdr" style="background: ${bgGradient};">
          <div class="mob-tier">${data.tier}</div>
          <div class="mob-name">${data.name}</div>
        </div>
        
        <div class="hp-badge">
          <div class="hp-label">HP</div>
          <div class="hp-val">${data.hp}</div>
        </div>
        
        <div class="art-zone">
          <div class="mob-spine" style="background: ${bgGradient}; border-left-color: ${borderCol};">
            <span class="spine-tier">${data.tier}</span>
            <span class="spine-name">${data.name}</span>
          </div>
          <div class="art-placeholder">ART</div>
          <img src="/mobs/${data.name.toLowerCase()}.jpg" 
               style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; object-fit: cover; z-index: 1;" 
               onerror="this.style.display='none'" />
          ${data.type !== "melee" ? `<div class="mob-type-tag">🎯 ${data.type}</div>` : ''}
        </div>
        
        <div class="mob-body">
          ${data.pattern.map((r, i) => `
            <div class="mob-round">
              <div class="round-num">ROUND ${i + 1}</div>
              <div class="round-stats">
                <div class="stat-box stat-dmg">🗡️ ${r[0]}</div>
                <div class="stat-box stat-blk">🛡️ ${r[1]}</div>
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    `;
    
    currentSheet.insertAdjacentHTML('beforeend', cardHtml);
    cardCount++;
  });
  
  // Fill remaining slots in the last sheet
  if (currentSheet && cardCount % 8 !== 0) {
    const remaining = 8 - (cardCount % 8);
    for (let i = 0; i < remaining; i++) {
      currentSheet.insertAdjacentHTML('beforeend', '<div class="card-empty"></div>');
    }
  }
}

// Set up UI filters
filterControls.addEventListener('click', (e) => {
  if (e.target.classList.contains('btn-filter')) {
    document.querySelectorAll('.btn-filter').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
    currentFilter = e.target.dataset.tier;
    renderCards();
  }
});

qtyStandard.addEventListener('change', renderCards);
qtyElite.addEventListener('change', renderCards);

// Initial render
renderCards();
