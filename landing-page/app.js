/**
 * Landing Page - Client-side Logic
 */

// Configuration
const API_BASE_URL = window.location.origin.includes('localhost')
    ? 'http://localhost:8000'
    : window.location.origin;

// TODO: Update this with your actual Telegram bot username from @BotFather
const TELEGRAM_BOT_USERNAME = "YOUR_BOT_USERNAME";  // ⚠️ CHANGE THIS IN PRODUCTION!

// State management
let authToken = localStorage.getItem('oracle_token');
let currentUser = null;

// Helper functions
function showError(message) {
    // Create error toast
    const toast = document.createElement('div');
    toast.className = 'fixed top-4 right-4 bg-red-500 text-white px-6 py-3 rounded-lg shadow-lg z-50 animate__animated animate__fadeInDown';
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('animate__fadeOutUp');
        setTimeout(() => toast.remove(), 1000);
    }, 3000);
}

function showSuccess(message) {
    const toast = document.createElement('div');
    toast.className = 'fixed top-4 right-4 bg-green-500 text-white px-6 py-3 rounded-lg shadow-lg z-50 animate__animated animate__fadeInDown';
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('animate__fadeOutUp');
        setTimeout(() => toast.remove(), 1000);
    }, 3000);
}

async function apiRequest(endpoint, options = {}) {
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers
    };

    if (authToken) {
        headers['Authorization'] = `Bearer ${authToken}`;
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

// Authentication functions
async function signup(email, password, tickers = []) {
    try {
        const data = await apiRequest('/api/auth/signup', {
            method: 'POST',
            body: JSON.stringify({ email, password, tickers })
        });

        authToken = data.access_token;
        localStorage.setItem('oracle_token', authToken);

        return data;
    } catch (error) {
        showError(error.message);
        throw error;
    }
}

async function login(email, password) {
    try {
        const data = await apiRequest('/api/auth/login', {
            method: 'POST',
            body: JSON.stringify({ email, password })
        });

        authToken = data.access_token;
        localStorage.setItem('oracle_token', authToken);

        return data;
    } catch (error) {
        showError(error.message);
        throw error;
    }
}

function logout() {
    authToken = null;
    currentUser = null;
    localStorage.removeItem('oracle_token');
    updateUI();
}

async function getCurrentUser() {
    try {
        currentUser = await apiRequest('/api/auth/me');
        return currentUser;
    } catch (error) {
        logout();
        return null;
    }
}

// Subscription functions
async function getSubscriptionStatus() {
    return await apiRequest('/api/subscription/status');
}

async function createSubscription(returnUrl) {
    return await apiRequest('/api/subscription/create', {
        method: 'POST',
        body: JSON.stringify({ return_url: returnUrl })
    });
}

async function cancelSubscription() {
    return await apiRequest('/api/subscription/cancel', {
        method: 'POST'
    });
}

// Portfolio functions
async function getPortfolio() {
    return await apiRequest('/api/portfolio');
}

async function addTicker(ticker) {
    return await apiRequest('/api/portfolio/ticker', {
        method: 'POST',
        body: JSON.stringify({ ticker })
    });
}

async function removeTicker(ticker) {
    return await apiRequest(`/api/portfolio/ticker/${ticker}`, {
        method: 'DELETE'
    });
}

// UI Update functions
function updateUI() {
    const loginBtn = document.getElementById('login-btn');
    const signupBtn = document.getElementById('signup-btn');
    const dashboardBtn = document.getElementById('dashboard-btn');

    if (authToken && currentUser) {
        if (loginBtn) loginBtn.style.display = 'none';
        if (signupBtn) signupBtn.style.display = 'none';
        if (dashboardBtn) {
            dashboardBtn.style.display = 'block';
            dashboardBtn.textContent = currentUser.email;
        }
    } else {
        if (loginBtn) loginBtn.style.display = 'block';
        if (signupBtn) signupBtn.style.display = 'block';
        if (dashboardBtn) dashboardBtn.style.display = 'none';
    }
}

// Modal functions
function openSignupModal() {
    document.getElementById('signup-modal').classList.remove('hidden');
}

function closeSignupModal() {
    document.getElementById('signup-modal').classList.add('hidden');
}

function openLoginModal() {
    document.getElementById('login-modal').classList.remove('hidden');
}

function closeLoginModal() {
    document.getElementById('login-modal').classList.add('hidden');
}

function openDashboard() {
    document.getElementById('dashboard-modal').classList.remove('hidden');
    loadDashboardData();
}

function closeDashboard() {
    document.getElementById('dashboard-modal').classList.add('hidden');
}

// Dashboard data loading
async function loadDashboard() {
    try {
        const [subscription, portfolio] = await Promise.all([
            getSubscriptionStatus(),
            getPortfolio()
        ]);

        // Update subscription info
        document.getElementById('subscription-status').textContent =
            subscription.is_active ? '✅ פעיל' : '❌ לא פעיל';
        document.getElementById('subscription-plan').textContent = subscription.plan || 'none';
        document.getElementById('subscription-expiry').textContent =
            subscription.subscription_end_date
                ? new Date(subscription.subscription_end_date).toLocaleDateString('he-IL')
                : '-';

        // Update portfolio
        const portfolioList = document.getElementById('portfolio-list');
        if (portfolio.tickers.length === 0) {
            portfolioList.innerHTML = '<li class="text-gray-500 text-center py-4">אין מניות בתיק</li>';
        } else {
            portfolioList.innerHTML = portfolio.tickers.map(ticker => `
                <li class="flex justify-between items-center bg-white p-3 rounded border">
                    <span class="font-bold">${ticker}</span>
                    <button onclick="handleRemoveTicker('${ticker}')" class="text-red-600 hover:text-red-800 text-sm">
                        הסר
                    </button>
                </li>
            `).join('');
        }

        // Update Telegram bot link
        const telegramLink = document.querySelector('a[href*="t.me"]');
        if (telegramLink && TELEGRAM_BOT_USERNAME !== "YOUR_BOT_USERNAME") {
            telegramLink.href = `https://t.me/${TELEGRAM_BOT_USERNAME}`;
        }

    } catch (error) {
        console.error('Failed to load dashboard:', error);
        showToast('שגיאה בטעינת הדשבורד', 'error');
    }
}

// Event handlers
async function handleSignup(e) {
    e.preventDefault();

    const email = document.getElementById('signup-email').value;
    const password = document.getElementById('signup-password').value;
    const tickers = document.getElementById('signup-tickers').value
        .split(',')
        .map(t => t.trim())
        .filter(t => t);

    try {
        await signup(email, password, tickers);
        await getCurrentUser();
        closeSignupModal();
        showSuccess('נרשמת בהצלחה!');

        // Redirect to payment
        const payment = await createSubscription(window.location.href + '?payment=success');
        window.location.href = payment.payment_url;

    } catch (error) {
        // Error already shown by signup function
    }
}

async function handleLogin(e) {
    e.preventDefault();

    const email = document.getElementById('login-email').value;
    const password = document.getElementById('login-password').value;

    try {
        await login(email, password);
        await getCurrentUser();
        closeLoginModal();
        showSuccess('התחברת בהצלחה!');
        updateUI();
    } catch (error) {
        // Error already shown by login function
    }
}

async function handleAddTicker(e) {
    e.preventDefault();

    const ticker = document.getElementById('new-ticker').value.toUpperCase().trim();

    if (!ticker) return;

    try {
        await addTicker(ticker);
        showSuccess(`${ticker} נוסף בהצלחה`);
        loadDashboardData();
        document.getElementById('new-ticker').value = '';
    } catch (error) {
        showError(error.message);
    }
}

async function handleRemoveTicker(ticker) {
    if (!confirm(`האם להסיר את ${ticker}?`)) return;

    try {
        await removeTicker(ticker);
        showSuccess(`${ticker} הוסר בהצלחה`);
        loadDashboardData();
    } catch (error) {
        showError(error.message);
    }
}

async function handleCancelSubscription() {
    if (!confirm('האם לבטל את המנוי? תוכל להמשיך עד תום התקופה ששולמה.')) return;

    try {
        await cancelSubscription();
        showSuccess('המנוי בוטל בהצלחה');
        loadDashboardData();
    } catch (error) {
        showError(error.message);
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', async () => {
    if (authToken) {
        await getCurrentUser();
        updateUI();
    }

    // Check for payment success
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('payment') === 'success') {
        showSuccess('התשלום בוצע בהצלחה! המנוי שלך פעיל.');
        window.history.replaceState({}, document.title, window.location.pathname);
    }
});
