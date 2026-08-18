import './style.css'
import cardsData from './cards_text.json'

let activeClass = 'all';
const classes = Object.keys(cardsData);
let productionMode = true;

function init() {
  renderFilters();
  renderSheets();

  document.getElementById('btn-print').addEventListener('click', () => {
    window.print();
  });

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
      document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
      e.target.classList.add('active');
      activeClass = e.target.getAttribute('data-class');
      renderSheets();
    });
  });
}

function renderSheets() {
  const container = document.getElementById('sheet-container');
  container.innerHTML = '';

  let cardsToRender = [];
  
  if (activeClass === 'all') {
    classes.forEach(cls => {
      Object.entries(cardsData[cls]).forEach(([name, data]) => {
        cardsToRender.push({ className: cls, name, data });
      });
    });
  } else {
    Object.entries(cardsData[activeClass]).forEach(([name, data]) => {
      cardsToRender.push({ className: activeClass, name, data });
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
       } else if (p.type === 'weave_source' || p.type === 'weave_payoff') {
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
    if (tlBadges) badgesHtml += `<div class="badge-wrapper badge-wrapper-tl">${tlBadges}</div>`;
    
    let trBadges = '';
    if (data.badges.heal) trBadges += `<div class="art-badge">➕ ${data.badges.heal}</div>`;
    if (data.badges.delayed_heal) trBadges += `<div class="art-badge">➕ ${data.badges.delayed_heal}</div>`;
    if (trBadges) badgesHtml += `<div class="badge-wrapper badge-wrapper-tr">${trBadges}</div>`;
    
    let blBadges = '';
    if (data.badges.range) blBadges += `<div class="art-badge">🎯 RANGE</div>`;
    if (blBadges) badgesHtml += `<div class="badge-wrapper badge-wrapper-bl">${blBadges}</div>`;
    
    let brBadges = '';
    if (data.badges.block) brBadges += `<div class="art-badge">🛡️ ${data.badges.block}</div>`;
    if (data.badges.delayed_block) brBadges += `<div class="art-badge">🛡️ ${data.badges.delayed_block}</div>`;
    if (brBadges) badgesHtml += `<div class="badge-wrapper badge-wrapper-br">${brBadges}</div>`;
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
          <div class="ftr-class">${className}</div>
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
        ${typeBarHtml}
        <div class="art-zone">
          ${badgesHtml}
        </div>
        <div class="divider"></div>
        <div class="card-body">
          ${data.panels ? htmlText : `<div class="effect-text">${htmlText}</div>`}
        </div>
        <div class="card-ftr">
          <div class="ftr-divider"></div>
          <div class="ftr-class">${className}</div>
        </div>
      </div>
    `;
  }
}

document.addEventListener('DOMContentLoaded', init);
