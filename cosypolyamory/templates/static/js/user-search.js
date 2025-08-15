/**
 * User Search Autocomplete Component
 * 
 * Usage:
 * const userSearch = new UserSearch('#search-input', {
 *     onSelect: function(user) { console.log('Selected:', user); },
 *     placeholder: 'Search for users...',
 *     approvedOnly: false
 * });
 */

class UserSearch {
    constructor(inputSelector, options = {}) {
        this.input = document.querySelector(inputSelector);
        if (!this.input) {
            throw new Error(`Input element not found: ${inputSelector}`);
        }
        
        this.options = {
            placeholder: 'Search for users...',
            minLength: 2,
            maxResults: 10,
            debounceDelay: 300,
            approvedOnly: false,
            onSelect: null,
            onClear: null,
            ...options
        };
        
        this.searchTimeout = null;
        this.selectedUser = null;
        this.suggestions = [];
        this.activeSuggestionIndex = -1;
        
        this.init();
    }
    
    init() {
        this.setupInput();
        this.createSuggestionsContainer();
        this.attachEventListeners();
    }
    
    setupInput() {
        this.input.setAttribute('autocomplete', 'off');
        this.input.setAttribute('placeholder', this.options.placeholder);
        this.input.classList.add('user-search-input');
    }
    
    createSuggestionsContainer() {
        this.suggestionsContainer = document.createElement('div');
        this.suggestionsContainer.className = 'user-search-suggestions';
        this.suggestionsContainer.style.display = 'none';
        
        // Position container relative to input
        this.input.parentNode.style.position = 'relative';
        this.input.parentNode.appendChild(this.suggestionsContainer);
    }
    
    attachEventListeners() {
        // Input events
        this.input.addEventListener('input', (e) => this.onInput(e));
        this.input.addEventListener('keydown', (e) => this.onKeyDown(e));
        this.input.addEventListener('blur', (e) => this.onBlur(e));
        this.input.addEventListener('focus', (e) => this.onFocus(e));
        
        // Click outside to close suggestions
        document.addEventListener('click', (e) => {
            if (!this.input.parentNode.contains(e.target)) {
                this.hideSuggestions();
            }
        });
    }
    
    onInput(e) {
        const query = e.target.value.trim();
        
        // Clear previous timeout
        if (this.searchTimeout) {
            clearTimeout(this.searchTimeout);
        }
        
        if (query.length < this.options.minLength) {
            this.hideSuggestions();
            this.clearSelection();
            return;
        }
        
        // Debounce the search
        this.searchTimeout = setTimeout(() => {
            this.performSearch(query);
        }, this.options.debounceDelay);
    }
    
    onKeyDown(e) {
        if (!this.suggestionsVisible()) return;
        
        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                this.navigateSuggestions(1);
                break;
            case 'ArrowUp':
                e.preventDefault();
                this.navigateSuggestions(-1);
                break;
            case 'Enter':
                e.preventDefault();
                if (this.activeSuggestionIndex >= 0) {
                    this.selectSuggestion(this.activeSuggestionIndex);
                }
                break;
            case 'Escape':
                this.hideSuggestions();
                break;
        }
    }
    
    onBlur(e) {
        // Delay hiding suggestions to allow for click on suggestion
        setTimeout(() => {
            if (!this.suggestionsContainer.matches(':hover')) {
                this.hideSuggestions();
            }
        }, 150);
    }
    
    onFocus(e) {
        if (this.suggestions.length > 0) {
            this.showSuggestions();
        }
    }
    
    async performSearch(query) {
        try {
            const endpoint = this.options.approvedOnly ? 
                '/api/users/search/approved' : '/api/users/search';
            
            const response = await fetch(`${endpoint}?q=${encodeURIComponent(query)}&limit=${this.options.maxResults}`);
            
            if (!response.ok) {
                throw new Error('Search failed');
            }
            
            const users = await response.json();
            this.displaySuggestions(users);
            
        } catch (error) {
            console.error('User search error:', error);
            this.hideSuggestions();
        }
    }
    
    displaySuggestions(users) {
        this.suggestions = users;
        this.activeSuggestionIndex = -1;
        
        if (users.length === 0) {
            this.hideSuggestions();
            return;
        }
        
        this.suggestionsContainer.innerHTML = '';
        
        users.forEach((user, index) => {
            const suggestion = document.createElement('div');
            suggestion.className = 'user-search-suggestion';
            suggestion.dataset.index = index;
            
            suggestion.innerHTML = `
                <div class="user-search-suggestion-content">
                    ${user.avatar_url ? `<img src="${user.avatar_url}" alt="${user.name}" class="user-avatar">` : 
                      '<div class="user-avatar-placeholder"></div>'}
                    <div class="user-details">
                        <div class="user-name">${this.escapeHtml(user.name)}</div>
                        <div class="user-email">${this.escapeHtml(user.email)}</div>
                        <div class="user-role">${this.escapeHtml(user.role_display)}</div>
                    </div>
                </div>
            `;
            
            suggestion.addEventListener('click', () => this.selectSuggestion(index));
            suggestion.addEventListener('mouseenter', () => this.setActiveSuggestion(index));
            
            this.suggestionsContainer.appendChild(suggestion);
        });
        
        this.showSuggestions();
    }
    
    navigateSuggestions(direction) {
        const newIndex = this.activeSuggestionIndex + direction;
        
        if (newIndex >= 0 && newIndex < this.suggestions.length) {
            this.setActiveSuggestion(newIndex);
        } else if (newIndex < 0) {
            this.setActiveSuggestion(this.suggestions.length - 1);
        } else {
            this.setActiveSuggestion(0);
        }
    }
    
    setActiveSuggestion(index) {
        // Remove previous active class
        const previousActive = this.suggestionsContainer.querySelector('.active');
        if (previousActive) {
            previousActive.classList.remove('active');
        }
        
        this.activeSuggestionIndex = index;
        
        // Add active class to new suggestion
        const suggestions = this.suggestionsContainer.querySelectorAll('.user-search-suggestion');
        if (suggestions[index]) {
            suggestions[index].classList.add('active');
            suggestions[index].scrollIntoView({ block: 'nearest' });
        }
    }
    
    selectSuggestion(index) {
        const user = this.suggestions[index];
        if (!user) return;
        
        this.selectedUser = user;
        this.input.value = user.display_name;
        this.hideSuggestions();
        
        if (this.options.onSelect) {
            this.options.onSelect(user);
        }
    }
    
    showSuggestions() {
        this.suggestionsContainer.style.display = 'block';
    }
    
    hideSuggestions() {
        this.suggestionsContainer.style.display = 'none';
        this.activeSuggestionIndex = -1;
    }
    
    suggestionsVisible() {
        return this.suggestionsContainer.style.display === 'block';
    }
    
    clearSelection() {
        this.selectedUser = null;
        if (this.options.onClear) {
            this.options.onClear();
        }
    }
    
    getSelectedUser() {
        return this.selectedUser;
    }
    
    setUser(user) {
        this.selectedUser = user;
        this.input.value = user ? user.display_name : '';
    }
    
    clear() {
        this.input.value = '';
        this.selectedUser = null;
        this.hideSuggestions();
        if (this.options.onClear) {
            this.options.onClear();
        }
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Auto-initialize user search inputs with data-user-search attribute
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('[data-user-search]').forEach(input => {
        const options = {};
        
        // Read options from data attributes
        if (input.dataset.userSearchApproved === 'true') {
            options.approvedOnly = true;
        }
        
        if (input.dataset.userSearchPlaceholder) {
            options.placeholder = input.dataset.userSearchPlaceholder;
        }
        
        if (input.dataset.userSearchMinLength) {
            options.minLength = parseInt(input.dataset.userSearchMinLength);
        }
        
        new UserSearch(input, options);
    });
});
