from services.socket_service import socketio, join_adventure_room


def register_socket_handlers(sio):

    @sio.on('connect')
    def on_connect():
        pass

    @sio.on('join_adventure')
    def on_join_adventure(data):
        adventure_id = data.get('adventureId') if data else None
        if adventure_id:
            from flask_socketio import join_room
            room = f'adventure_{adventure_id}'
            join_room(room)
            join_adventure_room(adventure_id)

            try:
                from routes.game_routes import _build_scene_update_payload
                events = _build_scene_update_payload(adventure_id)
                if events:
                    from flask_socketio import emit
                    for event_name, event_data in events:
                        emit(event_name, event_data, room=room)
            except Exception as e:
                print(f'[socket] join_adventure state emit error: {e}', flush=True)

    @sio.on('leave_adventure')
    def on_leave_adventure(data):
        adventure_id = data.get('adventureId') if data else None
        if adventure_id:
            from flask_socketio import leave_room
            leave_room(f'adventure_{adventure_id}')

    @sio.on('disconnect')
    def on_disconnect():
        pass
