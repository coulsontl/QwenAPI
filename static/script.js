document.addEventListener('DOMContentLoaded', function() {
    const loginSection = document.getElementById('login-section');
    const mainSection = document.getElementById('main-section');
    const passwordInput = document.getElementById('password');
    const loginBtn = document.getElementById('login-btn');
    const loginStatus = document.getElementById('login-status');
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const uploadStatus = document.getElementById('upload-status');
    const tokenStatus = document.getElementById('token-status');
    const refreshTokenBtn = document.getElementById('refresh-token-btn');
    const deleteAllTokensBtn = document.getElementById('delete-all-tokens-btn');
    const refreshStatus = document.getElementById('refresh-status');
    const messageInput = document.getElementById('message');
    const modelSelect = document.getElementById('model');
    const sendBtn = document.getElementById('send-btn');
    const apiStatus = document.getElementById('api-status');
    const apiResponse = document.getElementById('api-response');
    const responseContent = document.getElementById('response-content');
    const statusContainer = document.getElementById('status-container');
    const totalTokensToday = document.getElementById('total-tokens-today');
    const totalCallsToday = document.getElementById('total-calls-today');
    const modelUsageDetails = document.getElementById('model-usage-details');
    const tokenUsageStatus = document.getElementById('token-usage-status');
    const usageDateInput = document.getElementById('usage-date');
    const queryUsageBtn = document.getElementById('query-usage-btn');
    const deleteUsageBtn = document.getElementById('delete-usage-btn');
    
    const datePickerBtn = document.getElementById('date-picker-btn');
    const datePickerDropdown = document.getElementById('date-picker-dropdown');
    const prevMonthBtn = document.getElementById('prev-month');
    const nextMonthBtn = document.getElementById('next-month');
    const currentMonthYear = document.getElementById('current-month-year');
    const calendarDays = document.getElementById('calendar-days');
    
    const oauthLoginBtn = document.getElementById('oauth-login-btn');
    const oauthStatus = document.getElementById('oauth-status');
    const oauthDetails = document.getElementById('oauth-details');
    const oauthInstructions = document.getElementById('oauth-instructions');
    const oauthCancelBtn = document.getElementById('oauth-cancel-btn');
    const refreshTokenStatusBtn = document.getElementById('refresh-token-status-btn');
    
    let userPassword = '';
    let oauthStateId = null;
    let oauthPollTimer = null;
    let oauthStartTime = null;
    let oauthCountdownTimer = null;
    let oauthExpiresAt = null;
    
    let currentDate = new Date();
    let selectedDate = null;
    let availableDates = new Set();
    let isDatePickerOpen = false;
    
    loginBtn.addEventListener('click', async function() {
        const password = passwordInput.value;
        
        if (!password) {
            showStatus(loginStatus, '请输入密码', 'error');
            return;
        }
        
        loginBtn.disabled = true;
        loginBtn.textContent = '登录中...';
        showStatus(loginStatus, '正在登录，请稍候...', 'info');
        
        try {
            const response = await fetch('/api/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ password }),
            });
            
            const data = await response.json();
            
            if (response.ok) {
                showStatus(loginStatus, '登录成功', 'success');
                userPassword = password;
                loginSection.classList.add('hidden');
                mainSection.classList.remove('hidden');
                checkTokenStatus();
                loadVersion();
                
                const today = new Date();
                const yyyy = today.getFullYear();
                const mm = String(today.getMonth() + 1).padStart(2, '0');
                const dd = String(today.getDate()).padStart(2, '0');
                const todayString = `${yyyy}-${mm}-${dd}`;
                
                selectedDate = todayString;
                usageDateInput.value = todayString;
                
                initCustomDatePicker();
                loadAvailableDates();
                
                checkTokenUsage(todayString);
                
                if (queryUsageBtn) {
                    queryUsageBtn.addEventListener('click', async function() {
                        const selectedDate = usageDateInput.value;
                        if (!selectedDate) {
                            addStatusMessage('请选择日期', 'error', 3000);
                            return;
                        }
                        queryUsageBtn.disabled = true;
                        queryUsageBtn.textContent = '查询中...';
                        try {
                            await checkTokenUsage(selectedDate);
                            addStatusMessage(`已加载 ${selectedDate} 的用量数据`, 'success', 3000);
                        } catch (error) {
                            addStatusMessage('查询失败: ' + error.message, 'error', 3000);
                        } finally {
                            queryUsageBtn.disabled = false;
                            queryUsageBtn.textContent = '查询';
                        }
                    });
                }
                
                if (deleteUsageBtn) {
                    deleteUsageBtn.addEventListener('click', async function() {
                        const selectedDate = usageDateInput.value;
                        if (!selectedDate) {
                            addStatusMessage('请选择要删除的日期', 'error', 3000);
                            return;
                        }
                        
                        showConfirmDialog(
                            `确定要删除 ${selectedDate} 的用量数据吗？此操作不可撤销。`,
                            async function() {
                                deleteUsageBtn.disabled = true;
                                deleteUsageBtn.textContent = '删除中...';
                                try {
                                    const response = await fetch('/api/statistics/usage', {
                                        method: 'DELETE',
                                        headers: {
                                            'Content-Type': 'application/json',
                                            'Authorization': 'Bearer ' + userPassword,
                                        },
                                        body: JSON.stringify({ date: selectedDate }),
                                    });
                                    
                                    const data = await response.json();
                                    
                                    if (response.ok) {
                                        addStatusMessage(data.message || '删除成功', 'success', 3000);
                                        await checkTokenUsage(selectedDate);
                                        await loadAvailableDates();
                                    } else {
                                        addStatusMessage(data.error || '删除失败', 'error', 3000);
                                    }
                                } catch (error) {
                                    addStatusMessage('网络错误: ' + error.message, 'error', 3000);
                                } finally {
                                    deleteUsageBtn.disabled = false;
                                    deleteUsageBtn.textContent = '删除';
                                }
                            },
                            null,
                            "删除用量数据"
                        );
                    });
                }

                setTimeout(() => {
                    loginStatus.style.display = 'none';
                }, 3000);
            } else {
                showStatus(loginStatus, data.detail || '登录失败', 'error');
            }
        } catch (error) {
            showStatus(loginStatus, '网络错误: ' + error.message, 'error');
        } finally {
            loginBtn.disabled = false;
            loginBtn.textContent = '登录';
        }
    });
    
    if (dropZone && fileInput) {
        dropZone.addEventListener('click', function() { fileInput.click(); });
        
        dropZone.addEventListener('dragover', function(e) {
            e.preventDefault();
            dropZone.classList.add('dragover');
        });
        
        dropZone.addEventListener('dragleave', function() {
            dropZone.classList.remove('dragover');
        });
        
        dropZone.addEventListener('drop', function(e) {
            e.preventDefault();
            dropZone.classList.remove('dragover');
            
            if (e.dataTransfer.files.length) {
                handleFileUpload(e.dataTransfer.files[0]);
            }
        });
        
        fileInput.addEventListener('change', function(e) {
            if (e.target.files.length) {
                handleFileUpload(e.target.files[0]);
            }
        });
    }
    
    if (oauthLoginBtn) {
        oauthLoginBtn.addEventListener('click', startOAuthLogin);
    }
    
    if (oauthCancelBtn) {
        oauthCancelBtn.addEventListener('click', cancelOAuthLogin);
    }
    
    if (refreshTokenStatusBtn) {
        refreshTokenStatusBtn.addEventListener('click', async function() {
            // 显示loading状态
            refreshTokenStatusBtn.disabled = true;
            refreshTokenStatusBtn.classList.add('loading');
            
            try {
                await checkTokenStatus();
                addStatusMessage('Token状态已重新加载', 'success', 3000);
            } catch (error) {
                addStatusMessage('重新加载失败: ' + error.message, 'error', 3000);
            } finally {
                // 恢复原始状态
                refreshTokenStatusBtn.disabled = false;
                refreshTokenStatusBtn.classList.remove('loading');
            }
        });
    }
    
    const manualOpenBtn = document.getElementById('manual-open-btn');
    if (manualOpenBtn) {
        manualOpenBtn.disabled = true;
    }
    
    async function handleFileUpload(file) {
        if (!uploadStatus) return;
        
        if (file.name !== 'oauth_creds.json') {
            showStatus(uploadStatus, '请上传 oauth_creds.json 文件', 'error');
            resetFileInput();
            return;
        }
        
        try {
            const content = await file.text();
            const creds = JSON.parse(content);
            
            if (!creds.access_token || !creds.refresh_token) {
                showStatus(uploadStatus, '文件格式不正确，缺少access_token或refresh_token', 'error');
                resetFileInput();
                return;
            }
            
            const response = await fetch('/api/upload-token', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + userPassword,
                },
                body: JSON.stringify(creds),
            });
            
            const data = await response.json();
            
            if (response.ok) {
                showStatus(uploadStatus, '凭证上传成功', 'success');
                checkTokenStatus();
            } else {
                showStatus(uploadStatus, data.error || '上传失败', 'error');
            }
        } catch (error) {
            showStatus(uploadStatus, '文件处理错误: ' + error.message, 'error');
        } finally {
            resetFileInput();
        }
    }
    
    function resetFileInput() {
        if (fileInput) {
            fileInput.value = '';
            fileInput.blur();
            fileInput.focus();
        }
    }
    
    function rebindFileInputEvents() {
        if (fileInput) {
            const newFileInput = fileInput.cloneNode(true);
            fileInput.parentNode.replaceChild(newFileInput, fileInput);
            
            window.fileInput = newFileInput;
            
            newFileInput.addEventListener('change', function(e) {
                if (e.target.files.length) {
                    handleFileUpload(e.target.files[0]);
                }
            });
        }
    }
    
    async function startOAuthLogin() {
        if (!oauthLoginBtn || !oauthStatus || !oauthDetails || !oauthInstructions) return;
        
        try {
            oauthLoginBtn.disabled = true;
            oauthLoginBtn.textContent = '正在初始化...';
            
            showStatus(oauthStatus, '正在初始化 OAuth 认证...', 'info');
            
            const response = await fetch('/api/oauth-init', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + userPassword,
                }
            });
            
            const data = await response.json();
            
            if (response.ok && data.success) {
                oauthStateId = data.stateId;
                oauthExpiresAt = data.expiresAt;
                oauthStartTime = Date.now();
                
                oauthLoginBtn.textContent = '⏳ 等待授权...';
                
                try {
                    window.open(data.verificationUriComplete, '_blank');
                } catch (e) {
                }
                
                const expiresAt = new Date(oauthExpiresAt);
                const totalSeconds = Math.floor((oauthExpiresAt - oauthStartTime) / 1000);
                const minutes = Math.floor(totalSeconds / 60);
                oauthInstructions.innerHTML = 
                    '<div style="text-align: center; margin-bottom: 20px;">' +
                        '<p style="margin-bottom: 15px; color: #666;">' + 
                            '如授权页面未自动打开，请点击下方按钮' +
                        '</p>' +
                        '<p style="margin-top: 15px; font-size: 12px; color: #999;">' +
                            '授权完成后将自动获取 Token' +
                        '</p>' +
                        '<p style="margin-top: 5px; font-size: 12px; color: #999;">' +
                            '⏰ 过期时间: ' + expiresAt.toLocaleString() + ' (' + minutes + '分钟)' +
                        '</p>' +
                    '</div>';
                
                oauthDetails.classList.remove('hidden');
                showStatus(oauthStatus, '⏳ 等待授权完成...', 'info');
                
                const manualOpenBtn = document.getElementById('manual-open-btn');
                if (manualOpenBtn) {
                    manualOpenBtn.disabled = false;
                    manualOpenBtn.replaceWith(manualOpenBtn.cloneNode(true));
                    const newManualOpenBtn = document.getElementById('manual-open-btn');
                    if (newManualOpenBtn) {
                        newManualOpenBtn.addEventListener('click', () => {
                            window.open(data.verificationUriComplete, '_blank');
                        });
                    }
                }
                
                startOAuthPolling();
                startOAuthCountdown();
                
            } else {
                showStatus(oauthStatus, data.error || 'OAuth 初始化失败', 'error');
                resetOAuthLogin();
            }
        } catch (error) {
            showStatus(oauthStatus, '网络错误: ' + error.message, 'error');
            resetOAuthLogin();
        }
    }
    
    function startOAuthPolling() {
        if (!oauthStateId) return;
        
        pollOAuthStatus();
        oauthPollTimer = setInterval(pollOAuthStatus, 3000);
    }
    
    function startOAuthCountdown() {
        if (!oauthExpiresAt || !oauthStatus) return;
        
        updateCountdown();
        oauthCountdownTimer = setInterval(updateCountdown, 1000);
    }
    
    function updateCountdown() {
        if (!oauthExpiresAt || !oauthStatus) return;
        
        const now = Date.now();
        const remainingTime = Math.max(0, Math.floor((oauthExpiresAt - now) / 1000));
        const totalTime = Math.floor((oauthExpiresAt - oauthStartTime) / 1000);
        const timeRatio = remainingTime / totalTime;
        
        if (remainingTime > 0) {
            const minutes = Math.floor(remainingTime / 60);
            const seconds = remainingTime % 60;
            const timeString = minutes + ':' + seconds.toString().padStart(2, '0');
            
            let statusMessage = '⏳ 等待授权完成... 剩余时间: ' + timeString;
            let statusType = 'info';
            
            if (timeRatio < 0.2) {
                statusMessage = '⚠️ 授权即将过期! 剩余时间: ' + timeString;
                statusType = 'error';
            } else if (timeRatio < 0.5) {
                statusMessage = '⏰ 请尽快完成授权! 剩余时间: ' + timeString;
                statusType = 'info';
            }
            
            showStatus(oauthStatus, statusMessage, statusType);
        } else {
            showStatus(oauthStatus, '⏰ 授权码已过期，请重新获取', 'error');
            stopOAuthCountdown();
        }
    }
    
    function stopOAuthCountdown() {
        if (oauthCountdownTimer) {
            clearInterval(oauthCountdownTimer);
            oauthCountdownTimer = null;
        }
    }
    
    async function pollOAuthStatus() {
        if (!oauthStateId || !oauthStatus) return;
        
        try {
            const response = await fetch('/api/oauth-poll', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + userPassword,
                },
                body: JSON.stringify({ stateId: oauthStateId })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                if (data.success) {
                    showStatus(oauthStatus, '🎉 OAuth 认证成功！Token 已自动保存', 'success');
                    resetOAuthLogin();
                    // 延迟500ms再检查token状态，确保数据库已更新
                    setTimeout(checkTokenStatus, 500);
                } else if (data.status === 'pending') {
                    if (data.warning) {
                        showStatus(oauthStatus, '⚠️ ' + data.warning, 'info');
                    }
                    if (!oauthCountdownTimer && oauthExpiresAt) {
                        startOAuthCountdown();
                    }
                } else {
                    showStatus(oauthStatus, data.error || 'OAuth 认证失败', 'error');
                    resetOAuthLogin();
                }
            } else {
                showStatus(oauthStatus, data.error || '轮询失败', 'error');
                resetOAuthLogin();
            }
        } catch (error) {
            console.error('Failed to load available dates:', error);
        }
    }
    
    function resetOAuthLogin() {
        if (oauthPollTimer) {
            clearInterval(oauthPollTimer);
            oauthPollTimer = null;
        }
        
        stopOAuthCountdown();
        
        oauthStateId = null;
        oauthExpiresAt = null;
        oauthStartTime = null;
        
        if (oauthLoginBtn) {
            oauthLoginBtn.disabled = false;
            oauthLoginBtn.textContent = '🔑 OAuth 登录获取 Token';
        }
        
        const manualOpenBtn = document.getElementById('manual-open-btn');
        if (manualOpenBtn) {
            manualOpenBtn.disabled = true;
        }
        
        if (oauthDetails) {
            oauthDetails.classList.add('hidden');
        }
    }
    
    async function cancelOAuthLogin() {
        if (!oauthStateId) {
            resetOAuthLogin();
            return;
        }
        
        try {
            await fetch('/api/oauth-cancel', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + userPassword,
                },
                body: JSON.stringify({ stateId: oauthStateId })
            });
        } catch (error) {
            // 取消 OAuth 登录失败
        } finally {
            if (oauthStatus) {
                showStatus(oauthStatus, 'OAuth 授权已取消', 'info');
            }
            resetOAuthLogin();
        }
    }
    
    function showConfirmDialog(message, onConfirm, onCancel, title = "确认删除") {
        const modal = document.createElement('div');
        modal.style.cssText = 
            'position: fixed;' +
            'top: 0;' +
            'left: 0;' +
            'width: 100%;' +
            'height: 100%;' +
            'background-color: rgba(0, 0, 0, 0.5);' +
            'display: flex;' +
            'justify-content: center;' +
            'align-items: center;' +
            'z-index: 1000;';
        
        const dialog = document.createElement('div');
        dialog.style.cssText = 
            'background-color: white;' +
            'padding: 20px;' +
            'border-radius: 8px;' +
            'box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);' +
            'max-width: 400px;' +
            'width: 90%;';
        
        dialog.innerHTML = 
            '<h3 style="margin-top: 0; color: #e74c3c;">⚠️ ' + title + '</h3>' +
            '<p style="margin-bottom: 20px;">' + message + '</p>' +
            '<div style="display: flex; gap: 10px; justify-content: flex-end;">' +
            '<button id="confirm-cancel" style="padding: 8px 16px; border: 1px solid #ddd; background-color: #f8f9fa; border-radius: 4px; cursor: pointer; color: #333; font-weight: 500;">取消</button>' +
            '<button id="confirm-ok" style="padding: 8px 16px; border: none; background-color: #e74c3c; color: white; border-radius: 4px; cursor: pointer; font-weight: 500;">确认删除</button>' +
            '</div>';
        
        modal.appendChild(dialog);
        document.body.appendChild(modal);
        
        document.getElementById('confirm-ok').onclick = function() {
            document.body.removeChild(modal);
            if (onConfirm) onConfirm();
        };
        
        document.getElementById('confirm-cancel').onclick = function() {
            document.body.removeChild(modal);
            if (onCancel) onCancel();
        };
        
        modal.onclick = function(e) {
            if (e.target === modal) {
                document.body.removeChild(modal);
                if (onCancel) onCancel();
            }
        };
    }
    
    document.addEventListener('click', function(e) {
        const target = e.target;
        if (target.classList.contains('btn-refresh')) {
            const tokenId = decodeURIComponent(target.getAttribute('data-token-id') || '');
            if (tokenId) {
                e.preventDefault();
                refreshSingleToken(tokenId);
            }
        } else if (target.classList.contains('btn-delete')) {
            const tokenId = decodeURIComponent(target.getAttribute('data-token-id') || '');
            if (tokenId) {
                e.preventDefault();
                showConfirmDialog(
                    '确定要删除Token "' + tokenId + '" 吗?此操作不可撤销。',
                    function() {
                        deleteSingleToken(tokenId);
                    },
                    null,
                    "删除单个Token"
                );
            }
        }
    });
    
    async function checkTokenStatus() {
        if (!tokenStatus || !refreshTokenBtn) return;
        
        try {
            const response = await fetch('/api/token-status', {
                headers: {
                    'Authorization': 'Bearer ' + userPassword
                }
            });
            const data = await response.json();
            
            if (response.ok && data.hasToken) {
                let tokenListHtml = '';
                if (data.tokens && data.tokens.length > 0) {
                    tokenListHtml = '<div class="token-list-wrapper"><div class="token-list">';
                    data.tokens.forEach(function(token) {
                        const expiresAt = token.expiresAtDisplay || (token.expiresAt ? new Date(token.expiresAt).toLocaleString() : '未知');
                        const uploadedAt = token.uploadedAtDisplay || (token.uploadedAt ? new Date(token.uploadedAt).toLocaleString() : '未知');
                        const status = token.isExpired ? '已过期' : '有效';
                        const statusClass = token.isExpired ? 'status-expired' : 'status-valid';
                        const refreshInfo = token.wasRefreshed ? ' (已自动刷新)' : (token.refreshFailed ? ' (刷新失败)' : '');
                        tokenListHtml += '<div class="token-card" data-token-id="' + encodeURIComponent(token.id) + '">';
                        tokenListHtml += '<div class="token-header">';
                        tokenListHtml += '<div class="token-id">🔑 ' + token.id + '</div>';
                        tokenListHtml += '<div class="token-header-badges">';
                        tokenListHtml += `<div class="token-status status-usage">使用: ${token.usageCount.toLocaleString()}</div>`;
                        tokenListHtml += '<div class="token-status ' + statusClass + '">' + status + '</div>';
                        tokenListHtml += '</div>'; // close token-header-badges
                        tokenListHtml += '</div>'; // close token-header
                        tokenListHtml += '<div class="token-details">';
                        tokenListHtml += '<div><strong>过期时间:</strong> ' + expiresAt + '</div>';
                        tokenListHtml += '<div><strong>上传时间:</strong> ' + uploadedAt + '</div>';
                        if (refreshInfo) {
                            tokenListHtml += '<div><strong>状态:</strong> ' + refreshInfo + '</div>';
                        }
                        tokenListHtml += '</div>';
                        tokenListHtml += '<div class="token-actions">';
                        tokenListHtml += '<button class="btn-refresh" data-token-id="' + encodeURIComponent(token.id) + '">刷新</button>';
                        tokenListHtml += '<button class="btn-delete" data-token-id="' + encodeURIComponent(token.id) + '">删除</button>';
                        tokenListHtml += '</div>';
                        tokenListHtml += '</div>';
                    });
                    tokenListHtml += '</div></div>';
                }
                
                let headerHtml = '<div class="token-summary-badges">';
                headerHtml += `<div class="token-status status-info">🔢 Token总数: ${data.tokenCount}</div>`;
                headerHtml += '<div class="token-status status-valid">📊 状态: 有效</div>';
                headerHtml += '</div>';

                tokenStatus.innerHTML = headerHtml + tokenListHtml;
                tokenStatus.style.display = 'block';
                
                const tokenStatusButtons = document.querySelector('.token-status-buttons');
                if (tokenStatusButtons) {
                    tokenStatusButtons.style.display = 'flex';
                }
            } else {
                tokenStatus.innerHTML = '<div class="error">尚未上传凭证文件或Token已失效</div>';
                tokenStatus.style.display = 'block';
                
                const tokenStatusButtons = document.querySelector('.token-status-buttons');
                if (tokenStatusButtons) {
                    tokenStatusButtons.style.display = 'none';
                }
            }
        } catch (error) {
            addStatusMessage('获取Token状态失败: ' + error.message, 'error', 5000);
            tokenStatus.innerHTML = '<div class="error">获取Token状态失败: ' + error.message + '</div>';
            tokenStatus.style.display = 'block';
            
            const tokenStatusButtons = document.querySelector('.token-status-buttons');
            if (tokenStatusButtons) {
                tokenStatusButtons.style.display = 'none';
            }
        }
    }
    
    if (refreshTokenBtn && refreshStatus) {
        refreshTokenBtn.addEventListener('click', async function() {
            addStatusMessage('正在强制刷新所有Token...', 'info', 5000);
            try {
                const response = await fetch('/api/refresh-token', {
                    method: 'POST',
                    headers: {
                        'Authorization': 'Bearer ' + userPassword,
                    },
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    addStatusMessage('强制刷新完成！成功: ' + data.refreshResults.filter(r => r.success).length + '，失败: ' + data.refreshResults.filter(r => !r.success).length, 'success', 5000);
                    checkTokenStatus();
                } else {
                    addStatusMessage(data.error || '强制刷新失败', 'error', 5000);
                }
            } catch (error) {
                addStatusMessage('网络错误: ' + error.message, 'error', 5000);
            }
        });
    }
    
    if (deleteAllTokensBtn) {
        deleteAllTokensBtn.addEventListener('click', async function() {
            showConfirmDialog(
                '确定要删除所有Token吗?这将清除数据库中的所有Token数据，此操作不可撤销。',
                async function() {
                    addStatusMessage('正在删除所有Token...', 'info', 5000);
                    try {
                        const response = await fetch('/api/delete-all-tokens', {
                            method: 'POST',
                            headers: {
                                'Authorization': 'Bearer ' + userPassword,
                            },
                        });
                        
                        const data = await response.json();
                        
                        if (response.ok) {
                            addStatusMessage(data.message || '删除成功', 'success', 5000);
                            checkTokenStatus();
                        } else {
                            addStatusMessage(data.error || '删除失败', 'error', 5000);
                        }
                    } catch (error) {
                        addStatusMessage('网络错误: ' + error.message, 'error', 5000);
                    }
                },
                null,
                "删除所有Token"
            );
        });
    }
    
    if (sendBtn && apiStatus && apiResponse && responseContent && messageInput && modelSelect) {
        sendBtn.addEventListener('click', async function() {
            const message = messageInput.value.trim();
            const model = modelSelect.value;
            
            if (!message) {
                showStatus(apiStatus, '请输入消息', 'error');
                return;
            }
            
            showStatus(apiStatus, '正在发送请求...', 'info');
            apiResponse.classList.add('hidden');
            
            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer ' + userPassword,
                    },
                    body: JSON.stringify({
                        messages: [
                            {
                                role: "user",
                                content: message
                            }
                        ],
                        model
                    }),
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    showStatus(apiStatus, '请求成功', 'success');
                    responseContent.textContent = JSON.stringify(data, null, 2);
                    apiResponse.classList.remove('hidden');
                    checkTokenUsage();
                    loadAvailableDates();
                } else {
                    showStatus(apiStatus, data.error || '请求失败', 'error');
                }
            } catch (error) {
                showStatus(apiStatus, '网络错误: ' + error.message, 'error');
            }
        });
    }

    async function checkTokenUsage(date = null) {
        if (!totalTokensToday || !modelUsageDetails || !tokenUsageStatus) return;

        try {
            const url = date ? `/api/statistics/usage?date=${date}` : '/api/statistics/usage';
            const response = await fetch(url, {
                headers: {
                    'Authorization': 'Bearer ' + userPassword
                }
            });
            const data = await response.json();

            if (response.ok) {
                document.getElementById('total-tokens-today').textContent = data.total_tokens_today.toLocaleString();
                document.getElementById('total-calls-today').textContent = data.total_calls_today.toLocaleString();

                let detailsHtml = '';
                if (Object.keys(data.models).length > 0) {
                    detailsHtml = '<div class="token-list">';
                    for (const [model, usage] of Object.entries(data.models)) {
                        detailsHtml += `
                            <div class="token-card usage-stats-card">
                                <div class="usage-model-name">${model}</div>
                                <div class="usage-stats-badges">
                                    <div class="token-status status-tokens">Tokens: ${usage.total_tokens.toLocaleString()}</div>
                                    <div class="token-status status-calls">调用: ${usage.call_count.toLocaleString()}</div>
                                </div>
                            </div>
                        `;
                    }
                    detailsHtml += '</div>';
                } else {
                    detailsHtml = '<p>暂无分模型用量数据。</p>';
                }
                modelUsageDetails.innerHTML = detailsHtml;
                tokenUsageStatus.style.display = 'none';
            } else {
                showStatus(tokenUsageStatus, data.error || '获取用量失败', 'error');
            }
        } catch (error) {
            showStatus(tokenUsageStatus, '网络错误: ' + error.message, 'error');
        }
    }
    
    async function refreshSingleToken(tokenId) {
        const card = document.querySelector('[data-token-id="' + encodeURIComponent(tokenId) + '"]');
        if (!card) return;
        
        const refreshBtn = card.querySelector('.btn-refresh');
        const deleteBtn = card.querySelector('.btn-delete');
        
        if (refreshBtn) {
            refreshBtn.disabled = true;
            refreshBtn.textContent = '刷新中...';
        }
        if (deleteBtn) {
            deleteBtn.disabled = true;
        }
        
        try {
            const response = await fetch('/api/refresh-single-token', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + userPassword,
                },
                body: JSON.stringify({ tokenId }),
            });
            
            const data = await response.json();
            
            if (response.ok && data.success) {
                addStatusMessage('Token ' + tokenId + ' 刷新成功', 'success', 5000);
                checkTokenStatus();
            } else {
                addStatusMessage('Token ' + tokenId + ' 刷新失败: ' + (data.error || '未知错误'), 'error', 5000);
                checkTokenStatus();
            }
        } catch (error) {
            addStatusMessage('Token ' + tokenId + ' 刷新失败: ' + error.message, 'error', 5000);
            checkTokenStatus();
        } finally {
            const updatedCard = document.querySelector('[data-token-id="' + encodeURIComponent(tokenId) + '"]');
            if (updatedCard) {
                const updatedRefreshBtn = updatedCard.querySelector('.btn-refresh');
                const updatedDeleteBtn = updatedCard.querySelector('.btn-delete');
                
                if (updatedRefreshBtn) {
                    updatedRefreshBtn.disabled = false;
                    updatedRefreshBtn.textContent = '刷新';
                }
                if (updatedDeleteBtn) {
                    updatedDeleteBtn.disabled = false;
                }
            }
        }
    }
    
    async function deleteSingleToken(tokenId) {
        const card = document.querySelector('[data-token-id="' + encodeURIComponent(tokenId) + '"]');
        if (!card) return;
        
        const refreshBtn = card.querySelector('.btn-refresh');
        const deleteBtn = card.querySelector('.btn-delete');
        
        if (refreshBtn) {
            refreshBtn.disabled = true;
        }
        if (deleteBtn) {
            deleteBtn.disabled = true;
            deleteBtn.textContent = '删除中...';
        }
        
        try {
            const response = await fetch('/api/delete-token', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + userPassword,
                },
                body: JSON.stringify({ tokenId }),
            });
            
            const data = await response.json();
            
            if (response.ok && data.success) {
                addStatusMessage('Token ' + tokenId + ' 删除成功', 'success', 5000);
                checkTokenStatus();
            } else {
                addStatusMessage('Token ' + tokenId + ' 删除失败: ' + (data.error || '未知错误'), 'error', 5000);
            }
        } catch (error) {
            addStatusMessage('Token ' + tokenId + ' 删除失败: ' + error.message, 'error', 5000);
        } finally {
            if (refreshBtn) {
                refreshBtn.disabled = false;
            }
            if (deleteBtn) {
                deleteBtn.disabled = false;
                deleteBtn.textContent = '删除';
            }
        }
    }
    
    const statusQueue = [];
    let statusTimeouts = new Map();
    
    function showStatus(element, message, type) {
        if (!element) return;
        
        if ((element.id === 'token-status' || element.id === 'refresh-status') && 
            (message.includes('刷新') || message.includes('删除') || message.includes('成功') || message.includes('失败'))) {
            addStatusMessage(message, type, 5000);
            return;
        }
        
        if (element.hideTimeout) {
            clearTimeout(element.hideTimeout);
        }
        
        if (element.id === 'token-status' || element.id === 'refresh-status') {
            element.className = 'status ' + type;
        } else {
            element.className = 'status floating ' + type;
        }
        element.textContent = message;
        element.style.display = 'block';
        
        if (!message.includes('等待授权完成') && !message.includes('剩余时间')) {
            element.hideTimeout = setTimeout(() => {
                element.style.display = 'none';
                element.hideTimeout = null;
            }, 5000);
        }
    }
    
    function addStatusMessage(message, type, duration = 5000) {
        if (!statusContainer) return;
        
        statusContainer.style.display = 'flex';
        
        const statusElement = document.createElement('div');
        statusElement.className = 'status floating ' + type;
        statusElement.textContent = message;
        statusElement.style.display = 'block';
        
        statusContainer.appendChild(statusElement);
        
        const messageId = Date.now() + Math.random();
        statusQueue.push({ id: messageId, element: statusElement });
        
        const timeoutId = setTimeout(() => {
            removeStatusMessage(messageId);
        }, duration);
        
        statusTimeouts.set(messageId, timeoutId);
    }
    
    function removeStatusMessage(messageId) {
        const messageIndex = statusQueue.findIndex(msg => msg.id === messageId);
        if (messageIndex === -1) return;
        
        const message = statusQueue[messageIndex];
        
        if (statusTimeouts.has(messageId)) {
            clearTimeout(statusTimeouts.get(messageId));
            statusTimeouts.delete(messageId);
        }
        
        message.element.classList.add('removing');
        
        setTimeout(() => {
            if (message.element.parentNode) {
                message.element.parentNode.removeChild(message.element);
            }
            
            statusQueue.splice(messageIndex, 1);
            
            if (statusQueue.length === 0) {
                statusContainer.style.display = 'none';
            }
        }, 300);
    }

    async function loadVersion() {
        const versionElement = document.getElementById('current-version');
        if (!versionElement) return;
        
        try {
            const response = await fetch('/api/version', {
                headers: {
                    'Authorization': 'Bearer ' + userPassword
                }
            });
            
            if (response.ok) {
                const data = await response.json();
                versionElement.textContent = data.version;
            } else {
                versionElement.textContent = '获取失败';
            }
        } catch (error) {
            console.error('获取版本号失败:', error);
            versionElement.textContent = '获取失败';
        }
    }
    
    async function loadAvailableDates() {
        try {
            const response = await fetch('/api/statistics/available-dates', {
                headers: {
                    'Authorization': 'Bearer ' + userPassword
                }
            });
            
            if (response.ok) {
                const data = await response.json();
                availableDates.clear();
                data.dates.forEach(date => availableDates.add(date));
                if (isDatePickerOpen) {
                    renderCalendar();
                }
            }
        } catch (error) {
        }
    }

    function initCustomDatePicker() {
        if (usageDateInput) {
            usageDateInput.addEventListener('click', toggleDatePicker);
            usageDateInput.addEventListener('touchstart', (e) => {
                e.preventDefault();
                toggleDatePicker();
            });
        }
        if (datePickerBtn) {
            datePickerBtn.addEventListener('click', toggleDatePicker);
            datePickerBtn.addEventListener('touchstart', (e) => {
                e.preventDefault();
                toggleDatePicker();
            });
        }

        if (prevMonthBtn) {
            prevMonthBtn.addEventListener('click', () => {
                currentDate.setMonth(currentDate.getMonth() - 1);
                renderCalendar();
            });
            prevMonthBtn.addEventListener('touchstart', (e) => {
                e.preventDefault();
                currentDate.setMonth(currentDate.getMonth() - 1);
                renderCalendar();
            });
        }
        if (nextMonthBtn) {
            nextMonthBtn.addEventListener('click', () => {
                currentDate.setMonth(currentDate.getMonth() + 1);
                renderCalendar();
            });
            nextMonthBtn.addEventListener('touchstart', (e) => {
                e.preventDefault();
                currentDate.setMonth(currentDate.getMonth() + 1);
                renderCalendar();
            });
        }

        document.addEventListener('click', (event) => {
            if (!event.target.closest('.custom-date-picker')) {
                closeDatePicker();
            }
        });
        
        document.addEventListener('touchstart', (event) => {
            if (!event.target.closest('.custom-date-picker') && isDatePickerOpen) {
                closeDatePicker();
            }
        });

        window.addEventListener('resize', () => {
            if (isDatePickerOpen) {
                adjustDatePickerPosition();
            }
        });

        renderCalendar();
    }

    function toggleDatePicker() {
        if (isDatePickerOpen) {
            closeDatePicker();
        } else {
            openDatePicker();
        }
    }

    function openDatePicker() {
        if (datePickerDropdown) {
            datePickerDropdown.classList.remove('hidden');
            isDatePickerOpen = true;
            
            adjustDatePickerPosition();
            
            renderCalendar();
        }
    }

    function adjustDatePickerPosition() {
        if (!datePickerDropdown || !usageDateInput) return;
        
        const rect = usageDateInput.getBoundingClientRect();
        const viewportWidth = window.innerWidth;
        const dropdownWidth = 320;
        
        datePickerDropdown.style.left = '';
        datePickerDropdown.style.right = '';
        datePickerDropdown.style.width = '';
        
        if (rect.left + dropdownWidth > viewportWidth - 20) {
            datePickerDropdown.style.left = 'auto';
            datePickerDropdown.style.right = '0';
        }
        
        if (viewportWidth <= 480) {
            datePickerDropdown.style.left = '-5px';
            datePickerDropdown.style.right = '-5px';
            datePickerDropdown.style.width = 'calc(100% + 10px)';
        } else if (viewportWidth <= 768) {
            datePickerDropdown.style.left = '0';
            datePickerDropdown.style.right = '0';
            datePickerDropdown.style.width = '100%';
        }
    }

    function closeDatePicker() {
        if (datePickerDropdown) {
            datePickerDropdown.classList.add('hidden');
            isDatePickerOpen = false;
        }
    }

    function renderCalendar() {
        if (!currentMonthYear || !calendarDays) return;

        const year = currentDate.getFullYear();
        const month = currentDate.getMonth();
        
        const monthNames = ['1月', '2月', '3月', '4月', '5月', '6月', 
                           '7月', '8月', '9月', '10月', '11月', '12月'];
        currentMonthYear.textContent = `${year}年 ${monthNames[month]}`;

        calendarDays.innerHTML = '';

        const firstDay = new Date(year, month, 1);
        const lastDay = new Date(year, month + 1, 0);
        const firstDayOfWeek = firstDay.getDay();
        const daysInMonth = lastDay.getDate();

        const prevMonth = new Date(year, month - 1, 0);
        for (let i = firstDayOfWeek - 1; i >= 0; i--) {
            const day = prevMonth.getDate() - i;
            const dayElement = createDayElement(day, true);
            calendarDays.appendChild(dayElement);
        }

        for (let day = 1; day <= daysInMonth; day++) {
            const dayElement = createDayElement(day, false);
            calendarDays.appendChild(dayElement);
        }

        const totalCells = calendarDays.children.length;
        const remainingCells = 42 - totalCells;
        for (let day = 1; day <= remainingCells; day++) {
            const dayElement = createDayElement(day, true);
            calendarDays.appendChild(dayElement);
        }
    }

    function createDayElement(day, isOtherMonth) {
        const dayElement = document.createElement('div');
        dayElement.className = 'calendar-day';
        dayElement.textContent = day;

        if (isOtherMonth) {
            dayElement.classList.add('other-month');
            return dayElement;
        }

        const year = currentDate.getFullYear();
        const month = currentDate.getMonth();
        const dateString = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;

        const today = new Date();
        if (year === today.getFullYear() && month === today.getMonth() && day === today.getDate()) {
            dayElement.classList.add('today');
        }

        if (selectedDate === dateString) {
            dayElement.classList.add('selected');
        }

        if (availableDates.has(dateString)) {
            dayElement.classList.add('has-data');
        }

        dayElement.addEventListener('click', () => {
            selectDate(dateString);
        });
        
        dayElement.addEventListener('touchstart', (e) => {
            e.preventDefault();
            dayElement.style.transform = 'scale(0.95)';
            setTimeout(() => {
                dayElement.style.transform = '';
                selectDate(dateString);
            }, 100);
        });

        return dayElement;
    }

    function selectDate(dateString) {
        selectedDate = dateString;
        usageDateInput.value = dateString;
        renderCalendar();
        closeDatePicker();
        
        checkTokenUsage(dateString);
    }

    function formatDateForDisplay(dateString) {
        const date = new Date(dateString + 'T00:00:00');
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    }
});