const ChatUI = {
    adventureId: null,
    characterCode: null,
    targetCode: null,
    targetType: null,
    messageCount: 0,
    maxNPCMessages: 5,
    chatActive: false,

    init(adventureId, characterCode) {
        this.adventureId = adventureId;
        this.characterCode = characterCode;
    },

    async loadTargets(adventureId, characterCode) {
        this.adventureId = adventureId;
        this.characterCode = characterCode;

        const targetListEl = document.getElementById('chat-target-list');
        if (!targetListEl) return;

        targetListEl.innerHTML = '';

        try {
            const sceneData = await API.getCurrentScene(this.adventureId);
            const npcs = sceneData.npcs || [];
            const charactersData = await API.getAdventureCharacters(this.adventureId);
            const bots = (charactersData.characters || charactersData).filter(
                (c) => c.code !== this.characterCode && c.isBot
            );

            if (npcs.length > 0) {
                const npcHeader = document.createElement('div');
                npcHeader.className = 'chat-target-header';
                npcHeader.textContent = 'NPCs';
                targetListEl.appendChild(npcHeader);

                npcs.forEach((npc) => {
                    const btn = document.createElement('button');
                    btn.type = 'button';
                    btn.className = 'chat-target-btn';
                    btn.textContent = npc.name;
                    btn.addEventListener('click', () => {
                        this.openChat(npc.code, 'npc', npc.name);
                    });
                    targetListEl.appendChild(btn);
                });
            }

            if (bots.length > 0) {
                const botHeader = document.createElement('div');
                botHeader.className = 'chat-target-header';
                botHeader.textContent = 'Bots';
                targetListEl.appendChild(botHeader);

                bots.forEach((bot) => {
                    const btn = document.createElement('button');
                    btn.type = 'button';
                    btn.className = 'chat-target-btn';
                    btn.textContent = bot.name || bot.code;
                    btn.addEventListener('click', () => {
                        this.openChat(bot.code, 'bot', bot.name || bot.code);
                    });
                    targetListEl.appendChild(btn);
                });
            }

            if (npcs.length === 0 && bots.length === 0) {
                targetListEl.innerHTML = '<span class="chat-empty">Nenhum alvo disponível para conversa.</span>';
            }
        } catch (err) {
            targetListEl.innerHTML = '<span class="chat-empty">Erro ao carregar alvos.</span>';
        }
    },

    async openChat(targetCode, targetType, targetName) {
        this.targetCode = targetCode;
        this.targetType = targetType;
        this.messageCount = 0;
        this.chatActive = true;

        const selectorModal = document.getElementById('chat-selector-modal');
        if (selectorModal) selectorModal.style.display = 'none';

        const chatModal = document.getElementById('chat-modal');
        if (!chatModal) return;

        const titleEl = document.getElementById('chat-title');
        const messagesEl = document.getElementById('chat-messages');
        const counterEl = document.getElementById('chat-counter');
        const inputEl = document.getElementById('chat-input');
        const sendBtn = document.getElementById('chat-send-btn');
        const closeBtn = document.getElementById('chat-close-btn');

        if (titleEl) {
            titleEl.textContent = `Conversa com ${targetName || targetCode}`;
        }

        if (messagesEl) {
            messagesEl.innerHTML = '';
        }

        if (counterEl) {
            if (targetType === 'npc') {
                counterEl.textContent = `Mensagem 0 de ${this.maxNPCMessages}`;
                counterEl.style.display = 'block';
            } else {
                counterEl.textContent = '';
                counterEl.style.display = 'none';
            }
        }

        if (inputEl) {
            inputEl.value = '';
            inputEl.disabled = false;
        }

        chatModal.style.display = 'flex';

        if (sendBtn) {
            const newSendBtn = sendBtn.cloneNode(true);
            sendBtn.parentNode.replaceChild(newSendBtn, sendBtn);
            newSendBtn.addEventListener('click', () => this.sendMessage());
        }

        if (closeBtn) {
            const newCloseBtn = closeBtn.cloneNode(true);
            closeBtn.parentNode.replaceChild(newCloseBtn, closeBtn);
            newCloseBtn.addEventListener('click', () => this.endChat());
        }

        if (inputEl) {
            const newInput = inputEl.cloneNode(true);
            inputEl.parentNode.replaceChild(newInput, inputEl);
            newInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendMessage();
                }
            });
        }
    },

    async sendMessage() {
        const inputEl = document.getElementById('chat-input');
        if (!inputEl) return;

        const message = inputEl.value.trim();
        if (!message) return;
        if (!this.chatActive) return;

        if (this.targetType === 'npc' && this.messageCount >= this.maxNPCMessages) {
            this.appendSystemMessage('Limite de mensagens atingido para este NPC.');
            return;
        }

        this.appendMessage('self', message);
        inputEl.value = '';

        try {
            let result;
            if (this.targetType === 'npc') {
                result = await API.chatNPC(this.adventureId, this.characterCode, this.targetCode, message);
            } else {
                result = await API.chatBot(this.adventureId, this.characterCode, this.targetCode, message);
            }

            if (result.taskId) {
                result = await this._waitForChatTask(result.taskId);
            }

            this.messageCount++;

            const responseText = result.message || result.response || result.narration || '...';
            this.appendMessage('other', responseText);

            if (this.targetType === 'npc') {
                const counterEl = document.getElementById('chat-counter');
                if (counterEl) {
                    counterEl.textContent = `Mensagem ${this.messageCount} de ${this.maxNPCMessages}`;
                }

                if (this.messageCount >= this.maxNPCMessages) {
                    this.appendSystemMessage('Conversa encerrada');
                    this.chatActive = false;
                    const inputEl2 = document.getElementById('chat-input');
                    if (inputEl2) inputEl2.disabled = true;
                }
            }
        } catch (err) {
            this.appendSystemMessage(err.message || 'Erro ao enviar mensagem.');
        }
    },

    async _waitForChatTask(taskId) {
        const maxAttempts = 80;
        for (let i = 0; i < maxAttempts; i++) {
            try {
                const task = await API.getTask(this.adventureId, taskId);
                if (task.status === 'completed') return task.result || task;
                if (task.status === 'failed') throw new Error(task.error || 'Falha na conversa.');
            } catch (e) {
                if (e.message && !e.message.includes('status')) throw e;
            }
            await new Promise((r) => setTimeout(r, 1500));
        }
        throw new Error('Tempo esgotado aguardando resposta.');
    },

    appendMessage(sender, text) {
        const messagesEl = document.getElementById('chat-messages');
        if (!messagesEl) return;

        const div = document.createElement('div');
        div.className = `chat-msg chat-msg-${sender}`;
        div.innerHTML = `<span class="chat-text">${this.escapeHTML(text)}</span>`;
        messagesEl.appendChild(div);
        messagesEl.scrollTop = messagesEl.scrollHeight;
    },

    appendSystemMessage(text) {
        const messagesEl = document.getElementById('chat-messages');
        if (!messagesEl) return;

        const div = document.createElement('div');
        div.className = 'chat-msg chat-msg-system';
        div.textContent = text;
        messagesEl.appendChild(div);
        messagesEl.scrollTop = messagesEl.scrollHeight;
    },

    endChat() {
        this.chatActive = false;
        this.targetCode = null;
        this.targetType = null;
        this.messageCount = 0;

        const chatModal = document.getElementById('chat-modal');
        if (chatModal) {
            chatModal.style.display = 'none';
        }

        const messagesEl = document.getElementById('chat-messages');
        if (messagesEl) {
            messagesEl.innerHTML = '';
        }
    },

    escapeHTML(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    },
};
