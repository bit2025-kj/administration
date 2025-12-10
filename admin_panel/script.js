// script.js COMPLET - Admin Dashboard avec Profils Clients

// 🌐 API dynamique
const API_URL = window.location.origin;
let ws, notificationCount = 0, adminToken = localStorage.getItem('admin_token');
let currentTab = 'pending', selectedClientId = null;

// 🔄 SYNCHRONISER TOKEN
function syncToken() {
    adminToken = localStorage.getItem('admin_token');
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.close();
        setTimeout(connectWebSocket, 1000);
    }
}

// 🔐 API REQUEST sécurisée
async function apiRequest(url, options = {}) {
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers,
        ...(adminToken && { 'Authorization': `Bearer ${adminToken}` })
    };
    
    const response = await fetch(url, { ...options, headers });
    
    if (response.status === 401) {
        localStorage.removeItem('admin_token');
        window.location.href = '/login.html';
        throw new Error('Unauthorized');
    }
    return response;
}

// 🚪 LOGOUT
function logout() {
    localStorage.removeItem('admin_token');
    if (ws) ws.close();
    window.location.href = '/login.html';
}

// 👑 CHARGE ADMIN
async function loadAdminInfo() {
    try {
        const data = await apiRequest(`${API_URL}/admin/me`).then(r => r.json());
        document.getElementById('adminInfo').textContent = `👑 ${data.name} (${data.phone})`;
    } catch (error) {
        document.getElementById('adminInfo').textContent = '👑 Erreur';
    }
}

// 🔌 WEBSOCKET
function connectWebSocket() {
    if (!adminToken) return;
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const wsUrl = `${protocol}://${window.location.host}/ws/admin?token=${adminToken}`;
    ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
        document.getElementById('connectionStatus').textContent = '🟢 Connecté';
        document.getElementById('connectionStatus2').textContent = '🟢 OK';
    };
    
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'new_request') {
            notificationCount++;
            updateBadge();
            showNotification(data);
            if (currentTab === 'pending') loadPending();
            playNotificationSound();
        }
    };
    
    ws.onclose = () => {
        document.getElementById('connectionStatus').textContent = '🔴 Reconnexion...';
        document.getElementById('connectionStatus2').textContent = '🔴 Déconnecté';
        setTimeout(connectWebSocket, 3000);
    };
}

// 🔔 NOTIFICATION
function showNotification(data) {
    const notification = document.createElement('div');
    notification.className = 'notification-popup';
    notification.innerHTML = `
        <h3>🆕 Nouvelle demande !</h3>
        <p><strong>📱 Device:</strong> ${data.device_id.slice(0,25)}${data.device_id.length > 25 ? '...' : ''}</p>
        <p><strong>📞 Tel:</strong> ${data.phone}</p>
        <p><strong>📅 Mois:</strong> ${data.months}</p>
        <p><strong>🔑 Clé:</strong> ${data.key}</p>
        <div style="display: flex; gap: 10px; margin-top: 15px;">
            <button class="btn validate" onclick="validate('${data.device_id}'); this.closest('.notification-popup').remove();">✅ VALIDER</button>
            <button class="btn" onclick="this.closest('.notification-popup').remove();" style="background: rgba(255,255,255,0.2);">⏭️ Plus tard</button>
        </div>
    `;
    document.body.appendChild(notification);
    setTimeout(() => notification.remove(), 20000);
}

// 📋 EN ATTENTE
async function loadPending() {
    try {
        const pending = await apiRequest(`${API_URL}/admin/pending`).then(r => r.json());
        document.getElementById('pendingCount').textContent = pending.length;
        document.getElementById('totalCount').textContent = pending.length;
        
        const tbody = document.querySelector('#pendingTable tbody');
        tbody.innerHTML = '';
        pending.forEach(item => {
            const row = tbody.insertRow();
            row.innerHTML = `
                <td>${item.device_id.slice(0,8)}...</td>
                <td title="${item.device_id}">${item.device_id.slice(0,25)}${item.device_id.length > 25 ? '...' : ''}</td>
                <td>${item.phone}</td>
                <td>${item.months}</td>
                <td><span class="key">${item.key}</span></td>
                <td>${new Date(item.created).toLocaleString('fr-FR')}</td>
                <td><button class="btn validate" onclick="validate('${item.device_id}')">✅ Valider</button></td>
            `;
        });
    } catch (error) {
        console.error('loadPending:', error);
    }
}

// 📈 HISTORIQUE GLOBAL
async function loadHistory() {
    try {
        const history = await apiRequest(`${API_URL}/admin/validations`).then(r => r.json());
        const tbody = document.querySelector('#historyTable tbody');
        tbody.innerHTML = '';
        history.forEach(item => {
            const row = tbody.insertRow();
            row.innerHTML = `
                <td>${item.id}</td>
                <td>${item.client_phone}</td>
                <td>${item.months}</td>
                <td><span class="key">${item.key}</span></td>
                <td><strong style="color: #007bff;">${item.admin}</strong></td>
                <td>${new Date(item.validated_at).toLocaleString('fr-FR')}</td>
            `;
        });
    } catch (error) {
        console.error('loadHistory:', error);
    }
}

// ✅ 👥 PROFILS CLIENTS - LISTE
async function loadClients() {
    try {
        const data = await apiRequest(`${API_URL}/admin/clients`).then(r => r.json());
        document.getElementById('clientsCount').textContent = data.clients.length;
        document.getElementById('clientsList').innerHTML = 
            data.clients.map(c => `
                <div class="client-card" onclick="loadClientHistory('${c.device_id}')">
                    <h4>${c.name}</h4>
                    <p>📱 ${c.phone}</p>
                    <p><small>🔧 ${c.device_id.slice(-8)}</small></p>
                </div>
            `).join('');
        document.getElementById('clientDetail').style.display = 'none';
    } catch (error) {
        console.error('loadClients:', error);
        document.getElementById('clientsList').innerHTML = '<p>Erreur chargement clients</p>';
    }
}

// ✅ HISTORIQUE CLIENT SPÉCIFIQUE
async function loadClientHistory(deviceId) {
    try {
        const data = await apiRequest(`${API_URL}/admin/client/${deviceId}/history`).then(r => r.json());
        document.getElementById('clientDetail').style.display = 'block';
        document.getElementById('clientTitle').textContent = `📋 Historique ${deviceId.slice(-8)}`;
        document.getElementById('clientHistory').innerHTML = 
            data.history.length ? data.history.map(v => `
                <div class="validation-item">
                    <div>
                        <strong>👤 ${v.admin_name}</strong> 
                        <span style="color: #666;">${v.months} mois</span>
                    </div>
                    <div style="font-size: 0.9em; color: #888;">
                        📅 ${new Date(v.validated_at).toLocaleDateString('fr-FR')}
                        <br>🔑 ${v.activation_key}
                    </div>
                </div>
            `).join('') : '<p>Aucune validation pour ce client</p>';
    } catch (error) {
        console.error('loadClientHistory:', error);
    }
}

// 🔀 ONGLETS AMÉLIORÉS
function showTab(tabName, event) {
    currentTab = tabName;
    
    // Masquer tous
    document.querySelectorAll('.table-container').forEach(tab => tab.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    
    // Activer cible
    event.target.classList.add('active');
    document.getElementById(tabName + 'Tab').classList.add('active');
    
    // Charger contenu
    switch(tabName) {
        case 'pending': loadPending(); break;
        case 'history': loadHistory(); break;
        case 'clients': loadClients(); break;
    }
}

// ✅ VALIDER
async function validate(deviceId) {
    if (confirm(`Valider abonnement ${deviceId.slice(0,25)}... ?`)) {
        try {
            const response = await apiRequest(`${API_URL}/admin/validate/${deviceId}`, { method: 'POST' });
            if (response.ok) {
                notificationCount = Math.max(0, notificationCount - 1);
                updateBadge();
                if (currentTab === 'pending') loadPending();
                showSuccess('✅ Abonnement validé + LOGGÉ !');
            }
        } catch (error) {
            alert('❌ Erreur: ' + error.message);
        }
    }
}

// 🗑️ VIDER
async function clearAllPending() {
    if (confirm('🗑️ Vider TOUTES les demandes ?')) {
        try {
            await apiRequest(`${API_URL}/admin/clear`, { method: 'POST' });
            loadPending();
            showSuccess('✅ Demandes vidées !');
        } catch (error) {
            alert('❌ Erreur: ' + error.message);
        }
    }
}

// 🔔 UTILS
function updateBadge() {
    document.getElementById('notificationBadge').textContent = notificationCount;
}

function playNotificationSound() {
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const oscillator = audioContext.createOscillator();
    const gainNode = audioContext.createGain();
    oscillator.connect(gainNode);
    gainNode.connect(audioContext.destination);
    oscillator.frequency.value = 800;
    oscillator.type = 'sine';
    gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);
    oscillator.start();
    oscillator.stop(audioContext.currentTime + 0.5);
}

function showSuccess(message) {
    const snackbar = document.createElement('div');
    snackbar.style.cssText = `
        position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
        background: #28a745; color: white; padding: 15px 30px; border-radius: 25px;
        z-index: 10001; font-weight: 600; box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    `;
    snackbar.textContent = message;
    document.body.appendChild(snackbar);
    setTimeout(() => snackbar.remove(), 3000);
}

// 🚀 INITIALISATION
document.addEventListener('DOMContentLoaded', async () => {
    if (!adminToken) {
        window.location.href = '/login.html';
        return;
    }
    
    syncToken();
    await loadAdminInfo();
    connectWebSocket();
    loadPending();
    
    setInterval(() => {
        if (currentTab === 'pending') loadPending();
    }, 5000);
    
    window.addEventListener('storage', (e) => {
        if (e.key === 'admin_token') syncToken();
    });
});
