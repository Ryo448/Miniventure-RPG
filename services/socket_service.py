from flask_socketio import SocketIO

socketio = SocketIO(cors_allowed_origins='*', async_mode='threading')


def join_adventure_room(adventure_id):
    pass


def emit_to_adventure(adventure_id, event, data):
    socketio.emit(event, data, room=f'adventure_{adventure_id}')


def emit_task_result(adventure_id, task_id, status, result=None, error=None):
    payload = {'taskId': task_id, 'status': status}
    if result is not None:
        payload['result'] = result
    if error is not None:
        payload['error'] = error
    emit_to_adventure(adventure_id, 'task_result', payload)


def emit_scene_update(adventure_id):
    try:
        from routes.game_routes import _build_scene_update_payload
        events = _build_scene_update_payload(adventure_id)
        if events:
            for event_name, event_data in events:
                emit_to_adventure(adventure_id, event_name, event_data)
    except Exception as e:
        print(f'[socket] emit_scene_update error: {e}', flush=True)
