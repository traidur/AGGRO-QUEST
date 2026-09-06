import './style.css'
import cardsData from './cards_text.json'

let activeClass = 'all';
let activeVersion = 'all';
let activeLevel = 'all'; // 'all' | '1' | '2'
const classes = Object.keys(cardsData);
let productionMode = true;

function init() {
  document.body.classList.add('hide-images'); // default: images off (matches heroes.html's initial button state)

  renderFilters();
  renderSheets();

  document.getElementById('btn-print').addEventListener('click', () => {
    window.print();
  });


  const imgBtn = document.getElementById('btn-images');
  if (imgBtn) {
    imgBtn.addEventListener('click', (e) => {
      document.body.classList.toggle('hide-images');
      const isHidden = document.body.classList.contains('hide-images');
      e.target.textContent = isHidden ? '🖼️ Images: OFF' : '🖼️ Images: ON';
      e.target.style.background = isHidden ? '#444' : '#00695C';
    });
  }

  const modeBtn = document.getElementById('btn-mode');
  if (modeBtn) {
    modeBtn.addEventListener('click', (e) => {
      productionMode = !productionMode;
      e.target.textContent = productionMode ? '🎨 Production' : '📝 Prototype';
      e.target.style.background = productionMode ? '#4A148C' : '#444';
      renderSheets();
    });
  }
}

function renderFilters() {
  const container = document.getElementById('class-filters');
  container.innerHTML = `<button class="filter-btn active" data-class="all">All</button>`;
  
  classes.forEach(cls => {
    container.innerHTML += `<button class="filter-btn" data-class="${cls}">${cls}</button>`;
  });

  container.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      container.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
      e.target.classList.add('active');
      activeClass = e.target.getAttribute('data-class');
      renderSheets();
    });
  });

  // Version tick: a number input (with the browser's native up/down tick arrows), not a
  // button-per-version list -- a button row silently runs out once enough cards pass a given
  // version number and nobody remembers to check for missing buttons. A number input scales to
  // any version that will ever exist, with a "Clear" action for "all" instead of a button.
  let vContainer = document.getElementById('version-filters');
  if (!vContainer) {
    vContainer = document.createElement('div');
    vContainer.id = 'version-filters';
    vContainer.style.marginTop = '10px';
    container.parentNode.appendChild(vContainer);
  }

  const versions = new Set();
  classes.forEach(cls => {
    Object.values(cardsData[cls]).forEach(data => versions.add(data.version || 1));
  });
  const maxVersion = Math.max(...versions);

  vContainer.innerHTML = `
    <span style="color:#aaa;margin-right:10px;font-family:sans-serif;font-size:14px;">Version:</span>
    <input type="number" id="version-tick" min="1" max="${maxVersion}"
           placeholder="all" style="width:60px;" value="${activeVersion === 'all' ? '' : activeVersion}">
    <button class="filter-btn" id="version-clear">All</button>
  `;

  document.getElementById('version-tick').addEventListener('input', (e) => {
    const v = e.target.value.trim();
    activeVersion = v === '' ? 'all' : v;
    renderSheets();
  });
  document.getElementById('version-clear').addEventListener('click', () => {
    document.getElementById('version-tick').value = '';
    activeVersion = 'all';
    renderSheets();
  });

  // Level filter: Level 1 (base kit) vs. Level 2 (upgrade cards) vs. both -- a different axis
  // from Version (print revision) entirely, so it's a separate control, not folded into it.
  let lContainer = document.getElementById('level-filters');
  if (!lContainer) {
    lContainer = document.createElement('div');
    lContainer.id = 'level-filters';
    lContainer.style.marginTop = '10px';
    container.parentNode.appendChild(lContainer);
  }
  lContainer.innerHTML = `
    <span style="color:#aaa;margin-right:10px;font-family:sans-serif;font-size:14px;">Level:</span>
    <button class="filter-btn ${activeLevel === 'all' ? 'active' : ''}" data-level="all">All</button>
    <button class="filter-btn ${activeLevel === '1' ? 'active' : ''}" data-level="1">Level 1</button>
    <button class="filter-btn ${activeLevel === '2' ? 'active' : ''}" data-level="2">Level 2</button>
  `;
  lContainer.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      lContainer.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
      e.target.classList.add('active');
      activeLevel = e.target.getAttribute('data-level');
      renderSheets();
    });
  });
}


function getHeroArt(className, cardName) {
  const map = {
    "Heavy Swing": "warrior_offense",
    "Sundering Blow": "warrior_offense",
    "Execute": "warrior_offense",
    "Vanguard Blade": "warrior_offense",
    "Vanguard Shield": "warrior_defense",
    "Shield Block": "warrior_defense",
    "Void Mark": "cleric_offense",
    "Smite": "cleric_offense",
    "Call of the Void": "cleric_offense",
    "Cleansing Barrier": "cleric_defense",
    "Fiery Fortitude": "cleric_defense",
    "Heal": "cleric_defense",

    "Might of the Aegis": "paladin_offense",
    "Bastion's Hammer": "paladin_offense",
    "Holy Fortress": "paladin_offense",
    "Sacred Light": "paladin_defense",
    "Invocation of Sanctuary": "paladin_defense",
    "Invocation of Grace": "paladin_defense",

  };
  if (map[cardName]) return `/heroes/${map[cardName]}.jpg`;
  return null;
}

function renderSheets() {
  const container = document.getElementById('sheet-container');
  container.innerHTML = '';

  let cardsToRender = [];
  
  const passesFilters = (data) => {
    if (activeVersion !== 'all' && String(data.version || 1) !== activeVersion) return false;
    if (activeLevel === '1' && data.level2) return false;
    if (activeLevel === '2' && !data.level2) return false;
    return true;
  };

  if (activeClass === 'all') {
    classes.forEach(cls => {
      Object.entries(cardsData[cls]).forEach(([name, data]) => {
        if (passesFilters(data)) {
          cardsToRender.push({ className: cls, name, data });
        }
      });
    });
  } else {
    Object.entries(cardsData[activeClass]).forEach(([name, data]) => {
      if (passesFilters(data)) {
        cardsToRender.push({ className: activeClass, name, data });
      }
    });
  }

  const cardsPerSheet = 9;
  for (let i = 0; i < cardsToRender.length; i += cardsPerSheet) {
    const sheetCards = cardsToRender.slice(i, i + cardsPerSheet);
    const sheetEl = document.createElement('div');
    sheetEl.className = 'sheet';

    sheetCards.forEach(card => {
      sheetEl.innerHTML += renderCard(card);
    });

    for (let j = sheetCards.length; j < cardsPerSheet; j++) {
      sheetEl.innerHTML += `<div class="card"><div class="card-empty"></div></div>`;
    }

    container.appendChild(sheetEl);
  }
  
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(() => requestAnimationFrame(() => applyScaling()));
  } else {
    requestAnimationFrame(() => applyScaling());
  }
}

function applyScaling() {
  // Card name fitting
  document.querySelectorAll('.card-name').forEach(nameEl => {
    let size = 13.5;
    nameEl.style.fontSize = size + 'pt';
    while (nameEl.scrollHeight > 28 && size > 6.5) {
      size -= 0.5;
      nameEl.style.fontSize = size + 'pt';
    }
  });

  document.querySelectorAll('.card').forEach(card => {
    const artZone = card.querySelector('.art-zone');
    if (!artZone) return;

    const splitTops = card.querySelectorAll('.split-top');
    const splitBots = card.querySelectorAll('.split-bottom');
    const effectTexts = card.querySelectorAll('.effect-text');
    const panels = card.querySelectorAll('.panels-container');
    
    const textEls = [...splitTops, ...splitBots, ...effectTexts, ...panels];
    if (textEls.length === 0) return;
    
    const fits = () => {
      for (const el of textEls) {
        const body = el.closest('.card-body');
        const cs = window.getComputedStyle(body);
        const avail = body.clientHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom);
        
        const elCs = window.getComputedStyle(el);
        const margins = parseFloat(elCs.marginTop) + parseFloat(elCs.marginBottom);
        
        if (el.scrollHeight + margins > avail + 1) {
          return false;
        }
      }
      return true;
    };

    const tryFont = (floor) => {
      for (let fs = 13.5; fs >= floor; fs -= 0.5) {
        textEls.forEach(el => el.style.fontSize = fs + 'pt');
        if (fits()) return true;
      }
      return false;
    };

    const resetLevers = (artPt) => {
      artZone.style.height = artPt + 'pt';
      textEls.forEach(el => el.style.lineHeight = '1.25');
    };

    if (!productionMode) {
      resetLevers(38);
      tryFont(7.5);
      return;
    }

    const isSplit = splitTops.length > 0;
    const artSizes = isSplit ? [56, 38] : [114, 76, 56, 38];

    // Hide badges temporarily so their absolute positioning doesn't inflate scrollHeight
    const badges = card.querySelectorAll('.stance-badge');
    badges.forEach(b => b.style.display = 'none');

    for (const artPt of artSizes) {
      resetLevers(artPt);
      if (tryFont(9)) break;

      textEls.forEach(el => el.style.lineHeight = '1.15');
      if (tryFont(9)) break;
    }
    
    // If it didn't break out of the loop with a fit, it falls back
    if (!fits()) {
      resetLevers(38);
      tryFont(7.5);
    }

    // Restore badges
    badges.forEach(b => b.style.display = '');
  });
}

function renderCard({ className, name, data }) {
  let rawText = data.text;
  let rawTags = data.tags || [];

  function getTagClass(tag) {
    if (tag.includes('STRIKE') || tag.includes('COMBO') || tag.includes('SUNDER') || tag.includes('KILLING BLOW') || tag.includes('FINISHER') || tag.includes('OPENER')) return 'tag-attack';
    if (tag.includes('SACRED BALANCE') || tag.includes('INVOCATION') || tag.includes('HEAL')) return 'tag-holy';
    if (tag.includes('SPELLWEAVE') || tag.includes('ECHO')) return 'tag-magic';
    if (tag.includes('AT RANGE') || tag.includes('PET') || tag.includes('PERSISTENT') || tag.includes('SHAPESHIFT') || tag.includes('ECLIPSE')) return 'tag-nature';
    if (tag.includes('DOT')) return 'tag-dark';
    return 'tag-default';
  }

  let tagsHtml = rawTags.map(t => `<span class="tag ${getTagClass(t)}">${t}</span>`).join(' ');

  // Level 2 marker -- mandatory (free, automatic) vs. purchased (costs Gold) get different
  // colors since a player's mental model of "how do I get this" differs between them. Distinct
  // from the Version badge in the footer (print-revision tracking), a different axis entirely.
  let levelBadgeHtml = '';
  let replacesHtml = '';
  if (data.level2) {
    const tierColor = data.tier === 'mandatory' ? '#F9A825' : '#6A1B9A';
    const tierLabel = data.tier === 'mandatory' ? 'LV2 · FREE' : 'LV2 · PURCHASED';
    levelBadgeHtml = `<div class="level2-badge" style="background:${tierColor};" title="${data.tier}">${tierLabel}</div>`;
    replacesHtml = `<div class="replaces-line">Replaces: ${data.replaces}</div>`;
  }

  let typeBarHtml = rawTags.length > 0 ?
    `<div class="type-bar">${tagsHtml}</div>` : 
    `<div class="type-bar"></div>`;

  // Convert markdown bold to HTML bold and split into logical lines
  let htmlText = rawText.replace(/\*\*(.*?)\*\*/g, '<b>$1</b>');
  let aggroText = data.aggro.replace('Aggro ', '');

  if (data.panels && data.panels.length > 0) {
    let panelsHtml = data.panels.map(p => {
       let pText = p.text.replace(/\*\*(.*?)\*\*/g, '<b>$1</b>');
       if (p.type === 'base') {
          return `<div class="effect-text" style="margin-bottom: 4pt;">${pText}</div>`;
       } else if (p.type === 'positioning') {
          return `
            <div class="sub-panel panel-nature">
              <div class="sub-panel-label">${p.label}</div>
              <div class="sub-panel-text">${pText}</div>
            </div>
          `;
       } else if (p.type === 'weave_source' || p.type === 'weave_payoff' || p.type === 'echo') {
          return `
            <div class="sub-panel panel-magic">
              <div class="sub-panel-label">${p.label}</div>
              <div class="sub-panel-text">${pText}</div>
            </div>
          `;
       } else if (p.type === 'sacred_balance' || p.type === 'invocation') {
          return `
            <div class="sub-panel panel-holy">
              <div class="sub-panel-label">${p.label}</div>
              <div class="sub-panel-text">${pText}</div>
            </div>
          `;
       } else if (p.type === 'buff') {
          return `
            <div class="sub-panel panel-buff">
              <div class="sub-panel-label">${p.label}</div>
              <div class="sub-panel-text">${pText}</div>
            </div>
          `;
       } else if (p.type === 'finisher' || p.type === 'rider') {
          return `
            <div class="sub-panel panel-combo">
              <div class="sub-panel-label">${p.label}</div>
              <div class="sub-panel-text">${pText}</div>
            </div>
          `;
       }
    }).join('');
    htmlText = `<div class="panels-container">${panelsHtml}</div>`;
  }

  let badgesHtml = '';
  if (data.badges) {
    let tlBadges = '';
    if (data.badges.dmg) tlBadges += `<div class="art-badge">🗡️ ${data.badges.dmg}</div>`;
    if (data.badges.delayed_dmg) tlBadges += `<div class="art-badge">🗡️ ${data.badges.delayed_dmg}</div>`;
    if (tlBadges) badgesHtml += `<div class="badge-wrapper badge-wrapper-tl" style="z-index:2;">${tlBadges}</div>`;
    
    let trBadges = '';
    if (data.badges.heal) trBadges += `<div class="art-badge">➕ ${data.badges.heal}</div>`;
    if (data.badges.delayed_heal) trBadges += `<div class="art-badge">➕ ${data.badges.delayed_heal}</div>`;
    if (trBadges) badgesHtml += `<div class="badge-wrapper badge-wrapper-tr" style="z-index:2;">${trBadges}</div>`;
    
    let blBadges = '';
    if (data.badges.range) blBadges += `<div class="art-badge">🎯 RANGE</div>`;
    if (blBadges) badgesHtml += `<div class="badge-wrapper badge-wrapper-bl" style="z-index:2;">${blBadges}</div>`;
    
    let brBadges = '';
    if (data.badges.block) brBadges += `<div class="art-badge">🛡️ ${data.badges.block}</div>`;
    if (data.badges.delayed_block) brBadges += `<div class="art-badge">🛡️ ${data.badges.delayed_block}</div>`;
    if (brBadges) badgesHtml += `<div class="badge-wrapper badge-wrapper-br" style="z-index:2;">${brBadges}</div>`;
  }

  
  const artPath = getHeroArt(className, name);
  let artImgHtml = '';
  if (artPath) {
    artImgHtml = `<img src="${artPath}" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; object-fit: cover; z-index: 1;" onerror="this.style.display='none'" />`;
  }

  if (data.split) {
    let aggroG = data.aggro_G !== undefined ? data.aggro_G : data.aggro.replace('Aggro ', '');
    let cHtml = data.champion_text.replace(/\*\*(.*?)\*\*/g, '<b>$1</b>');
    let gHtml = data.guardian_text.replace(/\*\*(.*?)\*\*/g, '<b>$1</b>');
    
    let badgesCHtml = '';
    if (data.badges_C) {
      if (data.badges_C.dmg) badgesCHtml += `<div class="stance-badge badge-c-tl">🗡️ ${data.badges_C.dmg}</div>`;
      if (data.badges_C.block) badgesCHtml += `<div class="stance-badge badge-c-br">🛡️ ${data.badges_C.block}</div>`;
    }
    let badgesGHtml = '';
    if (data.badges_G) {
      if (data.badges_G.dmg) badgesGHtml += `<div class="stance-badge badge-c-tl">🗡️ ${data.badges_G.dmg}</div>`;
      if (data.badges_G.block) badgesGHtml += `<div class="stance-badge badge-c-br">🛡️ ${data.badges_G.block}</div>`;
    }

    return `
      <div class="card cls-${className}">
        <div class="card-hdr">
          <div class="card-name">${name}</div>
          <div class="aggro-badge" title="Aggro">A: ${aggroText}</div>
        </div>
        ${levelBadgeHtml}
        ${typeBarHtml}
        <div class="card-body" style="padding-bottom: 2pt;">
          <div class="split-top" style="border-bottom: none; padding-bottom: 0;">
            ${badgesCHtml}
            <div class="stance-label">Champion</div>
            <div>${cHtml}</div>
          </div>
        </div>
        <div class="divider"></div>
        <div class="art-zone">
          ${artImgHtml}
          ${badgesHtml}
        </div>
        <div class="divider"></div>
        <div class="card-body" style="padding-top: 2pt;">
          <div class="split-bottom">
            ${badgesGHtml}
            <div class="mini-hdr" style="display: flex; gap: 8pt; align-items: center;">
              <span>${name}</span>
              <span class="mini-aggro">A: ${aggroG}</span>
            </div>
            <div class="stance-label">Guardian</div>
            <div>${gHtml}</div>
          </div>
        </div>
        <div class="card-ftr">
          <div class="ftr-divider"></div>
          ${replacesHtml}
          <div class="ftr-class">${className}${data.version ? ` v${data.version}` : ' v1'}</div>
        </div>
      </div>
    `;
  } else {
    return `
      <div class="card cls-${className}">
        <div class="card-hdr">
          <div class="card-name">${name}</div>
          <div class="aggro-badge" title="Aggro">A: ${aggroText}</div>
        </div>
        ${levelBadgeHtml}
        ${typeBarHtml}
        <div class="art-zone">
          ${artImgHtml}
          ${badgesHtml}
        </div>
        <div class="divider"></div>
        <div class="card-body">
          ${data.panels ? htmlText : `<div class="effect-text">${htmlText}</div>`}
        </div>
        <div class="card-ftr">
          <div class="ftr-divider"></div>
          ${replacesHtml}
          <div class="ftr-class">${className}${data.version ? ` v${data.version}` : ' v1'}</div>
        </div>
      </div>
    `;
  }
}

document.addEventListener('DOMContentLoaded', init);
