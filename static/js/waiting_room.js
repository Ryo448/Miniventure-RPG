const WaitingRoom = {
    adventureId: null,
    pollInterval: null,
    previousStatus: null,

    PREPARATION_MESSAGES: {
        pending: 'Aguardando preparação...',
        generating_timeline: 'Gerando mundo e história...',
        generating_bots: 'Gerando personagens bot...',
        generating_scene: 'Gerando cena inicial...',
        completed: 'Preparação concluída!',
        failed: 'Erro na preparação. Tente novamente.',
    },

    init() {
        const el = document.getElementById('adventure-id');
        if (el) {
            this.adventureId = el.dataset.adventureId || el.value;
        }

        if (!this.adventureId) {
            const pathParts = window.location.pathname.split('/');
            this.adventureId = pathParts[pathParts.length - 2];
        }

        if (!this.adventureId) {
            console.error('ID da aventura não encontrado.');
            return;
        }

        this.startPolling();
        this.setupStartButton();
    },

    startPolling() {
        this.poll();
        this.pollInterval = setInterval(() => this.poll(), 3000);
    },

    stopPolling() {
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
            this.pollInterval = null;
        }
    },

    async poll() {
        try {
            const status = await API.getAdventureStatus(this.adventureId);
            this.updateUI(status);

            if (status.started) {
                this.stopPolling();
                window.location.href = `/adventure/${this.adventureId}/game`;
            }
        } catch (err) {
            console.error('Erro ao verificar status da aventura:', err);
        }
    },

    updateUI(status) {
        this.updatePlayerList(status.players || []);
        this.updateBotList(status.bots || []);
        this.updatePreparationStatus(status.aiPreparation || status.preparation);
        this.updateStartButton(status);
    },

    updatePlayerList(players) {
        const listEl = document.getElementById('player-list');
        if (!listEl) return;

        listEl.innerHTML = '';

        if (players.length === 0) {
            listEl.innerHTML = '<li class="empty-state">Nenhum jogador conectado ainda.</li>';
            return;
        }

        players.forEach((player) => {
            const li = document.createElement('li');
            li.className = 'player-entry';
            li.innerHTML = `
                <span class="player-name">${player.name || 'Jogador'}</span>
                <span class="player-race">${player.raceName || ''}</span>
                <span class="player-status ${player.ready ? 'ready' : 'waiting'}">
                    ${player.ready ? '✓ Pronto' : '○ Aguardando'}
                </span>
            `;
            listEl.appendChild(li);
        });
    },

    updateBotList(bots) {
        const listEl = document.getElementById('bot-list');
        if (!listEl) return;

        listEl.innerHTML = '';

        if (bots.length === 0) {
            listEl.innerHTML = '<li class="empty-state">Nenhum bot na aventura.</li>';
            return;
        }

        bots.forEach((bot) => {
            const li = document.createElement('li');
            li.className = 'bot-entry';
            li.innerHTML = `
                <span class="bot-name">${bot.name || 'Bot'}</span>
                <span class="bot-race">${bot.raceName || ''}</span>
            `;
            listEl.appendChild(li);
        });
    },

    updatePreparationStatus(preparation) {
        const statusEl = document.getElementById('preparation-status');
        const progressBar = document.getElementById('preparation-progress');

        if (!statusEl) return;

        const stage = preparation?.stage || preparation?.status || 'pending';
        const message = this.PREPARATION_MESSAGES[stage] || this.PREPARATION_MESSAGES.pending;

        statusEl.textContent = message;
        statusEl.className = `preparation-status preparation-${stage}`;

        if (progressBar) {
            const progressMap = {
                pending: 10,
                generating_timeline: 35,
                generating_bots: 60,
                generating_scene: 85,
                completed: 100,
                failed: 0,
            };
            progressBar.style.width = `${progressMap[stage] || 10}%`;
        }

        if (stage === 'failed') {
            statusEl.classList.add('preparation-error');
        }
    },

    updateStartButton(status) {
        const startBtn = document.getElementById('start-btn');
        if (!startBtn) return;

        const isReady = status.canStart === true || (
            status.aiPreparation?.stage === 'completed' || status.preparation?.stage === 'completed'
        );

        startBtn.disabled = !isReady;

        if (isReady) {
            startBtn.textContent = 'Iniciar Aventura';
            startBtn.classList.add('btn-ready');
        } else {
            startBtn.textContent = 'Aguardando preparação...';
            startBtn.classList.remove('btn-ready');
        }
    },

    setupStartButton() {
        const startBtn = document.getElementById('start-btn');
        if (!startBtn) return;

        startBtn.addEventListener('click', async () => {
            startBtn.disabled = true;
            startBtn.textContent = 'Iniciando...';

            try {
                await API.startAdventure(this.adventureId);
                this.stopPolling();
                window.location.href = `/adventure/${this.adventureId}/game`;
            } catch (err) {
                alert(err.message || 'Erro ao iniciar aventura.');
                startBtn.disabled = false;
                startBtn.textContent = 'Iniciar Aventura';
            }
        });
    },
};

document.addEventListener('DOMContentLoaded', () => {
    WaitingRoom.init();
});
