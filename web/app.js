let currentConfig = null;
let lastStatus = null;
let busyButtons = new Set();
let cameraTimer = null;
let cameraEnabled = null;
let cameraInflight = false;
let activeCameraFeed = 'local';
let activeTab = 'dash';
let cpuHist = [], ramHist = [], diskHist = [], loadHist = [], indoorTempHist = [], humidityHist = [], lightHist = [], rxHist = [], txHist = [];
let lastRecon = null;
let stealthMode = false;
let wifiVaultVisible = false;
let wifiVaultData = null;
let soundMode = false;
let selectedExternal = 'bak3ry';
let protonFxEnabled = localStorage.getItem('protonFxEnabled') !== '0';
let audioCtx = null;
let lastAlertLevel = null;
let lastGpsFixed = null;
let tiltPollBusy = false;

function line(label, value) { return `${label}: ${value ?? 'n/a'}`; }
function yes(v) { return v ? 'yes' : 'no'; }
function clamp(n, a=0, b=100) { return Math.max(a, Math.min(b, Number(n) || 0)); }
function eventTime(ts) { return ts ? new Date(ts * 1000).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'}) : '--:--'; }
function uptimeText(seconds) { const s=Math.max(0,Number(seconds||0)); const d=Math.floor(s/86400), h=Math.floor((s%86400)/3600), m=Math.floor((s%3600)/60); return d?`${d}d ${h}h`:h?`${h}h ${m}m`:`${m}m`; }
function diskShort(dfLine) { const p=String(dfLine||'').trim().split(/\s+/); return p.length>=5 ? `${p[2]}/${p[1]} ${p[4]}` : (dfLine || 'n/a'); }
function diskPercent(dfLine) { const m=String(dfLine||'').match(/(\d+)%/); return m ? Number(m[1]) : 0; }
function weatherIcon(summary='') { const s=summary.toLowerCase(); if(s.includes('rain')) return '🌧'; if(s.includes('storm')||s.includes('thunder')) return '⛈'; if(s.includes('snow')) return '❄'; if(s.includes('cloud')) return '☁'; if(s.includes('fog')||s.includes('mist')) return '🌫'; if(s.includes('sun')||s.includes('clear')) return '☀'; return '◌'; }
function tempClass(c) { if(c == null || Number.isNaN(Number(c))) return 'temp-ok'; if(c >= 75) return 'temp-hot'; if(c >= 65) return 'temp-warm'; if(c <= 45) return 'temp-cool'; return 'temp-ok'; }
function sensorTempClass(f) { if(f == null || Number.isNaN(Number(f))) return 'temp-ok'; if(f >= 88) return 'temp-hot'; if(f >= 78) return 'temp-warm'; if(f <= 60) return 'temp-cool'; return 'temp-ok'; }
function spark(values) { const max=Math.max(...values,1), min=Math.min(...values,0); const chars='▁▂▃▄▅▆▇█'; return values.map(v=>chars[Math.round(((v-min)/(max-min||1))*(chars.length-1))]).join(''); }
function wavePath(values, w=260, h=58, lo=0, hi=100) {
  const list = values.length ? values : [0];
  const span = Math.max(1, hi - lo);
  return list.map((v,i) => {
    const x = list.length === 1 ? 0 : (i / (list.length - 1)) * w;
    const y = h - ((clamp(v, lo, hi) - lo) / span) * h;
    return `${i?'L':'M'}${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
}
function liveWave(label, values, value, color='var(--green)', lo=0, hi=100) {
  const path = wavePath(values, 260, 58, lo, hi);
  const fill = `${path} L260,58 L0,58 Z`;
  return `<div class="wave-card" style="--wave:${color}"><div class="wave-head"><span>${label}</span><b>${value}</b></div><svg class="wave" viewBox="0 0 260 58" preserveAspectRatio="none" aria-label="${label} live line graph"><path class="wave-fill" d="${fill}"></path><path class="wave-line" d="${path}"></path></svg></div>`;
}
function pushHist(arr, val, max=48){ arr.push(Number(val)||0); while(arr.length>max) arr.shift(); return arr; }
function bytesPerSec(n){ n=Number(n)||0; const u=['B/s','KB/s','MB/s','GB/s']; let i=0; while(n>=1024&&i<u.length-1){n/=1024;i++;} return `${n>=10?n.toFixed(0):n.toFixed(1)} ${u[i]}`; }
function signalBars(sig){ sig=clamp(sig); const level=sig>=80?4:sig>=55?3:sig>=30?2:sig>0?1:0; return `<div class="signal-bars" title="${sig}%">${[1,2,3,4].map(i=>`<i class="${i<=level?'on':''}" style="height:${7+i*5}px"></i>`).join('')}<b>${sig||0}%</b></div>`; }
function weatherTileXY(lat, lon, z=6){ lat=Number(lat); lon=Number(lon); if(!Number.isFinite(lat)||!Number.isFinite(lon)) return null; const n=2**z; const x=Math.floor((lon+180)/360*n); const rad=lat*Math.PI/180; const y=Math.floor((1-Math.log(Math.tan(rad)+1/Math.cos(rad))/Math.PI)/2*n); return {z,x,y}; }
function tiltVisual(gpio={}, tilt={}){ const label=String(gpio.tiltOrientation||gpio.tiltLabel||tilt.orientation||'UNKNOWN'); const raw=gpio.tiltRaw ?? gpio.tilt ?? tilt.raw; const angle=Number(gpio.tiltAngle ?? tilt.angle ?? (raw===0?0:raw===1?28:0)); const side=raw===0?'LEVEL':raw===1?'TILTED':'UNKNOWN'; return `<div id="tiltStage" class="tilt-stage ${tilt.changed?'shake':''}"><div id="tiltLabel" class="tilt-label">${label} // ${side}</div><div id="tiltBoard" class="tilt-board" style="transform:rotate(${angle}deg)"><span></span></div><div class="tilt-axis"><b>L</b><em></em><b>R</b></div><small id="tiltReadout">LIVE raw=${raw ?? 'n/a'} angle=${angle}° age=${tilt.age_s!=null?Number(tilt.age_s).toFixed(1)+'s':'n/a'}</small></div>`; }
function applyTilt(data={}){ const gpio=data.gpio||{}, tilt=data.tilt_event||{}; const raw=gpio.tiltRaw ?? gpio.tilt ?? tilt.raw; const angle=Number(gpio.tiltAngle ?? tilt.angle ?? (raw===0?0:raw===1?28:0)); const label=String(gpio.tiltOrientation||gpio.tiltLabel||tilt.orientation||'UNKNOWN'); const side=raw===0?'LEVEL':raw===1?'TILTED':'UNKNOWN'; const board=document.getElementById('tiltBoard'), lab=document.getElementById('tiltLabel'), read=document.getElementById('tiltReadout'), stage=document.getElementById('tiltStage'); if(board) board.style.transform=`rotate(${angle}deg)`; if(lab) lab.textContent=`${label} // ${side}`; if(read) read.textContent=`LIVE raw=${raw ?? 'n/a'} angle=${angle}° ${data.live?'fast GPIO':''}`; if(stage){ stage.classList.toggle('shake', !!tilt.changed); stage.classList.toggle('tilt-left', raw===1); stage.classList.toggle('tilt-right', false); } }
function gpsBlipHtml(used){
  const n=Math.max(0, Math.min(24, Number(used)||0));
  const pts=[];
  for(let i=0;i<n;i++){
    const a=(i*137.508)%360, r=20+((i*17)%27);
    const x=50+Math.cos(a*Math.PI/180)*r, y=50+Math.sin(a*Math.PI/180)*r;
    pts.push(`<i class="gps-blip" style="left:${x.toFixed(1)}%;top:${y.toFixed(1)}%;animation-delay:${((i%8)*0.18).toFixed(2)}s"></i>`);
  }
  return pts.join('');
}
function bar(label, pct, value, cls='') { pct=clamp(pct); return `<div class="bar-row ${cls}"><div class="bar-head"><span>${label}</span><b>${value}</b></div><div class="bar"><i style="width:${pct}%"></i></div></div>`; }
function statPill(label, value, cls='') { return `<div class="pill ${cls}"><span>${label}</span><b>${value}</b></div>`; }
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

function showTab(name) {
  activeTab = name;
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.toggle('active', p.id === `tab-${name}`));
  document.querySelectorAll('.tab-button').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
  if (name === 'settings' && !document.getElementById('settingsJson').value) loadSettings();
  if (name === 'vision') refreshCameraFrame(true);
  if (name === 'externals') renderExternals(lastStatus?.externals||{});
}
function setTicker(sys, wifi, sens, vpn, controls) {
  const gps=sens?.gps||{}, indoor=sens?.indoor||{}, mem=sys.memory||{};
  const tailIp=(sys.ips||[]).find(ip=>ip.startsWith('100.')) || 'no-tailnet';
  const items=[`HOST ${sys.hostname||'unknown'}`,`CPU ${sys.cpu_temp_f?sys.cpu_temp_f.toFixed(1)+'F':'n/a'}`,`LOAD ${sys.load||'n/a'}`,`RAM ${mem.text||'n/a'}`,`DISK ${diskShort(sys.disk_root)}`,`UP ${uptimeText(sys.uptime_s)}`,`IP ${tailIp}`,`WIFI ${wifi?.current?.ssid||'offline'} ${wifi?.current?.signal||''}`,`GPS ${gps.modeLabel||'n/a'} ${gps.satellitesUsed||0}/${gps.satellitesVisible||0}`,`TEMP ${indoor.available?(indoor.tempF?.toFixed?.(1)||indoor.tempF)+'F':'n/a'}`,`VPN ${(vpn.active_connections||[]).length?'ON':(vpn.gui_running?'APP OPEN':'OFF')}`,`VNC ${controls?.vnc?.state_label||controls?.vnc?.active_text||'n/a'}`,`SYNC ${controls?.syncthing?.state_label||controls?.syncthing?.active_text||'n/a'}`];
  const text=` ${items.join('  //  ')}  // `; const top=document.getElementById('topTickerText'); if(top) top.textContent=text+text;
}
function setButton(id,label,active=false,ok=true){ const b=document.getElementById(id); if(!b)return; if(!busyButtons.has(id))b.textContent=label; b.classList.toggle('is-active',!!active); b.classList.toggle('is-off',!active); b.classList.toggle('is-error',!ok); }
function applyProtonFx(){ document.body.classList.toggle('proton-fx-off', !protonFxEnabled); setButton('protonFxButton', protonFxEnabled?'Proton FX On':'Proton FX Off', protonFxEnabled, true); }
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
  const timeout = setTimeout(() => controller.abort(), 3500);
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
  if(enabled === cameraEnabled && cameraTimer) return;
  cameraEnabled=enabled;
  if(cameraTimer) clearInterval(cameraTimer);
  cameraTimer=null;
  if(enabled){ refreshCameraFrame(true); cameraTimer=setInterval(()=>refreshCameraFrame(false), 900); }
}
async function pollTilt(){
  if(tiltPollBusy || !document.getElementById('tiltStage')) return;
  tiltPollBusy=true;
  try{ const r=await fetch('/api/sensors/tilt',{cache:'no-store'}); if(r.ok) applyTilt(await r.json()); }catch(e){}
  tiltPollBusy=false;
}

async function refresh(){
  const res=await fetch('/api/status',{cache:'no-store'}); const s=await res.json(); lastStatus=s; currentConfig=s.config;
  document.getElementById('clock').textContent=new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});
  const faceEl=document.getElementById('face'); faceEl.textContent=s.mood.face; faceEl.style.color=s.mood.color; document.getElementById('mood').textContent=cleanText(s.mood.name); document.getElementById('thought').textContent=cleanText(s.thought); const tail=document.getElementById('tailUrl'); if(tail){ tail.textContent=''; tail.title=s.tailscale_url||'local only'; }
  const sys=s.system||{}, wifi=s.wifi||{}, sens=s.sensors||{}; setTicker(sys,wifi,sens,s.vpn||{},s.controls||{}); scheduleCamera(s);
  renderMissionControl(s); renderWeatherSim(sens.weather||{}, sens.light||{}); renderSystem(sys); renderHackerDeck(s); renderKnownDevices(s.known_devices||{}); renderWifi(wifi); renderRFAudit(s.rf_audit||{}, s.rf_recommendations||[]); renderGlobalMap(s); renderDefenseOps(s.security_stack||{}); renderExternals(s.externals||{}); renderSensors(sens); renderGpsTrail(s.gps_trail||{}); renderServices(s.services||{},s.controls||{}); renderEvents(s.events||[]); renderPluginPanels(s.plugin_panels||[]); renderPluginSwitches(s.native_plugins||[]); renderControls(s); renderVision(s.vision||{}, s.vision_history||{}); soundEvents(s);
}
function renderMissionControl(s){
  const el=document.getElementById('missionViz'); if(!el) return;
  const a=s.alert||{}, sys=s.system||{}, wifi=s.wifi||{}, gps=s.sensors?.gps||{}, wx=s.sensors?.weather||{}, vision=s.vision||{}, known=s.known_devices||{};
  const hist=(s.status_history?.points||[]).slice(-24).map(p=>p.ram||0);
  el.innerHTML=`<div class="alert-card alert-${(a.level||'GREEN').toLowerCase()}" style="--alert:${a.color||'var(--green)'}"><b>${a.level||'GREEN'} ${a.score||0}%</b><span>${(a.reasons||['normal watch']).join(' // ')}</span></div><div class="mission-grid"><div><span>VPN</span><b>${s.vpn?.active?'ON':(s.vpn?.gui_running?'APP':'OFF')}</b></div><div><span>GPS</span><b>${gps.fixed?'LOCK':'NO FIX'} ${gps.satellitesUsed||0}/${gps.satellitesVisible||0}</b></div><div><span>WEATHER</span><b>${wx.available?`${wx.summary} ${wx.tempF}°F`:'n/a'}</b></div><div><span>VISION</span><b>${vision.enabled?'ARMED':'OFF'}</b></div><div><span>KNOWN</span><b>${known.online||0}/${known.total||0} online</b></div><div><span>FAN</span><b>${sys.fan?.available?`${sys.fan.rpm||0}rpm ${sys.fan.cooling_state ?? '?'}/${sys.fan.cooling_max ?? '?'}`:'n/a'}</b></div><div><span>WIFI</span><b>${wifi.current?.ssid||'offline'}</b></div></div>${liveWave('24-SAMPLE RAM HISTORY', hist, `${sys.memory?.percent||0}%`, 'var(--purple)')}`;
}
function renderWeatherSim(weather={}, light={}){
  const el=document.getElementById('weatherSimViz'); if(!el) return;
  const summary=String(weather.summary||'weather n/a');
  const s=summary.toLowerCase();
  const storm=s.includes('storm')||s.includes('thunder');
  const rain=storm||s.includes('rain')||s.includes('shower');
  const snow=s.includes('snow');
  const cloud=rain||snow||s.includes('cloud')||s.includes('fog')||s.includes('mist');
  const clear=s.includes('clear')||s.includes('sun');
  const cls=storm?'storm':rain?'rain':snow?'snow':cloud?'cloud':clear?'clear':'idle';
  const drops=Array.from({length: rain?22:snow?18:0},(_,i)=>`<i style="--x:${(i*37)%100}%;--d:${(i%7)*-.22}s;--l:${18+(i%5)*8}px"></i>`).join('');
  const forecast=(weather.forecast||[]).slice(0,3).map(d=>`<div><b>${(d.date||'').slice(5)||'day'}</b><span>${weatherIcon(d.summary)} ${d.highF??'?'}/${d.lowF??'?'}°F</span><small>${d.summary||''} rain ${d.chanceRain??0}%</small></div>`).join('');
  const xy=weatherTileXY(weather.lat, weather.lon, 6);
  const tile=weather.radar?.configured && xy ? `<img src="/api/weather/tile/precipitation_new/${xy.z}/${xy.x}/${xy.y}.png" alt="OpenWeather precipitation radar tile">` : '';
  const radarNote=weather.radar?.configured ? 'OpenWeather precip tile' : 'OpenWeather key missing // simulated radar';
  el.className=`weather-sim weather-${cls}`;
  el.innerHTML=`<div class="weather-sky"><div class="weather-sun"></div><div class="weather-cloud c1"></div><div class="weather-cloud c2"></div><div class="weather-rain">${drops}</div><div class="weather-lightning"></div><div class="weather-ground"></div></div><div class="weather-readout"><b>${weatherIcon(summary)} ${summary}</b><span>${weather.available?(weather.tempF ?? 'n/a')+'°F // humidity '+(weather.humidity ?? 'n/a')+'% // wind '+(weather.windMph ?? 'n/a')+'mph':'waiting for weather'}</span><small>${weather.location||weather.source||'source unknown'} // ${weather.source||'ip'}</small></div><div class="weather-radar"><div class="radar-tile">${tile}<i></i><b></b></div><small>${radarNote}</small></div><div class="forecast-strip">${forecast||'<div><b>forecast</b><span>waiting</span><small>weather cache warmup</small></div>'}</div>`;
}
function renderGlobalMap(s){
  const el=document.getElementById('globalMapViz'); if(!el) return;
  const sys=s.system||{}, vpn=s.vpn||{}, gps=s.sensors?.gps||{}, wx=s.sensors?.weather||{};
  const tail=(sys.ips||[]).find(ip=>String(ip).startsWith('100.'))||'no-tailnet';
  const vpnOn=!!vpn.active;
  const vpnLabel=vpnOn?'CONNECTED':(vpn.gui_running?'APP OPEN':'DISCONNECTED');
  const server=(vpn.active_connections||[])[0]?.name || vpn.selected_profile?.name || 'Fastest country';
  const profiles=(vpn.profiles||[]).slice(0,6);
  const gpsLabel=gps.fixed?`${Number(gps.lat).toFixed(3)}, ${Number(gps.lon).toFixed(3)}`:'GPS NO FIX';
  const markers=[
    [18,43,'US-NY'],[28,54,'US-W'],[37,38,'UK'],[45,40,'NL'],[48,43,'DE'],[50,48,'CH'],[53,44,'PL'],[57,49,'TR'],[64,52,'IN'],[70,46,'SG'],[78,58,'AU'],[41,66,'BR'],[33,72,'AR'],[60,64,'ZA'],[72,38,'JP'],[54,34,'SE'],[47,56,'IT'],[44,52,'ES']
  ];
  const markerHtml=markers.map((m,i)=>`<button class="proton-pin ${i===5?'connected':''}" style="left:${m[0]}%;top:${m[1]}%" title="${m[2]}" onclick="toggleVpn()"><span></span></button>`).join('');
  const list=profiles.length ? profiles.map((p,i)=>`<button class="proton-server-row" onclick="toggleVpn()"><i></i><span>${p.name}</span><em>${i===0?'selected':'profile'}</em></button>`).join('') : `<button class="proton-server-row" onclick="toggleVpn()"><i></i><span>${vpn.proton_installed?'Open/Quick Connect in Proton':'No VPN profile'}</span><em>${vpn.proton_installed?'GUI':'setup'}</em></button>`;
  el.innerHTML=`<div class="world-map proton-map proton-desktop-map">
    <aside class="proton-side-panel"><div class="proton-search">⌕ Browse from... <kbd>ctrl+F</kbd></div><div class="proton-tabs"><b>Countries</b><span>Profiles</span></div><div class="proton-filter"><button class="active">All</button><button>Secure Core</button><button>P2P</button><button>Tor</button></div><div class="proton-server-list">${list}</div></aside>
    <section class="proton-map-stage"><div class="map-grid" aria-hidden="true">${[10,22,34,46,58,70,82,94].map(x=>`<i style="left:${x}%"></i>`).join('')}${[18,34,50,66,82].map(y=>`<b style="top:${y}%"></b>`).join('')}</div><img class="proton-world" src="/assets/proton-world.svg" alt="ProtonVPN Android world map asset" loading="eager"/>${markerHtml}<div class="proton-connected-pill"><b>${vpnLabel}</b><span>${server}</span></div><div class="proton-zoom"><button>+</button><button>−</button></div><div class="proton-brand">⌁ ProtonVPN</div><div class="map-credit">PROTONVPN/android-app world.svg</div></section>
    <aside class="proton-tools"><button title="NetShield">🛡<span>NetShield</span></button><button title="Kill switch">⏻<span>Kill switch</span></button><button title="Port forwarding">⇄<span>Port</span></button><button title="Settings">⚙<span>Settings</span></button></aside>
    <footer class="proton-session"><div class="proton-status-card"><b>${vpnOn?'Protected':'Unprotected'}</b><span>VPN IP ${vpnOn?'active':'hidden'}</span><span>TAIL ${tail}</span><span>${gpsLabel}</span><div class="proton-actions"><button onclick="toggleVpn()">${vpn.button_label||'VPN'}</button><button onclick="postJson('/api/vpn/open').then(refresh)">Open Proton</button><button onclick="toggleProtonFx()">FX ${protonFxEnabled?'On':'Off'}</button></div></div><div class="traffic-card"><b>Session Traffic</b>${liveWave('CURRENT TRAFFIC', rxHist.map((v,i)=>Math.max(v, txHist[i]||0)), `↓${bytesPerSec(sys.net_io?.rx_bps)} ↑${bytesPerSec(sys.net_io?.tx_bps)}`, 'var(--green)')}</div><div class="map-overlay"><b>${vpnLabel}</b><span>SERVER ${server}</span><span>${wx.summary||'weather n/a'} ${wx.tempF?wx.tempF+'°F':''}</span><span>${tail}</span></div></footer>
  </div>`;
}
function renderDefenseOps(sec={}){
  const el=document.getElementById('defenseOpsViz'); if(!el) return;
  const stacks=(sec.stacks||[]).map(st=>`<div class="defense-row ${st.installed?'installed':''}"><b>${st.label}</b><span>${st.installed?'detected':'not installed'}</span><small>${(st.signals||[]).join(' // ')}</small><em>${st.safe_use||''}</em></div>`).join('');
  const recs=(sec.recommendations||[]).slice(0,3).map(r=>`<li>${r}</li>`).join('');
  el.innerHTML=`<div class="defense-mode">${sec.mode||'defensive-only'} // inspired by Security Onion, OpenNMS, HoneyPi, P4wnP1</div>${stacks||'<div class="scanline-note">security stack status unavailable</div>'}<ul class="defense-recs">${recs}</ul>`;
}
function renderExternals(externals={}){
  const nav=document.getElementById('externalDeviceTabs'), detail=document.getElementById('externalDetail'), title=document.getElementById('externalTitle');
  if(!nav || !detail) return;
  const devices=externals.devices||[];
  if(!devices.length){ nav.innerHTML='<div class="scanline-note">no external nodes configured</div>'; detail.textContent=''; return; }
  if(!devices.some(d=>d.id===selectedExternal)) selectedExternal=devices[0].id;
  nav.innerHTML=devices.map(d=>`<button class="${d.id===selectedExternal?'active':''}" onclick="selectExternal('${d.id}')"><b>${d.label||d.id}</b><span>${d.host||''}</span></button>`).join('');
  const d=devices.find(x=>x.id===selectedExternal)||devices[0]; if(title) title.textContent=d.label||d.id;
  const links=(d.links||[]).map(l=>`<a href="${l.url}" target="_blank" rel="noopener noreferrer">${l.label||l.url}</a>`).join('')||'<span>no web links configured</span>';
  const notes=(d.notes||[]).map(n=>`<li>${n}</li>`).join('');
  const controls=d.car_controls?`<div class="car-controls"><button onclick="externalCar('${d.id}','forward')">▲</button><button onclick="externalCar('${d.id}','left')">◀</button><button class="stop" onclick="externalCar('${d.id}','stop')">STOP</button><button onclick="externalCar('${d.id}','right')">▶</button><button onclick="externalCar('${d.id}','backward')">▼</button></div><div class="scanline-note">Local car controls only. Use STOP if behavior is wrong.</div>`:'';
  const camera=d.camera_feed?`<div class="external-camera"><img src="/api/camera/frame?feed=${encodeURIComponent(d.camera_feed)}&t=${Date.now()}" alt="${d.label||d.id} camera preview" onerror="this.classList.add('offline')"><button onclick="switchCameraFeed('${d.camera_feed}'); showTab('vision')">Open in Vision</button></div>`:'';
  detail.innerHTML=`<div class="external-grid"><div class="external-info"><b>${d.kind||'external node'}</b><span>host ${d.host||'n/a'}</span><span>ssh user ${d.user||'n/a'}</span><span>camera feed ${d.camera_feed||'n/a'}</span><span>password stored: ${d.password_stored?'yes':'no'}</span><div class="external-links">${links}</div><ul>${notes}</ul></div>${camera}<div class="external-controls">${controls}</div></div>`;
}
function selectExternal(id){ selectedExternal=id; renderExternals(lastStatus?.externals||{}); }
async function externalCar(id, action){
  const d=await postJson(`/api/externals/${id}/control`, {action});
  if(!d.ok) alert(`External control failed: ${d.error||'unknown'}`);
  await refresh();
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
  const cpu=sys.cpu_temp_c||0, cpuF=sys.cpu_temp_f||((cpu*9/5)+32), mem=sys.memory||{}, ram=mem.percent||0, disk=diskPercent(sys.disk_root), load1=Number(String(sys.load||'0').split(' ')[0])||0;
  const loadPct=Math.min(load1/8*100,100), cpuPct=Math.min(cpu/85*100,100), net=sys.net_io||{};
  pushHist(cpuHist, cpuPct); pushHist(ramHist, ram); pushHist(diskHist, disk); pushHist(loadHist, loadPct); pushHist(rxHist, Math.min((net.rx_bps||0)/1048576*100,100)); pushHist(txHist, Math.min((net.tx_bps||0)/1048576*100,100));
  document.getElementById('systemViz').innerHTML = `${liveWave('CPU TEMP', cpuHist, `${cpu?cpuF.toFixed(1):'n/a'}°F`, cpu>=75?'var(--red)':cpu>=65?'var(--yellow)':'var(--green)')}${liveWave('RAM PRESSURE', ramHist, mem.text||'n/a', 'var(--cyan)')}${liveWave('DISK', diskHist, disk+'%', disk>=90?'var(--red)':disk>=80?'var(--yellow)':'var(--green)')}${liveWave('LOAD', loadHist, sys.load||'n/a', loadPct>=80?'var(--red)':loadPct>=55?'var(--yellow)':'var(--purple)')}${liveWave('NET RX/TX PULSE', rxHist.map((v,i)=>Math.max(v, txHist[i]||0)), `↓${bytesPerSec(net.rx_bps)} ↑${bytesPerSec(net.tx_bps)}`, 'var(--blue)')}${statPill('FAN', sys.fan?.available ? `${sys.fan.rpm||0} RPM // ${sys.fan.cooling_state ?? '?'} / ${sys.fan.cooling_max ?? '?'}` : 'n/a')}`;
  document.getElementById('system').textContent=[line('host',sys.hostname),line('ip',(sys.ips||[]).find(ip=>ip.startsWith('100.'))||(sys.ips||[])[0]||'n/a'),line('up',uptimeText(sys.uptime_s))].join('\n');
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
  const sig=Number(wifi.current?.signal||0), nets=(wifi.networks||[]).slice(0,6);
  document.getElementById('wifiViz').innerHTML = `<div class="wifi-signal-card"><div><span>SIGNAL</span><b>${wifi.current?wifi.current.ssid:'offline'}</b></div>${signalBars(sig)}</div>${statPill('NETWORKS',(wifi.networks||[]).length)}${statPill('NEW',(wifi.new||[]).length)}<table class="mini-table"><tbody>${nets.map(n=>`<tr><td>${n.connected?'●':'○'}</td><td>${n.ssid}</td><td>${signalBars(Number(n.signal||0))}</td></tr>`).join('')||'<tr><td>none</td></tr>'}</tbody></table>`;
  document.getElementById('wifi').textContent=[line('connected',yes(wifi.connected)),line('current',wifi.current?wifi.current.ssid+' '+wifi.current.signal:'none')].join('\n');
}
function renderWifiVault(data){
  const el=document.getElementById('wifiVaultViz'); if(!el) return;
  if(!wifiVaultVisible){ el.innerHTML='<div class="scanline-note">Wi-Fi Vault hidden. Hit Wi-Fi Vault to show saved profiles.</div>'; return; }
  const rows=(data.networks||[]).map(n=>`<tr><td>${n.ssid||n.name}</td><td>${n.has_password?'saved':'none'}</td><td>${n.password||'••••••••'}</td></tr>`).join('') || '<tr><td>no saved Wi-Fi profiles</td></tr>';
  el.innerHTML = `<table class="mini-table"><thead><tr><th>SSID</th><th>Password</th><th>Value</th></tr></thead><tbody>${rows}</tbody></table><div class="scanline-note">Known Network Vault shown. Password values stay masked in Hack-Safe.</div>`;
}
async function loadWifiVault(){
  wifiVaultVisible=!wifiVaultVisible;
  setButton('wifiVaultButton',wifiVaultVisible?'Hide Wi-Fi Vault':'Wi-Fi Vault',wifiVaultVisible,true);
  if(!wifiVaultVisible){ renderWifiVault(wifiVaultData||{networks:[]}); return; }
  setBusy('wifiVaultButton',true,'Loading vault...');
  try { const r=await fetch('/api/wifi/passwords',{cache:'no-store'}); wifiVaultData=await r.json(); renderWifiVault(wifiVaultData); }
  catch(err){ const el=document.getElementById('wifiVaultViz'); if(el) el.innerHTML=`<div class="scanline-note">vault error: ${err}</div>`; }
  setBusy('wifiVaultButton',false); setButton('wifiVaultButton','Hide Wi-Fi Vault',true,true);
}
function renderRFAudit(audit, recs=[]){
  const el=document.getElementById('rfAuditViz'); if(!el) return;
  const wifi=audit.wifi||{}, bt=audit.bluetooth||{}, adapter=wifi.adapter||{}, current=wifi.current||{};
  const warnings=(wifi.security_warnings||[]).slice(0,4);
  const saved=(wifi.saved_networks||[]).slice(0,4);
  const modes=(adapter.modes||[]).slice(0,5).join(', ')||'n/a';
  const warnRows=warnings.length ? warnings.map(w=>`<small><b>${w.ssid||'<hidden>'}</b> ch ${w.channel||'?'} // ${w.issues.join(', ')}</small>`).join('') : '<small>no weak nearby configs flagged</small>';
  const savedRows=saved.length ? saved.map(n=>`<tr><td>${n.ssid}</td><td>${n.security||'unknown'}</td><td>${n.has_password?(n.password_strength?.label||'n/a')+' '+(n.password_strength?.score??0)+'%':'hidden/unavailable'}</td></tr>`).join('') : '<tr><td>no saved Wi-Fi profiles</td></tr>';
  const btWarn=(bt.warnings||[]).length ? bt.warnings.join(', ') : 'not discoverable/pairable';
  const pwn=wifi.pwnagotchi||{}, cap=pwn.handshake_capture||{}; const pwnChannelRows=(pwn.channel_plan||[]).slice(0,8).map(c=>`<tr><td>${c.channel}</td><td>${c.aps}</td><td>${c.max_signal||0}%</td><td>${(c.ssids||[]).join(', ')}</td></tr>`).join('') || '<tr><td colspan="4">no channel plan yet</td></tr>'; const monitorIfaces=(adapter.interfaces||[]).filter(i=>i.type==='monitor').map(i=>i.name); el.innerHTML = `<div class="rf-banner"><b>OWNED RF AUDIT</b><span>GhostESP/Kali vibe, Hack-Safe rules: no cracking, no deauth, no exploit.</span></div><div class="rf-grid"><div class="rf-tile"><span>CURRENT AP</span><b>${current.ssid||'offline'}</b><small>${current.security||'unknown'} // ch ${current.channel||'?'} // ${current.signal||0}%</small></div><div class="rf-tile"><span>ADAPTER</span><b>${adapter.monitor_supported?'monitor-capable':'managed'}</b><small>${(adapter.interfaces||[]).map(i=>`${i.name}:${i.type||'?'}`).join(', ')||'n/a'}</small></div><div class="rf-tile"><span>BT SURFACE</span><b>${bt.powered?'powered':'off'}</b><small>${bt.devices_seen||0} devices // ${btWarn}</small></div><div class="rf-tile"><span>SAFE MODE</span><b>audit only</b><small>${audit.kali_requested||audit.mode||''}</small></div></div><div class="recon-box pwn-deck"><b>PWNAGOTCHI RF DECK</b><small>${pwn.pattern||'Channel planning and owned-lab capture readiness.'}</small><table class="mini-table"><thead><tr><th>Ch</th><th>APs</th><th>Peak</th><th>SSIDs</th></tr></thead><tbody>${pwnChannelRows}</tbody></table><div class="device-actions"><button class="mini-btn" onclick="startOwnedLabCapture()">Owned-Lab Passive Capture</button></div><small>Capture gate: ${cap.ok?'ready':(cap.error||'waiting for adapter / explicit lab gate')}</small><small>Monitor interfaces: ${monitorIfaces.join(', ')||'none yet'}</small></div><div class="recon-box"><b>WI-FI WARNINGS</b>${warnRows}</div><div class="recon-box"><b>WHAT TO FIX</b>${(recs||[]).slice(0,4).map(r=>`<small>${r}</small>`).join('')||'<small>nothing urgent</small>'}</div><table class="mini-table"><thead><tr><th>Saved SSID</th><th>Security</th><th>PSK score</th></tr></thead><tbody>${savedRows}</tbody></table><div class="scanline-note">Allowed: AP/BT inventory, private LAN recon, saved-password strength scoring, and explicit owned-lab passive capture with a monitor adapter. Blocked: password cracking, deauth automation, Bluetooth exploitation.</div>`;
}
function renderSensors(sens){
  const gps=sens.gps||{}, indoor=sens.indoor||{}, light=sens.light||{}, weather=sens.weather||{}, tilt=sens.tilt_event||{}, gpio=sens.gpio||{};
  const sats=gps.satellitesVisible?Math.round((gps.satellitesUsed||0)/(gps.satellitesVisible||1)*100):0;
  const tempF=Number(indoor.tempF||0), humidity=Number(indoor.humidity||0), lux=Number(light.lux||0), wx=weatherIcon(weather.summary||'');
  pushHist(indoorTempHist, Math.min(tempF/110*100,100)); pushHist(humidityHist, humidity); pushHist(lightHist, Math.min(lux/400*100,100));
  const root=document.getElementById('sensorViz');
  if(!root.querySelector('.radar')){
    root.innerHTML = `<div class="sensor-top"><div class="radar"><i class="radar-pulse"></i><span class="gps-blips"></span><b class="gps-mode"></b><span class="gps-sats"></span></div><div id="weatherCard" class="weather"></div></div><div id="sensorWaves" class="viz-stack"></div>`;
  }
  const used=Number(gps.satellitesUsed||0), fixed=!!gps.fixed;
  const blipCount=fixed ? used : 0;
  const blips=root.querySelector('.gps-blips');
  if(blips && blips.dataset.count !== String(blipCount)) { blips.dataset.count=String(blipCount); blips.innerHTML=gpsBlipHtml(blipCount); }
  root.querySelector('.gps-mode').textContent = gps.modeLabel||'NO FIX';
  root.querySelector('.gps-sats').textContent = `${used}/${gps.satellitesVisible||0}`;
  const weatherCard=root.querySelector('#weatherCard');
  weatherCard.className=`weather ${sensorTempClass(weather.tempF)}`;
  weatherCard.innerHTML=`<span class="weather-icon">${wx}</span><b>${weather.available?weather.summary:'weather n/a'}</b><em>${weather.available?weather.tempF+'°F':''}</em><small>${weather.available?`humidity ${weather.humidity ?? 'n/a'}%`:''}</small><small>${weather.location||weather.source||''}</small>`;
  root.querySelector('#sensorWaves').innerHTML = `${liveWave('GPS SATS', [0, sats/2, sats], `${gps.satellitesUsed||0}/${gps.satellitesVisible||0}`, sats? 'var(--green)' : 'var(--yellow)')}${liveWave('INDOOR TEMP', indoorTempHist, indoor.available?`${tempF.toFixed(1)}°F`:'n/a', tempF>=88?'var(--red)':tempF>=78?'var(--yellow)':'var(--cyan)')}${liveWave('HUMIDITY', humidityHist, indoor.available?`${humidity.toFixed(0)}%`:'n/a', 'var(--blue)')}${liveWave('LIGHT', lightHist, light.available?`${lux} lux`:'n/a', lux>=250?'var(--yellow)':lux<=10?'var(--purple)':'var(--green)')}${tiltVisual(gpio, tilt)}`;
  document.getElementById('sensors').textContent=[line('lat/lon',gps.lat&&gps.lon?`${gps.lat}, ${gps.lon}`:'no fix')].join('\n');
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
  el.innerHTML = `<table class="plugin-table"><thead><tr><th>On</th><th>Plugin</th><th>Loaded</th><th>Description</th></tr></thead><tbody>${plugins.map(p=>`<tr><td><input type="checkbox" ${p.enabled?'checked':''} onchange="togglePlugin('${p.name}', this.checked)"></td><td>${p.name}</td><td>${p.loaded?'yes':'no'}</td><td>${p.description||''}</td></tr>`).join('')}</tbody></table>`;
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
  const quick=document.getElementById('quickCameraSwitch');
  const feeds=cam.feeds||[];
  if(quick){
    quick.innerHTML=`<label>Camera feed <select id="quickCameraSelect" onchange="switchCameraFeed(this.value)">${feeds.map(f=>`<option value="${f.id}" ${f.id===(cam.active_feed||activeCameraFeed)?'selected':''}>${f.label||f.id}${f.available?'':' ⚠'}</option>`).join('')}</select></label><span>${cam.active_feed||activeCameraFeed} // ${cam.camera_available?'ready':'offline'}</span>`;
  }
}
function renderVision(cam, history={}){
  const dets=cam.last_analysis?.detections||[];
  activeCameraFeed = cam.active_feed || activeCameraFeed || 'local';
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
  const pulse=document.getElementById('cameraPulse');
  if(pulse) pulse.textContent=`SWITCH ${activeCameraFeed}`;
  refreshCameraFrame(true);
  try { await postJson('/api/camera/feed', {feed: activeCameraFeed}); } catch(e) {}
  await refresh();
}
async function postJson(url, body){ const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined}); const data=await r.json(); if(!r.ok&&data.ok!==false)data.ok=false; return data; }
async function scan(kind){ await fetch(`/api/scan/${kind}`,{cache:'no-store'}); await refresh(); }
async function toggleVpn(){ setBusy('vpnButton',true,'Toggling...'); const d=await postJson('/api/vpn/toggle'); showAction('vpnControl',d); setBusy('vpnButton',false); await refresh(); }
async function toggleService(name){ const id=name==='syncthing'?'syncthingButton':`${name}Button`; setBusy(id,true,'Switching...'); const d=await postJson(`/api/services/${name}/toggle`); showAction('serviceControl',d); setBusy(id,false); await refresh(); }
async function toggleVision(){ const enabled=!(lastStatus?.vision?.enabled??currentConfig?.vision?.enabled); setBusy('visionButton',true,enabled?'Arming...':'Disarming...'); setBusy('visionButton2',true,enabled?'Arming...':'Disarming...'); const d=await postJson('/api/camera/vision',{enabled}); showAction('cameraControl',d); setBusy('visionButton',false); setBusy('visionButton2',false); cameraEnabled=null; refreshCameraFrame(true); await refresh(); }
async function analyzeVision(){ setBusy('analyzeButton',true,'Scanning...'); const d=await postJson('/api/camera/analyze'); document.getElementById('visionDetections').textContent=JSON.stringify(d,null,2); setBusy('analyzeButton',false); refreshCameraFrame(true); await refresh(); }

async function startOwnedLabCapture(){
  const adapter=lastStatus?.rf_audit?.wifi?.adapter||{};
  const monitors=(adapter.interfaces||[]).filter(i=>i.type==='monitor').map(i=>i.name);
  const iface=prompt('Monitor interface for owned-lab capture:', monitors[0]||'wlan1mon');
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
async function loadSettings(){ const r=await fetch('/api/config',{cache:'no-store'}); const d=await r.json(); currentConfig=d.config; document.getElementById('settingsJson').value=JSON.stringify(d.config,null,2); document.getElementById('settingsStatus').textContent='Settings loaded.'; renderPluginSwitches(d.plugins||[]); }
async function saveSettings(){ try{ const config=JSON.parse(document.getElementById('settingsJson').value); const d=await postJson('/api/config',{config}); document.getElementById('settingsStatus').textContent=d.ok?'Settings saved. Plugins reloaded.':`Save failed: ${d.error||'unknown'}`; await refresh(); }catch(err){ document.getElementById('settingsStatus').textContent=`Save failed: ${err}`; } }
async function togglePlugin(name, enabled){ if(!currentConfig) await loadSettings(); currentConfig.plugins=currentConfig.plugins||{}; currentConfig.plugins[name]=!!enabled; document.getElementById('settingsJson').value=JSON.stringify(currentConfig,null,2); const d=await postJson('/api/config',{config:currentConfig}); document.getElementById('pluginSwitches').classList.toggle('saving', false); if(!d.ok) alert(`Plugin save failed: ${d.error||'unknown'}`); await refresh(); }

document.title='Hack-Safe Spac3-Gh0st'; refresh(); setInterval(refresh,2000); setInterval(pollTilt,350);
