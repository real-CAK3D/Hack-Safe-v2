let currentConfig = null;
let lastStatus = null;
let lastAIChat = null;
let cydBuddyActionStatus = '';
let busyButtons = new Set();
let cameraTimer = null;
let cameraEnabled = null;
let cameraInflight = false;
let activeCameraFeed = localStorage.getItem('spac3ActiveCameraFeed') || 'local';
let activeTab = 'dash';
let cpuHist = [], ramHist = [], diskHist = [], loadHist = [], indoorTempHist = [], humidityHist = [], lightHist = [], rxHist = [], txHist = [], gpsSatsHist = [], gpsSignalHist = [], weatherTempHist = [], weatherHumidityHist = [], weatherWindHist = [];
let lastRecon = null;
let stealthMode = false;
let wifiVaultVisible = false;
let wifiPasswordsRevealed = false;
let wifiVaultData = null;
let soundMode = false;
let selectedExternal = 'bak3ry';
let protonFxEnabled = localStorage.getItem('protonFxEnabled') !== '0';
let protonMapZoom = Number(localStorage.getItem('protonMapZoom') || '1');
let selectedProtonProfile = localStorage.getItem('selectedProtonProfile') || '';
let protonActionStatus = '';
let currentTheme = localStorage.getItem('spac3Theme') || 'default';
let currentFacePack = localStorage.getItem('spac3FacePack') || 'default';
let connectedMarkerIndex = Number(localStorage.getItem('connectedMarkerIndex') || '5');
let lastMarkerShuffle = 0;
let audioCtx = null;
let lastAlertLevel = null;
let lastGpsFixed = null;
let tiltPollBusy = false;
let refreshBusy = false;
let refreshQueued = false;
let aquariumFeedCount = Number(localStorage.getItem('aquariumFeedCount') || '0');
let aquariumLastFed = Number(localStorage.getItem('aquariumLastFed') || '0');
let selectedWifiSsid = localStorage.getItem('spac3SelectedWifiSsid') || '';
let lastWifiAction = null;
let pwnFaceTimer = null;
let faceState = { mood: '', face: '', nextAt: 0, history: [] };

function line(label, value) { return `${label}: ${value ?? 'n/a'}`; }
function yes(v) { return v ? 'yes' : 'no'; }
function clamp(n, a=0, b=100) { return Math.max(a, Math.min(b, Number(n) || 0)); }
function eventTime(ts) { return ts ? new Date(ts * 1000).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'}) : '--:--'; }
function uptimeText(seconds) { const s=Math.max(0,Number(seconds||0)); const d=Math.floor(s/86400), h=Math.floor((s%86400)/3600), m=Math.floor((s%3600)/60); return d?`${d}d ${h}h`:h?`${h}h ${m}m`:`${m}m`; }
function diskShort(dfLine) { const p=String(dfLine||'').trim().split(/\s+/); return p.length>=5 ? `${p[2]}/${p[1]} ${p[4]}` : (dfLine || 'n/a'); }
function diskPercent(dfLine) { const m=String(dfLine||'').match(/(\d+)%/); return m ? Number(m[1]) : 0; }
function weatherIcon(summary='', night=false) { const s=String(summary||'').toLowerCase(); if(s.includes('rain')) return '🌧'; if(s.includes('storm')||s.includes('thunder')) return '⛈'; if(s.includes('snow')) return '❄'; if(s.includes('cloud')) return night?'☁':'☁'; if(s.includes('fog')||s.includes('mist')) return '🌫'; if(s.includes('sun')||s.includes('clear')) return night?'🌙':'☀'; return night?'◌':'◌'; }
function tempClass(c) { if(c == null || Number.isNaN(Number(c))) return 'temp-ok'; if(c >= 75) return 'temp-hot'; if(c >= 65) return 'temp-warm'; if(c <= 45) return 'temp-cool'; return 'temp-ok'; }
function sensorTempClass(f) { if(f == null || Number.isNaN(Number(f))) return 'temp-ok'; if(f >= 88) return 'temp-hot'; if(f >= 78) return 'temp-warm'; if(f <= 60) return 'temp-cool'; return 'temp-ok'; }
function spark(values) { const max=Math.max(...values,1), min=Math.min(...values,0); const chars='▁▂▃▄▅▆▇█'; return values.map(v=>chars[Math.round(((v-min)/(max-min||1))*(chars.length-1))]).join(''); }
let waveSeq=0;
window.__waveRegistry = window.__waveRegistry || new Map();
function liveWave(label, values, value, color='var(--green)', lo=0, hi=100) {
  const id=`wv${waveSeq++}`;
  const nums=(values||[]).map(Number).filter(Number.isFinite);
  window.__waveRegistry.set(id, {values:nums, color, lo, hi});
  const latest=nums.length?nums[nums.length-1]:0, prev=nums.length>1?nums[nums.length-2]:latest;
  const trend=latest>prev+.5?'▲':latest<prev-.5?'▼':'◆';
  const min=nums.length?Math.min(...nums).toFixed(0):'--', max=nums.length?Math.max(...nums).toFixed(0):'--';
  const avg=nums.length?(nums.reduce((a,b)=>a+b,0)/nums.length).toFixed(0):'--';
  return `<div class="wave-card sec-wave tc-card" style="--wave:${color}"><div class="wave-head"><span>${label}</span><b>${value}</b></div><div class="tc-wrap"><canvas class="tc-canvas" id="${id}" aria-label="${escapeHtml(label)} live line graph"></canvas><div class="tc-tip" data-for="${id}" hidden></div></div><div class="wave-meta"><span>${trend} live</span><span>min ${min}</span><span>avg ${avg}</span><span>max ${max}</span></div></div>`;
}
function pushHist(arr, val, max=48){ arr.push(Number(val)||0); while(arr.length>max) arr.shift(); return arr; }
function bytesPerSec(n){ n=Number(n)||0; const u=['B/s','KB/s','MB/s','GB/s']; let i=0; while(n>=1024&&i<u.length-1){n/=1024;i++;} return `${n>=10?n.toFixed(0):n.toFixed(1)} ${u[i]}`; }
function bytesFmt(n){ n=Number(n)||0; const u=['B','KB','MB','GB','TB']; let i=0; while(n>=1024&&i<u.length-1){n/=1024;i++;} return `${n>=10?n.toFixed(1):n.toFixed(2)} ${u[i]}`; }
function signalBars(sig){ sig=clamp(sig); const level=sig>=80?4:sig>=55?3:sig>=30?2:sig>0?1:0; return `<div class="signal-bars" title="${sig}%">${[1,2,3,4].map(i=>`<i class="${i<=level?'on':''}" style="height:${7+i*5}px"></i>`).join('')}<b>${sig||0}%</b></div>`; }
function weatherTileXY(lat, lon, z=6){ lat=Number(lat); lon=Number(lon); if(!Number.isFinite(lat)||!Number.isFinite(lon)) return null; const n=2**z; const x=Math.floor((lon+180)/360*n); const rad=lat*Math.PI/180; const y=Math.floor((1-Math.log(Math.tan(rad)+1/Math.cos(rad))/Math.PI)/2*n); return {z,x,y}; }
function parseWeatherClock(text){ const m=String(text||'').trim().match(/^(\d{1,2}):(\d{2})\s*(AM|PM)?$/i); if(!m) return null; let h=Number(m[1]), min=Number(m[2]); const ap=(m[3]||'').toUpperCase(); if(ap==='PM'&&h<12)h+=12; if(ap==='AM'&&h===12)h=0; return h*60+min; }
function weatherDayState(weather={}){ const now=new Date(); const mins=now.getHours()*60+now.getMinutes(); const sr=parseWeatherClock(weather.sunrise), ss=parseWeatherClock(weather.sunset); const has=sr!=null&&ss!=null; const isDay=has ? (mins>=sr&&mins<ss) : !String(weather.summary||'').toLowerCase().includes('night'); const span=has?Math.max(1,ss-sr):720; const progress=has?clamp(((mins-sr)/span)*100,0,100):50; return {isDay, isNight:!isDay, progress, sunrise:weather.sunrise||'n/a', sunset:weather.sunset||'n/a'}; }
function geoToMapPercent(lat, lon){ lat=Number(lat); lon=Number(lon); return [clamp(((lon+180)/360)*100,0,100), clamp(((90-lat)/180)*100,0,100)]; }
// Marker anchors are pixel coordinates inside assets/proton-world.svg (1538.434 x 700).
// Each one was verified with SVG isPointInFill to sit inside its country's land shape,
// so pins land on the country regardless of how the panel is sized.
const PROTON_MAP_W=1538.434, PROTON_MAP_H=700;
const MAP_ANCHORS={
  'US-ME':[363,168],'US-NY':[339,177],'US-FL':[323,236],'US-TX':[268,232],'US-CA':[203,208],'US-WA':[210,167],
  'UK':[696,131],'NL':[723,131],'DE':[739,137],'CH':[730,159],'PL':[779,133],'SE':[766,72],'IT':[743,166],'ES':[685,189],
  'TR':[838,196],'IN':[1042,280],'SG':[1159,387],'JP':[1280,209],'AU':[1306,528],'BR':[476,452],'AR':[427,573],'ZA':[797,547]
};
function mapAnchorPercent(marker){ const a=MAP_ANCHORS[marker.name]; return a ? [a[0]/PROTON_MAP_W*100, a[1]/PROTON_MAP_H*100] : geoToMapPercent(marker.lat, marker.lon); }
function tiltVisual(gpio={}, tilt={}){ const label=String(gpio.tiltOrientation||gpio.tiltLabel||tilt.orientation||'UNKNOWN'); const raw=gpio.tiltRaw ?? gpio.tilt ?? tilt.raw; const levelRaw=gpio.tiltLevelRaw ?? tilt.level_raw ?? 'n/a'; const angle=Number(gpio.tiltAngle ?? tilt.angle ?? (label==='LEVEL'?0:28)); const visualAngle=label==='LEVEL'?0:-angle; const side=label==='LEVEL'?'LEVEL':label==='TILTED'?'TILTED':'UNKNOWN'; return `<div id="tiltStage" class="tilt-stage ${tilt.changed?'shake':''}"><div id="tiltLabel" class="tilt-label">${label} // raw ${raw ?? 'n/a'} // level raw ${levelRaw}</div><div id="tiltBoard" class="tilt-board" style="transform:rotate(${visualAngle}deg)"><span></span></div><div class="tilt-axis"><b>R</b><em></em><b>L</b></div><small id="tiltReadout">LIVE raw=${raw ?? 'n/a'} levelRaw=${levelRaw} sensor=${angle}° display=${visualAngle}° age=${tilt.age_s!=null?Number(tilt.age_s).toFixed(1)+'s':'n/a'}</small></div>`; }
function applyTilt(data={}){ const gpio=data.gpio||{}, tilt=data.tilt_event||{}; const raw=gpio.tiltRaw ?? gpio.tilt ?? tilt.raw; const levelRaw=gpio.tiltLevelRaw ?? tilt.level_raw ?? 'n/a'; const label=String(gpio.tiltOrientation||gpio.tiltLabel||tilt.orientation||'UNKNOWN'); const angle=Number(gpio.tiltAngle ?? tilt.angle ?? (label==='LEVEL'?0:28)); const visualAngle=label==='LEVEL'?0:-angle; const board=document.getElementById('tiltBoard'), lab=document.getElementById('tiltLabel'), read=document.getElementById('tiltReadout'), stage=document.getElementById('tiltStage'); if(board) board.style.transform=`rotate(${visualAngle}deg)`; if(lab) lab.textContent=`${label} // raw ${raw ?? 'n/a'} // level raw ${levelRaw}`; if(read) read.textContent=`LIVE raw=${raw ?? 'n/a'} levelRaw=${levelRaw} sensor=${angle}° display=${visualAngle}° ${data.live?'fast GPIO':''}`; if(stage){ stage.classList.toggle('shake', !!tilt.changed); stage.classList.toggle('tilt-left', label==='TILTED'); stage.classList.toggle('tilt-right', false); } }
function satelliteStrengthGrid(sats=[]){
  const rows=(sats||[]).slice().sort((a,b)=>(b.used?1:0)-(a.used?1:0) || Number(b.ss||0)-Number(a.ss||0));
  if(!rows.length) return '<div class="gps-sat-list"><b>INDIVIDUAL SATELLITE STRENGTH</b><span>waiting for SKY signal</span></div>';
  return `<div class="gps-sat-list gps-sat-strength"><b>INDIVIDUAL SATELLITE STRENGTH</b>${rows.map(s=>{ const ss=Number(s.ss||0); const pct=Math.max(0,Math.min(100,Math.round((ss/50)*100))); return `<span class="${s.used?'used':'seen'}"><em>PRN ${escapeHtml(s.prn ?? '?')}</em><i><u style="width:${pct}%"></u></i><strong>${ss} dB-Hz</strong><small>${s.used?'used':'seen'}</small></span>`; }).join('')}</div>`;
}
function bar(label, pct, value, cls='') { pct=clamp(pct); return `<div class="bar-row ${cls}"><div class="bar-head"><span>${label}</span><b>${value}</b></div><div class="bar"><i style="width:${pct}%"></i></div></div>`; }
function statPill(label, value, cls='') { return `<div class="pill ${cls}"><span>${label}</span><b>${value}</b></div>`; }
function metricCell(label, value, detail='', cls='') { return `<div class="metric-cell ${cls}"><span>${escapeHtml(label)}</span><b>${escapeHtml(value)}</b>${detail?`<small>${escapeHtml(detail)}</small>`:''}</div>`; }
function miniGauge(label, pct, value, cls='') { pct=clamp(pct); return `<div class="mini-gauge ${cls}" style="--pct:${pct}"><div><span>${escapeHtml(label)}</span><b>${escapeHtml(value)}</b></div><i><u style="width:${pct}%"></u></i></div>`; }
function cleanText(text='') {
  return String(text)
    .replace(/goblins?/ig, 'gremlin')
    .replace(/plugin spirits/ig, 'plugins')
    .replace(/spirits are/ig, 'tools are')
    .replace(/\{bt_count\}/g, 'BT')
    .replace(/\{plugin_count\}/g, 'plugins')
    .replace(/\{wifi_count\}/g, 'Wi-Fi')
    .replace(/\{lan_count\}/g, 'LAN');
}
function escapeHtml(v){return String(v??'').replace(/[&<>"']/g, ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));}


let activeLabSection = 'quick';
function showTab(name) {
  activeTab = name;
  document.body.dataset.activeTab = name;
  if(location.hash !== '#'+name) history.replaceState(null, '', '#'+name);
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.toggle('active', p.id === `tab-${name}`));
  document.querySelectorAll('.tab-button').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
  if (name === 'settings' && !document.getElementById('settingsJson').value) loadSettings();
  if (name === 'lab') { renderLabToys(lastStatus?.lab_toys||{}, lastStatus||{}); showLabSection(activeLabSection || 'quick'); }
  else { document.body.dataset.labSection = ''; }
  if (name === 'externals') { refreshCameraFrame(true); renderExternals(lastStatus?.externals||{}); }
}
function showLabSection(section='quick'){
  activeLabSection = section;
  document.body.dataset.labSection = section;
  document.querySelectorAll('#labSectionTabs .subtab').forEach(b=>b.classList.toggle('active', b.dataset.labSection===section));
  document.querySelectorAll('#tab-lab .lab-section').forEach(card=>{
    const on = card.classList.contains('lab-section-'+section);
    card.classList.toggle('active', on);
    card.hidden = !on;
  });
}
function setTicker(sys, wifi, sens, vpn, controls) {
  const gps=sens?.gps||{}, indoor=sens?.indoor||{}, mem=sys.memory||{};
  const tailIp=(sys.ips||[]).find(ip=>ip.startsWith('100.')) || 'no-tailnet';
  const gpsSig = gps.satelliteSignalBest != null ? ` SIG ${gps.satelliteSignalBest}` : '';
  const items=[`HOST ${sys.hostname||'unknown'}`,`CPU ${sys.cpu_temp_f?sys.cpu_temp_f.toFixed(1)+'F':'n/a'}`,`LOAD ${sys.load||'n/a'}`,`RAM ${mem.text||'n/a'}`,`DISK ${diskShort(sys.disk_root)}`,`UP ${uptimeText(sys.uptime_s)}`,`IP ${tailIp}`,`WIFI ${wifi?.current?.ssid||'offline'} ${wifi?.current?.signal||''}`,`GPS ${gps.modeLabel||'n/a'} ${gps.satellitesUsed||0}/${gps.satellitesVisible||0}${gpsSig}`,`TEMP ${indoor.available?(indoor.tempF?.toFixed?.(1)||indoor.tempF)+'F':'n/a'}`,`VPN ${(vpn.active_connections||[]).length?'ON':(vpn.gui_running?'APP OPEN':'OFF')}`,`VNC ${controls?.vnc?.state_label||controls?.vnc?.active_text||'n/a'}`,`SYNC ${controls?.syncthing?.state_label||controls?.syncthing?.active_text||'n/a'}`];
  const text=` ${items.join('  //  ')}  // `;
  ['topTickerText','bottomTickerText'].forEach(id=>{
    const el=document.getElementById(id);
    if(!el) return;
    el.textContent=text.repeat(4);
    el.style.animation='none';
    void el.offsetWidth;
    el.style.animation='ticker-left 40s linear infinite';
  });
}
function setButton(id,label,active=false,ok=true){ const b=document.getElementById(id); if(!b)return; if(!busyButtons.has(id))b.textContent=label; b.classList.toggle('is-active',!!active); b.classList.toggle('is-off',!active); b.classList.toggle('is-error',!ok); }
function applyTheme(theme){ currentTheme=theme||currentTheme||'default'; document.body.dataset.theme=currentTheme; localStorage.setItem('spac3Theme', currentTheme); const sel=document.getElementById('themeSelect'); if(sel) sel.value=currentTheme; }
function setTheme(theme){ applyTheme(theme); if(currentConfig){ currentConfig.ui=currentConfig.ui||{}; currentConfig.ui.theme=theme; document.getElementById('settingsJson').value=JSON.stringify(currentConfig,null,2); } }

const FACE_PACKS = {
  'default': {label:'Default Spac3-Gh0st', type:'text'}
};
async function setFacePack(pack){
  currentFacePack = 'default';
  localStorage.setItem('spac3FacePack', 'default');
  if(currentConfig){
    currentConfig.ui=currentConfig.ui||{};
    currentConfig.ui.face_pack='default';
    const sj=document.getElementById('settingsJson'); if(sj) sj.value=JSON.stringify(currentConfig,null,2);
  }
  renderFace({...lastStatus, config:{...(lastStatus?.config||{}), ui:{...(lastStatus?.config?.ui||{}), face_pack:'default'}}});
}
function faceFallback(img){
  const list=String(img.dataset.fallbacks||'').split('|').map(decodeURIComponent).filter(Boolean);
  let idx=Number(img.dataset.fallbackIndex||0)+1;
  if(idx>=list.length){ img.onerror=null; img.style.display='none'; return; }
  img.dataset.fallbackIndex=String(idx); img.src=list[idx];
}
const FACE_VARIANTS = {
  hot:['(°▃▃°)','(>_<)','(-_-")','(🔥_🔥)'],
  warm:['(>_<)','(=_=;)','(•_•;)','(☼_☼)'],
  tilted:['(@_@)','(x_x)','( @_@)','(↯_↯)'],
  stormwatch:['(⚆_⚆)','(☂_☂)','(ϟ_ϟ)','(⊙_◎)'],
  night:['(⌐■_■)','(■_■¬)','(⌐□_□)','(■‿■¬)'],
  scanning:['(⊙_◎)','(◎_⊙)','(⊙_⊙)','(◉_◎)'],
  curious:['(◕‿‿◕)','( ⚆_⚆)','(☉_☉ )','(✜‿‿✜)','(@-@)','(•‿‿•)'],
  alert:['( ⚆_⚆)','(☉_☉ )','(@_@)','(#__#)'],
  bluetooth:['(⌁_⌁)','(⌁‿⌁)','(⌁_◎)'],
  located:['(⌖_⌖)','(⌖‿⌖)','(⌖_◎)','(◎_⌖)'],
  cold:['(⌐❄_❄)','(❄_❄)','(⌐■_■)'],
  lonely:['(ب__ب)','(-__-)','(╥☁╥ )'],
  rainwatch:['(☂_☂)','(•́_•̀)','(☁‿☁)','(雨_雨)'],
  snowghost:['(❄‿❄)','(❄_❄)','(⌐❄_❄)'],
  fogghost:['(░_░)','(◌_◌)','(=_=)'],
  windwatch:['(≋_≋)','(~_~)','(⌁_⌁)'],
  sunbaked:['(☼_☼)','(⌐□_□)','(>_<)'],
  skyclear:['(☼‿☼)','(◕‿◕)','(•‿‿•)'],
  humid:['(☁_☁)','(~_~;)','(=湿=)'],
  dry:['(砂_砂)','(._.)','(=_=)'],
  bright:['(☼_☼)','(⌐□_□)','(⊙_⊙)'],
  soundwave:['(♪_♪)','(♫‿♫)','(•‿•)'],
  watching:['(◉_◉)','(◎_◎)','(⊙_◎)'],
  cloaked:['(⌐■_■)','(■_■¬)','(¬‿¬)']
};
const FACE_DIRECTION_SETS = {
  hot:{left:'(>_< )', center:'(°▃▃°)', right:'( >_<)'},
  warm:{left:'(•_•;)', center:'(=_=;)', right:'(;•_•)'},
  tilted:{left:'( @_@)', center:'(@_@)', right:'(@_@ )'},
  stormwatch:{left:'(☂_☂ )', center:'(ϟ_ϟ)', right:'( ☂_☂)'},
  rainwatch:{left:'(☂_☂ )', center:'(☂_☂)', right:'( ☂_☂)'},
  snowghost:{left:'(❄_❄ )', center:'(❄‿❄)', right:'( ❄_❄)'},
  fogghost:{left:'(░_░ )', center:'(◌_◌)', right:'( ░_░)'},
  windwatch:{left:'(≋_≋ )', center:'(≋_≋)', right:'( ≋_≋)'},
  sunbaked:{left:'(☼_☼ )', center:'(☼_☼)', right:'( ☼_☼)'},
  skyclear:{left:'(◕‿◕ )', center:'(☼‿☼)', right:'( ◕‿◕)'},
  humid:{left:'(☁_☁ )', center:'(~_~;)', right:'( ☁_☁)'},
  dry:{left:'(砂_砂 )', center:'(._.)', right:'( 砂_砂)'},
  bright:{left:'(⌐□_□)', center:'(☼_☼)', right:'(□_□¬)'},
  night:{left:'(■_■¬)', center:'(⌐■_■)', right:'(⌐□_□)'},
  soundwave:{left:'(♪_♪ )', center:'(♫‿♫)', right:'( ♪_♪)'},
  watching:{left:'(◎_◉)', center:'(◉_◉)', right:'(◉_◎)'},
  cloaked:{left:'(■_■¬)', center:'(⌐■_■)', right:'(¬‿¬)'},
  scanning:{left:'(◎_⊙)', center:'(⊙_⊙)', right:'(⊙_◎)'},
  bluetooth:{left:'(⌁_◎)', center:'(⌁‿⌁)', right:'(◎_⌁)'},
  located:{left:'(◎_⌖)', center:'(⌖_⌖)', right:'(⌖_◎)'},
  alert:{left:'(☉_☉ )', center:'(@_@)', right:'( ⚆_⚆)'},
  curious:{left:'(☉_☉ )', center:'(@-@)', right:'( ⚆_⚆)'},
  lonely:{left:'(ب__ب )', center:'(-__-)', right:'( ب__ب)'},
  cold:{left:'(❄_❄ )', center:'(⌐❄_❄)', right:'( ❄_❄)'}
};
function configuredFaceList(mood, status){
  const faces=status.faces || currentConfig?.faces || {};
  const aliases={night:'dark', stormwatch:'storm', rainwatch:'rain', snowghost:'snow', fogghost:'fog', windwatch:'wind', sunbaked:'bright', skyclear:'curious', soundwave:'sound', watching:'scanning', cloaked:'dark'};
  const keys=[mood, aliases[mood], mood?.toUpperCase?.(), aliases[mood]?.toUpperCase?.()].filter(Boolean);
  for(const key of keys){
    const v=faces[key];
    if(Array.isArray(v) && v.length) return v.map(String);
    if(typeof v==='string' && v.trim()) return [v];
  }
  return [];
}
function faceListForMood(mood, status){
  const configured=configuredFaceList(mood, status);
  if(configured.length) return configured;
  const dirs=FACE_DIRECTION_SETS[mood];
  const directed=dirs ? [dirs.center, dirs.left, dirs.right].filter(Boolean) : [];
  return [...directed, ...(FACE_VARIANTS[mood]||[])].filter(Boolean);
}
function uniqueFaces(list){ return [...new Set((list||[]).map(String).filter(Boolean))]; }
function weatherFaceMoods(status){
  const s=String(status.sensors?.weather?.summary||status.weather?.summary||'').toLowerCase();
  const out=[];
  if(s.includes('storm')||s.includes('thunder')||s.includes('lightning')) out.push('stormwatch');
  if(s.includes('rain')||s.includes('shower')||s.includes('drizzle')) out.push('rainwatch');
  if(s.includes('snow')||s.includes('sleet')||s.includes('ice')) out.push('snowghost');
  if(s.includes('fog')||s.includes('mist')||s.includes('haze')) out.push('fogghost');
  if(s.includes('wind')||s.includes('gust')||s.includes('breezy')) out.push('windwatch');
  return out;
}
function normalFaceMoods(status){
  const h=new Date().getHours();
  const base=(h>=5&&h<11)?'morning':(h>=17&&h<21)?'evening':(h>=21||h<5)?'night':'daylight';
  return uniqueFaces([base, 'curious', 'skyclear']);
}
function lifelikeFaceCandidates(mood, status, fallback){
  const strong=['hot','warm','alert','scanning','watching','cloaked','soundwave'];
  if(strong.includes(mood)) return uniqueFaces([...faceListForMood(mood,status), fallback]);
  const normal=normalFaceMoods(status).flatMap(m=>faceListForMood(m,status));
  const moodFaces=faceListForMood(mood,status);
  const weather=weatherFaceMoods(status).flatMap(m=>faceListForMood(m,status));
  const rare=['(@-@)','(¬‿¬)','(✜‿‿✜)','(•‿‿•)','(☉_☉ )','( ⚆_⚆)'];
  // Weighted bag: mostly normal companion expressions, some current/context
  // flavor, rare ghost weirdness. This removes the obvious left-center-right loop.
  return [
    ...normal, ...normal, ...normal,
    ...moodFaces, ...moodFaces,
    ...weather,
    ...rare,
    fallback || '(@-@)'
  ].map(String).filter(Boolean);
}
function pickLifelikeFace(mood, status, fallback){
  const now=Date.now();
  const strong=['hot','warm','alert','scanning','watching','cloaked','soundwave'];
  const moodChanged=faceState.mood !== mood;
  if(!moodChanged && faceState.face && now < faceState.nextAt) return faceState.face;
  const candidates=lifelikeFaceCandidates(mood, status, fallback);
  let pool=candidates.filter(f=>f!==faceState.face && !faceState.history.slice(-2).includes(f));
  if(!pool.length) pool=candidates.filter(f=>f!==faceState.face);
  if(!pool.length) pool=candidates;
  const face=pool[Math.floor(Math.random()*pool.length)] || fallback || '(@-@)';
  faceState.mood=mood;
  faceState.face=face;
  faceState.history=[...faceState.history.slice(-5), face];
  const min=strong.includes(mood) ? 2200 : 3500;
  const spread=strong.includes(mood) ? 3600 : 8500;
  faceState.nextAt=now + min + Math.floor(Math.random()*spread);
  return face;
}
function renderFace(status){
  const faceEl=document.getElementById('face'); if(!faceEl) return;
  currentFacePack='default'; localStorage.setItem('spac3FacePack','default');
  let mood=String(status.mood?.name||'curious').toLowerCase();
  if(soundMode && ['curious','located','skyclear','night'].includes(mood)) mood='soundwave';
  let face=pickLifelikeFace(mood, status, status.mood?.face || '(@-@)');
  faceEl.classList.remove('image-face');
  faceEl.dataset.mood=mood;
  faceEl.style.color=status.mood?.color||'var(--green)';
  faceEl.textContent=face;
}

function startPwnFaceCycle(){
  if(pwnFaceTimer) return;
  pwnFaceTimer=setInterval(()=>{ if(lastStatus) renderFace(lastStatus); }, 1200);
}


function setProtonZoom(delta){
  protonMapZoom=Math.max(0.75, Math.min(1.75, Number(protonMapZoom||1)+delta));
  localStorage.setItem('protonMapZoom', String(protonMapZoom));
  const map=document.querySelector('.proton-map'); if(map) map.style.setProperty('--proton-zoom', protonMapZoom);
}
function resetProtonZoom(){ protonMapZoom=1; localStorage.setItem('protonMapZoom','1'); const map=document.querySelector('.proton-map'); if(map) map.style.setProperty('--proton-zoom','1'); }
async function selectProtonProfile(name, sync=true){
  selectedProtonProfile=String(name||'Fastest country');
  localStorage.setItem('selectedProtonProfile', selectedProtonProfile);
  protonActionStatus=`Selected ${selectedProtonProfile}`;
  renderGlobalMap(lastStatus||{});
  if(sync){
    try{
      const d=await postJson('/api/vpn/select',{profile:selectedProtonProfile});
      protonActionStatus=d.ok?(d.message||`Selected ${d.profile||selectedProtonProfile}`):(d.error||'VPN profile selection failed');
      await refresh();
    }catch(e){ protonActionStatus=`VPN select failed: ${e.message||e}`; renderGlobalMap(lastStatus||{}); }
  }
}
async function startProtonVpn(){
  setBusy('protonStartButton',true,'Starting...');
  try{
    const d=await postJson('/api/vpn/connect',{profile:selectedProtonProfile||''});
    protonActionStatus=d.ok?(d.message||`VPN ${d.action||'connect'} ok`):(d.error||d.stderr||'VPN start failed');
  }catch(e){ protonActionStatus=`VPN start failed: ${e.message||e}`; }
  setBusy('protonStartButton',false);
  await refresh();
}
async function openProtonVpn(){
  try{ const d=await postJson('/api/vpn/open',{}); protonActionStatus=d.message||d.error||'Open VPN requested'; }
  catch(e){ protonActionStatus=`Open VPN failed: ${e.message||e}`; }
  await refresh();
}
async function tailscaleAction(action){
  const map={status:'/api/tailscale/status',up:'/api/tailscale/up',restart:'/api/tailscale/restart',protect:'/api/tailscale/protect'};
  if(action==='restart' && !confirm('Restart tailscaled on Hack-Safe? This may briefly interrupt the dashboard connection, but should recover Tailscale.')) return;
  protonActionStatus=`Tailscale ${action} requested...`; renderGlobalMap(lastStatus||{});
  try{
    let d;
    if(action==='status') { const r=await fetch(map[action],{cache:'no-store'}); d=await r.json(); }
    else d=await postJson(map[action],{});
    protonActionStatus=d.message || `Tailscale ${action}: ${d.ip||'no ip'} // ${d.backend_state||d.active_text||'unknown'}`;
  }catch(e){ protonActionStatus=`Tailscale ${action} failed: ${e.message||e}`; }
  await refresh();
}
function selectProtonFilter(btn){ btn.closest('.proton-filter')?.querySelectorAll('button').forEach(b=>b.classList.toggle('active', b===btn)); }
function selectProtonPanel(name){ const tabs=document.querySelectorAll('.proton-tabs button'); tabs.forEach(b=>b.classList.toggle('active', b.textContent.toLowerCase().includes(name))); }
function applyProtonFx(){ document.body.classList.toggle('proton-fx-off', !protonFxEnabled); setButton('protonFxButton', protonFxEnabled?'Hack-Safe VPN FX On':'Hack-Safe VPN FX Off', protonFxEnabled, true); }
function toggleProtonFx(){ protonFxEnabled=!protonFxEnabled; localStorage.setItem('protonFxEnabled', protonFxEnabled?'1':'0'); applyProtonFx(); }
function setBusy(id,busy,label='Working...'){ const b=document.getElementById(id); if(!b)return; if(busy){busyButtons.add(id); b.textContent=label; b.disabled=true; b.classList.add('is-busy');} else {busyButtons.delete(id); b.disabled=false; b.classList.remove('is-busy');} }
function beep(freq=440, dur=0.08, type='square'){
  if(!soundMode) return;
  try{ audioCtx=audioCtx||new (window.AudioContext||window.webkitAudioContext)(); const o=audioCtx.createOscillator(), g=audioCtx.createGain(); o.type=type; o.frequency.value=freq; g.gain.value=.035; o.connect(g); g.connect(audioCtx.destination); o.start(); g.gain.exponentialRampToValueAtTime(.001,audioCtx.currentTime+dur); o.stop(audioCtx.currentTime+dur+.02); }catch(e){}
}
function soundEvents(s){
  const level=s.alert?.level||'GREEN', gpsFixed=!!s.sensors?.gps?.fixed;
  if(lastAlertLevel && level!==lastAlertLevel) beep(level==='RED'?180:level==='ORANGE'?260:level==='YELLOW'?360:620,.12,'sawtooth');
  if(lastGpsFixed===false && gpsFixed) { beep(740,.08,'sine'); setTimeout(()=>beep(990,.1,'sine'),90); }
  lastAlertLevel=level; lastGpsFixed=gpsFixed;
}
function showAction(preId,d){ /* controls no longer show text dumps under buttons */ }

async function refreshCameraFrame(force=false){
  const img=document.getElementById('cameraFeed');
  const pulse=document.getElementById('cameraPulse');
  if(!img || cameraInflight || (!force && activeTab !== 'vision')) return;
  cameraInflight=true;
  img.classList.add('loading');
  const started=performance.now();
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), activeCameraFeed==='local'?1800:3500);
  try {
    const r = await fetch(`/api/camera/frame?feed=${encodeURIComponent(activeCameraFeed)}&t=${Date.now()}`, {cache:'no-store', signal:controller.signal});
    if (!r.ok) throw new Error(`frame ${r.status}`);
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const old = img.dataset.objectUrl;
    const pre = new Image();
    pre.decoding = 'async';
    await new Promise((resolve, reject) => {
      pre.onload = resolve;
      pre.onerror = reject;
      pre.src = url;
    });
    if (pre.decode) { try { await pre.decode(); } catch(e){} }
    img.src = url;
    img.dataset.objectUrl = url;
    if (old) setTimeout(() => URL.revokeObjectURL(old), 250);
    if(pulse) pulse.textContent = `${pre.naturalWidth||''}x${pre.naturalHeight||''} // ${Math.max(1, Math.round(performance.now()-started))}ms`;
  } catch (err) {
    if(pulse) pulse.textContent = 'FRAME WAIT';
  } finally {
    clearTimeout(timeout);
    cameraInflight=false;
    img.classList.remove('loading');
  }
}
function scheduleCamera(s){
  const enabled=!!s?.vision?.enabled;
  const shouldRun=activeTab==='vision';
  const key=`${enabled}:${shouldRun}:${activeCameraFeed}`;
  if(key === cameraEnabled && cameraTimer) return;
  cameraEnabled=key;
  if(cameraTimer) clearInterval(cameraTimer);
  cameraTimer=null;
  if(shouldRun){ refreshCameraFrame(true); cameraTimer=setInterval(()=>refreshCameraFrame(false), enabled ? (activeCameraFeed==='local'?700:900) : 1800); }
}
async function pollTilt(){
  if(tiltPollBusy || activeTab!=='signals' || !document.getElementById('tiltStage')) return;
  tiltPollBusy=true;
  try{ const r=await fetch('/api/sensors/tilt',{cache:'no-store'}); if(r.ok) applyTilt(await r.json()); }catch(e){}
  tiltPollBusy=false;
}

function safeRender(name, fn){
  try { return fn(); }
  catch (err) {
    console.warn(`${name} render failed`, err);
    if(name==='Proton map'){
      const el=document.getElementById('globalMapViz');
      if(el) el.innerHTML='<div class="panel compact-panel"><b>Proton map render paused</b><span>Other dashboard panels are still live. Check console/logs for map exception.</span></div>';
    }
  }
}

async function refresh(){
  if(refreshBusy){ refreshQueued = true; return; }
  refreshBusy = true;
  waveSeq = 0;  // call order is deterministic per refresh, so ids (and the registry) stay stable across renders
  try {
    const res=await fetch('/api/status',{cache:'no-store'}); const s=await res.json(); lastStatus=s; currentConfig=s.config;
    document.getElementById('clock').textContent=new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});
    renderFace(s); document.getElementById('mood').textContent=cleanText(s.mood.name); document.getElementById('thought').textContent=cleanText(s.thought); const tail=document.getElementById('tailUrl'); if(tail){ tail.textContent=''; tail.title=s.tailscale_url||'local only'; }
    const sys=s.system||{}, wifi=s.wifi||{}, sens=s.sensors||{}; setTicker(sys,wifi,sens,s.vpn||{},s.controls||{}); scheduleCamera(s);
    applyTheme(s.config?.ui?.theme || localStorage.getItem('spac3Theme') || 'default');
    safeRender('Mission Control', ()=>renderMissionControl(s));
    safeRender('Cyber Test Kit', ()=>renderCyberTestKit(s));
    safeRender('AI Chat', ()=>renderAIChat(lastAIChat));
    safeRender('CYD Buddy', ()=>renderCydBuddy(s.cyd_buddy||{}));
    safeRender('Pwnagotchi Dock', ()=>renderPwnagotchiDock(s.pwnagotchi_dock||{}));
    safeRender('Open Tools', ()=>renderOpenTools(s));
    safeRender('Weather companion', ()=>renderWeatherSim(sens.weather||{}, sens.light||{}));
    safeRender('System', ()=>renderSystem(sys));
    safeRender('System Monitor', ()=>renderSystemMonitor(sys, s.services||{}, s.controls||{}));
    safeRender('Hacker Deck', ()=>renderHackerDeck(s));
    safeRender('Known Devices', ()=>renderKnownDevices(s.known_devices||{}));
    safeRender('Household Signals', ()=>renderHouseholdSignals(s.household_signals||{}));
    safeRender('Wi-Fi', ()=>renderWifi(wifi));
    safeRender('Meshtastic', ()=>renderMeshtastic(s.meshtastic||{}));
    safeRender('RF Audit', ()=>renderRFAudit(s.rf_audit||{}, s.rf_recommendations||[]));
    safeRender('Proton map', ()=>renderGlobalMap(s));
    safeRender('Defense Ops', ()=>renderDefenseOps(s.security_stack||{}));
    if(activeTab==='lab') safeRender('Lab Toys', ()=>{ renderLabToys(s.lab_toys||{}, s); showLabSection(activeLabSection||'quick'); });
    safeRender('Externals', ()=>renderExternals(s.externals||{}));
    safeRender('GPS + Sensors', ()=>renderSensors(sens));
    safeRender('GPS Trail', ()=>renderGpsTrail(s.gps_trail||{}));
    safeRender('Services', ()=>renderServices(s.services||{},s.controls||{}));
    safeRender('Events', ()=>renderEvents(s.events||[]));
    if(activeTab==='plugins'){ safeRender('Plugin Panels', ()=>renderPluginPanels(s.plugin_panels||[])); safeRender('Plugin Switches', ()=>renderPluginSwitches(s.native_plugins||[])); }
    safeRender('Controls', ()=>renderControls(s));
    safeRender('Vision', ()=>renderVision(s.vision||{}, s.vision_history||{}));
    safeRender('Sound Events', ()=>soundEvents(s));
  } catch (err) {
    console.warn('refresh failed', err);
  } finally {
    refreshBusy = false;
    if(refreshQueued){ refreshQueued = false; setTimeout(refresh, 250); }
  }
}
async function refreshAIChatStatus(){
  try{ const r=await fetch('/api/ai/chat',{cache:'no-store'}); lastAIChat=await r.json(); renderAIChat(lastAIChat); }catch(e){ renderAIChat({ok:false,error:String(e)}); }
}
function renderAIChat(chat={}){
  const el=document.getElementById('aiChatViz'); if(!el) return;
  chat=chat||{};
  const models=chat.models||[];
  const hist=(chat.history||[]).slice(-5).map(row=>`<div class="ai-msg user"><b>You</b><span>${escapeHtml(row.user||'')}</span></div><div class="ai-msg ghost"><b>Ghost</b><span>${escapeHtml(row.assistant||'')}</span></div>`).join('') || '<div class="scanline-note">No local chat yet. Ask a short question.</div>';
  const status=chat.ollama_running?`Ollama ready // ${models.length||0} model(s)`:((chat.error||'Ollama not reachable')+' // Open/Start Ollama from Open Tools if needed');
  const voice=`STT ${chat.stt?.available?'ready':'not installed'} // TTS ${chat.tts?.available?'ready':'not installed'} // ${chat.storage_note||'storage-aware voice setup pending'}`;
  const modelOptions=models.map(m=>`<option value="${escapeHtml(m)}">${escapeHtml(m)}</option>`).join('');
  el.innerHTML=`<div class="ai-status"><b>${escapeHtml(status)}</b><small>${escapeHtml(voice)}</small></div><div id="aiChatHistory" class="ai-chat-history">${hist}</div><div class="ai-chat-controls"><select id="aiModelSelect">${modelOptions||'<option value="">no local model</option>'}</select><textarea id="aiPrompt" rows="3" placeholder="Ask Spac3-Gh0st something about this Pi, the dashboard, Wi‑Fi, sensors, or lab setup..."></textarea><button id="aiAskButton" onclick="askAIChat()">Ask Local AI</button><button onclick="refreshAIChatStatus()">Refresh AI</button></div>`;
}

function renderCydBuddy(cyd={}){
  const el=document.getElementById('cydBuddyViz'); if(!el) return;
  const hs=cyd.hotspot||{};
  const connected=!!cyd.connected;
  const age=cyd.age_s==null?'never':`${Math.max(0, Math.round(cyd.age_s))}s ago`;
  const leases=(cyd.leases||[]).filter(l=>l.active).slice(0,4);
  const leaseHtml=leases.map(l=>`<div class="cyd-lease"><b>${escapeHtml(l.name||'unnamed')}</b><span>${escapeHtml(l.ip)} // ${escapeHtml(l.mac)}</span></div>`).join('') || '<div class="scanline-note">No CYD DHCP lease yet. Connect it to Wu-Tang LAN from the Windows-flashed firmware.</div>';
  const dock=`<div class="cyd-dock ${connected?'connected':'waiting'}"><div class="cyd-core"><b>${escapeHtml(cyd.dock_label||'HOTSPOT CHECK')}</b><span>${escapeHtml(cyd.name||'CYD Buddy')} // ${connected?'connected':'waiting'} // last seen ${age}</span><small>hotspot ${escapeHtml(hs.ssid||'Wu-Tang LAN')} @ ${escapeHtml(hs.ip||'10.42.7.1')} // ${hs.active?'active on '+escapeHtml(hs.device||'wlan1'):'not active'}</small></div></div>`;
  if(!connected){
    el.innerHTML=`${dock}<div class="cyd-grid">${metricCell('CYD IP', cyd.ip||'waiting', 'DHCP/heartbeat pending')}${metricCell('Telemetry', cyd.telemetry_url||'n/a', 'CYD polls this')}${metricCell('Dashboard', cyd.dashboard_url||'n/a', 'same Spac3-Gh0st over hotspot')}</div><div class="cyd-leases">${leaseHtml}</div><div class="scanline-note">Expanded Buddy stats stay hidden until CYD Buddy is connected and sending heartbeats.</div>`;
    return;
  }
  const stats=cyd.stats||{}, inter=cyd.interactions||{}, learn=cyd.learning||{}, mem=cyd.memory||{}, phrases=cyd.phrases||{}, life=cyd.lifecycle||{}, ai=cyd.ai_state||{};
  const memories=(mem.bank||[]).slice(-5).map(x=>`<li>${escapeHtml(x)}</li>`).join('') || '<li>No memory bank entries yet.</li>';
  const statGrid=[
    metricCell('Health', stats.health||'n/a', `hunger ${stats.hunger??'n/a'} // play ${stats.play_need??'n/a'}`),
    metricCell('Mood', cyd.mood||'n/a', ai.asleep?'sleeping':'awake'),
    metricCell('Care', `R${stats.restless??'n/a'} A${stats.anxious??'n/a'}`, `${stats.feeds_today??0} feeds // ${stats.plays_today??0} plays`),
    metricCell('Power', `STR ${stats.strength??'n/a'} / ARM ${stats.armor??'n/a'}`, `${inter.new_wifi??0} WiFi // ${inter.new_bluetooth??0} BT`),
    metricCell('Learning', `${learn.preference_learns??0} learns`, `${learn.memory_revisions??0} memory revisions`),
    metricCell('Favorite', learn.favorite_activity||'n/a', `${learn.favorite_time||'time n/a'} // ${learn.favorite_season||'season n/a'}`),
    metricCell('Alive', life.alive||'n/a', `${life.deaths??0} deaths // session ${life.session||'n/a'}`),
    metricCell('AI', `${ai.mode||'tiny-local'} ${ai.confidence??0}%`, ai.auto_mode?'auto mode':'manual mode')
  ].join('');
  const settings=renderCydSettingsPanel(cyd);
  el.innerHTML=`${dock}<div class="cyd-grid">${statGrid}</div>${settings}<div class="cyd-buddy-panels"><section><h3>Current Voice</h3><p>${escapeHtml(phrases.current||cyd.message||'quiet')}</p><small>${escapeHtml(phrases.personality||'personality n/a')} // scroll ${escapeHtml(phrases.scroll_ms??'n/a')}ms // SD phrases ${phrases.sd_lookup?'on':'off'}</small></section><section><h3>Tiny AI Insight</h3><p>${escapeHtml(ai.insight||learn.summary||'learning state pending')}</p><small>${escapeHtml(ai.daily_summary||'daily summary pending')}</small></section><section><h3>Memory Bank</h3><ul>${memories}</ul><small>${escapeHtml(mem.random||'')}</small></section></div><div class="cyd-leases">${leaseHtml}</div>`;
}

// Refresh the proxied Pwnagotchi face without rebuilding the whole card, so the
// image swaps in place on the 15s poll (cache-busted so we get the current frame).
function refreshPwnFace(){
  const img=document.getElementById('pwnDockFace');
  if(img && img.dataset.online==='1'){ img.src='/api/pwnagotchi/ui?t='+Date.now(); }
}

function renderPwnagotchiDock(pwn={}){
  const el=document.getElementById('pwnagotchiDockViz'); if(!el) return;
  const online=!!pwn.reachable;
  const authed=!!pwn.authed;
  const label=pwn.dock_label||(online?'ONLINE':'OFFLINE');
  const cls=online?(authed?'connected':'waiting'):'waiting';
  const age=pwn.age_s==null?(online?'just now':'never'):`${Math.max(0,Math.round(pwn.age_s))}s ago`;
  const host=pwn.host||(Array.isArray(pwn.hosts)?pwn.hosts[0]:'')||'no route';
  const webUrl=pwn.web_url||'';
  const face=online
    ? `<img id="pwnDockFace" class="pwn-face" data-online="1" src="/api/pwnagotchi/ui?t=${Date.now()}" alt="Pwnagotchi face" onerror="this.dataset.online='0'; this.replaceWith(Object.assign(document.createElement('div'),{className:'pwn-face pwn-face-empty',textContent:'face unavailable — check web-UI login'}));">`
    : `<div class="pwn-face pwn-face-empty">${escapeHtml(label==='PROBING'?'probing…':'offline — not reachable on the tailnet or USB')}</div>`;
  const dock=`<div class="cyd-dock ${cls}"><div class="cyd-core"><b>${escapeHtml(label)}</b><span>${escapeHtml(pwn.name||'CAK3DAGOTCHI')} // ${escapeHtml(host)} // last seen ${escapeHtml(age)}${pwn.latency_ms!=null?` // ${escapeHtml(pwn.latency_ms)}ms`:''}</span>${!authed&&online?'<small>Reachable, but the web-UI login was rejected. Set SPAC3GHOST_PWN_USER / SPAC3GHOST_PWN_PASS (or data/config.json) to read stats and the face.</small>':''}</div></div>`;
  const grid=`<div class="cyd-grid">${metricCell('Networks seen', pwn.networks_seen||(authed?'0':'n/a'), 'APs this session')}${metricCell('Handshakes', pwn.handshakes||(authed?'0':'n/a'), 'captured')}${metricCell('Mode', pwn.mode||pwn.status_text||'n/a', 'AI posture')}${metricCell('Channel', pwn.channel||'n/a', 'current')}${metricCell('Uptime', pwn.uptime||'n/a', 'since boot')}${metricCell('Route', host, `web :${pwn.port||8080}`)}</div>`;
  const actions=`<div class="pwn-dock-actions">${webUrl?`<a class="button-link open-now" href="${escapeHtml(webUrl)}" target="_blank" rel="noopener noreferrer">Open Web UI</a>`:''}<button onclick="refreshPwnDock()">Refresh</button></div>`;
  el.innerHTML=`<div class="pwn-dock ${cls}"><div class="pwn-face-wrap">${face}</div><div class="pwn-dock-body">${dock}${grid}${actions}</div></div>`;
}

async function refreshPwnDock(){
  try{ const r=await fetch('/api/pwnagotchi/dock',{cache:'no-store'}); const d=await r.json(); if(lastStatus) lastStatus.pwnagotchi_dock=d; renderPwnagotchiDock(d); }
  catch(e){ /* keep last render */ }
}

function renderCydSettingsPanel(cyd={}){
  const settings=cyd.settings||{};
  const menus=settings.menus||[];
  const active=settings.active_menu||'home';
  const display=settings.display||{}, face=settings.face||{}, phrases=settings.phrases||{}, advanced=settings.advanced||{};
  const menuButtons=menus.map(m=>`<button class="${m.id===active?'active':''}" onclick="cydBuddyOpenMenu('${escapeHtml(m.id)}')"><b>${escapeHtml(m.label||m.id)}</b><small>${escapeHtml(m.hint||'')}</small></button>`).join('') || '<div class="scanline-note">Buddy firmware has not advertised settings menus yet.</div>';
  const pending=settings.pending_command;
  const pendingText=pending?`pending ${escapeHtml(pending.action||'command')} → ${escapeHtml(pending.menu||'menu')}`:(settings.last_ack?`last ack ${escapeHtml(JSON.stringify(settings.last_ack).slice(0,80))}`:'ready');
  const msg=cydBuddyActionStatus?`<div class="scanline-note">${escapeHtml(cydBuddyActionStatus)}</div>`:'';
  return `<div class="cyd-settings-console"><div class="cyd-settings-head"><div><h3>Buddy Settings Console</h3><p>Open Buddy settings menus/submenus from Spac3-Gh0st while docked. Commands ride in the CYD telemetry payload; no passwords or secrets are stored.</p></div><span>${pendingText}</span></div><div class="cyd-menu-buttons">${menuButtons}</div><div class="cyd-settings-form"><label>Backlight %<input id="cydBrightness" type="range" min="5" max="100" value="${escapeHtml(display.brightness??100)}"></label><label>Sleep after (sec)<input id="cydSleep" type="number" min="30" max="3600" step="30" value="${escapeHtml(display.sleep_s??1800)}"></label><label>Eye theme<select id="cydTheme"><option value="default" ${!display.theme||display.theme==='default'?'selected':''}>default (mood-driven)</option><option value="matrix" ${display.theme==='matrix'?'selected':''}>matrix (green/lime)</option><option value="night" ${display.theme==='night'?'selected':''}>night (navy)</option><option value="amber" ${display.theme==='amber'?'selected':''}>amber</option><option value="mono" ${display.theme==='mono'?'selected':''}>mono (white)</option></select></label><label>Mood<select id="cydMood">${["auto","curious","happy","surprised","sleepy","angry","sad","excited","love","suspicious","stoner","drunk","hippy","bored","restless","anxious"].map(m=>`<option value="${m}" ${((face.mood||'auto')===m)?'selected':''}>${m}</option>`).join('')}</select></label><label>Personality<select id="cydPersonality">${["sassy","sweet","rude","nerdy","chill","chaotic"].map(p=>`<option value="${p}" ${((face.personality||'sassy')===p)?'selected':''}>${p}</option>`).join('')}</select></label><label>Phrase scroll ms<input id="cydScroll" type="number" min="50" max="600" value="${escapeHtml(phrases.scroll_ms??140)}"></label><label class="cyd-check"><input id="cydSdLookup" type="checkbox" ${phrases.sd_lookup?'checked':''}> Use SD phrase bank (off = faster built-in phrases)</label><button onclick="cydBuddySaveSettings()">Save Buddy Settings</button><button onclick="cydBuddyOpenMenu('home')">Back to Buddy Home</button></div><p class="mini">Mood set to anything other than auto holds for ~10 minutes on the Buddy, matching its own manual-mood behavior.</p>${msg}</div>`;
}

async function cydBuddyOpenMenu(menu){
  cydBuddyActionStatus=`Opening CYD Buddy ${menu} menu...`;
  try{ const r=await fetch('/api/cyd/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'open_menu',menu})}); const d=await r.json(); cydBuddyActionStatus=d.ok?`CYD Buddy menu queued: ${d.active_menu||menu}`:`CYD Buddy menu failed: ${d.error||r.status}`; }
  catch(e){ cydBuddyActionStatus=`CYD Buddy menu failed: ${e}`; }
  refresh();
}
async function cydBuddySaveSettings(){
  const values={
    display:{brightness:Number(document.getElementById('cydBrightness')?.value)||100, sleep_s:Number(document.getElementById('cydSleep')?.value)||1800, theme:document.getElementById('cydTheme')?.value||'default'},
    face:{mood:document.getElementById('cydMood')?.value||'auto', personality:document.getElementById('cydPersonality')?.value||'sassy'},
    phrases:{scroll_ms:Number(document.getElementById('cydScroll')?.value)||140, sd_lookup:!!document.getElementById('cydSdLookup')?.checked}
  };
  cydBuddyActionStatus='Saving CYD Buddy settings...';
  try{ const r=await fetch('/api/cyd/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'save',menu:'display',values})}); const d=await r.json(); cydBuddyActionStatus=d.ok?'CYD Buddy settings queued. Buddy applies them on its next telemetry poll (every few seconds while docked).':`CYD Buddy settings failed: ${d.error||r.status}`; }
  catch(e){ cydBuddyActionStatus=`CYD Buddy settings failed: ${e}`; }
  refresh();
}

function renderMeshtastic(mesh={}){
  const el=document.getElementById('meshtasticViz'); if(!el) return;
  const state=String(mesh.state||'waiting_hardware');
  const online=state==='online';
  const waiting=state==='waiting_hardware';
  const serials=mesh.serial_candidates||[];
  const nodes=mesh.nodes||[];
  const serialHtml=serials.slice(0,5).map(s=>`<div class="mesh-row"><b>${escapeHtml(s.path||'serial')}</b><span>${escapeHtml(s.resolved||'')}</span></div>`).join('') || '<div class="scanline-note">No LoRa serial device seen yet. Plug the upstairs ThinkNode gateway into Hack-Safe USB when it arrives.</div>';
  const nodeHtml=nodes.slice(0,8).map(n=>`<div class="mesh-node"><b>${escapeHtml(n.user||n.id||'node')}</b><span>${escapeHtml([n.id,n.last_heard,n.snr,n.via].filter(Boolean).join(' // '))}</span></div>`).join('') || `<div class="scanline-note">${online?'No neighbor nodes reported yet.':'Node list will appear after the gateway and CLI are readable.'}</div>`;
  const hooks=(mesh.cydbuddy_hooks||[]).map(h=>`<li>${escapeHtml(h)}</li>`).join('') || '<li>CYD reaction hooks pending.</li>';
  const notes=(mesh.notes||[]).map(n=>`<li>${escapeHtml(n)}</li>`).join('') || '';
  const statusClass=online?'online':(waiting?'waiting':'warn');
  el.innerHTML=`<div class="mesh-dock ${statusClass}"><div><b>${escapeHtml(mesh.gateway_label||'Upstairs LoRa gateway')}</b><span>${escapeHtml(mesh.summary||'Waiting for gateway telemetry.')}</span><small>${escapeHtml(mesh.expected_device||'ThinkNode M2')} // ${escapeHtml(mesh.region||'US915')} // ${escapeHtml(mesh.channel||'LongFast')}</small></div><button onclick="refreshMeshStatus()">Refresh Mesh</button></div><div class="cyd-grid">${metricCell('State', state.replaceAll('_',' '), mesh.protocol||'meshtastic')}${metricCell('CLI', mesh.cli_available?'installed':'missing', mesh.cli_path||'install meshtastic CLI later')}${metricCell('Serial', mesh.preferred_port||'waiting', `${serials.length} candidate(s)`)}${metricCell('Nodes', mesh.node_count??nodes.length??0, mesh.mode||'serial gateway first')}${metricCell('MQTT', mesh.mqtt?.configured?'configured':(mesh.mqtt?.enabled?'needs server':'off'), mesh.mqtt?.server||'optional bridge')}${metricCell('Buddy Hooks', (mesh.cydbuddy_hooks||[]).length, 'CYD telemetry gets mesh block')}</div><div class="mesh-panels"><section><h3>Serial Candidates</h3>${serialHtml}</section><section><h3>Nodes Heard</h3>${nodeHtml}</section><section><h3>CYD Reactions</h3><ul>${hooks}</ul></section><section><h3>Setup Notes</h3><ul>${notes}</ul></section></div>${mesh.info_excerpt?`<pre class="mesh-info">${escapeHtml(mesh.info_excerpt)}</pre>`:''}`;
}

async function refreshMeshStatus(){
  const el=document.getElementById('meshtasticViz');
  if(el) el.classList.add('loading');
  try{
    const r=await fetch('/api/mesh/status?refresh=1',{cache:'no-store'});
    const d=await r.json();
    renderMeshtastic(d.meshtastic||{state:'error',summary:'Mesh refresh returned no payload.'});
  }catch(e){
    renderMeshtastic({state:'error',summary:`Mesh refresh failed: ${e.message||e}`, notes:['Dashboard could not reach /api/mesh/status.']});
  }finally{
    if(el) el.classList.remove('loading');
  }
}
async function askAIChat(){
  const prompt=document.getElementById('aiPrompt')?.value||'';
  const model=document.getElementById('aiModelSelect')?.value||'';
  if(!prompt.trim()){ alert('Type a question first.'); return; }
  setBusy('aiAskButton',true,'Thinking...');
  const d=await postJson('/api/ai/chat',{prompt,model});
  setBusy('aiAskButton',false);
  if(!d.ok) alert(d.error||'Local AI failed');
  lastAIChat=d.chat||lastAIChat;
  if(d.record){ lastAIChat=lastAIChat||{}; lastAIChat.history=[...(lastAIChat.history||[]), d.record].slice(-12); }
  renderAIChat(lastAIChat);
}

function renderBak3ryDashboards(s={}){
  const el=document.getElementById('bak3ryDashViz'); if(!el) return;
  const mods=(((s.lab_toys||{}).software||{}).modules||[]);
  const byId=Object.fromEntries(mods.map(m=>[m.id,m]));
  const items=[
    byId.homeassistant||{id:'homeassistant',label:'Home Assistant',url:'http://100.65.33.36:8123',running:true,home:'theBAK3RY'},
    byId.heimdall||{id:'heimdall',label:'Heimdall',url:'http://100.65.33.36:8080',running:true,home:'theBAK3RY'},
    byId.ruview||{id:'ruview',label:'RuView',url:'/ruview/index.html',running:true,home:'local mirror'}
  ];
  el.innerHTML=items.map(m=>`<a class="bak3ry-tile ${m.running?'online':'offline'}" href="${escapeHtml(m.url||'#')}" target="_blank" rel="noopener noreferrer"><b>${escapeHtml(m.label||m.id)}</b><span>${escapeHtml(m.home||'dashboard')}</span><small>${m.running?'online/open':'check'}</small></a>`).join('');
}

function renderOpenTools(s={}){
  const el=document.getElementById('openToolsViz'); if(!el) return;
  const mods=(((s.lab_toys||{}).software||{}).modules||[]);
  const byId=Object.fromEntries(mods.map(m=>[m.id,m]));
  const fallback={
    homeassistant:{label:'Home Assistant @ theBAK3RY',url:'http://100.65.33.36:8123',running:true,home:'External Dashboards'},
    heimdall:{label:'Heimdall @ theBAK3RY',url:'http://100.65.33.36:8080',running:true,home:'External Dashboards'},
    osirisosint:{label:'OSIRIS AI Live',url:'https://www.osirisai.live/?layers=maritime,cctv,cctv_previews,live_news,earthquakes,global_incidents,day_night,cables,sdk_sea,sdk_air,sdk_naval',running:true,home:'Vision + OSINT Globe'},
    leolabsleo:{label:'LeoLabs LEO Visualization',url:'https://platform.leolabs.space/visualizations/leo',running:true,home:'Space / LEO Tracking'},
    ruview:{label:'RuView WiFi Sensing',url:'/ruview/index.html',running:true,home:'Local mirror'},
    godseye:{label:"God's Eye View",url:'http://127.0.0.1:8766/godseye-live/',running:false,home:'Vision + OSINT Globe'},
    hermesworkspace:{label:'Hermes Workspace',url:'http://100.75.120.80:3000',running:true,home:'Hermes'},
    projectnomad:{label:'Project N.O.M.A.D',url:'http://100.75.120.80:8080',running:true,home:'Field Kit'},
    uptimekuma:{label:'Uptime Kuma',url:'http://100.75.120.80:3001',running:true,home:'Monitoring'},
    docker:{label:'Docker',url:'',running:false,home:'Containers'},
    portainer:{label:'Portainer',url:'https://100.75.120.80:9443',running:false,home:'Containers'},
    ollama:{label:'Ollama API',url:'http://127.0.0.1:11434',running:true,home:'Local AI'},
    openwebui:{label:'Open WebUI',url:'http://100.75.120.80:3002',running:false,home:'Local AI'},
    jellyfin:{label:'Jellyfin',url:'http://100.75.120.80:8096',running:true,home:'Media'},
    syncthing:{label:'Syncthing',url:'http://100.75.120.80:8384',running:true,home:'Sync'}
  };
  // Keep global/space situational-awareness links on the first-screen launcher too.
  const order=['osirisosint','leolabsleo','ruview','godseye','hermesworkspace','projectnomad','openwebui','portainer','uptimekuma','docker','ollama','jellyfin','syncthing'];
  const card=id=>{ const m=byId[id]||fallback[id]||{}; const url=m.url||''; const state=m.running?'running':(m.installed?'installed/stopped':'not installed'); const onDemand=['godseye','hermesworkspace','projectnomad','openwebui','portainer']; const action=url?`<div class="open-tool-actions">${m.running?`<a class="button-link open-now" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">Open</a>${onDemand.includes(id)?`<button onclick="labSoftwareAction('${id}','disable')">Stop</button>`:''}`:(m.installed&&onDemand.includes(id)?`<button onclick="labSoftwareAction('${id}','open')">Start / Open</button>`:'')}</div>`:`<button onclick="showTab('lab'); setTimeout(()=>document.querySelector('.lab-software-card')?.scrollIntoView({behavior:'smooth',block:'center'}),50)">Docker Status</button>`; return `<div class="open-tool ${m.running?'running':''} ${url?'openable':'status-only'}"><b>${escapeHtml(m.label||id)}</b><span>${escapeHtml(m.home||'Local tool')} // ${escapeHtml(state)}</span>${action}<small>${url?escapeHtml(url):'Docker is managed from Lab → Launch Bay; Portainer gives the Docker UI.'}</small></div>`; };
  el.innerHTML=order.map(card).join('');
}

function renderMissionControl(s){
  const el=document.getElementById('missionViz'); if(!el) return;
  const a=s.alert||{}, sys=s.system||{}, wifi=s.wifi||{}, gps=s.sensors?.gps||{}, wx=s.sensors?.weather||{}, vision=s.vision||{}, known=s.known_devices||{};
  const hist=(s.status_history?.points||[]).slice(-24).map(p=>p.ram||0);
  const layers=a.layers||{};
  const layerCard=(title, items, cls, empty)=>`<div class="attention-layer ${cls}"><b>${title}</b><span>${(items&&items.length)?items.map(i=>escapeHtml(i.text||'')).join(' // '):empty}</span></div>`;
  const attentionLayers=`<div class="attention-layers">${layerCard('Urgent', layers.urgent||[], 'urgent', 'no active incident')}${layerCard('Advisory', layers.advisory||[], 'advisory', 'low-priority systems normal')}${layerCard('Wi-Fi Hygiene', layers.hygiene||[], 'hygiene', 'saved-password audit clean')}</div>`;
  el.innerHTML=`<div class="alert-card alert-${(a.level||'GREEN').toLowerCase()}" style="--alert:${a.color||'var(--green)'}"><b>${a.level||'GREEN'} ${a.score||0}%</b><span>${(a.reasons||['normal watch']).map(escapeHtml).join(' // ')}</span></div>${attentionLayers}<div class="mission-grid"><div><span>VPN</span><b>${s.vpn?.active?'ON':(s.vpn?.gui_running?'APP':'OFF')}</b></div><div><span>GPS</span><b>${gps.fixed?'LOCK':'NO FIX'} ${gps.satellitesUsed||0}/${gps.satellitesVisible||0}</b></div><div><span>WEATHER</span><b>${wx.available?`${wx.summary} ${wx.tempF}°F`:'n/a'}</b></div><div><span>VISION</span><b>${vision.enabled?'ARMED':'OFF'}</b></div><div><span>KNOWN</span><b>${known.online||0}/${known.total||0} online</b></div><div><span>FAN</span><b>${sys.fan?.available?`${sys.fan.rpm||0}rpm ${sys.fan.cooling_state ?? '?'}/${sys.fan.cooling_max ?? '?'}`:'n/a'}</b></div><div><span>WIFI</span><b>${wifi.current?.ssid||'offline'}</b></div></div>${liveWave('24-SAMPLE RAM HISTORY', hist, `${sys.memory?.percent||0}%`, 'var(--purple)')}`;
}
function renderCyberTestKit(s={}){
  const el=document.getElementById('cyberKitViz'); if(!el) return;
  const lab=s.lab_toys||{}, hw=lab.hardware_docks||{}, ir=lab.ir||{}, nfc=lab.nfc_rfid||{}, rf=s.rf_audit||{};
  const adapter=rf.wifi?.adapter||{}, setup=adapter.monitor_setup||rf.wifi?.pwnagotchi?.monitor_setup||{};
  const monitor=(adapter.interfaces||[]).some(i=>i.type==='monitor');
  const kit=[
    {id:'wifi', label:'Wi-Fi Scan', state:s.wifi?.available?'ready':'check', action:`scan('wifi')`, note:`${(s.wifi?.networks||[]).length} APs visible`},
    {id:'bt', label:'BT Scan', state:'bounded', action:`scan('bluetooth')`, note:`${(s.bluetooth?.devices||[]).length} BT seen`},
    {id:'lan', label:'Look for Devices', state:'local LAN', action:`scan('lan')`, note:`${(s.lan?.devices||[]).length} LAN devices`},
    {id:'recon', label:'Aggro Recon', state:'authorized local', action:`aggressiveRecon()`, note:'private LAN only, no exploit'},
    {id:'rf', label:monitor?'Passive Capture':'Prep Antenna', state:monitor?'monitor ready':(setup.can_enable?'dongle ready':'needs antenna'), action:monitor?`startOwnedLabCapture()`:`prepMonitorAdapter()`, note:'owned-lab passive only'},
    {id:'irscan', label:'Scan IR', state:ir.ready?'ready':'detect', action:`irAction('detect')`, note:ir.receiver||'IR status'},
    {id:'irrx', label:'Receive IR', state:ir.ready?'8s window':'needs LIRC', action:`irAction('receive-once')`, note:'no transmit/replay'},
    {id:'nfcr', label:'Read NFC/RFID', state:nfc.ready?'ready':'detect', action:`nfcRfidAction('read-once')`, note:nfc.reader||'reader status'},
    {id:'nfcw', label:'Write Owned Tag', state:nfc.ready?'gated':'needs reader', action:`nfcRfidWriteOwned()`, note:'owned blank text only'},
  ];
  el.innerHTML=kit.map(k=>`<button class="cyber-kit-action cyber-${k.id}" onclick="${k.action}"><b>${escapeHtml(k.label)}</b><span>${escapeHtml(k.state)}</span><small>${escapeHtml(k.note)}</small></button>`).join('') + `<div class="scanline-note cyber-kit-policy">Pwnagotchi-on-steroids mode: fast faces + home/owned-lab controls. Blocked here: deauth, cracking, credential capture, unknown tag cloning, IR replay/transmit.</div>`;
}
let weatherKeyStatusText='Key status: tap Recheck Key to verify.';
let weatherKeyChecking=false;
async function recheckWeatherKey(){
  weatherKeyChecking=true;
  const el=document.getElementById('weatherKeyStatus'); if(el) el.textContent='Checking OpenWeather key...';
  try{
    const r=await fetch('/api/weather/keycheck',{cache:'no-store'});
    const d=await r.json();
    if(!d.configured) weatherKeyStatusText=`No key found. ${d.note||''}`;
    else if(d.valid===true) weatherKeyStatusText=`Key ${d.masked} works (radar tiles enabled).`;
    else if(d.valid===false) weatherKeyStatusText=`Key ${d.masked} was rejected: ${d.note||'unauthorized'}`;
    else weatherKeyStatusText=`Key ${d.masked} found, but could not verify: ${d.note||'no network reply'}`;
    if(window.v2Toast) v2Toast('OpenWeather key', weatherKeyStatusText, d.valid===true?'ok':(d.configured?'warn':'info'), 5200);
  }catch(e){ weatherKeyStatusText=`Recheck failed: ${e.message||e}`; }
  weatherKeyChecking=false;
  await fetch('/api/status/slow?force=1',{cache:'no-store'}).catch(()=>{});
  await refresh();
}
let wxRadarFilter='now';
function setWxRadarFilter(mode, btn){
  wxRadarFilter=mode;
  const wrap=document.getElementById('weatherSimViz'); if(!wrap) return;
  wrap.querySelectorAll('.rf-btn').forEach(b=>b.classList.toggle('active', b===btn));
  const radar=wrap.querySelector('.weather-radar'); if(radar) radar.dataset.rf=mode;
  const cv=wrap.querySelector('.weather-radar-canvas'); if(cv && cv.__wxData) cv.__wxData.rf=mode;
}
function renderWeatherSim(weather={}, light={}){
  const el=document.getElementById('weatherSimViz'); if(!el) return;
  const day=weatherDayState(weather);
  const summary=String(weather.summary||'weather n/a');
  const s=summary.toLowerCase();
  const storm=s.includes('storm')||s.includes('thunder');
  const rain=storm||s.includes('rain')||s.includes('shower')||s.includes('drizzle');
  const snow=s.includes('snow')||s.includes('sleet');
  const cloud=rain||snow||s.includes('cloud')||s.includes('fog')||s.includes('mist')||s.includes('overcast');
  const clear=s.includes('clear')||s.includes('sun');
  const cls=storm?'storm':rain?'rain':snow?'snow':cloud?'cloud':clear?'clear':'idle';
  const drops=Array.from({length: rain?28:snow?22:0},(_,i)=>`<i style="--x:${(i*37)%100}%;--d:${(i%9)*-.18}s;--l:${18+(i%5)*8}px"></i>`).join('');
  const stars=Array.from({length:18},(_,i)=>`<i style="--x:${(i*53)%100}%;--y:${10+((i*29)%62)}%;--d:${(i%6)*.35}s"></i>`).join('');
  const forecast=(weather.forecast||[]).slice(0,5).map(d=>`<div class="fx-day"><b>${(d.date||'').slice(5)||'day'}</b><span>${weatherIcon(d.summary, day.isNight)} ${d.highF??'?'}°/${d.lowF??'?'}°F</span><small>${escapeHtml(d.summary||'')} // rain ${d.chanceRain??0}% snow ${d.chanceSnow??0}%</small></div>`).join('');
  const xy=weatherTileXY(weather.lat, weather.lon, 6);
  const layers=(weather.radar?.layers||['precipitation_new','clouds_new','wind_new']).slice(0,3);
  const tiles=weather.radar?.configured && xy ? layers.map((layer,i)=>`<img class="radar-layer radar-layer-${i}" src="/api/weather/tile/${layer}/${xy.z}/${xy.x}/${xy.y}.png" alt="${layer} weather radar tile">`).join('') : '';
  const radarNote=weather.radar?.configured ? `OpenWeather live tile: ${layers.join(' / ')} (Now only)` : 'OpenWeather key missing // stylized wind-tracked radar';
  const keyStatusHtml=`<span id="weatherKeyStatus">${escapeHtml(weatherKeyStatusText)}</span> <button class="tiny-btn" onclick="recheckWeatherKey()">${weatherKeyChecking?'Checking…':'Recheck Key'}</button>`;
  const phase=day.isNight?'night':'day';
  const temp=Number(weather.tempF), hum=Number(weather.humidity), wind=Number(weather.windMph||0), rainChance=Math.max(...(weather.forecast||[]).slice(0,3).map(d=>Number(d.chanceRain||0)),0);
  if(Number.isFinite(temp)) pushHist(weatherTempHist, clamp((temp+10)/120*100));
  if(Number.isFinite(hum)) pushHist(weatherHumidityHist, hum);
  pushHist(weatherWindHist, Math.min(wind/50*100,100));
  const wxRisk=storm?'RED':rainChance>=60||wind>=25?'AMBER':'GREEN';
  const wxTable=`<table class="mini-table sec-table weather-ops-table"><tbody><tr><td>source</td><td>${escapeHtml(weather.source||'n/a')}</td></tr><tr><td>location</td><td>${escapeHtml(weather.location||'unknown')}</td></tr><tr><td>coords</td><td>${weather.lat&&weather.lon?`${Number(weather.lat).toFixed(3)}, ${Number(weather.lon).toFixed(3)}`:'n/a'}</td></tr><tr><td>radar</td><td>${weather.radar?.configured?'live tile proxy':'simulated sweep'}</td></tr><tr><td>daylight</td><td>${phase.toUpperCase()} // sunrise ${day.sunrise} // sunset ${day.sunset}</td></tr></tbody></table>`;
  el.className=`weather-sim weather-state-${cls} weather-${phase}`;
  el.style.setProperty('--sun-x', `${12 + day.progress*.76}%`);
  el.style.setProperty('--sun-y', `${62 - Math.sin((day.progress/100)*Math.PI)*44}%`);
  const rfBtn=m=>`<button class="rf-btn${wxRadarFilter===m?' active':''}" onclick="setWxRadarFilter('${m}',this)">${m[0].toUpperCase()+m.slice(1)}</button>`;
  el.innerHTML=`<div class="weather-sky"><div class="weather-stars">${stars}</div><div class="weather-sun"></div><div class="weather-moon"></div><div class="weather-cloud c1"></div><div class="weather-cloud c2"></div><div class="weather-rain">${drops}</div><div class="weather-lightning"></div><div class="weather-ground"></div></div><div class="weather-readout sec-readout"><div class="sec-summary ${wxRisk.toLowerCase()}"><b>WEATHER OPS ${wxRisk}</b><span>${weatherIcon(summary, day.isNight)} ${escapeHtml(summary)} // ${weather.available?(weather.tempF ?? 'n/a')+'°F':'waiting'}</span></div><div class="metric-grid">${metricCell('TEMP', weather.available?`${weather.tempF ?? 'n/a'}°F`:'n/a', summary)}${metricCell('HUMIDITY', weather.available?`${weather.humidity ?? 'n/a'}%`:'n/a', 'outside weather')}${metricCell('WIND', weather.available?`${weather.windMph ?? 'n/a'} mph`:'n/a', `rain risk ${rainChance}%`)}${metricCell('LIGHT', light.available?`${light.lux} lux`:'n/a', 'room sensor')}</div>${wxTable}</div><div class="weather-radar" data-rf="${wxRadarFilter}"><div class="radar-filters">${rfBtn('recent')}${rfBtn('now')}${rfBtn('upcoming')}</div><div class="radar-tile">${tiles}<canvas class="weather-radar-canvas"></canvas></div><small>${radarNote}</small><small class="weather-key-row">${keyStatusHtml}</small></div><div class="forecast-strip">${forecast||'<div class="fx-day"><b>forecast</b><span>waiting</span><small>weather cache warmup</small></div>'}</div><div class="weather-waves">${liveWave('OUTSIDE TEMP', weatherTempHist, Number.isFinite(temp)?`${temp.toFixed(1)}°F`:'n/a', temp>=88?'var(--red)':temp<=35?'var(--cyan)':'var(--green)')}${liveWave('HUMIDITY', weatherHumidityHist, Number.isFinite(hum)?`${hum.toFixed(0)}%`:'n/a', 'var(--blue)')}${liveWave('WIND', weatherWindHist, `${wind||0} mph`, wind>=25?'var(--yellow)':'var(--purple)')}</div>`;
  const radarCanvas=el.querySelector('.weather-radar-canvas');
  if(radarCanvas) radarCanvas.__wxData={cls, windMph:wind, windDir:Number.isFinite(Number(weather.windDir))?Number(weather.windDir):0, precipMm:Number(weather.precipMm)||0, rf:wxRadarFilter};
}
function renderGlobalMap(s){
  const el=document.getElementById('globalMapViz'); if(!el) return;
  const sys=s.system||{}, vpn=s.vpn||{}, gps=s.sensors?.gps||{}, wx=s.sensors?.weather||{};
  const tail=(sys.ips||[]).find(ip=>String(ip).startsWith('100.'))||'no-tailnet';
  const vpnOn=!!vpn.active;
  const vpnLabel=vpnOn?'CONNECTED':(vpn.gui_running?'APP OPEN':'DISCONNECTED');
  const activeName=(vpn.active_connections||[])[0]?.name || '';
  const selectedName=selectedProtonProfile || vpn.selected_profile?.name || activeName || 'Fastest country';
  const profiles=(vpn.profiles||[]).slice(0,10);
  const gpsLabel=gps.fixed?`${Number(gps.lat).toFixed(3)}, ${Number(gps.lon).toFixed(3)}`:`GPS NO FIX // ${gps.satellitesVisible||0} seen // best ${gps.satelliteSignalBest ?? 'n/a'}`;
  const ts=s.tailscale||{};
  const tsLabel=ts.ip?`TS ${ts.ip} ${ts.online?'OK':'CHECK'}`:'TS OFFLINE';
  const markers=[
    {name:'US-ME',x:26.8,y:35.7,aliases:['US','United States','Maine']},{name:'US-NY',x:25.7,y:38.3,aliases:['US','United States','New York']},{name:'US-FL',x:25.2,y:47.7,aliases:['US','United States','Florida']},{name:'US-TX',x:20.0,y:45.8,aliases:['US','United States','Texas']},{name:'US-CA',x:14.0,y:39.4,aliases:['US','United States','California']},{name:'US-WA',x:14.8,y:30.4,aliases:['US','United States','Washington']},
    {name:'UK',x:47.5,y:31.7,aliases:['UK','United Kingdom','GB']},{name:'NL',x:49.2,y:33.5,aliases:['NL','Netherlands']},{name:'DE',x:50.4,y:35.1,aliases:['DE','Germany']},{name:'CH',x:49.9,y:39.0,aliases:['CH','Switzerland']},{name:'PL',x:53.0,y:34.9,aliases:['PL','Poland']},{name:'SE',x:52.2,y:25.6,aliases:['SE','Sweden']},{name:'IT',x:51.5,y:43.6,aliases:['IT','Italy']},{name:'ES',x:46.5,y:43.5,aliases:['ES','Spain']},{name:'TR',x:57.7,y:45.1,aliases:['TR','Turkey']},
    {name:'IN',x:68.5,y:53.8,aliases:['IN','India']},{name:'SG',x:73.9,y:65.2,aliases:['SG','Singapore']},{name:'JP',x:83.9,y:43.7,aliases:['JP','Japan']},{name:'AU',x:81.0,y:77.0,aliases:['AU','Australia']},{name:'BR',x:36.5,y:70.6,aliases:['BR','Brazil']},{name:'AR',x:31.8,y:82.0,aliases:['AR','Argentina']},{name:'ZA',x:54.0,y:78.2,aliases:['ZA','South Africa']}
  ];
  const norm=v=>String(v||'').toLowerCase();
  // Match a VPN profile name to a map marker. Two-letter country codes must match whole words
  // (a plain substring test made "Fastest country" light up ES and TR), and an exact marker name
  // like "US-NY" wins over the broader "US" alias so only one pin is highlighted.
  const matchesProfile=(m,n)=>{
    const nn=norm(n); if(!nn) return false;
    const words=nn.split(/[^a-z0-9]+/).filter(Boolean);
    const hit=a=>{ const na=norm(a); return na.length<=3 ? words.includes(na) : (nn.includes(na)||(nn.length>=4&&na.includes(nn))); };
    if(markers.some(x=>hit(x.name))) return hit(m.name);
    return [m.name,...(m.aliases||[])].some(hit);
  };
  const connectedMarkerIndex=Math.max(0, markers.findIndex(m=>matchesProfile(m, activeName||selectedName)));
  const enc=n=>encodeURIComponent(String(n));
  const markerHtml=markers.map((m,i)=>{ const sel=matchesProfile(m, selectedName); const conn=i===connectedMarkerIndex && (vpnOn||activeName); const [mx,my]=mapAnchorPercent(m); return `<button class="proton-pin ${conn?'connected':''} ${sel?'selected':''}" style="left:${mx.toFixed(2)}%;top:${my.toFixed(2)}%" aria-label="${m.name}" data-label="${m.name}" onclick="selectProtonProfile(decodeURIComponent('${enc(m.name)}'), false)"><span></span></button>`; }).join('');
  const list=profiles.length ? profiles.map((p,i)=>`<button class="proton-server-row ${p.name===selectedName?'selected':''}" onclick="selectProtonProfile(decodeURIComponent('${enc(p.name)}'), true)"><i></i><span>${p.name}</span><em>${p.name===activeName?'active':p.name===selectedName?'selected':i===0?'saved':'profile'}</em></button>`).join('') : `<button class="proton-server-row ${selectedName?'selected':''}" onclick="selectProtonProfile('Fastest country', true)"><i></i><span>${vpn.proton_installed?'Fastest country':'No VPN profile saved'}</span><em>${vpn.proton_installed?'open app':'setup needed'}</em></button>`;
  const actionText=protonActionStatus || vpn.message || 'Pick a marker/profile, then Start VPN.';
  el.innerHTML=`<div class="world-map proton-map proton-desktop-map" style="--proton-zoom:${protonMapZoom}"><aside class="proton-side-panel"><div class="proton-search">⌕ ${escapeHtml(selectedName)} <kbd>${vpnLabel}</kbd></div><div class="proton-tabs"><button class="active" onclick="selectProtonPanel('countries')">Countries</button><button onclick="selectProtonPanel('profiles')">Profiles</button></div><div class="proton-filter"><button class="active" onclick="selectProtonFilter(this)">All</button><button onclick="selectProtonFilter(this)">Secure Core</button><button onclick="selectProtonFilter(this)">P2P</button></div><div class="proton-server-list">${list}</div><div class="proton-action-row"><button id="protonStartButton" onclick="startProtonVpn()">${vpnOn?'VPN Active':'Start VPN'}</button><button onclick="toggleVpn()">${vpnOn?'Stop VPN':'Toggle'}</button><button onclick="openProtonVpn()">Open App</button></div><div class="tailscale-action-row"><button onclick="tailscaleAction('status')">TS Status</button><button onclick="tailscaleAction('up')">TS Up</button><button onclick="tailscaleAction('protect')">Protect TS</button></div><div class="proton-action-status">${escapeHtml(actionText)}</div></aside><div class="proton-map-stage"><div class="proton-map-toolbar"><button onclick="setProtonZoom(-0.1)">−</button><button onclick="resetProtonZoom()">Reset</button><button onclick="setProtonZoom(0.1)">+</button><button onclick="toggleProtonFx()">${protonFxEnabled?'FX on':'FX off'}</button></div><div class="proton-map-viewport"><div class="proton-map-canvas"><img src="/assets/proton-world.svg" alt="Proton world map">${markerHtml}</div></div><div class="proton-map-footer"><span>${vpnLabel}</span><span>${escapeHtml(selectedName)}</span><span>${escapeHtml(tsLabel)}</span><span>${tail}</span><span>${gpsLabel}</span><span>${wx.available?escapeHtml(wx.summary):'weather n/a'}</span></div></div></div>`;
  applyProtonFx();
}

function renderDefenseOps(sec={}){
  const el=document.getElementById('defenseOpsViz'); if(!el) return;
  const lanes=(sec.lanes||[]).map(l=>{
    const score=clamp((Number(l.score||0)/4)*100);
    const signals=(l.signals||[]).map(x=>`<li>${escapeHtml(x)}</li>`).join('');
    return `<div class="security-lane security-${escapeHtml(l.id)} ${l.installed?'installed':'staged'}"><div class="security-lane-head"><b><span>${escapeHtml(l.icon||'▣')}</span>${escapeHtml(l.label)}</b><em>${escapeHtml(l.state||'staged')}</em></div><div class="security-meter"><i style="width:${score}%"></i><span>${Math.round(score)}%</span></div><ul>${signals}</ul><small>${escapeHtml(l.safe_use||'defensive only')}</small></div>`;
  }).join('') || '<div class="scanline-note">Security Lab lanes unavailable.</div>';
  const stacks=(sec.stacks||[]).map(st=>`<div class="defense-row ${st.installed?'installed':''}"><b>${escapeHtml(st.label)}</b><span>${st.installed?'detected':'not installed'}</span><small>${(st.signals||[]).map(escapeHtml).join(' // ')}</small><em>${escapeHtml(st.safe_use||'')}</em></div>`).join('');
  const arch=(sec.architecture||[]).map(x=>`<span>${escapeHtml(x)}</span>`).join('');
  const recs=(sec.recommendations||[]).slice(0,3).map(r=>`<li>${escapeHtml(r)}</li>`).join('');
  el.innerHTML=`<div class="security-lab-board"><section class="security-lab-hero"><div><p class="mini">NATIVE BLUE-TEAM LAYOUT // FROM RASPBERRY PI SECURITY LAB IDEAS</p><h3>${escapeHtml(sec.mode||'Security Lab')}</h3><p>Hardening, IDS, honeypot, and dashboard/log-pipeline features live inside Spac3-Gh0st now instead of being orphan repo notes.</p></div><div class="security-lab-actions"><button onclick="showTab('systems')">Open Lab Bay</button><button onclick="labSoftwareAction('securitylab','check')">Check Repo</button>${sec.repo_present?'':`<button onclick="labSoftwareAction('securitylab','install')">Clone Security Lab</button>`}<a class="lab-link" href="${sec.source||'#'}" target="_blank" rel="noopener noreferrer">Source</a></div></section><div class="security-architecture">${arch}</div><div class="security-lanes">${lanes}</div><section class="security-source-map"><h3>Source / Similar Tools</h3>${stacks}</section><ul class="defense-recs">${recs}</ul></div>`;
}
function renderLabGuide(lab={}, status={}){
  const el=document.getElementById('labGuideViz'); if(!el) return;
  const sw=lab.software||{}, rf=status.rf_audit||{}, sec=status.security_stack||{};
  const modules=sw.modules||[];
  const securityLab=modules.find(m=>m.id==='securitylab')||{};
  const bjorn=modules.find(m=>m.id==='bjorn')||{};
  const adapter=rf.wifi?.adapter||{}, setup=adapter.monitor_setup||rf.wifi?.pwnagotchi?.monitor_setup||{};
  const monitor=(adapter.interfaces||[]).some(i=>i.type==='monitor');
  const dongleReady=!!setup.can_enable || !!monitor || (adapter.external_adapters||[]).length>0;
  const lanes=sec.lanes||[];
  const step=(id,title,state,body,actions,good=false)=>`<div class="lab-step ${good?'ready':'todo'}"><div class="lab-step-head"><b>${escapeHtml(title)}</b><span>${escapeHtml(state)}</span></div><p>${escapeHtml(body)}</p><div class="lab-step-actions">${actions}</div></div>`;
  const actions={
    wifi:`<button onclick="showTab('signals'); setTimeout(()=>document.querySelector('.wifi-target-list')?.scrollIntoView({behavior:'smooth',block:'center'}),50)">Pick Wi‑Fi Target</button><button onclick="scan('wifi')">Scan Wi‑Fi</button>`,
    rf:`<button onclick="showTab('signals'); setTimeout(()=>document.querySelector('.rf-card')?.scrollIntoView({behavior:'smooth',block:'center'}),50)">Open RF Audit</button>${monitor?'<button onclick="startOwnedLabCapture()">Passive Capture</button>':`<button onclick="prepMonitorAdapter()" ${setup.can_enable?'':'disabled title="No external monitor-capable dongle detected"'}>Prep Monitor</button>`}`,
    security:`${securityLab.installed?'<button onclick="labSoftwareAction(\'securitylab\',\'check\')">Check Security Lab</button>':'<button onclick="labSoftwareAction(\'securitylab\',\'install\')">Clone Security Lab</button>'}<button onclick="showTab('signals'); setTimeout(()=>document.querySelector('.defense-card')?.scrollIntoView({behavior:'smooth',block:'center'}),50)">Open Defensive Ops</button>`,
    tools:`<button onclick="showTab('lab'); setTimeout(()=>document.querySelector('.lab-software-card')?.scrollIntoView({behavior:'smooth',block:'center'}),50)">Lab Software</button><button onclick="showTab('lab'); setTimeout(()=>document.querySelector('.safety-boundary-card')?.scrollIntoView({behavior:'smooth',block:'center'}),50)">Safety Boundaries</button>`
  };
  const cards=[
    step('wifi','1. Select a Wi‑Fi target', status.wifi?.networks?.length?`${status.wifi.networks.length} network(s) visible`:'scan needed', 'Pick an AP first, then you can add it to Known, Trust/Watch it, rename it, or run a safe signal/security/channel audit.', actions.wifi, !!selectedWifiSsid),
    step('rf','2. Pick the safe RF action', monitor?'monitor interface ready':(dongleReady?'USB dongle ready':'no monitor dongle detected'), 'RF actions stay safe: inventory, warnings, channel plan, and owned-lab passive capture only when the external adapter is explicitly prepped for monitor mode.', actions.rf, dongleReady),
    step('security','3. Security Lab phases', securityLab.installed?'repo cloned/staged':'repo not cloned yet', 'Hardening, IDS, honeypot, and logs/dashboard live in Defensive Ops. Clone/review first; do not blindly run firewall/SSH scripts.', actions.security, !!securityLab.installed),
    step('tools','4. Enable only the matching boundary', lanes.length?`${lanes.length} defensive lanes reporting`:'waiting for status', 'The Lab page now groups software, spicy tools, workflows, safety boundaries, companion firmware, ADS-B, and optical audio by what they actually do.', actions.tools, lanes.length>0 || !!bjorn.installed),
  ];
  el.innerHTML=`<div class="spicy-banner"><b>DO THIS NEXT</b><span>Select target → choose action → read result. No mystery prerequisite dead ends.</span></div><div class="lab-steps">${cards.join('')}</div>`;
}

function renderSpicyTools(spicy={}){
  const el=document.getElementById('spicyToolsViz'); if(!el) return;
  const tools=spicy.tools||[];
  const cards=tools.map(t=>{
    const installed=t.installed?'installed':'missing';
    const running=t.running?'running':(t.enabled?'enabled':'disabled');
    const blocked=(t.blocked_actions||[]).join(', ')||'none';
    return `<div class="spicy-tool ${t.running?'running':''} ${t.installed?'installed':'missing'}"><div class="spicy-head"><b>${t.label}</b><span>${installed} // ${running}</span></div><small>${t.description||''}</small><div class="spicy-meta"><span>risk ${t.risk||'medium'}</span><span>${t.mode||'safe'}</span></div><div class="spicy-actions"><button onclick="spicyAction('${t.id}','enable')" ${!t.can_enable?'disabled':''}>Enable / Stage</button><button onclick="spicyAction('${t.id}','disable')" ${!t.can_disable?'disabled':''}>Disable</button><button onclick="spicyAction('${t.id}','reset')">Safe Reset</button></div><em>blocked: ${blocked}</em><code>${t.status_note||''}</code></div>`;
  }).join('') || '<div class="scanline-note">spicy status unavailable</div>';
  el.innerHTML=`<div class="spicy-banner"><b>${spicy.mode||'defensive-only'}</b><span>${spicy.policy||'no risky actions from dashboard toggles'}</span></div>${cards}`;
}
async function spicyAction(tool, action){
  if(action==='enable' && !confirm(`Enable/stage ${tool}? Safe services may start if installed; high-risk capture/deauth/injection/cracking/MITM will not start.`)) return;
  const d=await postJson('/api/spicy/action',{tool, action});
  alert(d.ok?`${tool} ${action}: ${d.message||'ok'}`:`${tool} ${action} refused: ${d.error||'unknown'}`);
  await refresh();
}
function renderLabToys(lab={}, status={}){
  renderLabGuide(lab, status);
  renderSpicyTools(status.spicy_tools||{});
  renderLabWorkflows(lab.workflows||{});
  renderSafetyBoundaries(lab.safety_boundaries||{});
  renderLabSoftware(lab.software||{});
  renderOpticalAudio(lab.optical_audio||{});
  renderPiAware(lab.piaware||{});
  renderCompanionFirmware(status);
  renderHardwareDocks(lab.hardware_docks||{});
  renderFlipperZero(lab.flipper||{});
}


function renderLabSoftware(sw={}){
  const el=document.getElementById('labSoftwareViz'); if(!el) return;
  const modules=sw.modules||[];
  const cardFor=m=>{
    const paths=(m.existing_paths||[]).map(p=>`<code>${escapeHtml(p)}</code>`).join('') || '<code>not installed on this Pi yet</code>';
    const needed=(m.needed||[]).map(x=>`<li>${escapeHtml(x)}</li>`).join('');
    const blocked=(m.blocked_actions||[]).map(x=>`<li>${escapeHtml(x)}</li>`).join('');
    const cmd=(m.commands||[]).join(', ') || `missing: ${(m.missing_commands||[]).join(', ')||'n/a'}`;
    const onDemand=['godseye','hermesworkspace','projectnomad','openwebui','portainer'];
    const openUi=(m.url&&m.running)?`<a class="lab-link open-ui" href="${escapeHtml(m.url)}" target="_blank" rel="noopener noreferrer">Open UI</a>`:'';
    const stopStart=onDemand.includes(m.id)?`<button onclick="labSoftwareAction('${m.id}', '${m.running?'disable':'open'}')">${m.running?'Stop Service':'Start Service'}</button>`:`<button onclick="labSoftwareAction('${m.id}', '${m.enabled?'disable':'enable'}')">${m.enabled?'Disable':'Enable / Stage'}</button>`;
    const canClone=['securitylab','ruview','cyberradar','payloadsallthethings','hacktricks','seclists','awesomehacking','awesomebugbounty','hackingtool'].includes(m.id) && !m.installed;
    return `<div class="lab-software ${m.installed?'installed':'missing'} ${m.enabled?'enabled':'disabled'}"><div class="lab-software-head"><b>${escapeHtml(m.label||m.id)}</b><span>${m.installed?'installed':'not installed'} // ${m.running?'running':'not running'} // ${m.state||'disabled'}</span></div><p>${escapeHtml(m.summary||'')}</p><div class="companion-meta"><span>${escapeHtml(m.home||'Lab')}</span><span>${escapeHtml(m.safe_mode||'safe gated')}</span></div><div class="lab-readiness"><b>${escapeHtml(m.readiness||'checking')}</b><span>commands: ${escapeHtml(cmd)}</span>${paths}</div><div class="companion-actions"><button onclick="labSoftwareAction('${m.id}','check')">Check</button>${canClone?`<button onclick="labSoftwareAction('${m.id}','install')">Clone Repo</button>`:''}${stopStart}<button onclick="labSoftwareAction('${m.id}','open')">${m.running?'Restart / Prep':'Start / Prep'}</button>${openUi}<a class="lab-link" href="${escapeHtml(m.source||'#')}" target="_blank" rel="noopener noreferrer">source</a></div><details><summary>needed / blocked</summary><div class="boundary-detail"><div><b>Needed</b><ul>${needed}</ul></div><div><b>Blocked here</b><ul>${blocked}</ul></div></div></details><small>${escapeHtml(m.last_message||sw.policy||'')}</small></div>`;
  };
  const homes=[...new Set(modules.map(m=>m.home||'Lab'))];
  const slug=home=>String(home||'lab').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'')||'lab';
  const groups=homes.map(home=>`<section class="launch-group launch-group-${slug(home)}"><h3>${escapeHtml(home)}</h3><div class="launch-group-grid">${modules.filter(m=>(m.home||'Lab')===home).map(cardFor).join('')}</div></section>`).join('') || '<div class="scanline-note">No lab software modules configured.</div>';
  el.innerHTML=`<div class="spicy-banner"><b>${escapeHtml(sw.mode||'lab software')}</b><span>${escapeHtml(sw.policy||'safe gated')}</span></div>${groups}`;
}
async function labSoftwareAction(module, action){
  const msg=action==='disable'?'Stop/disable this on-demand service if it is running?':action==='install'?'Clone this selected reference repo into /home/pi/apps? This downloads repo files only. It will NOT run installers, setup scripts, scanners, payloads, hardening, firewall, IDS, honeypot, or service scripts.':action==='open'?'Start/open this dashboard service if it is an on-demand local tool. Safe lab tools still only stage/readiness-check; no scans or installs.':action==='enable'?'Enable/stage this lab software boundary? Active use still requires owned-lab target approval.':null;
  if(msg && !confirm(msg)) return;
  const d=await postJson('/api/lab/software/action',{module, action});
  alert(d.ok?d.message:(d.error||'Lab software action refused'));
  await refresh();
  renderLabSoftware(lastStatus?.lab_toys?.software||d.software||{});
}

function renderLabWorkflows(wf={}){
  const el=document.getElementById('labWorkflowViz'); if(!el) return;
  const tools=Object.entries(wf.tools||{}).map(([k,v])=>`<span>${k}: ${v?'yes':'no'}</span>`).join('');
  const services=Object.entries(wf.services||{}).map(([k,v])=>`<tr><td>${k}</td><td>${v.active_text||'inactive'} / ${v.enabled_text||'n/a'}</td><td>${v.unit_exists?'unit':'no unit'}</td></tr>`).join('');
  const cards=(wf.workflows||[]).map(w=>`<div class="lab-workflow ${w.enabled?'enabled':'disabled'}"><div><b>${w.label}</b><span>${w.state} // ${w.mode}</span></div><p>${w.summary}</p><details><summary>process + requirements</summary><ul>${(w.needed||[]).map(x=>`<li>${x}</li>`).join('')}</ul><small>used by: ${(w.used_by||[]).join(', ')}</small><code>blocked: ${(w.blocked_actions||[]).join(', ')}</code></details><small>${w.readiness}</small><a class="lab-link" href="${w.source}" target="_blank" rel="noopener noreferrer">source notes</a></div>`).join('');
  el.innerHTML=`<div class="spicy-banner"><b>${wf.mode||'workflow readiness'}</b><span>${wf.policy||'disabled by default'}</span></div><div class="lab-tool-grid">${tools}</div><table class="mini-table"><tbody>${services}</tbody></table><div class="scanline-note">handshakes dir: ${wf.handshakes_dir||'n/a'} // artifacts: ${(wf.capture_artifacts||[]).length}</div>${cards}`;
}

function renderHardwareDocks(hw={}){
  const el=document.getElementById('hardwareDocksViz'); if(!el) return;
  const docks=hw.docks||[];
  const tools=Object.entries(hw.tools||{}).map(([k,v])=>`<span>${escapeHtml(k)}: ${v?'yes':'no'}</span>`).join('');
  const cards=docks.map(d=>{
    const cand=[...(d.candidates||[]),...(d.serials||[]),...(d.devices||[])].slice(0,4).map(x=>`<code>${escapeHtml(x)}</code>`).join('') || '<small>no direct device match yet</small>';
    const blocked=(d.blocked_actions||[]).slice(0,4).map(escapeHtml).join(', ');
    const action=d.id==='pwnagotchi-zero2'?`showTab('externals'); setTimeout(()=>document.querySelector('.pwnagotchi-dock-card')?.scrollIntoView({behavior:'smooth',block:'center'}),50)`:d.id==='cyd-buddy'?`showTab('externals'); setTimeout(()=>document.querySelector('.cyd-buddy-card')?.scrollIntoView({behavior:'smooth',block:'center'}),50)`:d.id.includes('esp32')||d.id.includes('bruce')?`companionAction('bruce','detect')`:d.id==='sdr-receiver'?`labSoftwareAction('sdrsuite','check')`:d.id==='ir-receiver'?`irAction('detect')`:d.id==='nfc-rfid-radio'?`nfcRfidAction('detect')`:`showTab('lab'); setTimeout(()=>document.querySelector('.safety-boundary-card')?.scrollIntoView({behavior:'smooth',block:'center'}),50)`;
    const extra=d.id==='nfc-rfid-radio'?`<button onclick="nfcRfidAction('read-once')">Read Owned Tag</button><button onclick="nfcRfidWriteOwned()">Write Owned Tag</button>`:d.id==='ir-receiver'?`<button onclick="irAction('receive-once')">Receive IR</button>`:'';
    return `<div class="companion-card dock-card ${d.detected?'installed':'missing'}"><div class="companion-head"><b>${escapeHtml(d.label)}</b><span>${d.detected?'detected':'waiting'}</span></div><p>${escapeHtml(d.readiness||'')}</p><div class="companion-meta"><span>${escapeHtml(d.kind||'hardware')}</span><span>${escapeHtml(d.home||'Lab')}</span></div><div class="dock-candidates">${cand}</div><div class="companion-actions"><button onclick="${action}">Detect / Open</button>${extra}</div><small>guarded: ${blocked}</small></div>`;
  }).join('') || '<div class="scanline-note">No hardware dock status yet.</div>';
  el.innerHTML=`<div class="spicy-banner"><b>PLUG-IN DOCKS</b><span>${escapeHtml(hw.policy||'detect/readiness only')}</span><span>serials: ${(hw.serial_candidates||[]).map(escapeHtml).join(', ')||'none'}</span><span>esptool: ${hw.esptool?'ready':'missing'}</span></div><div class="lab-tool-grid">${tools}</div>${cards}`;
}

function renderFlipperZero(fl={}){
  const el=document.getElementById('flipperViz'); if(!el) return;
  const tools=Object.entries(fl.tools||{}).map(([k,v])=>`<span>${escapeHtml(k)}: ${v?'yes':'no'}</span>`).join('');
  const cards=(fl.features||[]).map(f=>`<div class="companion-card dock-card ${f.enabled?'installed':'missing'}"><div class="companion-head"><b>${escapeHtml(f.label)}</b><span>${f.enabled?'enabled':'disabled'}</span></div><p>${escapeHtml(f.description||'')}</p><div class="companion-meta"><span>${escapeHtml(f.safe_mode||'reference only')}</span></div><div class="companion-actions"><button onclick="flipperFeatureAction('${escapeHtml(f.id)}','${f.enabled?'disable':'enable'}')">${f.enabled?'Disable':'Enable'}</button></div></div>`).join('') || '<div class="scanline-note">No Flipper-inspired features defined.</div>';
  const usb=(fl.usb_matches||[]).slice(0,3).map(x=>`<code>${escapeHtml(x)}</code>`).join('') || '<small>no Flipper USB match yet</small>';
  const blocked=(fl.blocked_actions||[]).map(escapeHtml).join(', ');
  el.innerHTML=`<div class="spicy-banner"><b>${fl.connected?'FLIPPER DETECTED':'NO FLIPPER DOCKED'}</b><span>${escapeHtml(fl.mode||'safe dock / disabled-by-default')}</span></div><div class="lab-tool-grid">${tools}</div><div class="dock-candidates">${usb}</div>${cards}<small>guarded: ${blocked}</small>`;
}
async function flipperFeatureAction(feature, action){
  const d=await postJson('/api/lab/flipper/action',{feature, action});
  showAction('flipperControl', d);
  renderFlipperZero(d.flipper||{});
}
async function nfcRfidAction(action){
  if(action==='read-once' && !confirm('Place an owned NFC/RFID tag on the CrowPi RC522 reader, then press OK. Spac3-Gh0st will wait up to 8 seconds and read once.')) return;
  const d=await postJson('/api/lab/nfc-rfid/action',{action});
  if(d.ok && d.tag) alert(`NFC/RFID read complete\nUID: ${d.tag.uid||''}\nText: ${d.tag.text||d.tag.raw||''}`);
  else alert(d.ok?(d.message||'NFC/RFID check complete'):(d.error||'NFC/RFID action failed'));
  await refresh();
}
async function nfcRfidWriteOwned(){
  const text=prompt('Text to write to an OWNED/BLANK NFC/RFID tag (128 chars max):','Spac3-Gh0st owned test tag');
  if(!text) return;
  if(text.length>128){ alert('Keep this safe one-shot NFC/RFID writer payload <=128 characters.'); return; }
  if(!confirm('Confirm this is your own blank/test tag. This will write text once; no cloning, emulation, payment/access-card work, or unknown-tag overwrite.')) return;
  const d=await postJson('/api/lab/nfc-rfid/action',{action:'write-owned-text', text, owned_blank:true});
  alert(d.ok?`${d.message} (${d.written_chars||text.length} chars)`:(d.error||'NFC/RFID write failed'));
  await refresh();
}
async function irAction(action){
  if(action==='receive-once' && !confirm('Point an owned IR remote at the configured receiver, then press OK. Spac3-Gh0st listens up to 8 seconds. No transmit/replay.')) return;
  const d=await postJson('/api/lab/ir/action',{action});
  if(d.ok && d.events) alert(`IR receive captured ${d.events.length} event(s):\n${d.events.join('\n')}`);
  else alert(d.ok?(d.message||'IR check complete'):(d.error||'IR action failed'));
  await refresh();
}

function renderCompanionFirmware(status={}){
  const el=document.getElementById('companionFirmwareViz'); if(!el) return;
  const wifi=status.wifi||{}, rf=status.rf_audit||{};
  const cards=[
    {id:'wirelesswizard',label:'WirelessWizard',home:'Wi-Fi + RF Audit',state:'Pi-native wrapper active through existing safe scans',mode:'safe scan/status wrapper',repo:'https://github.com/mind2hex/wirelesswizard',summary:'Lists wireless interfaces, scans networks, and feeds adapter/channel readiness into the Wi-Fi and RF Audit cards.',pi:'uses existing Wi-Fi scan + RF audit; no interface mode changes'},
    {id:'bruce',label:'Bruce Firmware',home:'Vision + Companion Firmware',state:'ESP32 companion detect/flasher bay',mode:'reference/flasher bay',repo:'https://github.com/brucedevices/firmware',summary:'Tracks ESP32-S3/M5Stack-style companion hardware when USB appears and keeps camera/firmware notes beside Vision.',pi:'detects serial/USB candidates; firmware flash still requires explicit approval'},
    {id:'marauder',label:'ESP32 Marauder',home:'RF Audit + Companion Firmware',state:'ESP32 owned-lab staging notes',mode:'defensive/owned-lab staging',repo:'https://github.com/justcallmekoko/ESP32Marauder',summary:'Keeps Marauder-style Wi-Fi/Bluetooth ideas mapped to defensive RF Audit and companion-device detection.',pi:'detects ESP32 hardware; no deauth/injection/cracking button'}
  ];
  const iface=(rf.wifi?.adapter?.interfaces||[]).map(i=>i.name||i).join(', ') || (wifi.available?'wlan0 detected':'wireless status unknown');
  const setup=rf.wifi?.adapter?.monitor_setup||rf.wifi?.pwnagotchi?.monitor_setup||{};
  el.innerHTML=`<div class="spicy-banner"><b>LAB EXPANSION QUEUE INTEGRATED</b><span>wireless interface: ${escapeHtml(iface)}</span><span>USB dongle: ${escapeHtml(setup.ready_label||'checking')}</span><span>items now point to their homes and safe actions</span></div>` + cards.map(c=>`<div class="companion-card companion-${c.id}"><div class="companion-head"><b>${escapeHtml(c.label)}</b><span>${escapeHtml(c.home)}</span></div><p>${escapeHtml(c.summary)}</p><div class="companion-meta"><span>${escapeHtml(c.mode)}</span><span>${escapeHtml(c.pi)}</span></div><div class="companion-actions"><button onclick="companionAction('${c.id}','activate')">Activate / Check</button><button onclick="companionHome('${c.id}')">Open Home</button><a class="lab-link" href="${c.repo}" target="_blank" rel="noopener noreferrer">source repo</a></div></div>`).join('');
}
function companionHome(id){ if(id==='wirelesswizard'||id==='marauder') showTab('signals'); else showTab('externals'); }
async function companionAction(id, action){
  const d=await postJson('/api/lab/companion/action',{companion:id, action});
  alert(d.ok?d.message:(d.error||'Companion action refused'));
  if(id==='wirelesswizard') await scan('wifi'); else await refresh();
}

function renderDashboardAquarium(aq={}, status={}){ renderAquarium(aq, status, '#aiAquariumDash'); }
function renderAquarium(aq={}, status={}, selector='[data-aquarium]'){
  const els=Array.from(document.querySelectorAll(selector)); if(!els.length) return;
  const weather=status.sensors?.weather||{}, mood=status.mood?.name||'curious', threat=Number(status.alert?.score||0), cam=status.vision||{};
  const day=weatherDayState(weather); const bg=day.isNight?'night':(weather.summary||'').toLowerCase().includes('rain')?'blue':'auto-sky';
  const fishGlyphs=['><(((°>','}<((((* >','><>','<°)))><','>)))\'>','><(((•>'];
  const fishCount=threat>65?6:threat>35?9:12;
  const fish=Array.from({length:fishCount},(_,i)=>{ const dir=i%3===0?'left':'right'; const glyph=fishGlyphs[i%fishGlyphs.length]; return `<span class="ascii-fish ${dir} f${i%6}" style="--y:${10+(i*11)%70}%;--d:${12+(i%6)*2}s;--delay:${-(i*1.31).toFixed(1)}s;--depth:${.62+(i%5)*.09}">${glyph}</span>`; }).join('');
  const bubbles=Array.from({length:24},(_,i)=>`<span class="ascii-bubble" style="--x:${4+(i*13)%92}%;--d:${5+(i%7)}s;--delay:${-(i*.47).toFixed(1)}s">${i%3?'o':'O'}</span>`).join('');
  const weeds=Array.from({length:18},(_,i)=>`<span class="ascii-weed" style="--x:${(i*6)%100}%;--h:${28+(i%5)*10}px;--delay:${-(i*.23).toFixed(1)}s">${i%2?'╽':'╿'}</span>`).join('');
  const visitors=`<span class="ascii-visitor octo">{\\__/}<br>( •.•)</span><span class="ascii-visitor horse">/)_/) <br>( 'x')</span><span class="ascii-visitor snail">_@/\_</span>`;
  const feeding=(Date.now()-aquariumLastFed)<4200;
  const className=`ai-aquarium ascii-aquarium aquarium-${bg} ${threat>65?'reef-alert':cam.enabled?'reef-watch':'reef-calm'} ${feeding?'feeding':''}`;
  const food=Array.from({length:16},(_,i)=>`<span style="--x:${20+(i*7)%55}%;--delay:${(i*.06).toFixed(2)}s">*</span>`).join('');
  const clock=new Date().toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
  const html=`<div class="ascii-water"></div><pre class="ascii-clock">${clock}</pre>${bubbles}${weeds}${fish}${visitors}<div class="fish-food">${food}</div><button class="feed-button" type="button" aria-label="Feed ASCII fish">tap tank to feed</button><div class="reef-floor"><b>ASCII AQUARIUM // POWER-PILL PORT</b><span>${mood} // ${weather.summary||'weather unknown'} // ${day.isNight?'night':'day'} // vision ${cam.enabled?'watching':'resting'} // threat ${threat||0} // fed ${aquariumFeedCount}x</span></div>`;
  els.forEach(el=>{ el.className=className; el.onclick=feedAquarium; el.ontouchstart=(ev)=>{ ev.stopPropagation(); feedAquarium(ev); }; el.innerHTML=html; });
}

function labGateButton(gate){
  if(!gate) return '';
  const action=gate.enabled?'disable':'enable';
  const label=gate.enabled?'Disable home-lab gate':'Enable / Stage';
  return `<div class="lab-gate ${gate.enabled?'enabled':'disabled'}"><div><b>${gate.label||gate.id}</b><span>${gate.note||gate.description||'staged only'}</span></div><button onclick="toggleLabGate('${gate.id}','${action}')">${label}</button><em>${gate.mode||'home-lab staging toggle only'}</em></div>`;
}
async function toggleLabGate(gate, action){
  const msg=action==='enable'?'Enable/stage this module? Safe installed services may start; missing or hardware-blocked modules stay staged. Offensive RF/USB/GPIO actions remain blocked.':'Disable this home-lab gate and stop safe known services if applicable?';
  if(!confirm(msg)) return;
  const d=await postJson('/api/lab/gate/action',{gate, action});
  if(!d.ok) alert(d.error||'Lab gate action refused');
  await refresh();
}

function renderSafetyBoundaries(sb={}){
  const el=document.getElementById('safetyBoundaryViz'); if(!el) return;
  const boundaries=sb.boundaries||[];
  const toolBits=Object.entries(sb.tools||{}).map(([k,v])=>`<span>${escapeHtml(k)}: ${v?'yes':'no'}</span>`).join('');
  const events=(lastStatus?.events||[]).filter(e=>String(e.kind||'').match(/lab|wifi|rf|sensors|vpn|vision|spicy/i)).slice(0,8);
  const captures=lastStatus?.lab_toys?.workflows?.capture_artifacts || [];
  const enabled=boundaries.filter(b=>b.enabled);
  const evidence=(b)=>{
    const tools=[...(b.needed_software||[]), b.service_or_tool||''].filter(Boolean).slice(0,5).map(x=>`<li>${escapeHtml(x)}</li>`).join('');
    const blocks=(b.blocked_actions||[]).slice(0,6).map(x=>`<li>${escapeHtml(x)}</li>`).join('');
    const ev=events.slice(0,4).map(e=>`<li><b>${escapeHtml(e.kind)}</b> ${escapeHtml(e.text||'')}</li>`).join('')||'<li>No recent matching events yet.</li>';
    return `<aside class="boundary-evidence"><b>${b.enabled?'LIVE/STAGED EVIDENCE':'WHAT THIS WOULD WATCH'}</b><div class="evidence-bars"><span style="--w:${b.enabled?88:22}%">boundary ${b.enabled?'armed':'off'}</span><span style="--w:${(b.needed_software||[]).length?62:18}%">tool checks</span><span style="--w:${captures.length?70:12}%">captures ${captures.length}</span></div><ul>${tools||'<li>No tool requirements listed.</li>'}</ul><details open><summary>blocked / guarded</summary><ul>${blocks||'<li>none listed</li>'}</ul></details><details><summary>recent related events</summary><ul>${ev}</ul></details></aside>`;
  };
  const catOf=(b)=>{
    const id=String(b.id||'');
    if(['monitor_mode','passive_capture'].includes(id)) return 'Passive';
    if(['packet_injection','deauth'].includes(id)) return 'Aggressive';
    if(['credential_capture','hash_cracking','mitm_spoofing'].includes(id)) return 'Offensive-gated';
    if(['badusb_hid','rf_transmit_emulation','nfc_rfid_write','gpio12_audio_output','kernel_module_reboot'].includes(id)) return 'Hardware / Experimental';
    return 'Defensive';
  };
  const cardFor=(b)=>{
    const used=(b.used_by||[]).map(x=>`<li>${escapeHtml(x)}</li>`).join('');
    const hw=(b.needed_hardware||[]).map(x=>`<li>${escapeHtml(x)}</li>`).join('');
    const sw=(b.needed_software||[]).map(x=>`<li>${escapeHtml(x)}</li>`).join('');
    const blocked=(b.blocked_actions||[]).join(', ');
    const action=b.enabled?'disable':'enable';
    const cat=catOf(b);
    const workflow=(cat==='Offensive-gated'||cat==='Aggressive')?'gated workflow':'safe workflow';
    return `<div class="safety-boundary-wrap ${b.enabled?'enabled':'disabled'}"><div class="safety-boundary ${b.enabled?'enabled':'disabled'}"><div class="safety-boundary-head"><b>${escapeHtml(b.label)}</b><span>${escapeHtml(b.state||'disabled')} // ${workflow}</span></div><p>${escapeHtml(b.summary||'')}</p><div class="safety-boundary-actions"><button onclick="toggleSafetyBoundary('${b.id}','${action}')">${b.enabled?'Disable':'Enable / Stage'}</button><em>${b.enabled?'evidence live':workflow}</em></div><details><summary>used by / needed</summary><div class="boundary-detail"><div><b>Used by</b><ul>${used}</ul></div><div><b>Hardware</b><ul>${hw}</ul></div><div><b>Software/service</b><ul>${sw}</ul><code>${escapeHtml(b.service_or_tool||'')}</code></div></div></details><small>${escapeHtml(b.readiness||'')}</small><code>guarded: ${escapeHtml(blocked||'none')}</code></div>${b.enabled?evidence(b):''}</div>`;
  };
  const order=['Defensive','Passive','Aggressive','Offensive-gated','Hardware / Experimental'];
  const cards=order.map(cat=>{
    const group=boundaries.filter(b=>catOf(b)===cat);
    if(!group.length) return '';
    const note=cat==='Offensive-gated'?'Requires explicit owned-lab target/approval before any active operation.':cat==='Aggressive'?'Active lab techniques are staged and target-gated; generic Enable never fires packets.':cat==='Passive'?'Observation/readiness first; management wlan0 and Tailscale stay protected.':cat==='Hardware / Experimental'?'Physical/kernel/RF experiments stay gated with rollback notes.':'Defensive checks, services, evidence, and recovery controls.';
    return `<section class="boundary-group boundary-${cat.toLowerCase().replace(/[^a-z0-9]+/g,'-')}"><h3>${cat}</h3><p>${note}</p>${group.map(cardFor).join('')}</section>`;
  }).join('') || '<div class="scanline-note">No safety boundary data.</div>';
  const summary=enabled.length?`${enabled.length} boundary panel(s) armed // evidence cards live beside enabled cards`:'Enable/stage a boundary to open a right-side evidence panel.';
  el.innerHTML=`<div class="spicy-banner"><b>${escapeHtml(sb.mode||'safety boundaries')}</b><span>${escapeHtml(sb.policy||'readiness only')}</span><span>${escapeHtml(sb.wlan0_policy||'')}</span><span>${summary}</span></div><div class="lab-tool-grid">${toolBits}</div>${cards}`;
}
async function toggleSafetyBoundary(boundary, action){
  const msg=action==='enable'?'Enable/stage this safety boundary? This arms the safe/gated workflow and shows live evidence. Risky actions still require explicit owned-lab target approval.':'Disable this safety boundary readiness flag?';
  if(!confirm(msg)) return;
  const d=await postJson('/api/lab/safety-boundary/action',{boundary, action});
  alert(d.ok?d.message:(d.error||'Safety boundary toggle refused'));
  await refresh();
}

function renderOpticalAudio(oa={}){
  const el=document.getElementById('opticalAudioViz'); if(!el) return;
  const tools=Object.entries(oa.tools||{}).map(([k,v])=>`<span>${k}: ${v?'yes':'no'}</span>`).join('');
  el.innerHTML=`<div class="lab-pill ${oa.raspispdif_card?'live':'idle'}"><b>${oa.raspispdif_card?'RASPISPDIF card online':'Optical GPIO driver not installed'}</b><span>${oa.pi5?'Pi5 ready':'not Pi5'} // RP1 PIO ${oa.rp1_pio_loaded?'loaded':'missing'}</span></div><table class="mini-table"><tbody><tr><td>model</td><td>${oa.model||'n/a'}</td></tr><tr><td>kernel</td><td>${oa.kernel||'n/a'}</td></tr><tr><td>GPIO12</td><td>${oa.gpio12_state||'n/a'}</td></tr><tr><td>headers</td><td>${oa.headers||'n/a'}</td></tr><tr><td>module</td><td>${oa.spdif_module_installed?'installed':'not installed'}</td></tr><tr><td>CamillaDSP</td><td>${oa.camilladsp_clone?'cloned':'not cloned'}</td></tr></tbody></table><div class="lab-tool-grid">${tools}</div><div class="scanline-note">${oa.wiring_warning||''}</div>${labGateButton(oa.gate)}<a class="lab-link" href="${oa.source||'#'}" target="_blank" rel="noopener noreferrer">RASPIAUDIO Pi5 GPIO S/PDIF notes</a>`;
}
function renderPiAware(pw={}){
  const el=document.getElementById('adsbViz'); if(!el) return;
  const tools=Object.entries(pw.tools||{}).map(([k,v])=>`<span>${k}: ${v?'yes':'no'}</span>`).join('');
  const svc=Object.entries(pw.services||{}).map(([k,v])=>`<tr><td>${k}</td><td>${v.active_text||'n/a'} / ${v.enabled_text||'n/a'}</td></tr>`).join('');
  const links=(pw.web_links||[]).map(l=>`<a class="lab-link" href="${l.url}" target="_blank" rel="noopener noreferrer">${l.label}</a>`).join('');
  const notes=(pw.notes||[]).map(n=>`<li>${n}</li>`).join('');
  el.innerHTML=`<div class="lab-pill ${pw.rtl_sdr_visible?'live':'idle'}"><b>${pw.installed?'PiAware pieces detected':'PiAware not installed'}</b><span>${pw.rtl_sdr_visible?'RTL-SDR visible':'No RTL-SDR visible'} // gated by default</span></div><div class="lab-tool-grid">${tools}</div><table class="mini-table"><tbody>${svc}</tbody></table><ul>${notes}</ul><div class="scanline-note">Blocked: ${(pw.blocked_actions||[]).join(', ')}</div>${labGateButton(pw.gate)}${links}`;
}
function renderExternals(externals={}){
  const nav=document.getElementById('externalDeviceTabs'), detail=document.getElementById('externalDetail'), title=document.getElementById('externalTitle');
  if(!nav || !detail) return;
  const devices=externals.devices||[];
  if(!devices.length){ nav.innerHTML='<div class="scanline-note">no external nodes configured</div>'; detail.textContent=''; return; }
  if(!devices.some(d=>d.id===selectedExternal)) selectedExternal=devices[0].id;
  const chipState=(d)=>{ const t=d.telemetry||{}; if(t.ping_ok && (t.ssh_ok || t.camera_http)) return 'online'; if(t.ping_ok || t.camera_http) return 'partial'; return 'offline'; };
  nav.innerHTML=devices.map(d=>{
    const t=d.telemetry||{};
    const state=chipState(d);
    const cam=t.camera_http?`CAM ${t.camera_http}`:(t.camera_error?'CAM ERR':'CAM n/a');
    const ssh=t.ssh_ok?'SSH live':(t.ssh_error?'SSH auth':'SSH n/a');
    const ping=t.ping_ok?`${t.latency_ms??'?'} ms`:'offline';
    return `<button class="external-device-chip ${d.id===selectedExternal?'active':''} external-${state}" onclick="selectExternal('${d.id}')"><span class="external-chip-head"><b>${d.label||d.id}</b><i>${state}</i></span><span>${d.host||''}</span><small>${ping} // ${ssh} // ${cam}</small></button>`;
  }).join('');
  const d=devices.find(x=>x.id===selectedExternal)||devices[0]; if(title) title.textContent=d.label||d.id;
  const links=(d.links||[]).map(l=>`<a href="${l.url}" target="_blank" rel="noopener noreferrer">${l.label||l.url}</a>`).join('')||'<span class="external-muted">no web links configured</span>';
  const notes=(d.notes||[]).map(n=>`<li>${n}</li>`).join('')||'<li>No notes configured.</li>';
  const t=d.telemetry||{}, sys=t.system||{}, mem=sys.memory||{};
  const diskPct=diskPercent(sys.disk_root||'');
  const load1=Number(String(sys.load||'0').split(' ')[0])||0;
  const tempC=Number(sys.cpu_temp_c||0);
  const tempText=sys.cpu_temp_f?`${sys.cpu_temp_f}°F`:'waiting';
  const state=chipState(d);
  const metric=(label,value,cls='')=>`<div class="external-metric ${cls}"><span>${label}</span><b>${value}</b></div>`;
  const metrics=`<div class="external-metrics">${metric('PING',t.ping_ok?`${t.latency_ms??'?'} ms`:'offline',t.ping_ok?'ok':'warn')}${metric('SSH',t.ssh_ok?'live':(t.ssh_error?'auth fail':'no key/closed'),t.ssh_ok?'ok':'warn')}${metric('CAM',t.camera_http?`HTTP ${t.camera_http}`:(t.camera_error?'endpoint fail':'n/a'),t.camera_http?'ok':'warn')}${metric('RAM',mem.percent!=null?`${mem.percent}%`:'waiting')}${metric('LOAD',sys.load||'waiting',load1>=4?'warn':'')}${metric('DISK',diskPct?`${diskPct}%`:'waiting',diskPct>=85?'warn':'')}${metric('TEMP',tempText,tempC>=75?'hot':tempC>=65?'warn':'')}${metric('KIND',d.kind||'external node')}</div>`;
  const bars=`<div class="external-bars">${bar('REMOTE DISK',diskPct,diskPct?diskPct+'%':'waiting')}${bar('REMOTE TEMP',Math.min(tempC/85*100,100),tempText,tempC>=75?'temp-hot':tempC>=65?'temp-warm':'')}</div>`;
  const camera=d.camera_feed?`<section class="external-panel external-camera camera-redirect"><h3>Camera</h3><b>Feed available</b><span>${d.camera_feed} // previews live in Externals</span><button onclick="switchCameraFeed('${d.camera_feed}'); showTab('externals')">Open in Externals</button></section>`:'';
  const controls=d.car_controls?`<section class="external-panel external-controls"><h3>Controls</h3><div class="car-controls"><button onclick="externalCar('${d.id}','forward')">▲</button><button onclick="externalCar('${d.id}','left')">◀</button><button class="stop" onclick="externalCar('${d.id}','stop')">STOP</button><button onclick="externalCar('${d.id}','right')">▶</button><button onclick="externalCar('${d.id}','backward')">▼</button></div><div class="scanline-note">Local car controls only. Use STOP if behavior is wrong.</div></section>`:'';
  const statusText=[t.error||'', t.ssh_error?`SSH ${t.ssh_error}`:'', t.camera_error?`CAMERA ${t.camera_error}`:''].filter(Boolean).join(' // ');
  detail.innerHTML=`<div class="external-grid external-dashboard"><section class="external-panel external-hero external-${state}"><div class="external-hero-title"><b>${d.kind||'external node'}</b><span>${state}</span></div><div class="external-hostline">${d.label||d.id} // ${d.host||'n/a'}</div><div class="external-facts"><span>ssh user <b>${d.user||'n/a'}</b></span><span>camera <b>${d.camera_feed||'n/a'}</b></span><span>password stored <b>${d.password_stored?'yes':'no'}</b></span></div><div class="external-links">${links}</div></section>${camera}<section class="external-panel external-metric-panel"><h3>Live Readouts</h3>${metrics}${bars}</section><section class="external-panel external-notes"><h3>Notes / Status</h3><ul>${notes}</ul>${statusText?`<div class="scanline-note">status: ${statusText}</div>`:''}</section>${controls}</div>`;
}

function selectExternal(id){ selectedExternal=id; renderExternals(lastStatus?.externals||{}); }
async function externalCar(id, action){
  const d=await postJson(`/api/externals/${id}/control`, {action});
  if(!d.ok) alert(`External control failed: ${d.error||'unknown'}`);
  await refresh();
}
function renderHouseholdSignals(hs={}){
  const el=document.getElementById('householdSignalsViz'); if(!el) return;
  const c=hs.counts||{};
  const unknown=(hs.unknown_online||[]).slice(0,8);
  const mapped=(hs.mapped_devices||[]).slice(0,8);
  const sigs=(hs.signals_used||[]).slice(0,6).map(x=>`<span>${escapeHtml(x)}</span>`).join('');
  const services=(hs.services||[]).map(s=>`<a class="house-service" href="${escapeHtml(s.url||'#')}" target="_blank" rel="noopener noreferrer"><b>${escapeHtml(s.label||s.id)}</b><small>${escapeHtml(s.role||'service')}</small></a>`).join('');
  const row=d=>`<div class="identity-row ${d.mapped?'mapped':'unknown'}"><b>${escapeHtml(d.identity||d.display||d.id)}</b><span>${escapeHtml((d.kind||'device').toUpperCase())} // ${escapeHtml(d.confidence||'unmapped')}</span><small>${escapeHtml(d.reason||'')}</small></div>`;
  el.innerHTML=`<div class="identity-score"><b>${escapeHtml(hs.summary||'mapping household signals')}</b><span>${c.online||0} online // ${c.mapped||0} mapped // ${c.unmapped_online||0} unmapped online</span></div><div class="house-services">${services}</div><div class="signal-chip-row">${sigs}</div><div class="identity-columns"><section><h3>Mapped home gear</h3>${mapped.map(row).join('')||'<div class="scanline-note">No mapped devices yet. Label/trust known rows to teach the map.</div>'}</section><section><h3>Sticks out / unmapped</h3>${unknown.map(row).join('')||'<div class="scanline-note">No unmapped online devices right now.</div>'}</section></div><div class="scanline-note">Home Assistant entity import is staged, not authenticated yet. Once connected, labels like Upstairs Light can be correlated with BT/LAN/Wi‑Fi evidence instead of guessed.</div>`;
}

function renderKnownDevices(kd){
  const el=document.getElementById('knownDevicesViz'); if(!el) return;
  const cards=(kd.devices||[]).slice(0,8).map(d=>{
    const kind=String(d.kind||'').replace(/'/g,"\\'"), id=String(d.id||'').replace(/'/g,"\\'");
    return `<div class="device-card"><div class="device-head"><span><i class="dot ${d.online?'on':'off'}"></i>${d.display||d.id}</span><b>${d.kind}</b></div><div class="device-meta">${d.trusted?'trusted':'new'}${d.watched?' // watched':''}</div><div class="device-actions"><button class="mini-btn" onclick="renameDevice('${kind}','${id}')">Name</button><button class="mini-btn" onclick="trustDevice('${kind}','${id}',${!d.trusted})">${d.trusted?'Untrust':'Trust'}</button><button class="mini-btn" onclick="watchDevice('${kind}','${id}',${!d.watched})">${d.watched?'Unwatch':'Watch'}</button></div></div>`;
  }).join('') || '<div class="scanline-note">no devices remembered yet</div>';
  el.innerHTML=`<div class="stat-row">${statPill('ONLINE',`${kd.online||0}/${kd.total||0}`)}${statPill('TRUSTED',kd.trusted||0)}${statPill('WATCHED',kd.watched||0)}</div><div class="device-list">${cards}</div>`;
}
async function updateKnownDevice(kind,id,body){ await postJson('/api/known-devices', {kind,id,...body}); await refresh(); }
function renameDevice(kind,id){ const label=prompt('Name this device:', id); if(label!==null) updateKnownDevice(kind,id,{label}); }
function trustDevice(kind,id,trusted){ updateKnownDevice(kind,id,{trusted}); }
function watchDevice(kind,id,watched){ updateKnownDevice(kind,id,{watched}); }
function renderSystem(sys){
  const cpu=sys.cpu_temp_c||0, cpuF=sys.cpu_temp_f||((cpu*9/5)+32), mem=sys.memory||{}, ram=Number(mem.percent||0), disk=diskPercent(sys.disk_root), load1=Number(String(sys.load||'0').split(' ')[0])||0;
  const loadPct=Math.min(load1/8*100,100), cpuPct=Math.min(cpu/85*100,100), net=sys.net_io||{}, fan=sys.fan||{};
  pushHist(cpuHist, cpuPct); pushHist(ramHist, ram); pushHist(diskHist, disk); pushHist(loadHist, loadPct); pushHist(rxHist, Math.min((net.rx_bps||0)/1048576*100,100)); pushHist(txHist, Math.min((net.tx_bps||0)/1048576*100,100));
  const posture=cpu>=75||ram>=85||disk>=90?'RED':cpu>=65||ram>=70||disk>=80||loadPct>=65?'AMBER':'GREEN';
  const summary=`${posture} // ${sys.hostname||'pi'} // up ${uptimeText(sys.uptime_s)} // ${fan.available?`${fan.rpm||0}rpm fan`:'fan n/a'}`;
  document.getElementById('systemViz').innerHTML = `<div class="sec-summary ${posture.toLowerCase()}"><b>SYSTEM POSTURE ${posture}</b><span>${escapeHtml(summary)}</span></div><div class="metric-grid">${metricCell('HOST', sys.hostname||'n/a', (sys.ips||[]).find(ip=>ip.startsWith('100.'))||(sys.ips||[])[0]||'no ip')}${metricCell('UPTIME', uptimeText(sys.uptime_s), sys.load||'load n/a')}${metricCell('THERMAL', cpu?`${cpuF.toFixed(1)}°F`:'n/a', 'CPU package')}${metricCell('FAN', fan.available?`${fan.rpm||0} RPM`:'n/a', fan.available?`state ${fan.cooling_state ?? '?'} / ${fan.cooling_max ?? '?'}`:'')}</div>${liveWave('CPU TEMP', cpuHist, `${cpu?cpuF.toFixed(1):'n/a'}°F`, cpu>=75?'var(--red)':cpu>=65?'var(--yellow)':'var(--green)')}${liveWave('RAM PRESSURE', ramHist, mem.text||'n/a', ram>=85?'var(--red)':'var(--cyan)')}${liveWave('DISK PRESSURE', diskHist, disk+'%', disk>=90?'var(--red)':disk>=80?'var(--yellow)':'var(--green)')}${liveWave('LOAD AVG', loadHist, sys.load||'n/a', loadPct>=80?'var(--red)':loadPct>=55?'var(--yellow)':'var(--purple)')}${liveWave('NET RX/TX PULSE', rxHist.map((v,i)=>Math.max(v, txHist[i]||0)), `↓${bytesPerSec(net.rx_bps)} ↑${bytesPerSec(net.tx_bps)}`, 'var(--blue)')}`;
  document.getElementById('system').textContent=[line('host',sys.hostname),line('ip',(sys.ips||[]).find(ip=>ip.startsWith('100.'))||(sys.ips||[])[0]||'n/a'),line('up',uptimeText(sys.uptime_s))].join('\n');
}
function renderSystemMonitor(sys={}, baseServices={}, controls={}){
  const el=document.getElementById('systemMonitorViz'); if(!el) return;
  const cpu=sys.cpu_live||{}, mem=sys.memory||{}, net=sys.net_io||{}, fan=sys.fan||{};
  const load1=Number(String(sys.load||'0').split(' ')[0])||0;
  const cores=Number(cpu.cores||navigator.hardwareConcurrency||4);
  const cpuPct=cpu.percent!=null?Number(cpu.percent):Math.min(100,(load1/Math.max(1,cores))*100);
  const ramPct=Number(mem.percent||0), diskPct=diskPercent(sys.disk_root), tempF=Number(sys.cpu_temp_f||0);
  const memSummary=`${mem.used_mb??'?'} MB used / ${mem.total_mb??'?'} MB total // ${mem.available_mb??'?'} MB available // ${ramPct}%`;
  const swapSummary=`${mem.swap_used_mb??0} MB used / ${mem.swap_total_mb??0} MB total // ${mem.swap_free_mb??0} MB free // ${mem.swap_percent??0}%`;
  const diskRows=(sys.disk_all||[]).map(d=>{ const pct=Number(String(d.use_percent||'0').replace('%',''))||0; return `<tr><td>${escapeHtml(d.mount)}</td><td>${escapeHtml(d.used)} / ${escapeHtml(d.size)}</td><td>${escapeHtml(d.avail)}</td><td>${miniGauge('use', pct, d.use_percent, pct>=90?'danger':pct>=80?'warn':'')}</td></tr>`; }).join('') || `<tr><td>/</td><td>${escapeHtml(diskShort(sys.disk_root))}</td><td>n/a</td><td>${diskPct}%</td></tr>`;
  const procRows=(sys.top_processes||[]).slice(0,10).map(p=>`<tr><td>${escapeHtml(p.pid)}</td><td>${escapeHtml(p.command)}</td><td>${miniGauge('cpu', Number(p.cpu||0), `${p.cpu}%`, Number(p.cpu||0)>60?'warn':'')}</td><td>${escapeHtml(p.memory)}%</td></tr>`).join('') || '<tr><td colspan="4">process snapshot unavailable</td></tr>';
  const runRows=(sys.running_services||[]).slice(0,18).map(s=>`<tr><td><span class="dot on"></span></td><td>${escapeHtml(s.unit)}</td><td>${escapeHtml(s.description||'running')}</td></tr>`).join('');
  const ifaceRows=Object.entries(net.rates||{}).map(([name,r])=>{ const totals=net.interfaces?.[name]||{}; return `<tr><td>${escapeHtml(name)}</td><td>↓ ${bytesPerSec(r.rx_bps)} <small>${bytesFmt(totals.rx_bytes)} total</small></td><td>↑ ${bytesPerSec(r.tx_bps)} <small>${bytesFmt(totals.tx_bytes)} total</small></td></tr>`; }).join('') || '<tr><td colspan="3">warming network counters</td></tr>';
  const resourceRows=`<tr><td>Memory</td><td>${escapeHtml(memSummary)}</td></tr><tr><td>Free / cache</td><td>${mem.free_mb??'?'} MB free // ${mem.cached_mb??'?'} MB cache // ${mem.buffers_mb??'?'} MB buffers</td></tr><tr><td>Swap</td><td>${escapeHtml(swapSummary)}</td></tr><tr><td>CPU load</td><td>${cpuPct.toFixed(1)}% live // load ${escapeHtml(sys.load||'n/a')} // ${cpu.load_percent_1m??'?'}% of ${cores} cores</td></tr><tr><td>CPU temp</td><td>${sys.cpu_temp_f??'?'}°F</td></tr><tr><td>Fan</td><td>${fan.available?`${fan.rpm||0} RPM // state ${fan.cooling_state ?? '?'} of ${fan.cooling_max ?? '?'}`:'n/a'}</td></tr>`;
  const health=cpuPct>=85||ramPct>=85||diskPct>=90||tempF>=167?'RED':cpuPct>=60||ramPct>=70||diskPct>=80||tempF>=149?'AMBER':'GREEN';
  const detail=[line('host',sys.hostname),line('ip',(sys.ips||[]).join(' ')),line('uptime',uptimeText(sys.uptime_s)),line('cpu model',cpu.model||'n/a'),line('cpu freq/governor',`${cpu.freq_mhz?cpu.freq_mhz+' MHz':'n/a'} / ${cpu.governor||'n/a'}`),line('throttle',cpu.throttle?.flags?.length?cpu.throttle.flags.join(', '):(cpu.throttle?.raw||'ok'))].join('\n');
  el.innerHTML=`<div class="sec-summary ${health.toLowerCase()}"><b>LIVE HOST HEALTH ${health}</b><span>cheap /proc telemetry // no heavy collectors // refreshed ${new Date().toLocaleTimeString()}</span></div><div class="metric-grid">${metricCell('CPU', `${cpuPct.toFixed(1)}%`, `${cores} cores // ${cpu.freq_mhz?cpu.freq_mhz+' MHz':'freq n/a'}`, cpuPct>=85?'danger':cpuPct>=60?'warn':'')}${metricCell('MEMORY', `${ramPct}%`, memSummary, ramPct>=85?'danger':ramPct>=70?'warn':'')}${metricCell('DISK', `${diskPct}%`, diskShort(sys.disk_root), diskPct>=90?'danger':diskPct>=80?'warn':'')}${metricCell('NETWORK', `↓${bytesPerSec(net.rx_bps)}`, `↑${bytesPerSec(net.tx_bps)}`)}</div><div class="monitor-hero"><div>${liveWave('CPU USAGE', pushHist(cpuHist,cpuPct), `${cpuPct.toFixed(1)}% of ${cores} cores`, cpuPct>=85?'var(--red)':cpuPct>=60?'var(--yellow)':'var(--green)')}</div><div>${liveWave('MEMORY', pushHist(ramHist,ramPct), memSummary, ramPct>=85?'var(--red)':'var(--cyan)')}</div><div>${liveWave('DOWNLOAD', pushHist(rxHist,Math.min((net.rx_bps||0)/1048576*100,100)), `${bytesPerSec(net.rx_bps)} now`, 'var(--blue)')}</div><div>${liveWave('UPLOAD', pushHist(txHist,Math.min((net.tx_bps||0)/1048576*100,100)), `${bytesPerSec(net.tx_bps)} now`, 'var(--purple)')}</div></div><div class="monitor-grid sec-table-grid"><section><h3>Resource Details</h3><table class="mini-table sec-table"><tbody>${resourceRows}</tbody></table></section><section><h3>Network Speeds</h3><table class="mini-table sec-table"><tbody>${ifaceRows}</tbody></table></section><section><h3>Disk</h3><table class="mini-table sec-table"><thead><tr><th>Mount</th><th>Used / Total</th><th>Free</th><th>Use</th></tr></thead><tbody>${diskRows}</tbody></table></section><section><h3>Top Processes</h3><table class="mini-table sec-table"><thead><tr><th>PID</th><th>Command</th><th>CPU</th><th>Mem</th></tr></thead><tbody>${procRows}</tbody></table></section><section><h3>Running Services</h3><table class="mini-table sec-table"><tbody>${runRows||'<tr><td>running service list unavailable</td></tr>'}</tbody></table></section><section><h3>System Details</h3><pre>${escapeHtml(detail)}</pre></section></div>`;
}

function renderHackerDeck(s){
  const el=document.getElementById('hackerViz'); if(!el) return;
  const wifi=s.wifi||{}, lan=s.lan||{}, bt=s.bluetooth||{}, sys=s.system||{}, controls=s.controls||{}, vpn=s.vpn||{}, vision=s.vision||{}, mem=s.device_memory||{};
  const newCount=(wifi.new||[]).length+(lan.new||[]).length+(bt.new||[]).length;
  const services=Object.values({...s.services,...controls}).filter(v=>v&&typeof v==='object');
  const activeSvc=services.filter(v=>v.active).length;
  const tailIp=(sys.ips||[]).find(ip=>ip.startsWith('100.'));
  const heat=Number(sys.cpu_temp_c||0)>=75?35:Number(sys.cpu_temp_c||0)>=65?18:0;
  const threat=clamp(newCount*18 + (vpn.active?0:8) + (vision.enabled?4:0) + heat);
  const reason = [`mood=${s.mood?.name||'n/a'}`, newCount?`${newCount} new contact(s)`:'no new contacts', vpn.active?'vpn cloaked':'vpn open-ish', vision.enabled?'vision armed':'vision off', heat?`heat +${heat}`:'thermals ok'].join(' // ');
  const deckRows=[
    ['TAILNET', tailIp?'LINKED':'LOCAL'], ['VPN', vpn.active?'CLOAKED':(vpn.gui_running?'APP OPEN':'OFF')],
    ['NEW CONTACTS', newCount], ['MEMORY', `${mem.total_known||0} known / ${mem.total_new||0} new`],
    ['WIFI/LAN/BT', `${(wifi.networks||[]).length}/${(lan.devices||[]).length}/${(bt.devices||[]).length}`],
    ['SERVICES', `${activeSvc}/${services.length} UP`], ['VISION', vision.enabled?'ARMED':'OFF']
  ];
  const recon = lastRecon ? `<div class="recon-box"><b>LAST ACTIVE RECON</b><span>${lastRecon.ok?'OK':'FAIL'} ${lastRecon.scope||''} // hosts ${lastRecon.host_count??0} // ${lastRecon.duration_s||0}s</span>${(lastRecon.hosts||[]).slice(0,5).map(h=>`<small>${h.ip} ${h.open_ports?.length?'ports '+h.open_ports.join(','):''} ${h.hostname||h.vendor||''}</small>`).join('')}</div>` : '<div class="recon-box"><b>LAST ACTIVE RECON</b><span>not run this session</span></div>';
  const logs = (s.log_tail||[]).slice(-4).map(x=>`<small>${cleanText(x)}</small>`).join('') || '<small>log visor quiet</small>';
  el.innerHTML = `${liveWave('THREAT / MISCHIEF', [0,8,5,12,threat/2,threat], `${threat}%`, threat>65?'var(--red)':threat>35?'var(--yellow)':'var(--purple)')}<div class="mood-reason">${reason}</div><table class="mini-table deck-table"><tbody>${deckRows.map(([k,v])=>`<tr><td>${k}</td><td>${v}</td></tr>`).join('')}</tbody></table>${recon}<div class="log-visor"><b>LOG VISOR</b>${logs}</div><div class="scanline-note">authorized active local recon only // no deauth // no exploit // no dumb illegal shit</div>`;
}
function renderWifi(wifi){
  const sig=Number(wifi.current?.signal||0), nets=(wifi.networks||[]);
  if(selectedWifiSsid && !nets.some(n=>n.ssid===selectedWifiSsid)) selectedWifiSsid='';
  const chosen=nets.find(n=>n.ssid===selectedWifiSsid) || wifi.current || nets[0] || null;
  if(chosen && !selectedWifiSsid) selectedWifiSsid=chosen.ssid;
  const rows=nets.slice(0,18).map(n=>`<button class="wifi-target-row ${n.ssid===selectedWifiSsid?'selected':''} ${n.connected?'connected':''}" onclick="selectWifiTarget(decodeURIComponent('${encodeURIComponent(n.ssid)}'))"><span>${n.connected?'●':'○'} ${escapeHtml(n.ssid||'<hidden>')}</span><b>${signalBars(Number(n.signal||0))}</b><em>ch ${escapeHtml(n.channel||'?')} // ${escapeHtml(n.security||'unknown')}</em></button>`).join('') || '<div class="scanline-note">No Wi-Fi networks found. Hit Wi-Fi Scan.</div>';
  const actionText=lastWifiAction?`<div class="scanline-note">${escapeHtml(lastWifiAction.message||lastWifiAction.error||'action complete')} ${(lastWifiAction.findings||[]).slice(0,4).map(escapeHtml).join(' // ')}</div>`:'';
  const chosenBox=chosen?`<div class="wifi-selected"><h3>Selected Target</h3><b>${escapeHtml(chosen.ssid)}</b><span>${chosen.connected?'connected':'nearby'} // signal ${chosen.signal||0}% // ch ${escapeHtml(chosen.channel||'?')} // ${escapeHtml(chosen.security||'unknown')}</span><div class="wifi-target-actions"><button onclick="wifiTargetAction('remember')">Add to Known</button><button onclick="wifiTargetAction('trust')">Trust</button><button onclick="wifiTargetAction('watch')">Watch</button><button onclick="wifiTargetName()">Name</button><button onclick="wifiTargetAction('audit')">Safe Audit</button><button onclick="wifiTargetAction('connect-plan')">Connect Plan</button></div>${actionText}</div>`:'<div class="wifi-selected"><h3>Selected Target</h3><span>Select a network to unlock actions.</span></div>';
  document.getElementById('wifiViz').innerHTML = `<div class="wifi-signal-card"><div><span>CURRENT SIGNAL</span><b>${wifi.current?escapeHtml(wifi.current.ssid):'offline'}</b></div>${signalBars(sig)}</div>${statPill('NETWORKS',(wifi.networks||[]).length)}${statPill('NEW',(wifi.new||[]).length)}<div class="wifi-target-layout"><div class="wifi-target-list">${rows}</div>${chosenBox}</div>`;
  document.getElementById('wifi').textContent=[line('connected',yes(wifi.connected)),line('current',wifi.current?wifi.current.ssid+' '+wifi.current.signal:'none'),line('selected',selectedWifiSsid||'none')].join('\n');
}
function selectWifiTarget(ssid){ selectedWifiSsid=ssid; localStorage.setItem('spac3SelectedWifiSsid', ssid); renderWifi(lastStatus?.wifi||{}); }
async function wifiTargetAction(action){
  if(!selectedWifiSsid){ alert('Select a Wi-Fi network first.'); return; }
  if(action==='connect-plan' && !confirm('Create a safe connection plan only? This will not auto-connect or reveal/use passwords.')) return;
  const d=await postJson('/api/wifi/target/action',{ssid:selectedWifiSsid, action});
  lastWifiAction=d;
  if(!d.ok) alert(d.error||'Wi-Fi action failed');
  await refresh();
}
function wifiTargetName(){ const label=prompt('Friendly name for this Wi-Fi target:', selectedWifiSsid); if(label!==null) postJson('/api/wifi/target/action',{ssid:selectedWifiSsid, action:'name', label}).then(d=>{ lastWifiAction=d; return refresh(); }); }
function renderWifiVault(data){
  const el=document.getElementById('wifiVaultViz'); if(!el) return;
  if(!wifiVaultVisible){ el.innerHTML='<div class="scanline-note">Wi-Fi Vault hidden. Hit Wi-Fi Vault to load saved profiles. Passwords stay masked until you flip the reveal switch.</div>'; return; }
  const rows=(data.networks||[]).map((n,i)=>{
    const ssid=escapeHtml(n.ssid||n.name||`network-${i+1}`);
    const value=n.password?escapeHtml(n.password):'••••••••';
    const shown=wifiPasswordsRevealed && n.password;
    return `<tr><td>${ssid}</td><td>${n.has_password?'saved':'none'}</td><td><span class="wifi-pass ${shown?'revealed':'masked'}">${shown?value:'••••••••'}</span></td></tr>`;
  }).join('') || '<tr><td colspan="3">no saved Wi-Fi profiles</td></tr>';
  el.innerHTML = `<div class="wifi-vault-toolbar"><label class="toggle-switch"><input type="checkbox" ${wifiPasswordsRevealed?'checked':''} onchange="toggleWifiPasswords(this.checked)"><span></span><b>${wifiPasswordsRevealed?'Passwords visible':'Passwords hidden'}</b></label></div><table class="mini-table"><thead><tr><th>SSID</th><th>Password</th><th>Value</th></tr></thead><tbody>${rows}</tbody></table><div class="scanline-note">Known Network Vault shown. Use the switch to reveal/hide values on this screen.</div>`;
}
async function toggleWifiPasswords(show){
  wifiPasswordsRevealed=!!show;
  if(wifiVaultVisible){
    try{
      const r=await fetch(`/api/wifi/passwords${wifiPasswordsRevealed?'?reveal=1':''}`,{cache:'no-store'});
      wifiVaultData=await r.json();
    }catch(e){}
  }
  renderWifiVault(wifiVaultData||{networks:[]});
}
async function loadWifiVault(){
  wifiVaultVisible=!wifiVaultVisible;
  setButton('wifiVaultButton',wifiVaultVisible?'Hide Wi-Fi Vault':'Wi-Fi Vault',wifiVaultVisible,true);
  if(!wifiVaultVisible){ renderWifiVault(wifiVaultData||{networks:[]}); return; }
  setBusy('wifiVaultButton',true,'Loading vault...');
  try { const r=await fetch(`/api/wifi/passwords${wifiPasswordsRevealed?'?reveal=1':''}`,{cache:'no-store'}); wifiVaultData=await r.json(); renderWifiVault(wifiVaultData); }
  catch(err){ const el=document.getElementById('wifiVaultViz'); if(el) el.innerHTML=`<div class="scanline-note">vault error: ${err}</div>`; }
  setBusy('wifiVaultButton',false); setButton('wifiVaultButton','Hide Wi-Fi Vault',true,true);
}
function renderRFAudit(audit, recs=[]){
  const el=document.getElementById('rfAuditViz'); if(!el) return;
  const wifi=audit.wifi||{}, bt=audit.bluetooth||{}, adapter=wifi.adapter||{}, current=wifi.current||{};
  const setup=adapter.monitor_setup||wifi.pwnagotchi?.monitor_setup||{};
  const warnings=(wifi.security_warnings||[]).slice(0,4);
  const saved=(wifi.saved_networks||[]).slice(0,4);
  const modes=(adapter.modes||[]).slice(0,5).join(', ')||'driver/airmon-ng';
  const warnRows=warnings.length ? warnings.map(w=>`<small><b>${w.ssid||'<hidden>'}</b> ch ${w.channel||'?'} // ${w.issues.join(', ')}</small>`).join('') : '<small>no weak nearby configs flagged</small>';
  const savedRows=saved.length ? saved.map(n=>{ const weak=Number(n.password_strength?.score||0)<55 && n.has_password; const enc=encodeURIComponent(n.ssid||n.name||''); return `<tr><td>${escapeHtml(n.ssid)}</td><td>${escapeHtml(n.security||'unknown')}</td><td>${n.has_password?(n.password_strength?.label||'n/a')+' '+(n.password_strength?.score??0)+'%':'hidden/unavailable'}</td><td>${weak?`<button class="mini-btn" onclick="wifiPskAction(decodeURIComponent('${enc}'),'generate')">Generate Fix</button><button class="mini-btn" onclick="wifiPskAction(decodeURIComponent('${enc}'),'review')">Mark Reviewed</button><button class="mini-btn danger" onclick="wifiPskAction(decodeURIComponent('${enc}'),'forget')">Forget</button>`:'ok'}</td></tr>`; }).join('') : '<tr><td colspan="4">no saved Wi-Fi profiles</td></tr>';
  const btWarn=(bt.warnings||[]).length ? bt.warnings.join(', ') : 'not discoverable/pairable';
  const pwn=wifi.pwnagotchi||{}, cap=pwn.handshake_capture||{};
  const pwnChannelRows=(pwn.channel_plan||[]).slice(0,8).map(c=>`<tr><td>${c.channel}</td><td>${c.aps}</td><td>${c.max_signal||0}%</td><td>${(c.ssids||[]).map(escapeHtml).join(', ')}</td></tr>`).join('') || '<tr><td colspan="4">no channel plan yet</td></tr>';
  const monitorIfaces=(adapter.interfaces||[]).filter(i=>i.type==='monitor').map(i=>i.name);
  const ifaceSummary=(adapter.interfaces||[]).map(i=>`${i.name}:${i.type||'?'}${i.driver?'/'+i.driver:''}`).join(', ')||'n/a';
  const external=(adapter.external_adapters||[]).join(', ')||'none';
  const monitorAction=monitorIfaces.length
    ? `<button class="mini-btn" onclick="startOwnedLabCapture()">Owned-Lab Passive Capture</button><button class="mini-btn" onclick="stopMonitorAdapter()">Stop Monitor</button>`
    : `<button class="mini-btn" onclick="prepMonitorAdapter()" ${setup.can_enable?'':'disabled title="No safe USB monitor adapter ready"'}>Prep ${escapeHtml(setup.preferred_interface||'USB')} Monitor</button>`;
  el.innerHTML = `<div class="rf-banner"><b>OWNED RF AUDIT</b><span>USB dongle wired: ${escapeHtml(setup.ready_label||'checking adapter')} // wlan0 protected.</span></div><div class="rf-grid"><div class="rf-tile"><span>CURRENT AP</span><b>${escapeHtml(current.ssid||'offline')}</b><small>${escapeHtml(current.security||'unknown')} // ch ${escapeHtml(current.channel||'?')} // ${current.signal||0}%</small></div><div class="rf-tile"><span>USB DONGLE</span><b>${escapeHtml(setup.preferred_interface||external||'not selected')}</b><small>${escapeHtml(setup.preferred_driver||'driver n/a')} // external ${escapeHtml(external)} // hint ${escapeHtml(setup.monitor_interface_hint||'wlan1mon')}</small></div><div class="rf-tile"><span>MONITOR MODE</span><b>${monitorIfaces.length?'live':'available on demand'}</b><small>${escapeHtml(modes)} // active ${escapeHtml(monitorIfaces.join(', ')||'none')}</small></div><div class="rf-tile"><span>BT SURFACE</span><b>${bt.powered?'powered':'off'}</b><small>${bt.devices_seen||0} devices // ${escapeHtml(btWarn)}</small></div><div class="rf-tile"><span>SAFE MODE</span><b>audit only</b><small>${escapeHtml(audit.kali_requested||audit.mode||'')}</small></div></div><div class="recon-box pwn-deck"><b>PWNAGOTCHI RF DECK</b><small>${escapeHtml(pwn.pattern||'Channel planning and owned-lab capture readiness.')}</small><table class="mini-table"><thead><tr><th>Ch</th><th>APs</th><th>Peak</th><th>SSIDs</th></tr></thead><tbody>${pwnChannelRows}</tbody></table><div class="device-actions">${monitorAction}</div><small>Capture gate: ${cap.ok?'ready':escapeHtml(cap.error||setup.ready_label||'waiting for explicit lab gate')}</small><small>Interfaces: ${escapeHtml(ifaceSummary)}</small><small>${escapeHtml(setup.note||'')}</small></div><div class="recon-box"><b>WI-FI WARNINGS</b>${warnRows}</div><div class="recon-box"><b>WHAT TO FIX</b>${(recs||[]).slice(0,4).map(r=>`<small>${escapeHtml(r)}</small>`).join('')||'<small>nothing urgent. spooky but fine.</small>'}</div><details><summary>Saved Wi-Fi posture</summary><table class="mini-table"><tbody>${savedRows}</tbody></table></details>`;
}

function renderSensors(sens){
  const gps=sens.gps||{}, indoor=sens.indoor||{}, light=sens.light||{}, weather=sens.weather||{}, tilt=sens.tilt_event||{}, gpio=sens.gpio||{};
  const used=Number(gps.satellitesUsed||0), visible=Number(gps.satellitesVisible||0), fixed=!!gps.fixed;
  const sats=visible?Math.round((used/(visible||1))*100):0;
  const best=Number(gps.satelliteSignalBest||0), avg=Number(gps.satelliteSignalAvg||0);
  const signalPct=best?Math.min(100, Math.round((best/50)*100)):0;
  const skyPct=visible?Math.min(100, Math.round((used/Math.max(visible,1))*100)):0;
  const signalLabel=best?`${best.toFixed(0)} dB-Hz best // ${avg?avg.toFixed(0):'n/a'} avg // ${signalPct}% strength`:(visible?`${visible} satellite signal(s) seen // acquiring`:'no usable signal yet');
  const satGrid=satelliteStrengthGrid(gps.satellites||[]);
  const tempF=Number(indoor.tempF||0), humidity=Number(indoor.humidity||0), lux=Number(light.lux||0), wx=weatherIcon(weather.summary||'');
  pushHist(indoorTempHist, Math.min(tempF/110*100,100)); pushHist(humidityHist, humidity); pushHist(lightHist, Math.min(lux/400*100,100)); pushHist(gpsSatsHist, sats); pushHist(gpsSignalHist, best?signalPct:skyPct);
  const root=document.getElementById('sensorViz');
  if(!root.querySelector('.radar')){
    root.innerHTML = `<div class="sensor-top"><div class="radar canvas-driven"><i class="radar-pulse"></i><canvas class="gps-radar-canvas"></canvas><b class="gps-mode"></b><span class="gps-sats"></span></div><div id="weatherCard" class="weather"></div></div><div id="sensorWaves" class="viz-stack"></div>`;
  }
  const blipCount=fixed ? used : Math.min(visible, 12);
  const gpsCanvas=root.querySelector('.gps-radar-canvas');
  if(gpsCanvas) gpsCanvas.__gpsData={count:blipCount, sats:gps.satellites||[], fixed};
  root.querySelector('.radar')?.classList.toggle('gps-searching', !fixed && visible>0);
  root.querySelector('.gps-mode').textContent = gps.modeLabel||'NO FIX';
  root.querySelector('.gps-sats').textContent = `${used}/${visible}`;
  const weatherCard=root.querySelector('#weatherCard');
  weatherCard.className=`weather ${sensorTempClass(weather.tempF)}`;
  weatherCard.innerHTML=`<span class="weather-icon">${wx}</span><b>${weather.available?weather.summary:'weather n/a'}</b><em>${weather.available?weather.tempF+'°F':''}</em><small>${weather.available?`humidity ${weather.humidity ?? 'n/a'}% // wind ${weather.windMph ?? 'n/a'}mph`:''}</small><small>${weather.location||weather.source||''}</small>`;
  const gpsOps=`<div class="gps-ops-panel"><div class="sec-summary ${fixed?'green':'amber'}"><b>GPS OPS ${fixed?'LOCK':'ACQUIRE'}</b><span>${escapeHtml(signalLabel)} // trail ${(lastStatus?.gps_trail?.points||[]).length} point(s)</span></div><div class="metric-grid">${metricCell('MODE', gps.modeLabel||'NO FIX', fixed?'coordinates locked':'waiting')}${metricCell('SATELLITES', `${used}/${visible}`, `${sats}% used ratio`)}${metricCell('BEST SIGNAL', best?`${best.toFixed(0)} dB-Hz`:'n/a', avg?`${avg.toFixed(0)} avg`:'SKY warming')}${metricCell('POSITION', gps.lat&&gps.lon?`${Number(gps.lat).toFixed(5)}, ${Number(gps.lon).toFixed(5)}`:'no fix', gps.source||'gpsd')}</div></div>`;
  root.querySelector('#sensorWaves').innerHTML = `${gpsOps}${liveWave('GPS SATELLITE RATIO', gpsSatsHist, `${used}/${visible}`, sats? 'var(--green)' : 'var(--yellow)')}${liveWave('GPS SIGNAL TREND', gpsSignalHist, signalLabel, fixed?'var(--green)':'var(--yellow)')}${satGrid}${liveWave('INDOOR TEMP', indoorTempHist, indoor.available?`${tempF.toFixed(1)}°F`:'n/a', tempF>=88?'var(--red)':tempF>=78?'var(--yellow)':'var(--cyan)')}${liveWave('HUMIDITY', humidityHist, indoor.available?`${humidity.toFixed(0)}%`:'n/a', 'var(--blue)')}${liveWave('LIGHT', lightHist, light.available?`${lux} lux`:'n/a', lux>=250?'var(--yellow)':lux<=10?'var(--purple)':'var(--green)')}${tiltVisual(gpio, tilt)}`;
  document.getElementById('sensors').textContent=[line('lat/lon',gps.lat&&gps.lon?`${gps.lat}, ${gps.lon}`:'no fix'), line('gps signal', signalLabel), line('satellites', `${used}/${visible} used/visible`)].join('\n');
}
function renderGpsTrail(trail){
  const el=document.querySelector('#sensorWaves'); if(!el) return;
  const pts=(trail.points||[]).slice(-6);
  const line=pts.length?pts.map(p=>`<small>${eventTime(p.ts)} ${Number(p.lat).toFixed(5)}, ${Number(p.lon).toFixed(5)} // sats ${p.used||0}</small>`).join(''):'<small>no GPS trail yet</small>';
  el.insertAdjacentHTML('beforeend', `<div class="recon-box"><b>GPS TRAIL</b>${line}</div>`);
}
function renderServices(baseServices, controls){
  const merged={...baseServices,...controls}; delete merged.cached;
  const rows=Object.entries(merged).filter(([,v])=>v&&typeof v==='object').slice(0,8);
  document.getElementById('servicesViz').innerHTML = `<table class="mini-table service-table"><tbody>${rows.map(([k,v])=>`<tr><td><span class="dot ${v.active?'on':'off'}"></span></td><td>${k}</td><td>${v.active_text||v.state_label||'n/a'}</td><td>${v.enabled_text||''}</td></tr>`).join('')}</tbody></table>`;
  document.getElementById('services').textContent='';
}
function renderEvents(events){ document.getElementById('events').innerHTML=(events||[]).slice(0,7).map(e=>`<div class="event"><span class="etime">${eventTime(e.ts)}</span> <span class="kind">${e.kind}</span> ${cleanText(e.text)}</div>`).join('')||'<div class="event">no events</div>'; }
function renderPluginPanels(panels){ document.getElementById('pluginPanels').innerHTML=panels.map(p=>`<div class="panel compact-panel"><b>${p.title||'Plugin'}</b>${((p.lines||[])[0]||'')?`<span>${((p.lines||[])[0]||'').slice(0,42)}</span>`:''}</div>`).join('')||'<div class="panel compact-panel"><b>No active plugin panels.</b></div>'; }
function renderPluginSwitches(plugins){
  const el=document.getElementById('pluginSwitches'); if(!el) return;
  const items=(plugins||[]).map(p=>`<label class="plugin-card ${p.enabled?'enabled':'disabled'} ${p.loaded?'loaded':'not-loaded'}"><input type="checkbox" ${p.enabled?'checked':''} onchange="togglePlugin('${p.name}', this.checked)"><span><b>${p.name}</b><em>${p.loaded?'loaded':'not loaded'} // ${p.enabled?'enabled':'disabled'}</em><small>${p.description||''}</small></span></label>`).join('');
  el.innerHTML = items || '<div class="panel compact-panel"><b>No plugins found.</b></div>';
}
function renderControls(s){
  const vpn=s.vpn||{}, cam=s.vision||{}, controls=s.controls||{}, vnc=controls.vnc||{}, sync=controls.syncthing||{};

  setButton('vpnButton',vpn.button_label||'VPN',!!vpn.active,true);

  setButton('vncButton',`${vnc.button_label||'Toggle'} VNC`,!!vnc.active,true); setButton('syncthingButton',`${sync.button_label||'Toggle'} Sync`,!!sync.active,true);

  setButton('visionButton',cam.button_label||(cam.enabled?'Disarm Vision':'Arm Vision'),!!cam.enabled,true); setButton('visionButton2',cam.button_label||(cam.enabled?'Disarm Vision':'Arm Vision'),!!cam.enabled,true);
  setButton('reconButton','Aggro Recon',!!lastRecon?.ok,true);
  setButton('stealthButton',stealthMode?'Exit Stealth':'Stealth UI',stealthMode,true);
  applyProtonFx();
  setButton('soundButton',soundMode?'Sound On':'Sound Off',soundMode,true);
}
function renderVision(cam, history={}){
  const dets=cam.last_analysis?.detections||[];
  activeCameraFeed = localStorage.getItem('spac3ActiveCameraFeed') || cam.active_feed || activeCameraFeed || 'local';
  const feeds=cam.feeds||[];
  const feedButtons=document.getElementById('cameraFeedButtons');
  if(feedButtons){
    feedButtons.innerHTML=`<label class="feed-select-label">Camera <select id="visionCameraSelect" onchange="switchCameraFeed(this.value)">${feeds.map(f=>`<option value="${f.id}" ${f.id===activeCameraFeed?'selected':''}>${f.label||f.id}${f.available?'':' ⚠'}</option>`).join('')}</select></label>` + (feeds.map(f=>`<button class="${f.id===activeCameraFeed?'active':''} ${f.available?'':'offline'}" onclick="switchCameraFeed('${f.id}')">${f.label||f.id}${f.available?'':' ⚠'}</button>`).join('') || '<span class="scanline-note">no camera feeds configured</span>');
  }
  const feedLines=feeds.map(f=>`Feed ${f.label||f.id}: ${f.available?'ready':'not reachable/configured'} (${f.id})`).join('\n');
  document.getElementById('visionStatus').textContent=[line('Vision',cam.state_label||(cam.enabled?'ARMED':'OFF')),line('Active feed',activeCameraFeed),feedLines,line('Camera',cam.camera_available?'visible':'not visible'),line('USB camera',yes(cam.usb_camera_available)),line('Pi camera',yes(cam.pi_camera_available)),line('Device',cam.device||'/dev/video0'),line('AI backend',cam.ai_backend||'not_configured'),line('AI model',cam.ai_model||'none'),line('AI available',yes(cam.ai_available)),cam.ai_error?line('AI error',cam.ai_error):'',cam.message||''].filter(Boolean).join('\n');
  document.getElementById('visionDetections').textContent=dets.length?dets.map(d=>`${d.label} ${(d.confidence*100).toFixed(1)}% [${(d.xyxy||[]).join(', ')}]`).join('\n'):(cam.last_analysis?.error||'No YOLO detections yet. Hit Run YOLO Scan.');
  const histEl=document.getElementById('visionHistoryViz');
  if(histEl){
    const rows=(history.items||[]).slice(0,8).map(h=>`<div class="vision-history-row">${h.snapshot?`<img src="${h.snapshot}" alt="vision snapshot">`:''}<div><b>${eventTime(h.ts)}</b><small>${(h.labels||[]).join(', ')||'no detections'} // ${h.elapsed_s||0}s</small></div></div>`).join('') || '<div class="scanline-note">No YOLO scan history yet.</div>';
    histEl.innerHTML=rows;
  }
}
async function switchCameraFeed(feed){
  activeCameraFeed = feed || 'local';
  localStorage.setItem('spac3ActiveCameraFeed', activeCameraFeed);
  const pulse=document.getElementById('cameraPulse');
  if(pulse) pulse.textContent=`SWITCH ${activeCameraFeed}`;
  refreshCameraFrame(true);
  try { await postJson('/api/camera/feed', {feed: activeCameraFeed}); } catch(e) {}
  await refresh();
}
async function postJson(url, body){ const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined}); const data=await r.json(); if(!r.ok&&data.ok!==false)data.ok=false; return data; }
async function scan(kind){ await fetch(`/api/scan/${kind}`,{cache:'no-store'}); await refresh(); }
async function toggleVpn(){ setBusy('vpnButton',true,'Toggling...'); const d=await postJson('/api/vpn/toggle'); protonActionStatus=d.message||d.error||d.stderr||`VPN ${d.action||'toggle'}`; showAction('vpnControl',d); setBusy('vpnButton',false); await refresh(); }
async function toggleService(name){ const id=name==='syncthing'?'syncthingButton':`${name}Button`; setBusy(id,true,'Switching...'); const d=await postJson(`/api/services/${name}/toggle`); showAction('serviceControl',d); setBusy(id,false); await refresh(); }
async function toggleVision(){ const enabled=!(lastStatus?.vision?.enabled??currentConfig?.vision?.enabled); setBusy('visionButton',true,enabled?'Arming...':'Disarming...'); setBusy('visionButton2',true,enabled?'Arming...':'Disarming...'); const d=await postJson('/api/camera/vision',{enabled}); showAction('cameraControl',d); setBusy('visionButton',false); setBusy('visionButton2',false); cameraEnabled=null; refreshCameraFrame(true); await refresh(); }
async function analyzeVision(){ setBusy('analyzeButton',true,`Scanning ${activeCameraFeed}...`); const d=await postJson('/api/camera/analyze',{feed:activeCameraFeed}); document.getElementById('visionDetections').textContent=JSON.stringify(d,null,2); setBusy('analyzeButton',false); refreshCameraFrame(true); await refresh(); }
async function clearVisionHistory(){ if(!confirm('Delete captured Vision history and saved snapshot JPGs from this Pi?')) return; const d=await postJson('/api/vision/history/clear',{}); alert(d.ok?`Vision history cleared: ${d.removed_rows||0} rows / ${d.removed_snapshots||0} snapshots.`:(d.error||'Clear failed')); await refresh(); renderVision(lastStatus?.vision||{}, lastStatus?.vision_history||{}); }
async function calibrateTiltLevel(){ const d=await postJson('/api/sensors/tilt/calibrate',{}); alert(d.ok?d.message:(d.error||'Tilt calibration failed')); await pollTilt(); await refresh(); }

async function wifiPskAction(ssid, action){
  if(action==='forget' && !confirm(`Delete saved Wi-Fi profile for ${ssid}? This does not change the router; you will need to reconnect after fixing the password.`)) return;
  if(action==='generate' && !confirm(`Generate a strong replacement password for ${ssid}? You still need to change it in the router/AP admin UI.`)) return;
  const d=await postJson('/api/wifi/psk/action',{ssid,action});
  if(d.password){
    try{ await navigator.clipboard.writeText(d.password); alert(`${d.message}\n\nGenerated password copied to clipboard.`); }
    catch(e){ alert(`${d.message}\n\nGenerated password: ${d.password}`); }
  } else {
    alert(d.ok?(d.message||'Wi-Fi PSK action complete'):(d.error||'Wi-Fi PSK action failed'));
  }
  await refresh();
}

async function prepMonitorAdapter(){
  const setup=lastStatus?.rf_audit?.wifi?.adapter?.monitor_setup||lastStatus?.rf_audit?.wifi?.pwnagotchi?.monitor_setup||{};
  const iface=setup.preferred_interface||'wlan1';
  if(!confirm(`Prep ${iface} for monitor mode? wlan0 stays connected; no deauth, no injection, no cracking.`)) return;
  const d=await postJson('/api/pwnagotchi/capture',{action:'prep-monitor',interface:iface});
  alert(d.ok?(d.message||'Monitor mode ready'):`Monitor prep failed: ${d.error||'unknown error'}`);
  await refresh();
}
async function stopMonitorAdapter(){
  const setup=lastStatus?.rf_audit?.wifi?.adapter?.monitor_setup||lastStatus?.rf_audit?.wifi?.pwnagotchi?.monitor_setup||{};
  const iface=(setup.monitor_interfaces||[])[0]||setup.monitor_interface_hint||'wlan1mon';
  if(!confirm(`Stop monitor mode on ${iface}?`)) return;
  const d=await postJson('/api/pwnagotchi/capture',{action:'stop-monitor',interface:iface});
  alert(d.ok?(d.message||'Monitor mode stopped'):`Monitor stop failed: ${d.error||'unknown error'}`);
  await refresh();
}
async function startOwnedLabCapture(){
  const adapter=lastStatus?.rf_audit?.wifi?.adapter||{};
  const setup=adapter.monitor_setup||lastStatus?.rf_audit?.wifi?.pwnagotchi?.monitor_setup||{};
  let monitors=(adapter.interfaces||[]).filter(i=>i.type==='monitor').map(i=>i.name);
  if(!monitors.length && setup.can_enable){
    if(!confirm(`No monitor interface is active yet. Prep ${setup.preferred_interface||'wlan1'} for monitor mode first? wlan0 stays connected.`)) return;
    const prep=await postJson('/api/pwnagotchi/capture',{action:'prep-monitor',interface:setup.preferred_interface||'wlan1'});
    if(!prep.ok){ alert(`Monitor prep failed: ${prep.error||'unknown error'}`); await refresh(); return; }
    await refresh();
    monitors=(lastStatus?.rf_audit?.wifi?.adapter?.interfaces||[]).filter(i=>i.type==='monitor').map(i=>i.name);
  }
  const iface=prompt('Monitor interface for owned-lab capture:', monitors[0]||setup.monitor_interface_hint||'wlan1mon');
  if(!iface) return;
  const bssid=prompt('Owned lab AP BSSID (blank for any AP seen by monitor):','');
  if(bssid===null) return;
  const channel=prompt('Channel (blank for all):', lastStatus?.rf_audit?.wifi?.current?.channel||'');
  if(channel===null) return;
  if(!confirm('Confirm this is your owned/authorized lab network. Passive capture only: no deauth, no cracking.')) return;
  const d=await postJson('/api/pwnagotchi/capture',{owned_lab:true,interface:iface,bssid,channel});
  alert(d.ok?`Capture started pid ${d.pid}`:`Capture refused: ${d.error||'unknown error'}`);
  await refresh();
}
async function aggressiveRecon(){ setBusy('reconButton',true,'Sweeping LAN...'); const d=await postJson('/api/recon/aggressive'); lastRecon=d; setBusy('reconButton',false); await refresh(); }
function toggleStealth(){ stealthMode=!stealthMode; document.body.classList.toggle('stealth-mode', stealthMode); setButton('stealthButton',stealthMode?'Exit Stealth':'Stealth UI',stealthMode,true); }
function toggleSound(){ soundMode=!soundMode; if(soundMode){ try{ audioCtx=audioCtx||new (window.AudioContext||window.webkitAudioContext)(); audioCtx.resume?.(); }catch(e){} beep(660,.08,'sine'); setTimeout(()=>beep(880,.08,'sine'),90); } setButton('soundButton',soundMode?'Sound On':'Sound Off',soundMode,true); }
function readSettingsJson(){
  const sj=document.getElementById('settingsJson');
  return sj?.value?.trim()?JSON.parse(sj.value):structuredClone(currentConfig||{});
}
function writeSettingsJson(config){
  currentConfig=config||{};
  const sj=document.getElementById('settingsJson'); if(sj) sj.value=JSON.stringify(currentConfig,null,2);
}
function linesFromSetting(value){
  if(Array.isArray(value)) return value.map(String).join('\n');
  if(typeof value==='string') return value;
  return '';
}
function settingFromLines(text){
  const lines=String(text||'').split(/\r?\n/).map(x=>x.trim()).filter(Boolean);
  return lines.length<=1 ? (lines[0]||'') : lines;
}
function syncFaceSetting(encodedKey, value){
  try{
    const key=decodeURIComponent(encodedKey), cfg=readSettingsJson();
    cfg.faces=cfg.faces||{}; cfg.faces[key]=settingFromLines(value);
    writeSettingsJson(cfg);
    document.getElementById('settingsStatus').textContent=`Face ${key} updated in JSON. Hit Save Settings to persist.`;
  }catch(err){ document.getElementById('settingsStatus').textContent=`Face edit failed: ${err}`; }
}
function syncMoodSetting(encodedKey, value){
  try{
    const key=decodeURIComponent(encodedKey), cfg=readSettingsJson();
    cfg.mood=cfg.mood||{};
    const n=Number(value); cfg.mood[key]=Number.isFinite(n)?n:value;
    writeSettingsJson(cfg);
    document.getElementById('settingsStatus').textContent=`Mood ${key} updated in JSON. Hit Save Settings to persist.`;
  }catch(err){ document.getElementById('settingsStatus').textContent=`Mood edit failed: ${err}`; }
}
function syncPhraseSetting(encodedKey, value){
  try{
    const key=decodeURIComponent(encodedKey), cfg=readSettingsJson();
    cfg.phrases=cfg.phrases||{}; cfg.phrases[key]=String(value||'').split(/\r?\n/).map(x=>x.trim()).filter(Boolean);
    writeSettingsJson(cfg);
    document.getElementById('settingsStatus').textContent=`Phrase bank ${key} updated in JSON. Hit Save Settings to persist.`;
  }catch(err){ document.getElementById('settingsStatus').textContent=`Phrase edit failed: ${err}`; }
}
function addMissingFacesToSettings(){
  try{
    const cfg=readSettingsJson(); cfg.faces=cfg.faces||{};
    const merged=lastStatus?.faces||{}; let added=0;
    Object.entries(merged).sort(([a],[b])=>a.localeCompare(b)).forEach(([k,v])=>{
      const key=String(k).toLowerCase();
      if(cfg.faces[key] === undefined && cfg.faces[k] === undefined && (Array.isArray(v) || typeof v==='string')){ cfg.faces[key]=v; added++; }
    });
    writeSettingsJson(cfg); renderFaceMoodSettings(cfg, merged);
    document.getElementById('settingsStatus').textContent=added?`Added ${added} missing built-in face mood(s) to JSON. Hit Save Settings to persist.`:'No missing built-in faces found.';
  }catch(err){ document.getElementById('settingsStatus').textContent=`Add faces failed: ${err}`; }
}
function renderFaceMoodSettings(config=currentConfig||{}, mergedFaces=lastStatus?.faces||{}){
  const el=document.getElementById('faceMoodSettings'); if(!el) return;
  const cfgFaces=config.faces||{};
  const faceKeys=[...new Set([...Object.keys(cfgFaces), ...Object.keys(mergedFaces).map(k=>k.toLowerCase())])].sort((a,b)=>a.localeCompare(b));
  const moodEntries=Object.entries(config.mood||{}).sort(([a],[b])=>a.localeCompare(b));
  const phraseKeys=Object.keys(config.phrases||{}).filter(k=>['alert','bluetooth_chatter','bright','camera','chatter','cold','dark','gps_fix','gps_no_fix','hot','idle','located','rain','scanning','storm','vpn','warm','wind'].includes(k) || (config.faces||{})[k]).sort();
  const faceCards=faceKeys.map(key=>{
    const own=cfgFaces[key]!==undefined?cfgFaces[key]:cfgFaces[key.toUpperCase()];
    const built=mergedFaces[key]!==undefined?mergedFaces[key]:mergedFaces[key.toUpperCase()];
    const value=own!==undefined?own:built;
    const count=Array.isArray(value)?value.length:(value?1:0);
    return `<label class="face-editor"><span><b>${escapeHtml(key)}</b><em>${count} face${count===1?'':'s'} ${own!==undefined?'// settings':'// built-in'}</em></span><textarea rows="${Math.min(Math.max(count,2),7)}" spellcheck="false" oninput="syncFaceSetting('${encodeURIComponent(key)}', this.value)">${escapeHtml(linesFromSetting(value))}</textarea></label>`;
  }).join('') || '<div class="scanline-note">No faces configured.</div>';
  const moodInputs=moodEntries.map(([key,value])=>`<label class="mood-editor"><span>${escapeHtml(key)}</span><input type="number" step="any" value="${escapeHtml(String(value))}" oninput="syncMoodSetting('${encodeURIComponent(key)}', this.value)"></label>`).join('') || '<div class="scanline-note">No mood thresholds configured.</div>';
  const phraseEditors=phraseKeys.map(key=>`<label class="phrase-editor"><span>${escapeHtml(key)}</span><textarea rows="4" spellcheck="false" oninput="syncPhraseSetting('${encodeURIComponent(key)}', this.value)">${escapeHtml(linesFromSetting((config.phrases||{})[key]))}</textarea></label>`).join('') || '<div class="scanline-note">No mood phrase banks configured.</div>';
  el.innerHTML=`<details open><summary>Face packs / mood faces (${faceKeys.length})</summary><div class="face-editor-grid">${faceCards}</div></details><details open><summary>Mood thresholds + rules (${moodEntries.length})</summary><div class="mood-editor-grid">${moodInputs}</div></details><details><summary>Mood phrase banks (${phraseKeys.length})</summary><div class="phrase-editor-grid">${phraseEditors}</div></details>`;
}
async function loadSettings(){ const r=await fetch('/api/config',{cache:'no-store'}); const d=await r.json(); currentConfig=d.config; applyTheme(currentConfig.ui?.theme || localStorage.getItem('spac3Theme') || 'default'); setFacePack(currentConfig.ui?.face_pack || localStorage.getItem('spac3FacePack') || 'default'); writeSettingsJson(d.config); document.getElementById('settingsStatus').textContent='Settings loaded.'; renderPluginSwitches(d.plugins||[]); renderFaceMoodSettings(currentConfig, lastStatus?.faces||{}); }
async function saveSettings(){ try{ const config=readSettingsJson(); const d=await postJson('/api/config',{config}); document.getElementById('settingsStatus').textContent=d.ok?'Settings saved. Plugins reloaded.':`Save failed: ${d.error||'unknown'}`; if(d.ok) currentConfig=config; await refresh(); renderFaceMoodSettings(currentConfig, lastStatus?.faces||{}); }catch(err){ document.getElementById('settingsStatus').textContent=`Save failed: ${err}`; } }
async function togglePlugin(name, enabled){ if(!currentConfig) await loadSettings(); currentConfig.plugins=currentConfig.plugins||{}; currentConfig.plugins[name]=!!enabled; document.getElementById('settingsJson').value=JSON.stringify(currentConfig,null,2); const d=await postJson('/api/config',{config:currentConfig}); document.getElementById('pluginSwitches').classList.toggle('saving', false); if(!d.ok) alert(`Plugin save failed: ${d.error||'unknown'}`); await refresh(); }

document.title='Hack-Safe Spac3-Gh0st'; applyTheme(currentTheme); refreshAIChatStatus(); startPwnFaceCycle(); let initialTab=(location.hash||'#dash').slice(1); if(initialTab==='godseye') initialTab='vision'; if(['dash','deck','systems','signals','vision','externals','plugins','lab','settings'].includes(initialTab)) showTab(initialTab); refresh(); setInterval(refresh,15000); setInterval(pollTilt,3000); setInterval(refreshPwnFace,7000);
