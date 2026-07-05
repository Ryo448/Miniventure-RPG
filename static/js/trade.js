const TradeUI = {
    adventureId: null,
    characterCode: null,
    myInventory: [],
    partnerInventory: [],
    myCoins: 0,
    partnerCoins: 0,
    offerItems: [],
    requestItems: [],
    offerCoins: 0,
    requestCoins: 0,
    partnerCode: null,
    pendingTradeId: null,

    init(adventureId, characterCode) {
        this.adventureId = adventureId;
        this.characterCode = characterCode;
        this.offerItems = [];
        this.requestItems = [];
        this.offerCoins = 0;
        this.requestCoins = 0;
        this.partnerCode = null;
        this.loadPlayerData();
        this.setupListeners();
    },

    async loadPlayerData() {
        try {
            const charData = await API.getAdventureCharacter(this.adventureId, this.characterCode);
            this.myInventory = charData.inventory || charData.items || [];
            this.myCoins = charData.coins || 0;

            this.renderMyInventory();
            this.renderMyCoins();
        } catch (err) {
            this.showError('Erro ao carregar inventário.');
        }

        await this.loadPartners();
    },

    async loadPartners() {
        try {
            const data = await API.getAdventureCharacters(this.adventureId);
            const others = (data.characters || data).filter((c) => c.code !== this.characterCode);
            this.renderPartnerSelector(others);
        } catch (err) {
            this.showError('Erro ao carregar personagens.');
        }
    },

    renderMyInventory() {
        const listEl = document.getElementById('trade-my-inventory');
        if (!listEl) return;

        listEl.innerHTML = '';
        this.myInventory.forEach((item, idx) => {
            if (!item) return;
            const div = document.createElement('div');
            div.className = 'trade-item';
            div.dataset.slotIndex = idx;
            div.textContent = item.name;
            div.addEventListener('click', () => this.toggleOfferItem(idx, item));
            listEl.appendChild(div);
        });
    },

    renderMyCoins() {
        const coinsEl = document.getElementById('trade-my-coins');
        if (coinsEl) {
            coinsEl.textContent = `Moedas: ${this.myCoins}`;
        }
    },

    renderPartnerSelector(characters) {
        const selectEl = document.getElementById('trade-partner-select');
        if (!selectEl) return;

        selectEl.innerHTML = '<option value="">-- Selecione parceiro --</option>';
        characters.forEach((c) => {
            const opt = document.createElement('option');
            opt.value = c.code;
            opt.textContent = c.name || c.code;
            selectEl.appendChild(opt);
        });
    },

    async onPartnerSelected(partnerCode) {
        this.partnerCode = partnerCode;
        this.requestItems = [];
        this.requestCoins = 0;

        if (!partnerCode) {
            this.renderPartnerInventory([]);
            return;
        }

        try {
            const data = await API.getAdventureCharacter(this.adventureId, partnerCode);
            this.partnerInventory = data.inventory || data.items || [];
            this.partnerCoins = data.coins || 0;
            this.renderPartnerInventory();
            this.renderPartnerCoins();
        } catch (err) {
            this.showError('Erro ao carregar inventário do parceiro.');
        }
    },

    renderPartnerInventory() {
        const listEl = document.getElementById('trade-partner-inventory');
        if (!listEl) return;

        listEl.innerHTML = '';
        this.partnerInventory.forEach((item, idx) => {
            if (!item) return;
            const div = document.createElement('div');
            div.className = 'trade-item trade-item-partner';
            div.dataset.slotIndex = idx;
            div.textContent = item.name;
            div.addEventListener('click', () => this.toggleRequestItem(idx, item));
            listEl.appendChild(div);
        });
    },

    renderPartnerCoins() {
        const coinsEl = document.getElementById('trade-partner-coins');
        if (coinsEl) {
            coinsEl.textContent = `Moedas: ${this.partnerCoins}`;
        }
    },

    toggleOfferItem(slotIndex, item) {
        const existingIdx = this.offerItems.findIndex((o) => o.slotIndex === slotIndex);
        if (existingIdx >= 0) {
            this.offerItems.splice(existingIdx, 1);
        } else {
            this.offerItems.push({ slotIndex, item });
        }
        this.renderOfferList();
        this.highlightMyItems();
    },

    toggleRequestItem(slotIndex, item) {
        const existingIdx = this.requestItems.findIndex((r) => r.slotIndex === slotIndex);
        if (existingIdx >= 0) {
            this.requestItems.splice(existingIdx, 1);
        } else {
            this.requestItems.push({ slotIndex, item });
        }
        this.renderRequestList();
        this.highlightPartnerItems();
    },

    renderOfferList() {
        const listEl = document.getElementById('trade-offer-list');
        if (!listEl) return;

        listEl.innerHTML = '';
        if (this.offerItems.length === 0) {
            listEl.innerHTML = '<span class="trade-empty">Nenhum item oferecido</span>';
            return;
        }
        this.offerItems.forEach((o) => {
            const div = document.createElement('div');
            div.className = 'trade-offer-item';
            div.textContent = o.item.name;
            div.addEventListener('click', () => {
                this.toggleOfferItem(o.slotIndex, o.item);
            });
            listEl.appendChild(div);
        });
    },

    renderRequestList() {
        const listEl = document.getElementById('trade-request-list');
        if (!listEl) return;

        listEl.innerHTML = '';
        if (this.requestItems.length === 0) {
            listEl.innerHTML = '<span class="trade-empty">Nenhum item solicitado</span>';
            return;
        }
        this.requestItems.forEach((r) => {
            const div = document.createElement('div');
            div.className = 'trade-request-item';
            div.textContent = r.item.name;
            div.addEventListener('click', () => {
                this.toggleRequestItem(r.slotIndex, r.item);
            });
            listEl.appendChild(div);
        });
    },

    highlightMyItems() {
        const offeredSlots = new Set(this.offerItems.map((o) => o.slotIndex));
        document.querySelectorAll('#trade-my-inventory .trade-item').forEach((el) => {
            const idx = parseInt(el.dataset.slotIndex);
            el.classList.toggle('trade-item-selected', offeredSlots.has(idx));
        });
    },

    highlightPartnerItems() {
        const requestedSlots = new Set(this.requestItems.map((r) => r.slotIndex));
        document.querySelectorAll('#trade-partner-inventory .trade-item').forEach((el) => {
            const idx = parseInt(el.dataset.slotIndex);
            el.classList.toggle('trade-item-selected', requestedSlots.has(idx));
        });
    },

    setupListeners() {
        const partnerSelect = document.getElementById('trade-partner-select');
        if (partnerSelect) {
            partnerSelect.addEventListener('change', (e) => {
                this.onPartnerSelected(e.target.value);
            });
        }

        const offerCoinsInput = document.getElementById('trade-offer-coins');
        if (offerCoinsInput) {
            offerCoinsInput.addEventListener('input', (e) => {
                this.offerCoins = parseInt(e.target.value) || 0;
            });
        }

        const requestCoinsInput = document.getElementById('trade-request-coins');
        if (requestCoinsInput) {
            requestCoinsInput.addEventListener('input', (e) => {
                this.requestCoins = parseInt(e.target.value) || 0;
            });
        }

        const proposeBtn = document.getElementById('trade-propose-btn');
        if (proposeBtn) {
            proposeBtn.addEventListener('click', () => this.proposeTrade());
        }

        const cancelBtn = document.getElementById('trade-cancel-btn');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => this.close());
        }

        const acceptBtn = document.getElementById('trade-accept-btn');
        if (acceptBtn) {
            acceptBtn.addEventListener('click', () => this.respondTrade(true));
        }

        const rejectBtn = document.getElementById('trade-reject-btn');
        if (rejectBtn) {
            rejectBtn.addEventListener('click', () => this.respondTrade(false));
        }

        const confirmBtn = document.getElementById('trade-confirm-btn');
        if (confirmBtn) {
            confirmBtn.addEventListener('click', () => this.confirmTrade());
        }
    },

    validate() {
        if (this.offerCoins > this.myCoins) {
            this.showError('Moedas insuficientes.');
            return false;
        }

        for (const offer of this.offerItems) {
            const item = this.myInventory[offer.slotIndex];
            if (!item) {
                this.showError('Você não possui este item.');
                return false;
            }
        }

        const totalMySlots = this.myInventory.length;
        const incomingItems = this.requestItems.length;
        const myFreeSlots = this.myInventory.filter((i) => !i).length;
        const outgoingItems = this.offerItems.length;

        if (incomingItems - outgoingItems > myFreeSlots) {
            this.showError('Inventário cheio.');
            return false;
        }

        return true;
    },

    async proposeTrade() {
        if (!this.partnerCode) {
            this.showError('Selecione um parceiro para troca.');
            return;
        }
        if (!this.validate()) return;

        try {
            const result = await API.requestTrade(
                this.adventureId,
                this.characterCode,
                this.partnerCode,
                this.offerItems.map((o) => o.slotIndex),
                this.offerCoins,
                this.requestItems.map((r) => r.slotIndex),
                this.requestCoins
            );

            this.showMessage('Troca proposta');
            if (result.tradeId) {
                this.pendingTradeId = result.tradeId;
            }
        } catch (err) {
            this.showError(err.message || 'Erro ao propor troca.');
        }
    },

    async respondTrade(accept) {
        if (!this.pendingTradeId) {
            this.showError('Nenhuma troca pendente.');
            return;
        }

        try {
            await API.respondTrade(this.adventureId, this.pendingTradeId, accept);
            this.showMessage(accept ? 'Troca aceita' : 'Troca recusada');
            if (!accept) {
                this.pendingTradeId = null;
                this.close();
            }
        } catch (err) {
            this.showError(err.message || 'Erro ao responder troca.');
        }
    },

    async confirmTrade() {
        if (!this.pendingTradeId) {
            this.showError('Nenhuma troca para confirmar.');
            return;
        }

        try {
            await API.confirmTrade(this.adventureId, this.pendingTradeId);
            this.showMessage('Troca confirmada!');
            this.pendingTradeId = null;
            this.close();
        } catch (err) {
            this.showError(err.message || 'Erro ao confirmar troca.');
        }
    },

    handleIncomingTrade(data) {
        this.pendingTradeId = data.tradeId;
        this.partnerCode = data.fromCharacterCode;

        const notification = document.getElementById('trade-incoming');
        if (notification) {
            notification.style.display = 'flex';
            notification.innerHTML = `
                <p>${data.fromName || 'Alguém'} quer trocar com você!</p>
                <button onclick="TradeUI.respondTrade(true)" class="btn-accept">Aceitar</button>
                <button onclick="TradeUI.respondTrade(false)" class="btn-reject">Recusar</button>
            `;
        }
    },

    showMessage(text) {
        const msgEl = document.getElementById('trade-message');
        if (msgEl) {
            msgEl.textContent = text;
            msgEl.style.display = 'block';
            setTimeout(() => {
                msgEl.style.display = 'none';
            }, 3000);
        }
    },

    showError(text) {
        const errEl = document.getElementById('trade-error');
        if (errEl) {
            errEl.textContent = text;
            errEl.style.display = 'block';
        }
    },

    close() {
        const modal = document.getElementById('trade-modal');
        if (modal) {
            modal.style.display = 'none';
        }
        this.offerItems = [];
        this.requestItems = [];
        this.offerCoins = 0;
        this.requestCoins = 0;
    },
};

document.addEventListener('DOMContentLoaded', () => {
    const partnerSelect = document.getElementById('trade-partner-select');
    if (partnerSelect) {
        partnerSelect.addEventListener('change', (e) => {
            TradeUI.onPartnerSelected(e.target.value);
        });
    }
});
