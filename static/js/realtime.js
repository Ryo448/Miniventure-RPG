const Realtime = {
    socket: null,
    adventureId: null,
    callbacks: {},
    reconnectAttempts: 0,
    maxReconnectAttempts: 10,

    connectToAdventure(adventureId, callbacks = {}) {
        this.adventureId = adventureId;
        this.callbacks = callbacks;
        this.reconnectAttempts = 0;
        this._connect();
    },

    _connect() {
        if (this.socket) {
            this.socket.disconnect();
        }

        this.socket = io({ transports: ['websocket', 'polling'] });

        this.socket.on('connect', () => {
            this.reconnectAttempts = 0;
            this.socket.emit('join_adventure', { adventureId: this.adventureId });
            if (this.callbacks.onConnection) {
                this.callbacks.onConnection(true);
            }
        });

        this.socket.on('disconnect', () => {
            if (this.callbacks.onConnection) {
                this.callbacks.onConnection(false);
            }
            if (this.reconnectAttempts < this.maxReconnectAttempts) {
                this.reconnectAttempts++;
                setTimeout(() => this._connect(), Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000));
            }
        });

        this.socket.on('connect_error', () => {
            if (this.callbacks.onConnection) {
                this.callbacks.onConnection(false);
            }
        });

        this.socket.on('scene_update', (data) => {
            if (this.callbacks.onSceneUpdate) {
                this.callbacks.onSceneUpdate(data);
            }
        });

        this.socket.on('turn_change', (data) => {
            if (this.callbacks.onTurnChange) {
                this.callbacks.onTurnChange(data);
            }
        });

        this.socket.on('inventory_update', (data) => {
            if (this.callbacks.onInventoryUpdate) {
                this.callbacks.onInventoryUpdate(data);
            }
        });

        this.socket.on('coins_update', (data) => {
            if (this.callbacks.onCoinsUpdate) {
                this.callbacks.onCoinsUpdate(data);
            }
        });

        this.socket.on('life_update', (data) => {
            if (this.callbacks.onLifeUpdate) {
                this.callbacks.onLifeUpdate(data);
            }
        });

        this.socket.on('trade_request', (data) => {
            if (this.callbacks.onTradeRequest) {
                this.callbacks.onTradeRequest(data);
            }
        });

        this.socket.on('chat_message', (data) => {
            if (this.callbacks.onChatMessage) {
                this.callbacks.onChatMessage(data);
            }
        });

        this.socket.on('enemy_update', (data) => {
            if (this.callbacks.onEnemyUpdate) {
                this.callbacks.onEnemyUpdate(data);
            }
        });

        this.socket.on('task_result', (data) => {
            if (this.callbacks.onTaskResult) {
                this.callbacks.onTaskResult(data);
            }
        });
    },

    disconnect() {
        if (this.socket) {
            this.socket.emit('leave_adventure', { adventureId: this.adventureId });
            this.socket.disconnect();
            this.socket = null;
        }
        this.adventureId = null;
        this.callbacks = {};
        this.reconnectAttempts = 0;
    },

    isConnected() {
        return this.socket && this.socket.connected;
    },
};
