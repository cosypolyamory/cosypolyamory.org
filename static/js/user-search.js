/**
 * UserSearch Component
 * 
 * A reusable autocomplete component for searching users with keyboard navigation,
 * debouncing, and flexible configuration options.
 */

class UserSearch {
    constructor(inputElement, options = {}) {
        this.input = inputElement;
        this.options = {
            apiEndpoint: '/api/users/search',
            minChars: 2,
            debounceMs: 300,
            maxResults: 10,
            onSelect: null,
            onResults: null,
            onError: null,
            ...options
        };

        this.suggestions = null;
        this.currentIndex = -1;
        this.searchTimeout = null;
        this.isVisible = false;

        this.init();
    }

    init() {
        this.createSuggestionContainer();
        this.bindEvents();
        
        // Auto-initialize from data attributes
        const endpoint = this.input.dataset.userSearchEndpoint;
        const minChars = this.input.dataset.userSearchMinChars;
        
        if (endpoint) this.options.apiEndpoint = endpoint;
        if (minChars) this.options.minChars = parseInt(minChars);
    }

    createSuggestionContainer() {
        this.suggestions = document.createElement('div');
        this.suggestions.className = 'user-search-suggestions';
        this.suggestions.style.display = 'none';
        
        // Position relative to input
        this.input.parentNode.style.position = 'relative';
        this.input.parentNode.appendChild(this.suggestions);
    }

    bindEvents() {
        // Input events
        this.input.addEventListener('input', (e) => this.handleInput(e));
        this.input.addEventListener('keydown', (e) => this.handleKeydown(e));
        this.input.addEventListener('focus', (e) => this.handleFocus(e));
        this.input.addEventListener('blur', (e) => this.handleBlur(e));

        // Click outside to close
        document.addEventListener('click', (e) => {
            if (!this.input.contains(e.target) && !this.suggestions.contains(e.target)) {
                this.hideSuggestions();
            }
        });
    }

    handleInput(e) {
        const value = e.target.value.trim();
        
        clearTimeout(this.searchTimeout);
        
        if (value.length < this.options.minChars) {
            this.hideSuggestions();
            return;
        }

        this.searchTimeout = setTimeout(() => {
            this.search(value);
        }, this.options.debounceMs);
    }

    handleKeydown(e) {
        if (!this.isVisible) return;

        const items = this.suggestions.querySelectorAll('.user-search-suggestion');
        
        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                this.currentIndex = Math.min(this.currentIndex + 1, items.length - 1);
                this.updateSelection(items);
                break;
            case 'ArrowUp':
                e.preventDefault();
                this.currentIndex = Math.max(this.currentIndex - 1, -1);
                this.updateSelection(items);
                break;
            case 'Enter':
                e.preventDefault();
                if (this.currentIndex >= 0 && items[this.currentIndex]) {
                    this.selectUser(items[this.currentIndex]);
                }
                break;
            case 'Escape':
                this.hideSuggestions();
                this.input.blur();
                break;
        }
    }

    handleFocus(e) {
        const value = e.target.value.trim();
        if (value.length >= this.options.minChars) {
            this.search(value);
        }
    }

    handleBlur(e) {
        // Delay hiding to allow clicks on suggestions
        setTimeout(() => {
            if (document.activeElement !== this.input && 
                !this.suggestions.contains(document.activeElement)) {
                this.hideSuggestions();
            }
        }, 150);
    }

    async search(query) {
        try {
            const url = new URL(this.options.apiEndpoint, window.location.origin);
            url.searchParams.set('q', query);
            url.searchParams.set('limit', this.options.maxResults);
            
            const response = await fetch(url);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const users = await response.json();
            this.displaySuggestions(users);
            
            if (this.options.onResults) {
                this.options.onResults(users);
            }
        } catch (error) {
            console.error('User search error:', error);
            this.hideSuggestions();
            
            if (this.options.onError) {
                this.options.onError(error);
            }
        }
    }

    displaySuggestions(users) {
        if (!Array.isArray(users) || users.length === 0) {
            this.hideSuggestions();
            return;
        }

        this.suggestions.innerHTML = '';
        this.currentIndex = -1;

        users.forEach((user, index) => {
            const item = this.createSuggestionItem(user, index);
            this.suggestions.appendChild(item);
        });

        this.showSuggestions();
    }

    createSuggestionItem(user, index) {
        const item = document.createElement('div');
        item.className = 'user-search-suggestion';
        item.dataset.index = index;
        item.dataset.userId = user.id;

        const avatar = user.avatar_url ? 
            `<img src="${user.avatar_url}" alt="${user.name}" class="user-search-avatar">` :
            `<div class="user-search-avatar user-search-avatar-placeholder">
                <i class="fas fa-user"></i>
            </div>`;

        const roleClass = this.getRoleClass(user.role);
        
        item.innerHTML = `
            <div class="user-search-item-content">
                ${avatar}
                <div class="user-search-item-info">
                    <div class="user-search-item-name">${this.escapeHtml(user.name)}</div>
                    <div class="user-search-item-email">${this.escapeHtml(user.email)}</div>
                    <span class="badge bg-${roleClass} user-search-item-role">${user.role_display || user.role}</span>
                </div>
            </div>
        `;

        // Event handlers
        item.addEventListener('mousedown', (e) => {
            e.preventDefault(); // Prevent input blur
            this.selectUser(item);
        });

        item.addEventListener('mouseenter', () => {
            this.currentIndex = index;
            this.updateSelection(this.suggestions.querySelectorAll('.user-search-suggestion'));
        });

        return item;
    }

    getRoleClass(role) {
        const roleClasses = {
            'admin': 'warning',
            'organizer': 'info', 
            'approved': 'success',
            'pending': 'warning',
            'rejected': 'danger',
            'new': 'secondary'
        };
        return roleClasses[role] || 'secondary';
    }

    updateSelection(items) {
        items.forEach((item, index) => {
            item.classList.toggle('active', index === this.currentIndex);
        });

        // Scroll active item into view
        if (this.currentIndex >= 0 && items[this.currentIndex]) {
            items[this.currentIndex].scrollIntoView({ 
                block: 'nearest',
                behavior: 'smooth'
            });
        }
    }

    selectUser(item) {
        const userId = item.dataset.userId;
        const userInfo = this.extractUserInfo(item);
        
        // Don't set the input value - we want to show the user card instead
        // this.input.value = userInfo.name;
        this.input.value = ''; // Clear the search input
        this.hideSuggestions();

        if (this.options.onSelect) {
            this.options.onSelect({
                id: userId,
                ...userInfo
            });
        }

        // Dispatch custom event
        this.input.dispatchEvent(new CustomEvent('userSelected', {
            detail: { id: userId, ...userInfo }
        }));
    }

    extractUserInfo(item) {
        const nameEl = item.querySelector('.user-search-item-name');
        const emailEl = item.querySelector('.user-search-item-email');
        const roleEl = item.querySelector('.user-search-item-role');
        
        return {
            name: nameEl ? nameEl.textContent : '',
            email: emailEl ? emailEl.textContent : '',
            role: roleEl ? roleEl.textContent : ''
        };
    }

    showSuggestions() {
        this.suggestions.style.display = 'block';
        this.isVisible = true;
        this.suggestions.setAttribute('aria-hidden', 'false');
    }

    hideSuggestions() {
        this.suggestions.style.display = 'none';
        this.isVisible = false;
        this.currentIndex = -1;
        this.suggestions.setAttribute('aria-hidden', 'true');
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    destroy() {
        clearTimeout(this.searchTimeout);
        if (this.suggestions && this.suggestions.parentNode) {
            this.suggestions.parentNode.removeChild(this.suggestions);
        }
    }
}

// Auto-initialize from data attributes
document.addEventListener('DOMContentLoaded', function() {
    const searchInputs = document.querySelectorAll('[data-user-search]');
    
    searchInputs.forEach(input => {
        const searchType = input.dataset.userSearch;
        const endpoint = searchType === 'approved' ? '/api/users/search/approved' : '/api/users/search';
        
        new UserSearch(input, {
            apiEndpoint: endpoint
        });
    });
});

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = UserSearch;
}

// Global access
window.UserSearch = UserSearch;
