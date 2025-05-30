/**
 * 智能搜索建议和历史记录功能的JavaScript文件
 * 支持自动补全、相关查询、热门搜索等功能
 */

// 声明为全局函数
window.toggleSearchType = function() {
    const btn = document.getElementById('search-type-btn');
    const text = document.getElementById('search-type-text');
    const input = document.getElementById('search-type');
    const searchInput = document.getElementById('search-input');
    
    if (input.value === 'webpage') {
        // 切换到文档搜索
        input.value = 'document';
        text.textContent = '文档搜索';
        searchInput.placeholder = '搜索PDF、Word、Excel等文档...';
        btn.classList.add('doc-mode');
    } else {
        // 切换到网页搜索
        input.value = 'webpage';
        text.textContent = '网页搜索';
        searchInput.placeholder = '输入搜索关键词...';
        btn.classList.remove('doc-mode');
    }
};

// 搜索建议管理器
class SearchSuggestionManager {
    constructor() {
        this.searchInput = null;
        this.suggestionBox = null;
        this.debounceTimer = null;
        this.isShowingHistory = false;
        this.currentSuggestions = [];
        this.selectedIndex = -1;
        this.lastQuery = '';
        this.lastPinyinQuery = '';
        
        this.init();
    }
    
    init() {
        document.addEventListener('DOMContentLoaded', () => {
            this.searchInput = document.getElementById('search-input');
            this.suggestionBox = document.getElementById('search-suggestions');
            
            if (!this.searchInput || !this.suggestionBox) return;
            
            this.bindEvents();
            this.loadHotSearches();
        });
    }
    
    bindEvents() {
        // 搜索框点击事件
        this.searchInput.addEventListener('click', () => {
            if (this.searchInput.value.trim() === '') {
                this.showSearchHistory();
            }
        });
        
        // 搜索框获得焦点事件
        this.searchInput.addEventListener('focus', () => {
            if (this.searchInput.value.trim() === '') {
                this.showSearchHistory();
            }
        });
        
        // 输入事件，实现防抖
        this.searchInput.addEventListener('input', (e) => {
            const query = e.target.value.trim();
            this.lastQuery = query;
            
            clearTimeout(this.debounceTimer);
            this.selectedIndex = -1;
            
            if (!query) {
                this.showSearchHistory();
                return;
            }
            
            this.isShowingHistory = false;
            this.debounceTimer = setTimeout(() => {
                // 检查是否是拼音输入
                const isPinyin = /^[a-zA-Z]+$/.test(query);
                this.fetchIntelligentSuggestions(query, isPinyin);
            }, 200);
        });
        
        // 键盘导航支持
        this.searchInput.addEventListener('keydown', (e) => {
            this.handleKeyNavigation(e);
        });
        
        // 点击页面其他地方时隐藏建议框
        document.addEventListener('click', (e) => {
            if (e.target !== this.searchInput && !this.suggestionBox.contains(e.target)) {
                this.hideSuggestions();
            }
        });
    }
    
    handleKeyNavigation(e) {
        const items = this.suggestionBox.querySelectorAll('.suggestion-item, .history-item .history-text');
        
        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                this.selectedIndex = Math.min(this.selectedIndex + 1, items.length - 1);
                this.updateSelection(items);
                break;
            case 'ArrowUp':
                e.preventDefault();
                this.selectedIndex = Math.max(this.selectedIndex - 1, -1);
                this.updateSelection(items);
                break;
            case 'Enter':
                e.preventDefault();
                if (this.selectedIndex >= 0 && items[this.selectedIndex]) {
                    const text = items[this.selectedIndex].textContent || items[this.selectedIndex].dataset.query;
                    this.searchInput.value = text;
                    this.searchInput.form.submit();
                } else {
                    this.searchInput.form.submit();
                }
                break;
            case 'Escape':
                this.hideSuggestions();
                break;
        }
    }
    
    updateSelection(items) {
        // 清除所有选中状态
        items.forEach(item => item.classList.remove('selected'));
        
        // 设置当前选中项
        if (this.selectedIndex >= 0 && items[this.selectedIndex]) {
            items[this.selectedIndex].classList.add('selected');
            // 滚动到可见区域
            items[this.selectedIndex].scrollIntoView({ block: 'nearest' });
        }
    }
    
    showSearchHistory() {
        fetch('/api/suggestions?history=true')
            .then(response => {
                if (!response.ok) {
                    throw new Error('网络响应不正常');
                }
                return response.json();
            })            .then(data => {
                if (data && data.suggestions) {
                    this.displayHistory(data.suggestions);
                } else {
                    this.displayHistory([]);
                }
            })
            .catch(error => {
                console.error('获取搜索历史时出错:', error);
                this.displayHistory([]);
            });
    }
      displayHistory(history) {
        this.suggestionBox.innerHTML = '';
        this.isShowingHistory = true;
        this.selectedIndex = -1;
        
        // 创建历史记录部分
        if (history && history.length > 0) {
            const historyHeader = document.createElement('div');
            historyHeader.className = 'suggestion-section-header';
            historyHeader.innerHTML = `
                <span>搜索历史</span>
                <button onclick="clearSearchHistory()" class="clear-history">清空历史</button>
            `;
            this.suggestionBox.appendChild(historyHeader);
            
            history.slice(0, 8).forEach(item => {
                const historyItem = document.createElement('div');
                historyItem.className = 'history-item';
                
                const itemContent = document.createElement('span');
                itemContent.className = 'history-text';
                itemContent.textContent = item;
                itemContent.dataset.query = item;
                itemContent.onclick = () => {
                    this.searchInput.value = item;
                    this.searchInput.form.submit();
                };
                
                const deleteBtn = document.createElement('button');
                deleteBtn.className = 'delete-history';
                deleteBtn.innerHTML = '×';
                deleteBtn.onclick = (e) => {
                    e.stopPropagation();
                    this.removeHistoryItem(item);
                };
                
                historyItem.appendChild(itemContent);
                historyItem.appendChild(deleteBtn);
                this.suggestionBox.appendChild(historyItem);
            });
        } else {
            this.suggestionBox.innerHTML = '<div class="history-empty">暂无搜索历史</div>';
        }
        
        this.suggestionBox.style.display = 'block';
    }      fetchIntelligentSuggestions(query, isPinyin = false) {
        if (!query) return;
        
        const params = new URLSearchParams({
            query: query,
            simple: true,
            pinyin: isPinyin
        });
        
        fetch(`/api/suggestions?${params}`)
        .then(response => response.json())
        .then(data => {
            if (data.correction) {
                this.displaySuggestions([
                    { text: data.correction, type: 'correction', icon: '✍️' },
                    ...data.suggestions.map(s => ({ text: s, type: 'suggestion', icon: '💡' }))
                ]);
            } else {
                this.displaySuggestions(
                    data.suggestions.map(s => ({ text: s, type: 'suggestion', icon: '💡' }))
                );
            }
        })
        .catch(error => {
            console.error('获取建议时出错:', error);
            this.displaySuggestions([]);
        });
    }

    displaySuggestions(suggestions) {
        this.suggestionBox.innerHTML = '';
        this.isShowingHistory = false;
        this.selectedIndex = -1;
        this.currentSuggestions = suggestions;
        
        if (suggestions && suggestions.length > 0) {
            suggestions.forEach((suggestion, index) => {
                const item = this.createSuggestionItem(suggestion);
                this.suggestionBox.appendChild(item);
            });
            this.suggestionBox.style.display = 'block';
        } else {
            this.hideSuggestions();
        }
    }
    
    createSuggestionItem(suggestion) {
        const item = document.createElement('div');
        item.className = `suggestion-item ${suggestion.type}-suggestion`;
        
        const icon = document.createElement('span');
        icon.className = 'suggestion-icon';
        icon.textContent = suggestion.icon;
        
        const text = document.createElement('span');
        text.className = 'suggestion-text';
        text.textContent = suggestion.text;
        
        item.appendChild(icon);
        item.appendChild(text);
        
        item.addEventListener('click', () => {
            this.searchInput.value = suggestion.text;
            this.searchInput.form.submit();
        });
        
        return item;
    }
    
    hideSuggestions() {
        this.suggestionBox.style.display = 'none';
        this.selectedIndex = -1;
    }
    
    removeHistoryItem(query) {
        if (!query) return;
        
        fetch('/api/remove_history', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ query: query })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('删除历史记录失败');
            }
            return response.json();
        })
        .then(() => {
            this.showSearchHistory(); // 刷新历史记录显示
        })
        .catch(error => {
            console.error('删除历史记录时出错:', error);
            this.showSearchHistory();
        });
    }
}

// 清空搜索历史（全局函数）
window.clearSearchHistory = function() {
    fetch('/api/clear_history', {
        method: 'POST'
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('清空历史记录失败');
        }
        return response.json();
    })
    .then(() => {
        const suggestionBox = document.getElementById('search-suggestions');
        if (suggestionBox) {
            suggestionBox.innerHTML = '<div class="history-empty">暂无搜索历史</div>';
        }
    })
    .catch(error => {
        console.error('清空历史记录时出错:', error);
        const suggestionBox = document.getElementById('search-suggestions');
        if (suggestionBox) {
            suggestionBox.innerHTML = '<div class="history-empty">操作失败，请重试</div>';
        }
    });
};

// 初始化搜索建议管理器
const searchManager = new SearchSuggestionManager();
