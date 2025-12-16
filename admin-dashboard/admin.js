/**
 * Admin Dashboard - Client-side Logic
 */

const API_BASE_URL = window.location.origin.includes('localhost')
    ? 'http://localhost:8000'
    : window.location.origin;

let adminToken = localStorage.getItem('admin_token');
let currentUserDetails = null;

// Utility functions
function showToast(message, type = 'success') {
    const colors = {
        success: 'bg-green-500',
        error: 'bg-red-500',
        info: 'bg-blue-500'
    };

    const toast = document.createElement('div');
    toast.className = `fixed top-4 right-4 ${colors[type]} text-white px-6 py-3 rounded-lg shadow-lg z-50`;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => toast.remove(), 3000);
}

async function apiRequest(endpoint, options = {}) {
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers
    };

    if (adminToken) {
        headers['Authorization'] = `Bearer ${adminToken}`;
    }

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        ...options,
        headers
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Request failed');
    }

    return response.json();
}

// Authentication
async function handleAdminLogin(e) {
    e.preventDefault();

    const username = document.getElementById('admin-username').value;
    const password = document.getElementById('admin-password').value;

    try {
        const data = await apiRequest('/api/admin/auth', {
            method: 'POST',
            body: JSON.stringify({ username, password })
        });

        adminToken = data.access_token;
        localStorage.setItem('admin_token', adminToken);

        showDashboard();
        loadDashboardData();
    } catch (error) {
        showToast(error.message, 'error');
    }
}

function adminLogout() {
    adminToken = null;
    localStorage.removeItem('admin_token');
    showLoginScreen();
}

function showDashboard() {
    document.getElementById('login-screen').classList.add('hidden');
    document.getElementById('admin-dashboard').classList.remove('hidden');
}

function showLoginScreen() {
    document.getElementById('login-screen').classList.remove('hidden');
    document.getElementById('admin-dashboard').classList.add('hidden');
}

// Load dashboard data
async function loadDashboardData() {
    try {
        const [analytics, users] = await Promise.all([
            apiRequest('/api/admin/analytics'),
            apiRequest('/api/admin/users?limit=100')
        ]);

        // Update analytics cards
        document.getElementById('total-users').textContent = analytics.total_users;
        document.getElementById('active-subs').textContent = analytics.active_subscribers;
        document.getElementById('monthly-revenue').textContent = `₪${analytics.monthly_revenue.toFixed(0)}`;
        document.getElementById('churn-rate').textContent = `${analytics.churn_rate.toFixed(1)}%`;

        // Update users table
        renderUsersTable(users);

    } catch (error) {
        if (error.message.includes('403') || error.message.includes('401')) {
            adminLogout();
        }
        showToast('שגיאה בטעינת נתונים', 'error');
    }
}

function renderUsersTable(users) {
    const tbody = document.getElementById('users-table-body');

    if (users.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="px-6 py-4 text-center text-gray-500">אין משתמשים</td></tr>';
        return;
    }

    tbody.innerHTML = users.map(user => {
        const statusBadge = user.is_active
            ? '<span class="px-2 py-1 bg-green-100 text-green-800 text-xs rounded-full">פעיל</span>'
            : '<span class="px-2 py-1 bg-gray-100 text-gray-800 text-xs rounded-full">לא פעיל</span>';

        const expiryDate = user.subscription_end_date
            ? new Date(user.subscription_end_date).toLocaleDateString('he-IL')
            : '-';

        const joinDate = new Date(user.created_at).toLocaleDateString('he-IL');

        return `
            <tr class="hover:bg-gray-50">
                <td class="px-6 py-4 text-sm">${user.id}</td>
                <td class="px-6 py-4 text-sm font-medium">${user.email}</td>
                <td class="px-6 py-4 text-sm">${user.telegram_chat_id || '-'}</td>
                <td class="px-6 py-4">${statusBadge}</td>
                <td class="px-6 py-4 text-sm">${user.plan || 'none'}</td>
                <td class="px-6 py-4 text-sm">${expiryDate}</td>
                <td class="px-6 py-4 text-sm">${joinDate}</td>
                <td class="px-6 py-4">
                    <button onclick="viewUser(${user.id})" class="text-blue-600 hover:text-blue-800 text-sm font-medium">
                        פרטים
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

async function refreshUsers() {
    showToast('מרענן נתונים...', 'info');
    await loadDashboardData();
    showToast('הנתונים עודכנו', 'success');
}

// User details modal
async function viewUser(userId) {
    try {
        const users = await apiRequest(`/api/admin/users?limit=1000`);
        const user = users.find(u => u.id === userId);

        if (!user) {
            showToast('משתמש לא נמצא', 'error');
            return;
        }

        currentUserDetails = user;

        const detailsHTML = `
            <div class="space-y-3">
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <p class="text-sm text-gray-600">ID</p>
                        <p class="font-bold">${user.id}</p>
                    </div>
                    <div>
                        <p class="text-sm text-gray-600">אימייל</p>
                        <p class="font-bold">${user.email}</p>
                    </div>
                </div>
                
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <p class="text-sm text-gray-600">Telegram Chat ID</p>
                        <p class="font-mono">${user.telegram_chat_id || 'לא מחובר'}</p>
                    </div>
                    <div>
                        <p class="text-sm text-gray-600">סטטוס</p>
                        <p class="font-bold ${user.is_active ? 'text-green-600' : 'text-gray-600'}">
                            ${user.is_active ? 'פעיל ✓' : 'לא פעיל'}
                        </p>
                    </div>
                </div>
                
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <p class="text-sm text-gray-600">תוכנית</p>
                        <p class="font-bold">${user.plan || 'none'}</p>
                    </div>
                    <div>
                        <p class="text-sm text-gray-600">תוקף מנוי</p>
                        <p>${user.subscription_end_date ? new Date(user.subscription_end_date).toLocaleDateString('he-IL') : '-'}</p>
                    </div>
                </div>
                
                <div>
                    <p class="text-sm text-gray-600">הצטרף בתאריך</p>
                    <p>${new Date(user.created_at).toLocaleDateString('he-IL')}</p>
                </div>
            </div>
        `;

        document.getElementById('user-details').innerHTML = detailsHTML;
        document.getElementById('user-modal').classList.remove('hidden');

    } catch (error) {
        showToast('שגיאה בטעינת פרטי משתמש', 'error');
    }
}

function closeUserModal() {
    document.getElementById('user-modal').classList.add('hidden');
    currentUserDetails = null;
}

async function extendSubscription() {
    if (!currentUserDetails) return;

    if (!confirm(`האם להאריך את המנוי של ${currentUserDetails.email} ב-30 ימים?`)) return;

    try {
        // This would call an admin endpoint to extend subscription
        // For now, we'll show a placeholder
        showToast('תכונה זו תהיה זמינה בקרוב', 'info');
        closeUserModal();

    } catch (error) {
        showToast('שגיאה בהארכת מנוי', 'error');
    }
}

async function deactivateUser() {
    if (!currentUserDetails) return;

    if (!confirm(`האם להשעות את ${currentUserDetails.email}?`)) return;

    try {
        // This would call an admin endpoint to deactivate user
        showToast('תכונה זו תהיה זמינה בקרוב', 'info');
        closeUserModal();

    } catch (error) {
        showToast('שגיאה בהשעיית משתמש', 'error');
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    if (adminToken) {
        showDashboard();
        loadDashboardData();
    } else {
        showLoginScreen();
    }
});
