import mobData from './mobs_text.json';

const sheetsContainer = document.getElementById('sheetsContainer');
const filterControls = document.getElementById('filterControls');
const levelControls = document.getElementById('levelControls');
const qtyStandard = document.getElementById('qtyStandard');
const qtyElite = document.getElementById('qtyElite');
let currentFilter = 'all';
let currentLevelFilter = 'all';

const ROLE_DATA = {
  'grunt': { icon: '🛡️', role: 'Grunt' },
  'bruiser': { icon: '⏳', role: 'Bruiser' },
  'enforcer': { icon: '💥', role: 'Enforcer' },
  'raider': { icon: '⚔️', role: 'Raider' },
  'ambusher': { icon: '🗡️', role: 'Ambusher' },
  'scout': { icon: '🎯', role: 'Scout' },
  'bulwark': { icon: '🏰', role: 'Bulwark' },
  'berserker': { icon: '🩸', role: 'Berserker' },
  'warlord': { icon: '👑', role: 'Warlord' }
};

function renderCards() {
  sheetsContainer.innerHTML = '';

  const levelMatches = (m) => currentLevelFilter === 'all' || m.level === parseInt(currentLevelFilter);

  let filteredMobs = [];

  if (currentFilter === 'all' || currentFilter === 'Standard') {
    const stdMultiplier = parseInt(qtyStandard.value) || 0;
    const stdMobs = mobData.filter(m => m.tier === "Standard" && levelMatches(m));
    for (let i = 0; i < stdMultiplier; i++) {
      filteredMobs.push(...stdMobs);
    }
  }

  if (currentFilter === 'all' || currentFilter === 'Elite') {
    const eliteMultiplier = parseInt(qtyElite.value) || 0;
    const eliteMobs = mobData.filter(m => m.tier === "Elite" && levelMatches(m));
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

    const slug = (data.name || '').toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
    const mech = (data.mechanical_name || '').replace(/_L\d+$/i, '').toLowerCase();
    const knownFlavorArt = [
      'syndicate_deckhand',
      'the_powder_keg',
      'syndicate_enforcer',
      'the_cutthroat',
      'the_wrecker',
      'syndicate_gunner'
    ];
    const imgSrc = knownFlavorArt.includes(slug) ? `/mobs/${slug}.jpg` : (mech ? `/mobs/${mech}.jpg` : `/mobs/${slug}.jpg`);
    const fallbackSrc = mech ? `/mobs/${mech}.jpg` : '';

    const roleInfo = ROLE_DATA[mech] || { icon: '⚔️', role: data.tier.toUpperCase() };
    const roleBorder = isElite ? 'border-color: rgba(255, 68, 68, 0.6);' : '';

    const nameLen = (data.name || '').length;
    const spineClass = nameLen >= 18 ? 'spine-name tiny' : (nameLen >= 14 ? 'spine-name compact' : 'spine-name');
    const hdrStyle = nameLen > 18 ? 'font-size: 10.5pt;' : (nameLen > 14 ? 'font-size: 11.5pt;' : '');

    const cardHtml = `
      <div class="mob-card" style="border-color: ${borderCol};">
        <div class="mob-hdr" style="background: ${bgGradient};">
          <div class="mob-tier">${data.tier}</div>
          <div class="mob-name" style="${hdrStyle}">${data.name}</div>
        </div>
        
        <div class="hp-badge">
          <div class="hp-label">HP</div>
          <div class="hp-val">${data.hp}</div>
        </div>
        
        <div class="art-zone">
          <div class="mob-spine" style="background: ${bgGradient}; border-right-color: ${borderCol};">
            <div class="spine-content">
              <div class="${spineClass}">${data.name}</div>
              <div class="spine-sub">
                <span class="spine-role">${roleInfo.icon} ${roleInfo.role}</span>
                <span class="spine-hp">HP ${data.hp}</span>
              </div>
            </div>
          </div>
          <div class="art-placeholder">ART</div>
          <img src="${imgSrc}" 
               class="mob-art-img"
               data-fallback="${fallbackSrc}"
               onerror="if (this.dataset.fallback && this.src !== this.dataset.fallback && !this.src.endsWith(this.dataset.fallback)) { this.src = this.dataset.fallback; } else { this.style.display='none'; }" />
        </div>
        
        <div class="mob-body">
          ${data.pattern.map((r, i) => {
            const dmgIcon = data.type === 'ranged' ? '🏹' : '🗡️';
            return `
            <div class="mob-round">
              <div class="round-num">ROUND ${i + 1}</div>
              <div class="round-stats">
                <div class="stat-box stat-dmg">${dmgIcon} ${r[0]}</div>
                <div class="stat-box stat-blk">🛡️ ${r[1]}</div>
              </div>
            </div>
          `;}).join('')}
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

levelControls.addEventListener('click', (e) => {
  if (e.target.classList.contains('btn-level-filter')) {
    document.querySelectorAll('.btn-level-filter').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
    currentLevelFilter = e.target.dataset.level;
    renderCards();
  }
});

qtyStandard.addEventListener('change', renderCards);
qtyElite.addEventListener('change', renderCards);

// Art fit & zoom controls
const btnFitContain = document.getElementById('btnFitContain');
const btnFitCover = document.getElementById('btnFitCover');
const artZoom = document.getElementById('artZoom');
const zoomVal = document.getElementById('zoomVal');

if (btnFitContain && btnFitCover) {
  btnFitContain.addEventListener('click', () => {
    btnFitContain.classList.add('active');
    btnFitCover.classList.remove('active');
    document.documentElement.style.setProperty('--art-fit', 'contain');
  });
  btnFitCover.addEventListener('click', () => {
    btnFitCover.classList.add('active');
    btnFitContain.classList.remove('active');
    document.documentElement.style.setProperty('--art-fit', 'cover');
  });
}

if (artZoom && zoomVal) {
  artZoom.addEventListener('input', (e) => {
    const val = e.target.value;
    zoomVal.textContent = `${val}%`;
    document.documentElement.style.setProperty('--art-zoom', (val / 100).toString());
  });
}

// Initial render
renderCards();
