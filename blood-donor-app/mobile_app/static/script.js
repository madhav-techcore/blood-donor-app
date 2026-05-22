const baseUrl = '';

function showBanner(message, type = 'info') {
    const banner = document.getElementById('notification-banner');
    if (!banner) return;
    banner.textContent = message;
    banner.className = `notification-banner ${type}`;
    banner.classList.remove('hidden');
    setTimeout(() => banner.classList.add('hidden'), 6000);
}

let mapInstances = {};
function initializeMap(elementId, center = [20.5937, 78.9629], zoom = 5) {
    const container = document.getElementById(elementId);
    if (!container) return null;
    if (mapInstances[elementId]) {
        mapInstances[elementId].remove();
    }
    container.innerHTML = '';
    const map = L.map(container).setView(center, zoom);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors'
    }).addTo(map);
    mapInstances[elementId] = map;
    return map;
}

function getMapColor(type) {
    if (type === 'urgent') return '#dc3545';
    if (type === 'request') return '#198754';
    return '#0d6efd';
}

async function loadStats() {
    try {
        const response = await fetch('/api/stats');
        const stats = await response.json();
        const statsContainer = document.getElementById('stats-cards');
        if (!statsContainer) return;
        statsContainer.innerHTML = `
            <div class="stat-card"><h2>${stats.donors || 0}</h2><p>Registered Donors</p></div>
            <div class="stat-card"><h2>${stats.donations || 0}</h2><p>Donations Recorded</p></div>
            <div class="stat-card"><h2>${stats.requests || 0}</h2><p>Blood Requests</p></div>
            <div class="stat-card"><h2>${stats.urgent_requests || 0}</h2><p>Urgent Requests</p></div>
        `;
    } catch (e) {
        console.error('Stats loading error:', e);
    }
}
function addMarkers(map, items, options) {
    const group = L.featureGroup();
    items.forEach(item => {
        if (!item.latitude || !item.longitude) return;
        const marker = L.circleMarker([item.latitude, item.longitude], {
            radius: 8,
            color: getMapColor(options.type),
            fillColor: getMapColor(options.type),
            fillOpacity: 0.8,
            weight: 2
        });
        marker.bindPopup(options.popup(item));
        marker.addTo(map);
        group.addLayer(marker);
    });
    if (group.getLayers().length) {
        map.fitBounds(group.getBounds().pad(0.5));
    }
}

function captureLocation(type) {
    if (!navigator.geolocation) {
        showBanner('Geolocation is not supported by this browser.', 'error');
        return;
    }

    navigator.geolocation.getCurrentPosition(
        position => {
            const latField = document.getElementById(`${type}_latitude`);
            const lngField = document.getElementById(`${type}_longitude`);
            if (latField && lngField) {
                latField.value = position.coords.latitude;
                lngField.value = position.coords.longitude;
                showBanner('Location captured successfully.', 'success');
            }
        },
        () => {
            showBanner('Unable to access your location. Please allow location permission.', 'error');
        },
        { enableHighAccuracy: true, timeout: 10000 }
    );
}

async function registerDonor() {
    const data = {
        name: document.getElementById('name').value,
        phone: document.getElementById('phone').value,
        email: document.getElementById('email').value,
        password: document.getElementById('password').value,
        blood_group: document.getElementById('blood_group').value,
        address: document.getElementById('address').value,
        city: document.getElementById('city').value,
        latitude: document.getElementById('donor_latitude')?.value || null,
        longitude: document.getElementById('donor_longitude')?.value || null
    };

    const response = await fetch('/api/register-donor', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });
    const result = await response.json();
    showBanner(result.message, result.success ? 'success' : 'error');
    if (result.success) loadDonors();
}

async function loadDonors() {
    const response = await fetch('/api/donors');
    const donors = await response.json();
    const list = document.getElementById('donor-list');
    const donorSelect = document.getElementById('donor_id');
    if (donorSelect) {
        donorSelect.innerHTML = '<option value="">Choose donor</option>' + donors.map(donor => `
            <option value="${donor.id}">${donor.name} (${donor.blood_group}, ${donor.city})</option>
        `).join('');
    }
    if (!list) return;
    list.innerHTML = donors.map(donor => `
        <div class="record-card donor-clickable" onclick="showDonorDetails(${donor.id})" style="cursor:pointer">
            <div class="card-tag">${donor.token || 'No ID'}</div>
            <h3>${donor.name}</h3>
            <p>${donor.blood_group} • ${donor.city}</p>
            <p>${donor.address || 'Address not provided'}</p>
            <p>${donor.phone} <a href="tel:${donor.phone}" class="btn-call" onclick="event.stopPropagation()">📞 Call</a></p>
            <p>${donor.email || ''}</p>
            <small style="color:#888">Tap for medical details</small>
        </div>
    `).join('');
}

async function recordDonation() {
    const donorId = document.getElementById('donor_id').value;
    const amountMl = document.getElementById('amount_ml').value;
    const date = document.getElementById('donation_date').value;
    const bloodGroup = document.getElementById('donation_group')?.value || '';
    const city = document.getElementById('donation_city')?.value || '';
    const notes = document.getElementById('notes')?.value || '';
    const age = document.getElementById('donation_age')?.value || null;
    const sex = document.getElementById('donation_sex')?.value || '';
    const bp = document.getElementById('donation_bp')?.value || '';
    const sugar = document.getElementById('donation_sugar')?.value || '';
    const medicalCondition = document.getElementById('donation_medical_condition')?.value || '';

    if (!donorId) {
        showBanner('Select a donor before recording donation.', 'error');
        return;
    }

    const response = await fetch('/api/add-donation', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ donor_id: donorId, amount_ml: amountMl, date, blood_group: bloodGroup, city, notes, age, sex, bp, sugar, medical_condition: medicalCondition })
    });
    const result = await response.json();
    showBanner(result.message, result.success ? 'success' : 'error');
    if (result.success) loadDonations();
}

async function loadDonations() {
    const response = await fetch('/api/donations');
    const donations = await response.json();
    const list = document.getElementById('donation-list');
    if (!list) return;
    list.innerHTML = donations.map(record => `
        <div class="record-card">
            <h3>${record.donor_name}</h3>
            <p>${record.amount_ml} ml • ${record.blood_group} • ${record.city}</p>
            <p>${record.date}</p>
            <p>${record.notes || 'No notes'}</p>
        </div>
    `).join('');
}

async function createBloodRequest() {
    const data = {
        patient_name: document.getElementById('patient_name').value,
        blood_group: document.getElementById('request_blood_group').value,
        city: document.getElementById('request_city').value,
        hospital: document.getElementById('hospital').value,
        details: document.getElementById('details')?.value || '',
        age: document.getElementById('request_age')?.value || null,
        sex: document.getElementById('request_sex')?.value || '',
        urgent: false,
        latitude: document.getElementById('request_latitude')?.value || null,
        longitude: document.getElementById('request_longitude')?.value || null
    };

    const response = await fetch('/api/create-request', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });
    const result = await response.json();
    showBanner(result.message, result.success ? 'success' : 'error');
    if (result.success) loadRequests();
}

async function loadRequests() {
    const response = await fetch('/api/requests');
    const requests = await response.json();
    const list = document.getElementById('requests-list');
    if (!list) return;
    list.innerHTML = requests.map(req => `
        <div class="record-card">
            <div class="card-tag">${req.token || 'REQ'}</div>
            <h3>${req.patient_name}</h3>
            <p>${req.blood_group} • ${req.city} • ${req.hospital}</p>
            <p>${req.details}</p>
            <small>${new Date(req.created_at).toLocaleString()}</small>
        </div>
    `).join('');
}

async function createUrgentRequest() {
    const data = {
        patient_name: document.getElementById('urgent_patient_name').value,
        blood_group: document.getElementById('urgent_blood_group').value,
        city: document.getElementById('urgent_city').value,
        hospital: document.getElementById('urgent_hospital').value,
        details: document.getElementById('urgent_details')?.value || '',
        age: document.getElementById('urgent_age')?.value || null,
        sex: document.getElementById('urgent_sex')?.value || '',
        urgent: true,
        latitude: document.getElementById('urgent_latitude')?.value || null,
        longitude: document.getElementById('urgent_longitude')?.value || null
    };

    const response = await fetch('/api/create-request', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });
    const result = await response.json();
    showBanner(result.message, result.success ? 'success' : 'error');
    if (result.success) {
        if (typeof loadUrgentRequests === 'function' && document.getElementById('urgent-list')) loadUrgentRequests();
        if (typeof loadSmsLog === 'function' && document.getElementById('sms-log')) loadSmsLog();
        if (typeof loadUrgentMap === 'function' && document.getElementById('urgent-map')) loadUrgentMap();
        
        // Show notified donors if applicable
        renderNotifiedDonors(result.notified_donors, 'urgent-notified-donors');
    }
}

function renderNotifiedDonors(donors, containerId) {
    const list = document.getElementById(containerId);
    if (!list) return;
    if (!donors || donors.length === 0) {
        list.innerHTML = '<div class="record-card"><p>No donors found in this area/blood group.</p></div>';
        return;
    }
    list.innerHTML = '<h3>Notified Donors (Nearest First)</h3>' + donors.map(donor => `
        <div class="record-card donor-clickable" onclick="showDonorDetails(${donor.id})" style="cursor:pointer">
            <h3>${donor.name}</h3>
            <p>Distance: ${donor.distance_km !== null ? donor.distance_km + ' km' : 'Unknown distance'}</p>
            <p>Phone: ${donor.phone}</p>
            <p>Email: ${donor.email || 'N/A'}</p>
            <small style="color:#888">Tap for medical details</small>
        </div>
    `).join('');
}

async function loadUrgentRequests() {
    const response = await fetch('/api/urgent-requests');
    const requests = await response.json();
    const list = document.getElementById('urgent-list');
    if (!list) return;
    list.innerHTML = requests.map(req => `
        <div class="record-card urgent-card">
            <h3>${req.patient_name} (Urgent)</h3>
            <p>${req.blood_group} • ${req.city}</p>
            <p>${req.hospital}</p>
            <p>${req.details}</p>
            <small>${new Date(req.created_at).toLocaleString()}</small>
        </div>
    `).join('');
}

async function loadSmsLog() {
    const response = await fetch('/api/sms-log');
    const logs = await response.json();
    const list = document.getElementById('sms-log');
    if (!list) return;
    list.innerHTML = logs.map(row => `
        <div class="record-card">
            <h3>SMS to ${row.donor_name || 'Unknown'}</h3>
            <p>${row.donor_phone}</p>
            <p>${row.message}</p>
            <small>${new Date(row.sent_at).toLocaleString()}</small>
        </div>
    `).join('');
}

async function findDonorByKey() {
    const key = document.getElementById('donor_key')?.value?.trim() || '';
    if (!key) {
        showBanner('Enter donor token/id first.', 'error');
        return;
    }

    try {
        const response = await fetch(`/api/find-donor?key=${encodeURIComponent(key)}`);
        const result = await response.json();

        const list = document.getElementById('donor-search-results');
        if (!list) return;

        if (!result.success || !result.donor) {
            list.innerHTML = '<div class="record-card"><p>Donor not found.</p></div>';
            return;
        }

        const donor = result.donor;
        list.innerHTML = `
            <div class="record-card">
                <div class="card-tag">${donor.token || 'No ID'}</div>
                <h3>${donor.name}</h3>
                <p>${donor.blood_group} • ${donor.city}</p>
                <p>${donor.address || 'Address not provided'}</p>
                <p>${donor.phone}</p>
                <p>${donor.email || ''}</p>
            </div>
        `;
    } catch (e) {
        console.error('findDonorByKey error:', e);
        showBanner('Unable to find donor right now.', 'error');
    }
}

async function searchDonors() {
    const bloodGroup = document.getElementById('search_blood_group')?.value || '';
    const city = document.getElementById('search_city')?.value || '';
    const list = document.getElementById('donor-search-results');

    if (!list) return;

    list.innerHTML = '<div class="record-card"><p>Searching donors...</p></div>';

    let url = `/api/search-donors?blood_group=${encodeURIComponent(bloodGroup)}&city=${encodeURIComponent(city)}`;

    try {
        const response = await fetch(url);
        const donors = await response.json();

        if (donors.length > 0) {
            list.innerHTML = donors.map(donor => `
                <div class="record-card donor-clickable" onclick="showDonorDetails(${donor.id})" style="cursor:pointer">
                    <div class="card-tag">${donor.token || 'ID'}</div>
                    <h3>${donor.name}</h3>
                    <p>${donor.blood_group} • ${donor.city}</p>
                    <p>${donor.address || 'Address not provided'}</p>
                    <p>${donor.phone} <a href="tel:${donor.phone}" class="btn-call" onclick="event.stopPropagation()">📞 Call</a></p>
                    <p>${donor.email || ''}</p>
                    <small style="color:#888">Tap for medical details</small>
                </div>
            `).join('');
        } else {
            list.innerHTML = '<div class="record-card"><p>No donors found matching your criteria.</p></div>';
        }

        const mapId = document.getElementById('patient-map') ? 'patient-map' : 'search-map';
        const map = initializeMap(mapId);
        if (map) {
            addMarkers(map, donors, {
                type: 'donor',
                popup: donor => `<strong>${donor.name}</strong><br>${donor.blood_group}<br>${donor.city}`
            });
        }
    } catch (e) {
        list.innerHTML = '<div class="record-card"><p>Unable to search donors right now. Please try again.</p></div>';
        console.error('searchDonors error:', e);
    }
}

async function createPatientBloodRequest() {
    const patientName = document.getElementById('patient_name')?.value || '';
    const bloodGroup = document.getElementById('request_blood_group')?.value || '';
    const city = document.getElementById('request_city')?.value || '';
    const hospital = document.getElementById('hospital')?.value || '';
    const details = document.getElementById('details')?.value || '';
    const age = document.getElementById('request_age')?.value || null;
    const sex = document.getElementById('request_sex')?.value || '';
    const latitude = document.getElementById('request_latitude')?.value || null;
    const longitude = document.getElementById('request_longitude')?.value || null;

    if (!patientName || !bloodGroup || !city || !hospital) {
        showBanner('Please fill all required fields', 'error');
        return;
    }

    const response = await fetch('/api/patient-blood-request', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ patient_name: patientName, blood_group: bloodGroup, city, hospital, details, latitude, longitude, age, sex })
    });
    const result = await response.json();
    showBanner(result.message, result.success ? 'success' : 'error');
    if (result.success) {
        document.getElementById('patient_name').value = '';
        document.getElementById('request_blood_group').value = '';
        document.getElementById('request_city').value = '';
        document.getElementById('hospital').value = '';
        document.getElementById('details').value = '';
        if (document.getElementById('request_latitude')) document.getElementById('request_latitude').value = '';
        if (document.getElementById('request_longitude')) document.getElementById('request_longitude').value = '';
        
        // For standard patient requests, this might not have notified donors since urgent=false,
        // but if it triggers notification, we handle it:
        if (result.notified_donors) {
            renderNotifiedDonors(result.notified_donors, 'patient-notified-donors');
        }

        setTimeout(() => searchDonors(), 2000);
    }
}

async function loadDashboardMap() {
    const map = initializeMap('admin-map');
    if (!map) return;
    const [donorRes, requestRes] = await Promise.all([fetch('/api/donors'), fetch('/api/requests')]);
    const donors = await donorRes.json();
    const requests = await requestRes.json();
    addMarkers(map, donors, {
        type: 'donor',
        popup: donor => `<strong>${donor.name}</strong><br>${donor.blood_group}<br>${donor.city}`
    });
    addMarkers(map, requests, {
        type: 'request',
        popup: req => `<strong>${req.patient_name}</strong><br>${req.blood_group} needed<br>${req.city}`
    });
}

async function loadBloodNeededMap() {
    const map = initializeMap('search-map');
    if (!map) return;
    const response = await fetch('/api/donors');
    const donors = await response.json();
    addMarkers(map, donors, {
        type: 'donor',
        popup: donor => `<strong>${donor.name}</strong><br>${donor.blood_group}<br>${donor.city}`
    });
}

async function loadUrgentMap() {
    const map = initializeMap('urgent-map');
    if (!map) return;
    const [donorsResponse, urgentResponse] = await Promise.all([fetch('/api/donors'), fetch('/api/urgent-requests')]);
    const donors = await donorsResponse.json();
    const requests = await urgentResponse.json();
    addMarkers(map, donors, {
        type: 'donor',
        popup: donor => `<strong>${donor.name}</strong><br>${donor.blood_group}<br>${donor.city}`
    });
    addMarkers(map, requests, {
        type: 'urgent',
        popup: req => `<strong>${req.patient_name}</strong><br>${req.blood_group} urgent<br>${req.city}`
    });
}

async function loadUserMap() {
    const map = initializeMap('user-map');
    if (!map) return;
    const response = await fetch('/api/requests');
    const requests = await response.json();
    addMarkers(map, requests, {
        type: 'request',
        popup: req => `<strong>${req.patient_name}</strong><br>${req.blood_group} needed<br>${req.city}`
    });
}

async function loadPatientMap() {
    const map = initializeMap('patient-map');
    if (!map) return;
    try {
        const [donorRes, requestRes] = await Promise.all([fetch('/api/donors'), fetch('/api/urgent-requests')]);
        const donors = await donorRes.json();
        const requests = await requestRes.json();
        addMarkers(map, donors, {
            type: 'donor',
            popup: donor => `<strong>${donor.name}</strong><br>${donor.blood_group}<br>${donor.city}`
        });
        addMarkers(map, requests, {
            type: 'urgent',
            popup: req => `<strong>${req.patient_name}</strong><br>${req.blood_group} needed<br>${req.city}`
        });
    } catch (e) {
        console.error('Map loading error:', e);
    }
}

async function loadPatientHistory() {
    const list = document.getElementById('patient-history-list');
    if (!list) return;
    try {
        const response = await fetch('/api/patient-history');
        const history = await response.json();
        list.innerHTML = history.map(req => `
            <div class="record-card">
                <div class="card-tag">${req.token || 'REQ'}</div>
                <h3>${req.hospital}</h3>
                <p>Blood Group: ${req.blood_group}</p>
                <p>City: ${req.city}</p>
                <small>${new Date(req.created_at).toLocaleString()}</small>
            </div>
        `).join('');
    } catch (e) {
        console.error('Patient history error:', e);
        list.innerHTML = '<p>Unable to load history.</p>';
    }
}

function switchDashboardTab(tabId) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panels > div').forEach(p => p.classList.remove('active'));
    
    const btn = document.getElementById(`tab-${tabId}`);
    const panel = document.getElementById(`panel-${tabId}`);
    
    if (btn) btn.classList.add('active');
    if (panel) panel.classList.add('active');
    
    // Invalidate map sizes since they might have been initialized while hidden
    setTimeout(() => {
        Object.values(mapInstances).forEach(map => {
            if (map && typeof map.invalidateSize === 'function') {
                map.invalidateSize();
            }
        });
    }, 100);
}

window.addEventListener('load', () => {
    const body = document.body;
    if (body.classList.contains('dashboard-page')) {
        loadStats();
        loadDashboardMap();
    }
    if (body.classList.contains('donate-page')) {
        loadDonors();
        loadDonations();
        const dateField = document.getElementById('donation_date');
        if (dateField) {
            dateField.value = new Date().toISOString().slice(0, 10);
        }
    }
    if (body.classList.contains('blood-needed-page')) {
        loadRequests();
        loadBloodNeededMap();
    }
    if (body.classList.contains('urgent-page')) {
        loadUrgentRequests();
        loadSmsLog();
        loadUrgentMap();
    }
    if (body.classList.contains('donor-dashboard-page')) {
        loadRequests();
        loadUserMap();
    }
    if (body.classList.contains('patient-dashboard-page')) {
        searchDonors();
        loadPatientMap();
        loadPatientHistory();
    }
});

// Show donor details modal with medical info
async function showDonorDetails(donorId) {
    try {
        const response = await fetch(`/api/donor-details/${donorId}`);
        const result = await response.json();
        if (!result.success || !result.donor) {
            showBanner('Could not load donor details.', 'error');
            return;
        }
        const d = result.donor;
        const med = d.last_donation;

        let medicalHtml = '<p style="color:#999">No donation/medical records yet.</p>';
        if (med) {
            medicalHtml = `
                <table style="width:100%;border-collapse:collapse;margin-top:8px">
                    <tr><td style="padding:4px 8px;font-weight:bold">Age</td><td style="padding:4px 8px">${med.age || 'N/A'}</td></tr>
                    <tr><td style="padding:4px 8px;font-weight:bold">Sex</td><td style="padding:4px 8px">${med.sex || 'N/A'}</td></tr>
                    <tr><td style="padding:4px 8px;font-weight:bold">Blood Pressure</td><td style="padding:4px 8px">${med.bp || 'N/A'}</td></tr>
                    <tr><td style="padding:4px 8px;font-weight:bold">Sugar Level</td><td style="padding:4px 8px">${med.sugar || 'N/A'}</td></tr>
                    <tr><td style="padding:4px 8px;font-weight:bold">Medical Conditions</td><td style="padding:4px 8px">${med.medical_condition || 'None reported'}</td></tr>
                    <tr><td style="padding:4px 8px;font-weight:bold">Last Donation</td><td style="padding:4px 8px">${med.amount_ml || '?'} ml on ${med.date || 'N/A'}</td></tr>
                    <tr><td style="padding:4px 8px;font-weight:bold">Notes</td><td style="padding:4px 8px">${med.notes || 'None'}</td></tr>
                </table>
            `;
        }

        // Remove old modal if exists
        const oldModal = document.getElementById('donor-detail-modal');
        if (oldModal) oldModal.remove();

        const modal = document.createElement('div');
        modal.id = 'donor-detail-modal';
        modal.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.6);display:flex;align-items:center;justify-content:center;z-index:9999;padding:16px';
        modal.innerHTML = `
            <div style="background:#1e1e2e;color:#fff;border-radius:16px;max-width:500px;width:100%;max-height:80vh;overflow-y:auto;padding:24px;position:relative;box-shadow:0 8px 32px rgba(0,0,0,0.4)">
                <button onclick="closeDonorModal()" style="position:absolute;top:12px;right:16px;background:none;border:none;color:#fff;font-size:24px;cursor:pointer">&times;</button>
                <h2 style="margin:0 0 4px 0">${d.name}</h2>
                <span style="background:#e74c3c;color:#fff;padding:2px 10px;border-radius:8px;font-size:13px">${d.blood_group}</span>
                <span style="background:#3498db;color:#fff;padding:2px 10px;border-radius:8px;font-size:13px;margin-left:6px">${d.token || ''}</span>
                <div style="margin-top:12px">
                    <p><strong>Phone:</strong> ${d.phone} <a href="tel:${d.phone}" style="color:#3498db">Call</a></p>
                    <p><strong>Email:</strong> ${d.email || 'N/A'}</p>
                    <p><strong>Address:</strong> ${d.address || 'N/A'}, ${d.city || ''}</p>
                </div>
                <hr style="border-color:#333;margin:12px 0">
                <h3 style="margin:0 0 8px 0">Medical Information</h3>
                ${medicalHtml}
            </div>
        `;
        modal.addEventListener('click', (e) => { if (e.target === modal) closeDonorModal(); });
        document.body.appendChild(modal);
    } catch (e) {
        console.error('showDonorDetails error:', e);
        showBanner('Unable to load donor details.', 'error');
    }
}

function closeDonorModal() {
    const modal = document.getElementById('donor-detail-modal');
    if (modal) modal.remove();
}

// Ensure inline onclick handlers can always find these functions
window.captureLocation = captureLocation;
window.registerDonor = registerDonor;
window.recordDonation = recordDonation;
window.createBloodRequest = createBloodRequest;
window.createUrgentRequest = createUrgentRequest;
window.findDonorByKey = findDonorByKey;
window.createPatientBloodRequest = createPatientBloodRequest;
window.switchDashboardTab = switchDashboardTab;
window.loadPatientHistory = loadPatientHistory;
window.showDonorDetails = showDonorDetails;
window.closeDonorModal = closeDonorModal;
