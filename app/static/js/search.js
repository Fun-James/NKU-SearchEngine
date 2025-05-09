/**
 * 搜索建议和历史记录功能的JavaScript文件
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

document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('search-input');
    const suggestionBox = document.getElementById('search-suggestions');
    
    if (!searchInput || !suggestionBox) return;
    
    let debounceTimer;
    let isShowingHistory = false;
    
    // 监听搜索框点击事件
    searchInput.addEventListener('click', function() {
        if (this.value.trim() === '') {
            showSearchHistory();
        }
    });
    
    // 监听搜索框获得焦点事件
    searchInput.addEventListener('focus', function() {
        if (this.value.trim() === '') {
            showSearchHistory();
        }
    });
    
    // 监听输入事件，实现防抖
    searchInput.addEventListener('input', function() {
        const query = this.value.trim();
        
        clearTimeout(debounceTimer);
        
        if (!query) {
            showSearchHistory();
            return;
        }
        
        isShowingHistory = false;
        debounceTimer = setTimeout(() => {
            fetchSuggestions(query);
        }, 300);
    });
    
    // 点击页面其他地方时隐藏建议框
    document.addEventListener('click', function(e) {
        if (e.target !== searchInput && !suggestionBox.contains(e.target)) {
            suggestionBox.style.display = 'none';
        }
    });
    
    // 获取并显示搜索历史
    function showSearchHistory() {
        fetch('/api/suggestions?history=true')
            .then(response => response.json())
            .then(data => {
                displayHistory(data.suggestions);
            })
            .catch(error => {
                console.error('获取搜索历史时出错:', error);
            });
    }
    
    // 显示搜索历史
    function displayHistory(history) {
        if (!history || history.length === 0) {
            suggestionBox.innerHTML = '<div class="history-empty">暂无搜索历史</div>';
            suggestionBox.style.display = 'block';
            return;
        }
        
        suggestionBox.innerHTML = '<div class="history-header">搜索历史 <button onclick="clearSearchHistory()" class="clear-history">清空历史</button></div>';
        isShowingHistory = true;
        
        history.forEach(item => {
            const historyItem = document.createElement('div');
            historyItem.className = 'history-item';
            
            // 创建历史记录的文本和操作按钮
            const itemContent = document.createElement('span');
            itemContent.className = 'history-text';
            itemContent.textContent = item;
            itemContent.onclick = () => {
                searchInput.value = item;
                searchInput.form.submit();
            };
            
            const deleteBtn = document.createElement('button');
            deleteBtn.className = 'delete-history';
            deleteBtn.innerHTML = '×';
            deleteBtn.onclick = (e) => {
                e.stopPropagation();
                removeHistoryItem(item);
            };
            
            historyItem.appendChild(itemContent);
            historyItem.appendChild(deleteBtn);
            suggestionBox.appendChild(historyItem);
        });
        
        suggestionBox.style.display = 'block';
    }
    
    // 清空搜索历史
    window.clearSearchHistory = function() {
        fetch('/api/clear_history', {
            method: 'POST'
        }).then(() => {
            suggestionBox.innerHTML = '<div class="history-empty">暂无搜索历史</div>';
        });
    };
    
    // 删除单个历史记录
    function removeHistoryItem(query) {
        fetch('/api/remove_history', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ query: query })
        }).then(() => {
            showSearchHistory();
        });
    }
    
    // 从后端获取搜索建议
    function fetchSuggestions(query) {
        fetch(`/api/suggestions?query=${encodeURIComponent(query)}`)
            .then(response => response.json())
            .then(data => {
                displaySuggestions(data.suggestions);
            })
            .catch(error => {
                console.error('获取搜索建议时出错:', error);
            });
    }
    
    // 显示搜索建议
    function displaySuggestions(suggestions) {
        if (!suggestions || suggestions.length === 0) {
            if (!isShowingHistory) {
                suggestionBox.innerHTML = '';
                suggestionBox.style.display = 'none';
            }
            return;
        }
        
        suggestionBox.innerHTML = '';
        suggestions.forEach(suggestion => {
            const item = document.createElement('div');
            item.className = 'suggestion-item';
            item.textContent = suggestion;
            
            item.addEventListener('click', () => {
                searchInput.value = suggestion;
                searchInput.form.submit();
            });
            
            suggestionBox.appendChild(item);
        });
        
        suggestionBox.style.display = 'block';
    }
});
