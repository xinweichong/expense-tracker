// Auth
async function apiFetch(url, options = {}) {
    const resp = await fetch(url, options);
    if (resp.status === 401) {
        document.getElementById('login-overlay').style.display = 'flex';
        document.getElementById('settings-page').style.display = 'none';
        throw new Error('Not authenticated');
    }
    return resp;
}

document.getElementById('login-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const password = document.getElementById('password').value;
    const resp = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password }),
    });
    if (resp.ok) {
        document.getElementById('login-overlay').style.display = 'none';
        document.getElementById('settings-page').style.display = 'block';
        loadSettings();
    } else {
        document.getElementById('login-error').style.display = 'block';
    }
});

// Check if already logged in
async function checkAuth() {
    try {
        const resp = await fetch('/api/categories');
        if (resp.ok) {
            document.getElementById('login-overlay').style.display = 'none';
            document.getElementById('settings-page').style.display = 'block';
            loadSettings();
        }
    } catch {}
}
checkAuth();

// Load data
async function loadSettings() {
    await Promise.all([loadCategories(), loadOverrides()]);
}

async function loadCategories() {
    const resp = await apiFetch('/api/categories');
    const categories = await resp.json();
    const list = document.getElementById('categories-list');
    list.innerHTML = '';
    categories.forEach(cat => {
        const row = document.createElement('div');
        row.className = 'settings-item';
        row.innerHTML = `
            <div class="settings-item-info">
                <span class="settings-item-icon">${cat.icon || ''}</span>
                <span class="settings-item-name">${cat.name}</span>
                <span class="settings-item-keywords">${cat.keywords || '(no keywords)'}</span>
            </div>
            <div class="settings-item-actions">
                <button class="btn-secondary" onclick="editCategory('${cat.name}', '${escapeAttr(cat.keywords || '')}', '${escapeAttr(cat.icon || '')}')">Edit</button>
                <button class="btn-danger" onclick="deleteCategory('${cat.name}')">Delete</button>
            </div>
        `;
        list.appendChild(row);
    });
}

async function loadOverrides() {
    const resp = await apiFetch('/api/merchant-overrides');
    const overrides = await resp.json();
    const list = document.getElementById('overrides-list');
    const noOverrides = document.getElementById('no-overrides');
    list.innerHTML = '';
    if (overrides.length === 0) {
        noOverrides.style.display = 'block';
        return;
    }
    noOverrides.style.display = 'none';
    overrides.forEach(o => {
        const row = document.createElement('div');
        row.className = 'settings-item';
        row.innerHTML = `
            <div class="settings-item-info">
                <span class="override-merchant">${o.merchant}</span>
                <span class="override-arrow">&rarr;</span>
                <span class="override-category">${o.category}</span>
            </div>
            <div class="settings-item-actions">
                <button class="btn-danger" onclick="removeOverride('${escapeAttr(o.merchant)}')">Remove</button>
            </div>
        `;
        list.appendChild(row);
    });
}

// Category CRUD
function showAddCategoryModal() {
    document.getElementById('modal-title').textContent = 'Add Category';
    document.getElementById('modal-submit').textContent = 'Add';
    document.getElementById('edit-mode').value = 'add';
    document.getElementById('cat-name').value = '';
    document.getElementById('cat-name').disabled = false;
    document.getElementById('cat-keywords').value = '';
    document.getElementById('cat-icon').value = '';
    document.getElementById('category-modal').style.display = 'flex';
}

function editCategory(name, keywords, icon) {
    document.getElementById('modal-title').textContent = 'Edit Category';
    document.getElementById('modal-submit').textContent = 'Save';
    document.getElementById('edit-mode').value = 'edit';
    document.getElementById('cat-name').value = name;
    document.getElementById('cat-name').disabled = true;
    document.getElementById('cat-keywords').value = keywords;
    document.getElementById('cat-icon').value = icon;
    document.getElementById('category-modal').style.display = 'flex';
}

function closeModal() {
    document.getElementById('category-modal').style.display = 'none';
}

document.getElementById('category-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const mode = document.getElementById('edit-mode').value;
    const name = document.getElementById('cat-name').value.trim();
    const keywords = document.getElementById('cat-keywords').value.trim();
    const icon = document.getElementById('cat-icon').value.trim() || '\uD83D\uDCCD';

    if (mode === 'add') {
        const resp = await apiFetch('/api/categories', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, keywords, icon }),
        });
        if (!resp.ok) {
            const err = await resp.json();
            alert(err.detail || 'Failed to add category');
            return;
        }
    } else {
        const resp = await apiFetch(`/api/categories/${encodeURIComponent(name)}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ keywords }),
        });
        if (!resp.ok) {
            const err = await resp.json();
            alert(err.detail || 'Failed to update category');
            return;
        }
    }
    closeModal();
    loadCategories();
});

async function deleteCategory(name) {
    if (!confirm(`Delete category "${name}"? Transactions will be moved to "Other".`)) return;
    const resp = await apiFetch(`/api/categories/${encodeURIComponent(name)}`, { method: 'DELETE' });
    if (!resp.ok) {
        const err = await resp.json();
        alert(err.detail || 'Failed to delete category');
        return;
    }
    const result = await resp.json();
    alert(`Deleted "${name}". ${result.reassigned} transaction(s) moved to "Other".`);
    loadCategories();
}

async function removeOverride(merchant) {
    if (!confirm(`Remove override for "${merchant}"?`)) return;
    await apiFetch(`/api/merchant-overrides/${encodeURIComponent(merchant)}`, { method: 'DELETE' });
    loadOverrides();
}

function escapeAttr(str) {
    return str.replace(/'/g, "\\'").replace(/"/g, '&quot;');
}
