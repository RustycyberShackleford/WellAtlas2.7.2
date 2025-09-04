let map;
let markers = [];
let currentPin = null;

async function fetchSites(query=""){
  const res = await fetch(`/api/sites?q=${encodeURIComponent(query)}`);
  return await res.json();
}
function setCoordFields(lat, lon){
  const latField = document.getElementById('latField');
  const lonField = document.getElementById('lonField');
  if(latField) latField.value = (+lat).toFixed(6);
  if(lonField) lonField.value = (+lon).toFixed(6);
}
function placePin(lat, lon){
  if(currentPin){ map.removeLayer(currentPin); }
  currentPin = L.marker([lat, lon], {draggable:true}).addTo(map);
  currentPin.on('dragend', function(ev){
    const {lat, lng} = ev.target.getLatLng();
    setCoordFields(lat, lng);
  });
}
function populateDatalists(sites){
  const names = document.getElementById('siteNames');
  const jobs = document.getElementById('jobNumbers');
  const customers = document.getElementById('customers');
  if(names) names.innerHTML = '';
  if(jobs) jobs.innerHTML = '';
  if(customers) customers.innerHTML = '';
  const seenName = new Set(), seenJob = new Set(), seenCust = new Set();
  sites.forEach(s => {
    if(s.name && !seenName.has(s.name)){ seenName.add(s.name); const o=document.createElement('option'); o.value=s.name; names?.appendChild(o); }
    if(s.job_number && !seenJob.has(s.job_number)){ seenJob.add(s.job_number); const o=document.createElement('option'); o.value=s.job_number; jobs?.appendChild(o); }
    if(s.customer && !seenCust.has(s.customer)){ seenCust.add(s.customer); const o=document.createElement('option'); o.value=s.customer; customers?.appendChild(o); }
  });
}
async function refreshSites(){
  const q = document.getElementById('searchInput')?.value || '';
  const sites = await fetchSites(q);
  markers.forEach(m => map.removeLayer(m)); markers = [];
  const list = document.getElementById('siteList'); if(list) list.innerHTML = '';
  sites.forEach(s => {
    const lat = s.latitude || 0; const lon = s.longitude || 0;
    const marker = L.marker([lat, lon]).addTo(map);
    marker.bindPopup(`<b>${s.name || 'Untitled'}</b><br>Job: ${s.job_number || ''}<br><a href="/sites/${s.id}">Open</a>`);
    markers.push(marker);
    if(list){
      const li = document.createElement('li');
      li.innerHTML = `<a href="/sites/${s.id}">${s.name || 'Untitled'}</a>
        <div class="meta">Job: ${s.job_number || '—'} • ${s.customer || '—'}</div>`;
      list.appendChild(li);
    }
  });
  populateDatalists(sites);
}
function locateMe(){
  if(!navigator.geolocation){ alert('Geolocation not supported by your browser.'); return; }
  navigator.geolocation.getCurrentPosition((pos)=>{
    const lat = pos.coords.latitude; const lon = pos.coords.longitude;
    map.setView([lat, lon], 14); placePin(lat, lon); setCoordFields(lat, lon);
  }, (err)=>{ alert('Could not get your location.'); console.error(err); });
}
function initMap(){
  map = L.map('map', { zoomControl:true }).setView([40.55, -122.39], 8);
  const imagery = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { attribution: 'Tiles © Esri' }).addTo(map);
  map.on('click', function(e){ placePin(e.latlng.lat, e.latlng.lng); setCoordFields(e.latlng.lat, e.latlng.lng); });
  document.getElementById('locateBtn')?.addEventListener('click', locateMe);
  document.getElementById('searchBtn')?.addEventListener('click', () => refreshSites());
  document.getElementById('searchInput')?.addEventListener('keyup', (ev)=>{ if(ev.key === 'Enter'){ refreshSites(); } });
  refreshSites();
}
document.addEventListener('DOMContentLoaded', initMap);
