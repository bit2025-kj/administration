
const API_URL = 'https://administration-otev.onrender.com';

let ws; // WebSocket sera créé plus tard
let notificationCount = 0;
let adminToken = localStorage.getItem('admin_token'); // ✅ Récupération initiale
let currentTab = 'pending';

// 🔄 SYNCHRONISER TOKEN DYNAMIQUEMENT
function syncToken() {
    adminToken = localStorage.getItem('admin_token');
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.close(); // Force reconnexion WS avec nouveau token
        setTimeout(connectWebSocket, 1000);
    }
}

// 🔐 API REQUEST avec JWT AMÉLIORÉ
async function apiRequest(url, options = {}) {
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers,
        ...(adminToken && { 'Authorization': `Bearer ${adminToken}` })
    };
    
    const response = await fetch(url, { ...options, headers });
    
    if (response.status === 401) {
        localStorage.removeItem('admin_token');
        adminToken = null;
        // Relogin automatique si page admin
        if (window.location.pathname.includes('admin.html')) {
            showSuccess('🔐 Token expiré - Reconnexion...');
            setTimeout(() => window.location.href = '/login.html', 1500);
        }
        throw new Error('Unauthorized');
    }
    
    return response;
}

// 🚪 LOGOUT
function logout() {
    localStorage.removeItem('admin_token');
    adminToken = null;
    if (ws) ws.close();
    window.location.href = '/login.html';
}

// 👑 CHARGE INFOS ADMIN
async function loadAdminInfo() {
    try {
        const response = await apiRequest(`${API_URL}/admin/me`);
        const data = await response.json();
        document.getElementById('adminInfo').textContent = `👑 ${data.name} (${data.phone})`;
    } catch (error) {
        document.getElementById('adminInfo').textContent = '👑 Erreur';
        console.error('loadAdminInfo error:', error);
    }
}

// 🔌 WEBSOCKET ROBUSTE
function connectWebSocket() {
    if (!adminToken) return;

    try {
        const wsUrl = `${API_URL.replace('https', 'wss')}/ws/admin?token=${adminToken}`;
        ws = new WebSocket(wsUrl);
        
        ws.onopen = () => {
            const status1 = document.getElementById('connectionStatus');
            const status2 = document.getElementById('connectionStatus2');
            if (status1) {
                status1.textContent = '🟢 Connecté';
                status1.className = 'status connected';
            }
            if (status2) status2.textContent = '🟢 OK';
        };
        
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'new_request') {
                notificationCount++;
                updateBadge();
                showNotification(data);
                if (currentTab === 'pending') loadPending();
                playNotificationSound();
            } else if (data.type === 'validated') {
                if (currentTab === 'pending') loadPending();
            }
        };
        
        ws.onclose = () => {
            const status1 = document.getElementById('connectionStatus');
            const status2 = document.getElementById('connectionStatus2');
            if (status1) {
                status1.textContent = '🔴 Reconnexion...';
                status1.className = 'status disconnected';
            }
            if (status2) status2.textContent = '🔴 Déconnecté';
            setTimeout(connectWebSocket, 3000);
        };
        
        ws.onerror = (error) => {
            console.error('WS Error:', error);
            setTimeout(connectWebSocket, 5000);
        };
    } catch (error) {
        console.error('WS Connection failed:', error);
        setTimeout(connectWebSocket, 5000);
    }
}

// 🔔 NOTIFICATION POPUP
function showNotification(data) {
    const notification = document.createElement('div');
    notification.className = 'notification-popup';
    notification.innerHTML = `
        <h3>🆕 Nouvelle demande !</h3>
        <p><strong>📱 Device:</strong> ${data.device_id.slice(0,25)}${data.device_id.length > 25 ? '...' : ''}</p>
        <p><strong>📞 Tel:</strong> ${data.phone}</p>
        <p><strong>📅 Mois:</strong> ${data.months}</p>
        <p><strong>🔑 Clé:</strong> ${data.key}</p>
        <div style="display: flex; gap: 10px; margin-top: 15px; flex-wrap: wrap;">
            <button class="btn validate" onclick="validate('${data.device_id}'); this.closest('.notification-popup').remove();">
                ✅ VALIDER
            </button>
            <button class="btn" onclick="this.closest('.notification-popup').remove();" style="background: rgba(255,255,255,0.2);">
                ⏭️ Plus tard
            </button>
        </div>
    `;
    document.body.appendChild(notification);
    
    setTimeout(() => {
        if (notification.parentNode) notification.remove();
    }, 20000);
}

// 📋 CHARGE TABLEAU EN ATTENTE
async function loadPending() {
    try {
        const response = await apiRequest(`${API_URL}/admin/pending`);
        const pending = await response.json();
        
        document.getElementById('pendingCount').textContent = pending.length;
        document.getElementById('totalCount').textContent = pending.length;
        
        const tbody = document.querySelector('#pendingTable tbody');
        if (tbody) tbody.innerHTML = '';
        
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
        console.error('Erreur loadPending:', error);
    }
}

// ✅ HISTORIQUE VALIDATIONS
async function loadHistory() {
    try {
        const response = await apiRequest(`${API_URL}/admin/validations`);
        const history = await response.json();
        
        const tbody = document.querySelector('#historyTable tbody');
        if (tbody) tbody.innerHTML = '';
        
        history.forEach(item => {
            const row = tbody.insertRow();
            row.innerHTML = `
                <td>${item.device_id}</td>
                <td>${item.client_phone}</td>
                <td>${item.months}</td>
                <td><span class="key">${item.key}</span></td>
                <td><strong style="color: #007bff;">${item.admin}</strong></td>
                <td>${new Date(item.validated_at).toLocaleString('fr-FR')}</td>
            `;
        });
    } catch (error) {
        console.error('Erreur historique:', error);
    }
}

// 🔀 ONGLETS
function showTab(tab, event) {
    currentTab = tab;
    document.querySelectorAll('.table-container').forEach(el => el.style.display = 'none');
    const targetTab = document.getElementById(tab + 'Tab');
    if (targetTab) targetTab.style.display = 'block';
    
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    if (event && event.target) event.target.classList.add('active');
    
    if (tab === 'pending') loadPending();
    else if (tab === 'history') loadHistory();
}

// ✅ VALIDER ABONNEMENT
async function validate(deviceId) {
    if (confirm(`Valider abonnement ${deviceId.slice(0,25)}... ?`)) {
        try {
            const response = await apiRequest(`${API_URL}/admin/validate/${deviceId}`, { method: 'POST' });
            if (response.ok) {
                notificationCount = Math.max(0, notificationCount - 1);
                updateBadge();
                if (currentTab === 'pending') loadPending();
                showSuccess('✅ Abonnement validé et LOGGÉ !');
            }
        } catch (error) {
            alert('❌ Erreur: ' + error.message);
        }
    }
}

// 🗑️ VIDER TOUT
async function clearAllPending() {
    if (confirm('🗑️ Vider TOUTES les demandes en attente ?')) {
        try {
            await apiRequest(`${API_URL}/admin/clear`, { method: 'POST' });
            loadPending();
            showSuccess('✅ Base vidée !');
        } catch (error) {
            alert('❌ Erreur: ' + error.message);
        }
    }
}

// 🔔 BADGE NOTIFICATIONS
function updateBadge() {
    const badge = document.getElementById('notificationBadge');
    if (badge) badge.textContent = notificationCount;
}

// 🔊 SON NOTIFICATION
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
    oscillator.start(audioContext.currentTime);
    oscillator.stop(audioContext.currentTime + 0.5);
}

// 🎉 MESSAGE SUCCÈS
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

// 🚀 INITIALISATION COMPLÈTE
document.addEventListener('DOMContentLoaded', async () => {
    syncToken(); // ✅ Synchronise token au démarrage
    
    if (!adminToken) {
        window.location.href = '/login.html';
        return;
    }
    
    await loadAdminInfo();
    connectWebSocket();
    loadPending();
    setInterval(() => {
        if (currentTab === 'pending') loadPending();
    }, 5000);
    updateBadge();
    
    // Écoute les changements de storage (autre onglet)
    window.addEventListener('storage', (e) => {
        if (e.key === 'admin_token') syncToken();
    });
});
