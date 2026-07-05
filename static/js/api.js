const API = {
    baseUrl: '',

    async get(url) {
        const response = await fetch(this.baseUrl + url);
        if (!response.ok) {
            const error = await response.json().catch(() => ({ error: response.statusText }));
            throw new Error(error.error || 'Erro desconhecido');
        }
        return response.json();
    },

    async post(url, data = {}) {
        const response = await fetch(this.baseUrl + url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!response.ok) {
            const error = await response.json().catch(() => ({ error: response.statusText }));
            throw new Error(error.error || 'Erro desconhecido');
        }
        return response.json();
    },

    async put(url, data = {}) {
        const response = await fetch(this.baseUrl + url, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!response.ok) {
            const error = await response.json().catch(() => ({ error: response.statusText }));
            throw new Error(error.error || 'Erro desconhecido');
        }
        return response.json();
    },

    async del(url) {
        const response = await fetch(this.baseUrl + url, { method: 'DELETE' });
        if (!response.ok) {
            const error = await response.json().catch(() => ({ error: response.statusText }));
            throw new Error(error.error || 'Erro desconhecido');
        }
        return response.json();
    },

    // Adventure APIs
    createAdventure: (totalParticipants, botCount) => API.post('/api/adventures/create', { totalParticipants, botCount }),
    getAdventures: () => API.get('/api/adventures'),
    getAdventure: (id) => API.get(`/api/adventures/${id}`),
    joinAdventure: (id, characterCode) => API.post(`/api/adventures/${id}/join`, { characterCode }),
    getAdventureStatus: (id) => API.get(`/api/adventures/${id}/status`),
    startAdventure: (id) => API.post(`/api/adventures/${id}/start`),
    deleteAdventure: (id) => API.del(`/api/adventures/${id}`),

    // Catalog APIs
    getWeapons: () => API.get('/api/catalog/weapons'),
    getAbilities: () => API.get('/api/catalog/abilities'),
    getRaces: () => API.get('/api/catalog/races'),

    // Character APIs
    getLocalCharacters: () => API.get('/api/local-characters'),
    createLocalCharacter: (data) => API.post('/api/local-characters/create', data),
    getLocalCharacter: (code) => API.get(`/api/local-characters/${code}`),
    updateLocalCharacter: (code, data) => API.put(`/api/local-characters/${code}`, data),
    deleteLocalCharacter: (code) => API.del(`/api/local-characters/${code}`),

    // AI Enhance APIs
    enhanceField: (field, context) => API.post('/api/ai/enhance', { field, context }),
    addCharacterToAdventure: (adventureId, data) => API.post(`/api/adventures/${adventureId}/characters/add`, data),
    getAdventureCharacters: (id) => API.get(`/api/adventures/${id}/characters`),
    getAdventureCharacter: (advId, charCode) => API.get(`/api/adventures/${advId}/characters/${charCode}`),

    // Game APIs
    getCurrentScene: (advId) => API.get(`/api/adventures/${advId}/scene/current`),
    postAction: (advId, characterCode, action) => API.post(`/api/adventures/${advId}/turn/action`, { characterCode, action }),
    botAct: (advId, botCode) => API.post(`/api/adventures/${advId}/bot/act`, { botCode }),
    getTask: (advId, taskId) => API.get(`/api/adventures/${advId}/task/${taskId}`),
    passTurn: (advId, characterCode) => API.post(`/api/adventures/${advId}/turn/pass`, { characterCode }),
    rollDice: (advId, characterCode, attribute, difficulty, reason) => API.post(`/api/adventures/${advId}/dice/roll`, { characterCode, attribute, difficulty, reason }),
    dropItem: (advId, characterCode, slotIndex) => API.post(`/api/adventures/${advId}/item/drop`, { characterCode, slotIndex }),
    useItem: (advId, characterCode, slotIndex) => API.post(`/api/adventures/${advId}/item/use`, { characterCode, slotIndex }),
    transferCoins: (advId, fromCode, toCode, amount) => API.post(`/api/adventures/${advId}/coins/transfer`, { fromCharacterCode: fromCode, toCharacterCode: toCode, amount }),
    heal: (advId, characterCode, targetCode, abilityId) => API.post(`/api/adventures/${advId}/heal`, { characterCode, targetCode, abilityId }),
    requestTrade: (advId, fromCode, toCode, offerItems, offerCoins, requestItems, requestCoins) => API.post(`/api/adventures/${advId}/trade/request`, { fromCharacterCode: fromCode, toCharacterCode: toCode, offerItems, offerCoins, requestItems, requestCoins }),
    respondTrade: (advId, tradeId, accept) => API.post(`/api/adventures/${advId}/trade/respond`, { tradeId, accept }),
    confirmTrade: (advId, tradeId) => API.post(`/api/adventures/${advId}/trade/confirm`, { tradeId }),
    chatNPC: (advId, characterCode, npcCode, message) => API.post(`/api/adventures/${advId}/npc/chat`, { characterCode, npcCode, message }),
    chatBot: (advId, characterCode, botCode, message) => API.post(`/api/adventures/${advId}/bot/chat`, { characterCode, botCode, message }),
    confirmSceneTransition: (advId, characterCode, sceneId, accept) => API.post(`/api/adventures/${advId}/scene/transition/confirm`, { characterCode, sceneId, accept }),
    pickupItem: (advId, characterCode, itemId) => API.post(`/api/adventures/${advId}/item/pickup`, { characterCode, itemId }),
    attackEnemy: (advId, characterCode, enemyCode, amount) => API.post(`/api/adventures/${advId}/enemy/attack`, { characterCode, enemyCode, amount }),
    lootEnemy: (advId, characterCode, enemyCode) => API.post(`/api/adventures/${advId}/enemy/loot`, { characterCode, enemyCode }),
    getAdventureEnemy: (advId, enemyCode) => API.get(`/api/adventures/${advId}/enemies/${enemyCode}`),
};
