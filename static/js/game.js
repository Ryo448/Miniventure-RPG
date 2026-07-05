const Game = {
    adventureId: null,
    characterCode: null,
    isSpectator: false,
    typingTimer: null,
    actionInProgress: false,
    abilities: [],
    cooldowns: {},
    lastSceneDescription: null,
    currentTaskId: null,
    npcs: [],
    enemies: [],
    allCharacters: [],

    init() {
        const advEl = document.getElementById('adventure-id');
        const charEl = document.getElementById('character-code');

        this.adventureId = advEl?.dataset?.adventureId || advEl?.value || (typeof adventureCode !== 'undefined' ? adventureCode : null);
        this.characterCode = charEl?.dataset?.characterCode || charEl?.value || (typeof characterCode !== 'undefined' ? characterCode : null);
        this.isSpectator = !this.characterCode;

        if (!this.adventureId) {
            const pathParts = window.location.pathname.split('/');
            this.adventureId = pathParts[pathParts.length - 2];
        }

        this.connectSSE();
        this.setupActionForm();
        this.setupActionButtons();
        this.setupInventoryListeners();
        this.setupModalTriggers();
        this.setupPartyClickHandlers();
        this.loadInitialScene();
    },

    connectSSE() {
        Realtime.connectToAdventure(this.adventureId, {
            onConnection: (connected) => {
                const indicator = document.getElementById('connection-status');
                if (indicator) {
                    indicator.textContent = connected ? 'Conectado' : 'Desconectado';
                    indicator.className = connected ? 'status-connected' : 'status-disconnected';
                }
            },
            onSceneUpdate: (data) => this.updateScene(data),
            onTurnChange: (data) => this.updateTurn(data),
            onInventoryUpdate: (data) => this.updateInventory(data),
            onCoinsUpdate: (data) => this.updateCoins(data),
            onLifeUpdate: (data) => this.updateLife(data),
            onTradeRequest: (data) => this.handleTradeRequest(data),
            onChatMessage: (data) => this.handleChatMessage(data),
            onEnemyUpdate: (data) => this.updateEnemies(data),
            onTaskResult: (data) => this.handleTaskResult(data),
        });
    },

    async handleTaskResult(data) {
        if (!data || !data.taskId) return;
        if (this.currentTaskId !== data.taskId) return;

        if (data.status === 'completed') {
            this.currentTaskId = null;
            this.setActionInProgress(false);
            const submitBtn = document.getElementById('action-submit-btn');
            if (submitBtn) submitBtn.disabled = false;
            if (data.result && data.result.narration) {
                const narrationEl = document.getElementById('scene-narration');
                this.typeText(narrationEl, data.result.narration);
            }
        } else if (data.status === 'failed') {
            this.currentTaskId = null;
            const submitBtn = document.getElementById('action-submit-btn');
            if (submitBtn) submitBtn.disabled = false;
            const result = data.result || {};
            if (result.retryable && (result.botCode || result.characterCode)) {
                this.setBotActionInProgress(false);
                this._showRetryableError(data.error || 'Erro ao processar ação.', result);
            } else {
                this.setActionInProgress(false);
                this._showActionError(data.error || 'Erro ao processar ação.');
            }
        }
    },

    _showRetryableError(message, info) {
        const narrationEl = document.getElementById('scene-narration');
        if (!narrationEl) return;
        const existing = document.getElementById('retry-action-box');
        if (existing) existing.remove();
        const isBot = !!info.botCode;
        const charCode = info.botCode || info.characterCode;
        const charName = info.botName || info.characterName || charCode;
        const box = document.createElement('div');
        box.id = 'retry-action-box';
        box.style.cssText = 'margin-top:12px; padding:12px; border:1px solid var(--accent-danger); border-radius:8px; background:rgba(139,26,26,0.15);';
        const msg = document.createElement('p');
        msg.style.cssText = 'color:var(--accent-danger); margin:0 0 10px 0;';
        msg.textContent = (isBot ? `${charName}: ` : '') + message;
        box.appendChild(msg);
        const retryBtn = document.createElement('button');
        retryBtn.className = 'btn btn-primary';
        retryBtn.textContent = isBot ? 'Tentar novamente' : 'Reenviar ação';
        retryBtn.style.marginRight = '8px';
        retryBtn.onclick = () => {
            box.remove();
            if (isBot) {
                this.maybeTriggerBotAction(charCode);
            } else {
                this.setActionInProgress(false);
                this.submitAction(info.lastAction || 'age de acordo com sua personalidade');
            }
        };
        const skipBtn = document.createElement('button');
        skipBtn.className = 'btn';
        skipBtn.textContent = 'Pular turno';
        skipBtn.style.display = this.isSpectator ? 'none' : '';
        skipBtn.onclick = () => {
            box.remove();
            this.setBotActionInProgress(true, 'Pulando turno...');
            API.passTurn(this.adventureId, charCode).then(() => {
                this.setBotActionInProgress(false);
            }).catch((err) => {
                this._showActionError(err.message || 'Erro ao pular turno.');
                this.setBotActionInProgress(false);
            });
        };
        box.appendChild(retryBtn);
        box.appendChild(skipBtn);
        narrationEl.appendChild(box);
        narrationEl.scrollTop = narrationEl.scrollHeight;
    },

    setBotActionInProgress(inProgress, message) {
        this.actionInProgress = inProgress;
        const statusEl = document.getElementById('action-status');
        if (statusEl) {
            statusEl.textContent = inProgress ? (message || 'Processando ação...') : '';
            statusEl.style.display = inProgress ? 'block' : 'none';
        }
    },

    _showActionError(msg) {
        const narrationEl = document.getElementById('scene-narration');
        if (!narrationEl) return;
        const p = document.createElement('p');
        p.className = 'action-error';
        p.style.color = 'var(--accent-danger)';
        p.textContent = msg;
        narrationEl.appendChild(p);
        narrationEl.scrollTop = narrationEl.scrollHeight;
    },

    typeText(element, text) {
        if (this.typingTimer) {
            clearInterval(this.typingTimer);
        }

        element.textContent = '';
        let index = 0;

        this.typingTimer = setInterval(() => {
            if (index < text.length) {
                element.textContent += text[index];
                index++;
                element.scrollTop = element.scrollHeight;
            } else {
                clearInterval(this.typingTimer);
                this.typingTimer = null;
            }
        }, 20);
    },

    updateScene(data) {
        const scene = data.scene || data;
        const sceneTitle = document.getElementById('scene-title');
        const narrationEl = document.getElementById('scene-narration');
        const npcsEl = document.getElementById('npc-row');
        const npcSection = document.getElementById('npc-section');
        const enemiesEl = document.getElementById('enemy-row');
        const enemySection = document.getElementById('enemy-section');

        if (sceneTitle && scene.title) {
            sceneTitle.textContent = scene.title;
        }
        if (narrationEl && scene.description) {
            if (this.lastSceneDescription === scene.description) return;
            this.lastSceneDescription = scene.description;
            this.typeText(narrationEl, scene.description);
        }

        if (npcsEl && scene.availableNPCs) {
            this.npcs = scene.availableNPCs || [];
            npcSection.style.display = this.npcs.length > 0 ? 'block' : 'none';
            npcsEl.innerHTML = this.npcs.map((n) => {
                const key = n.code || n.id || n.name;
                const life = n.life || {};
                const cur = (typeof life === 'object' ? life.currentPercent : life) ?? '?';
                const max = (typeof life === 'object' ? life.maxPercent : 100) ?? '?';
                const state = (typeof life === 'object' ? life.state : 'alive') ?? 'alive';
                const statePT = { alive: 'Vivo', dead: 'Morto', unconscious: 'Inconsciente' }[state] || state;
                const raceTag = n.race ? ` <span style="color:var(--text-muted); font-size:0.78rem;">${n.race}</span>` : '';
                return `<div class="party-member" data-char-code="${key}" data-entity-type="npc"><span class="party-status-dot" style="background:var(--gold);"></span><span>${n.name}</span>${raceTag}<span class="life-tooltip">Vida: ${cur}/${max} (${statePT})</span></div>`;
            }).join('');
        }
        if (enemiesEl && scene.availableEnemies) {
            this.updateEnemies({enemies: scene.availableEnemies});
        }
    },

    updateTurn(data) {
        const turnIndicator = document.getElementById('turn-indicator');
        const isMyTurn = data.characterCode === this.characterCode;

        if (turnIndicator) {
            turnIndicator.className = isMyTurn ? 'turn-indicator turn-mine' : 'turn-indicator turn-other';
            turnIndicator.textContent = 'Turno de: ' + (data.characterName || data.characterCode || '?');
        }

        const actionForm = document.getElementById('action-form');
        if (actionForm && !this.isSpectator) {
            actionForm.style.display = isMyTurn ? 'block' : 'none';
        }

        document.querySelectorAll('.action-btn').forEach((btn) => {
            btn.disabled = !isMyTurn || this.actionInProgress;
        });

        document.querySelectorAll('.party-member').forEach((pm) => {
            pm.classList.toggle('party-member-active', pm.dataset.charCode === data.characterCode);
        });

        if (data.characterCode && data.characterCode !== this.characterCode) {
            const turnChar = (this.allCharacters || []).find((c) => c.code === data.characterCode);
            if (turnChar && turnChar.isBot) {
                this.maybeTriggerBotAction(data.characterCode);
            }
        }
    },

    maybeTriggerBotAction(botCode) {
        if (this.botActionTimer) clearTimeout(this.botActionTimer);
        this.botActionTimer = setTimeout(() => this.doBotAction(botCode), 1500);
    },

    async doBotAction(botCode) {
        if (this.actionInProgress && this.currentTaskId) return;
        const bot = (this.allCharacters || []).find((c) => c.code === botCode);
        if (!bot) return;
        try {
            this.setActionInProgress(true, 'Bot agindo...');
            const res = await API.botAct(this.adventureId, botCode);
            if (res && res.taskId) {
                this.currentTaskId = res.taskId;
                if (!Realtime.isConnected()) {
                    await this._pollTaskResult(res.taskId);
                }
            }
        } catch (e) {
            console.error('[bot] auto-action failed', e);
            this.setActionInProgress(false);
        }
    },

    updateInventory(data) {
        if (data.characterCode && data.characterCode !== this.characterCode) return;
        const slotsEl = document.getElementById('inventory-slots');
        if (!slotsEl) return;

        const items = data.items || data.inventory || [];
        slotsEl.innerHTML = '';

        items.forEach((item, index) => {
            const slot = document.createElement('div');
            slot.className = item ? 'inv-slot inv-slot-filled' : 'inv-slot';
            slot.dataset.slotIndex = index;

            if (item) {
                slot.textContent = item.name ? item.name.charAt(0).toUpperCase() : '📦';
                slot.title = item.description || item.name || `Item ${index}`;
            }
            slotsEl.appendChild(slot);
        });

        this.setupInventoryListeners();
    },

    updateCoins(data) {
        if (data.characterCode && data.characterCode !== this.characterCode) return;
        const coinsEl = document.getElementById('coins-display');
        if (coinsEl) {
            const amount = data.coins?.amount ?? data.coins ?? data.amount ?? 0;
            coinsEl.textContent = amount;
        }
    },

    updateLife(data) {
        if (data.characterCode && data.characterCode !== this.characterCode) return;
        const lifeBar = document.getElementById('life-bar');
        const lifeText = document.getElementById('life-text');

        const current = data.life?.currentPercent ?? data.currentLife ?? data.current ?? 0;
        const max = data.life?.maxPercent ?? data.maxLife ?? data.max ?? 100;

        if (lifeBar) {
            const pct = Math.max(0, Math.min(100, (current / max) * 100));
            lifeBar.style.width = `${pct}%`;
        }
        if (lifeText) {
            lifeText.textContent = `${current}%`;
        }
    },

    updateEnemies(data) {
        const enemiesEl = document.getElementById('enemy-row');
        const enemySection = document.getElementById('enemy-section');
        if (!enemiesEl) return;

        const enemies = data.enemies || [];
        if (enemies.length === 0) {
            if (enemySection) enemySection.style.display = 'none';
            return;
        }
        if (enemySection) enemySection.style.display = 'block';

        this.enemies = enemies;
        enemiesEl.innerHTML = enemies.map((enemy) => {
            const lifeTip = `Vida: ${enemy.currentLife ?? '?'}/${enemy.maxLife ?? '?'}`;
            return `
            <div class="party-member" data-char-code="${enemy.code}" data-entity-type="enemy">
                <span class="party-status-dot" style="background:#e05555;"></span>
                <span>${enemy.name}</span>
                <span style="color:var(--text-muted); font-size:0.78rem;">${enemy.currentLife ?? '?'}/${enemy.maxLife ?? '?'}</span>
                <span class="life-tooltip">${lifeTip}</span>
            </div>`;
        }).join('');
    },

    handleTradeRequest(data) {
        const notification = document.getElementById('trade-incoming');
        if (notification) {
            notification.style.display = 'block';
            notification.innerHTML = `
                <p style="margin-bottom:8px;">${data.fromName || 'Alguém'} quer trocar com você!</p>
                <button onclick="TradeUI.respondTrade(true)" class="btn btn-sm" style="margin-right:8px;">Aceitar</button>
                <button onclick="TradeUI.respondTrade(false)" class="btn btn-sm btn-danger">Recusar</button>
            `;
        }
    },

    handleChatMessage(data) {
        if (typeof ChatUI !== 'undefined') {
            ChatUI.handleIncomingMessage(data);
        }
    },

    setupActionForm() {
        const form = document.getElementById('action-form');
        if (!form) return;

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const input = document.getElementById('action-input');
            if (!input || !input.value.trim()) return;

            const action = input.value.trim();
            input.value = '';
            await this.submitAction(action);
        });
    },

    setupActionButtons() {
        document.querySelectorAll('.action-btn').forEach((btn) => {
            btn.addEventListener('click', () => {
                const action = btn.dataset.action;
                this.handleActionButton(action);
            });
        });
    },

    async handleActionButton(action) {
        if (this.actionInProgress) return;

        switch (action) {
            case 'usar_item':
                this.openItemSelector('use');
                break;
            case 'curar':
                this.openHealSelector();
                break;
            case 'trocar':
                this.openTradeModal();
                break;
            case 'conversar':
                this.openChatSelector();
                break;
            case 'inspecionar':
                await this.submitAction('inspecionar arredores');
                break;
            case 'passar_turno':
                await this.passTurn();
                break;
            default:
                await this.submitAction(action);
        }
    },

    openItemSelector(mode) {
        const modal = document.getElementById('item-selector-modal');
        if (!modal) return;

        const slots = document.querySelectorAll('.inventory-slot.occupied');
        const listEl = modal.querySelector('.item-selector-list');
        if (!listEl) return;

        listEl.innerHTML = '';
        slots.forEach((slot) => {
            const idx = slot.dataset.slotIndex;
            const item = document.createElement('button');
            item.type = 'button';
            item.className = 'item-selector-entry';
            item.textContent = slot.querySelector('.item-name')?.textContent || `Item ${idx}`;
            item.addEventListener('click', async () => {
                modal.style.display = 'none';
                if (mode === 'use') {
                    await this.useItem(parseInt(idx));
                } else {
                    await this.dropItem(parseInt(idx));
                }
            });
            listEl.appendChild(item);
        });

        modal.style.display = 'flex';
    },

    setupInventoryListeners() {
        document.querySelectorAll('.inventory-slot.occupied').forEach((slot) => {
            slot.onclick = () => {
                const idx = parseInt(slot.dataset.slotIndex);
                if (confirm('O que deseja fazer com este item?\n\nOK = Usar\nCancelar = Largar')) {
                    this.useItem(idx);
                } else {
                    this.dropItem(idx);
                }
            };
        });
    },

    setupModalTriggers() {
        document.querySelectorAll('.modal-close').forEach((btn) => {
            btn.addEventListener('click', () => {
                btn.closest('.modal').style.display = 'none';
            });
        });

        document.querySelectorAll('.modal-overlay').forEach((overlay) => {
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) {
                    overlay.style.display = 'none';
                }
            });
        });
    },

    async submitAction(action) {
        if (this.actionInProgress || this.isSpectator) return;
        this.setActionInProgress(true, 'Processando ação...');

        try {
            const result = await API.postAction(this.adventureId, this.characterCode, action);
            if (result.taskId) {
                this.currentTaskId = result.taskId;
                if (!Realtime.isConnected()) {
                    await this._pollTaskResult(result.taskId);
                }
            } else {
                this.displayActionResult(result);
                this.setActionInProgress(false);
            }
        } catch (err) {
            this.showGameError(err.message);
            this.setActionInProgress(false);
        }
    },

    async _pollTaskResult(taskId) {
        const poll = async (resolve, reject) => {
            let attempts = 0;
            const maxAttempts = 90;
            const interval = setInterval(async () => {
                attempts++;
                try {
                    const task = await API.getTask(this.adventureId, taskId);
                    if (task.status === 'completed') {
                        clearInterval(interval);
                        this.displayActionResult(task.result || task);
                        this.setActionInProgress(false);
                        resolve();
                    } else if (task.status === 'failed') {
                        clearInterval(interval);
                        this.showGameError(task.error || 'A ação falhou.');
                        this.setActionInProgress(false);
                        resolve();
                    } else if (attempts >= maxAttempts) {
                        clearInterval(interval);
                        this.showGameError('Tempo esgotado aguardando resposta do Mestre.');
                        this.setActionInProgress(false);
                        resolve();
                    }
                } catch (err) {
                }
            }, 1500);
        };
        return new Promise(poll);
    },

    async passTurn() {
        if (this.actionInProgress || this.isSpectator) return;
        this.setActionInProgress(true, 'Passando turno...');

        try {
            await API.passTurn(this.adventureId, this.characterCode);
        } catch (err) {
            this.showGameError(err.message);
        } finally {
            this.setActionInProgress(false);
        }
    },

    async useItem(slotIndex) {
        if (this.actionInProgress || this.isSpectator) return;
        this.setActionInProgress(true, 'Usando item...');

        try {
            await API.useItem(this.adventureId, this.characterCode, slotIndex);
        } catch (err) {
            this.showGameError(err.message);
        } finally {
            this.setActionInProgress(false);
        }
    },

    async dropItem(slotIndex) {
        if (this.actionInProgress || this.isSpectator) return;
        this.setActionInProgress(true, 'Largando item...');

        try {
            await API.dropItem(this.adventureId, this.characterCode, slotIndex);
        } catch (err) {
            this.showGameError(err.message);
        } finally {
            this.setActionInProgress(false);
        }
    },

    openHealSelector() {
        const modal = document.getElementById('heal-modal');
        if (modal) {
            modal.style.display = 'flex';
            if (typeof HealUI !== 'undefined') {
                HealUI.loadTargets(this.adventureId, this.characterCode);
            }
        }
    },

    openTradeModal() {
        const modal = document.getElementById('trade-modal');
        if (modal) {
            modal.style.display = 'flex';
            if (typeof TradeUI !== 'undefined') {
                TradeUI.init(this.adventureId, this.characterCode);
            }
        }
    },

    openChatSelector() {
        const modal = document.getElementById('chat-selector-modal');
        if (modal) {
            modal.style.display = 'flex';
            if (typeof ChatUI !== 'undefined') {
                ChatUI.loadTargets(this.adventureId, this.characterCode);
            }
        }
    },

    displayActionResult(result) {
        const narrationEl = document.getElementById('scene-narration');
        if (!narrationEl) return;

        const entry = document.createElement('div');
        entry.className = 'action-log-entry';
        entry.style.borderTop = '1px solid var(--border-subtle)';
        entry.style.marginTop = '12px';
        entry.style.paddingTop = '12px';
        const narration = result.narration || result.message || '';
        if (narration) {
            const p = document.createElement('p');
            p.className = 'narration-paragraph';
            p.innerHTML = narration;
            entry.appendChild(p);
        }
        narrationEl.appendChild(entry);
        narrationEl.scrollTop = narrationEl.scrollHeight;
    },

    setActionInProgress(inProgress, message) {
        this.actionInProgress = inProgress;
        const statusEl = document.getElementById('action-status');
        const input = document.getElementById('action-input');

        if (statusEl) {
            statusEl.textContent = inProgress ? (message || 'Processando ação...') : '';
            statusEl.style.display = inProgress ? 'block' : 'none';
        }

        document.querySelectorAll('.action-btn').forEach((btn) => {
            btn.disabled = inProgress;
        });

        if (input) {
            input.disabled = inProgress;
        }
    },

    showGameError(message) {
        const errorEl = document.getElementById('game-error');
        if (errorEl) {
            errorEl.textContent = message || 'Ocorreu um erro.';
            errorEl.style.display = 'block';
            setTimeout(() => {
                errorEl.style.display = 'none';
            }, 5000);
        }
    },

    async loadInitialScene() {
        if (!this.adventureId) return;
        try {
            const scenePromise = API.getCurrentScene(this.adventureId);
            const charsPromise = this.characterCode ? API.getAdventureCharacters(this.adventureId) : null;
            const charPromise = this.characterCode ? API.getAdventureCharacter(this.adventureId, this.characterCode) : null;

            const scene = await scenePromise;
            if (scene) {
                scene.description = scene.currentContext || scene.mainDescription || '';
                scene.sceneLog = scene.sceneLog || [];
            }
            this.updateScene({scene: scene});

            if (charsPromise) {
                try {
                    const characters = await charsPromise;
                    this.allCharacters = characters || [];
                    this.populateLifeTooltips();
                } catch (e) {}
            }

            if (scene && scene.currentTurnCharacterCode) {
                let turnName = scene.currentTurnCharacterCode;
                const turnChar = (this.allCharacters || []).find((c) => c.code === scene.currentTurnCharacterCode);
                if (turnChar) turnName = turnChar.name;
                this.updateTurn({
                    characterCode: scene.currentTurnCharacterCode,
                    characterName: turnName
                });
            }
            this.updateScene({scene: scene});

            if (scene && scene.currentTurnCharacterCode) {
                let turnName = scene.currentTurnCharacterCode;
                if (charsPromise) {
                    try {
                        const characters = await charsPromise;
                        this.allCharacters = characters || [];
                        const turnChar = characters.find((c) => c.code === scene.currentTurnCharacterCode);
                        if (turnChar) turnName = turnChar.name;
                    } catch (e) {}
                }
            }
            this.updateScene({scene: scene});

            if (scene && scene.currentTurnCharacterCode) {
                let turnName = scene.currentTurnCharacterCode;
                if (charsPromise) {
                    try {
                        const characters = await charsPromise;
                        const turnChar = characters.find((c) => c.code === scene.currentTurnCharacterCode);
                        if (turnChar) turnName = turnChar.name;
                    } catch (e) {}
                }
                this.updateTurn({
                    characterCode: scene.currentTurnCharacterCode,
                    characterName: turnName
                });
            }

            if (charPromise) {
                const character = await charPromise;
                if (character) {
                    this.updateInventory({ items: character.inventory || [] });
                    this.updateCoins({ coins: character.coins || 0 });
                    this.updateLife({ life: character.life || {} });
                }
            }
        } catch (err) {
            // Scene may not be ready yet (still generating)
        }
    },

    destroy() {
        Realtime.disconnect();
        if (this.typingTimer) clearInterval(this.typingTimer);
    },

    setupPartyClickHandlers() {
        document.addEventListener('click', (e) => {
            const row = e.target.closest('.party-member');
            if (!row) return;
            const code = row.dataset.charCode;
            const type = row.dataset.entityType;
            if (!code || !type) return;
            this.openCharViewModal(code, type);
        });

        const closeBtn = document.getElementById('char-view-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                document.getElementById('char-view-modal').style.display = 'none';
            });
        }
        const overlay = document.getElementById('char-view-modal');
        if (overlay) {
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) overlay.style.display = 'none';
            });
        }
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                const m = document.getElementById('char-view-modal');
                if (m) m.style.display = 'none';
            }
        });
    },

    populateLifeTooltips() {
        const chars = this.allCharacters || [];
        const byCode = {};
        chars.forEach(c => { byCode[c.code] = c; });
        document.querySelectorAll('#player-row .party-member, #bot-row .party-member').forEach(row => {
            const code = row.dataset.charCode;
            const c = byCode[code];
            if (!c) return;
            const life = c.life || {};
            const cur = (typeof life === 'object' ? life.currentPercent : life) ?? '?';
            const max = (typeof life === 'object' ? life.maxPercent : 100) ?? '?';
            const state = (typeof life === 'object' ? life.state : 'alive') ?? 'alive';
            const statePT = { alive: 'Vivo', dead: 'Morto', unconscious: 'Inconsciente' }[state] || state;
            let tip = row.querySelector('.life-tooltip');
            if (!tip) {
                tip = document.createElement('span');
                tip.className = 'life-tooltip';
                row.appendChild(tip);
            }
            tip.textContent = `Vida: ${cur}/${max} (${statePT})`;
        });
    },

    async openCharViewModal(code, type) {
        const modal = document.getElementById('char-view-modal');
        const title = document.getElementById('char-view-title');
        const body = document.getElementById('char-view-body');
        if (!modal || !title || !body) return;
        body.innerHTML = '<p style="color:var(--text-muted);">Carregando...</p>';
        modal.style.display = 'flex';

        try {
            if (type === 'player' || type === 'bot') {
                const c = await API.getAdventureCharacter(this.adventureId, code);
                title.textContent = (c.name || 'Personagem') + (type === 'bot' ? ' (Bot)' : '');
                body.innerHTML = this.renderCharFicha(c);
            } else if (type === 'npc') {
                const npc = (this.npcs || []).find(n => (n.code || n.id || n.name) === code);
                if (!npc) throw new Error('NPC não encontrado.');
                title.textContent = npc.name || 'NPC';
                body.innerHTML = this.renderNPCFicha(npc);
            } else if (type === 'enemy') {
                const en = await API.getAdventureEnemy(this.adventureId, code);
                title.textContent = en.name || 'Inimigo';
                body.innerHTML = this.renderEnemyFicha(en);
            } else {
                body.innerHTML = '<p class="char-view-empty">Tipo desconhecido.</p>';
            }
        } catch (err) {
            body.innerHTML = '<p style="color:var(--accent-danger);">Não foi possível carregar os dados.</p>';
        }
    },

    renderCharFicha(c) {
        const ATTR_PT = {
            strength: 'Força', dexterity: 'Destreza', constitution: 'Constituição',
            intelligence: 'Inteligência', wisdom: 'Sabedoria', charisma: 'Carisma',
            magic: 'Magia', perception: 'Furtividade', luck: 'Sorte'
        };
        const life = c.life || {};
        const lifePct = (typeof life === 'object' ? life.currentPercent : life) ?? '?';
        const lifeMax = (typeof life === 'object' ? life.maxPercent : 100) ?? '?';
        const lifeState = (typeof life === 'object' ? life.state : 'alive') ?? '?';
        const coins = c.coins || {};
        const coinsAmt = (typeof coins === 'object' ? coins.amount : coins) ?? '?';
        const attrs = c.attributes || {};
        const attrPills = Object.keys(ATTR_PT).map(k => {
            const v = attrs[k];
            if (v === undefined) return '';
            return `<span class="char-view-attr-pill">${ATTR_PT[k]}: ${v}</span>`;
        }).join('');
        const inv = c.inventory || [];
        const invSlots = inv.map((item, i) => item
            ? `<div class="char-view-field"><span class="char-view-field-label">Slot ${i}</span><span class="char-view-field-value">${item.name || 'Item'}</span></div>`
            : ''
        ).join('');
        const armor = c.armor || {};
        const armorSlots = Object.entries(armor).map(([k, v]) => {
            const slotPT = { head: 'Cabeça', torso: 'Tronco', hands: 'Mãos', legs: 'Pernas', feet: 'Pés', chest: 'Peito' };
            return `<div class="char-view-field"><span class="char-view-field-label">${slotPT[k] || k}</span><span class="char-view-field-value">${v ? (v.name || 'Armadura') : '—'}</span></div>`;
        }).join('');
        const abilities = (c.specialAbilities || []).map(a => `<div class="char-view-field"><span class="char-view-field-label">Habilidade</span><span class="char-view-field-value">${a.name || a.nome || '—'}</span></div>`).join('');
        const physDesc = c.physicalDescription || {};
        const physText = (typeof physDesc === 'object' ? [physDesc.raceBaseDescription, physDesc.customDescription].filter(Boolean).join(' ') : physDesc) || '';
        const statePT = { alive: 'Vivo', dead: 'Morto', unconscious: 'Inconsciente' };

        return `
            <div class="char-view-section">
                <div class="char-view-section-title">Informações</div>
                <div class="char-view-grid">
                    <div class="char-view-field"><span class="char-view-field-label">Nome</span><span class="char-view-field-value">${c.name || '—'}</span></div>
                    <div class="char-view-field"><span class="char-view-field-label">Raça</span><span class="char-view-field-value">${c.race || '—'}</span></div>
                    <div class="char-view-field"><span class="char-view-field-label">Gênero</span><span class="char-view-field-value">${c.gender || '—'}</span></div>
                    <div class="char-view-field"><span class="char-view-field-label">Idade</span><span class="char-view-field-value">${c.age || '—'}</span></div>
                    <div class="char-view-field"><span class="char-view-field-label">Vida</span><span class="char-view-field-value">${lifePct}/${lifeMax} (${statePT[lifeState] || lifeState})</span></div>
                    <div class="char-view-field"><span class="char-view-field-label">Moedas</span><span class="char-view-field-value">${coinsAmt}</span></div>
                </div>
            </div>
            ${attrPills ? `<div class="char-view-section"><div class="char-view-section-title">Atributos</div><div class="char-view-attrs">${attrPills}</div></div>` : ''}
            ${invSlots ? `<div class="char-view-section"><div class="char-view-section-title">Inventário</div><div class="char-view-grid">${invSlots}</div></div>` : ''}
            ${armorSlots ? `<div class="char-view-section"><div class="char-view-section-title">Armadura</div><div class="char-view-grid">${armorSlots}</div></div>` : ''}
            ${abilities ? `<div class="char-view-section"><div class="char-view-section-title">Habilidades</div><div class="char-view-grid">${abilities}</div></div>` : ''}
            ${physText ? `<div class="char-view-section"><div class="char-view-section-title">Descrição Física</div><p class="char-view-desc">${physText}</p></div>` : ''}
            ${c.story ? `<div class="char-view-section"><div class="char-view-section-title">História</div><p class="char-view-desc">${c.story}</p></div>` : ''}
        `;
    },

    renderNPCFicha(n) {
        const life = n.life || {};
        const lifePct = (typeof life === 'object' ? life.currentPercent : life) ?? '?';
        const lifeMax = (typeof life === 'object' ? life.maxPercent : 100) ?? '?';
        const lifeState = (typeof life === 'object' ? life.state : 'alive') ?? '?';
        const statePT = { alive: 'Vivo', dead: 'Morto', unconscious: 'Inconsciente' };
        return `
            <div class="char-view-section">
                <div class="char-view-section-title">Informações</div>
                <div class="char-view-grid">
                    <div class="char-view-field"><span class="char-view-field-label">Nome</span><span class="char-view-field-value">${n.name || '—'}</span></div>
                    <div class="char-view-field"><span class="char-view-field-label">Raça</span><span class="char-view-field-value">${n.race || '—'}</span></div>
                    <div class="char-view-field"><span class="char-view-field-label">Papel</span><span class="char-view-field-value">${n.role || '—'}</span></div>
                    <div class="char-view-field"><span class="char-view-field-label">Vida</span><span class="char-view-field-value">${lifePct}/${lifeMax} (${statePT[lifeState] || lifeState})</span></div>
                </div>
            </div>
            ${n.visibleDescription ? `<div class="char-view-section"><div class="char-view-section-title">Descrição Visível</div><p class="char-view-desc">${n.visibleDescription}</p></div>` : ''}
            ${n.description ? `<div class="char-view-section"><div class="char-view-section-title">Descrição</div><p class="char-view-desc">${n.description}</p></div>` : ''}
            ${n.hook ? `<div class="char-view-section"><div class="char-view-section-title">Hook</div><p class="char-view-desc">${n.hook}</p></div>` : ''}
        `;
    },

    renderEnemyFicha(en) {
        const life = en.life || {};
        const lifePct = (typeof life === 'object' ? life.currentPercent : en.currentLife) ?? '?';
        const lifeMax = (typeof life === 'object' ? life.maxPercent : en.maxLife) ?? '?';
        const lifeState = (typeof life === 'object' ? life.state : 'alive') ?? '?';
        const coins = en.coins || {};
        const coinsAmt = (typeof coins === 'object' ? coins.amount : coins) ?? '?';
        const inv = en.inventory || [];
        const invSlots = inv.filter(Boolean).map((item, i) => `<div class="char-view-field"><span class="char-view-field-label">Drop ${i + 1}</span><span class="char-view-field-value">${item.name || 'Item'}</span></div>`).join('');
        const statePT = { alive: 'Vivo', dead: 'Derrotado', unconscious: 'Inconsciente' };

        return `
            <div class="char-view-section">
                <div class="char-view-section-title">Informações</div>
                <div class="char-view-grid">
                    <div class="char-view-field"><span class="char-view-field-label">Nome</span><span class="char-view-field-value">${en.name || '—'}</span></div>
                    <div class="char-view-field"><span class="char-view-field-label">Vida</span><span class="char-view-field-value">${lifePct}/${lifeMax} (${statePT[lifeState] || lifeState})</span></div>
                    <div class="char-view-field"><span class="char-view-field-label">Moedas</span><span class="char-view-field-value">${coinsAmt}</span></div>
                </div>
            </div>
            ${en.description ? `<div class="char-view-section"><div class="char-view-section-title">Descrição</div><p class="char-view-desc">${en.description}</p></div>` : ''}
            ${invSlots ? `<div class="char-view-section"><div class="char-view-section-title">Drops</div><div class="char-view-grid">${invSlots}</div></div>` : ''}
        `;
    },
};

document.addEventListener('DOMContentLoaded', () => {
    Game.init();
});

window.addEventListener('beforeunload', () => {
    Game.destroy();
});
