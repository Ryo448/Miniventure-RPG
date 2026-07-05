from flask import Blueprint, request, jsonify
from services import adventure_service, file_storage

adventure_routes = Blueprint('adventure_routes', __name__)


@adventure_routes.route('/api/adventures/create', methods=['POST'])
def create_adventure():
    data = request.get_json() or {}
    total = data.get('totalParticipants', 4)
    bots = data.get('botCount', 0)
    bot_source = data.get('botSource', 'ai')
    bot_codes = data.get('botCharacterCodes') if bot_source == 'host' else None

    adventure, error = adventure_service.create_adventure(total, bots, bot_character_codes=bot_codes)
    if error:
        return jsonify({'error': error}), 400

    return jsonify(adventure), 201


@adventure_routes.route('/api/adventures', methods=['GET'])
def list_adventures():
    adventures = file_storage.list_adventures()
    return jsonify(adventures)


@adventure_routes.route('/api/adventures/<adventure_id>', methods=['GET'])
def get_adventure(adventure_id):
    adventure = file_storage.get_adventure(adventure_id)
    if not adventure:
        return jsonify({'error': 'Aventura não encontrada.'}), 404
    return jsonify(adventure)


@adventure_routes.route('/api/adventures/<adventure_id>', methods=['DELETE'])
def delete_adventure(adventure_id):
    adventure = file_storage.get_adventure(adventure_id)
    if not adventure:
        return jsonify({'error': 'Aventura não encontrada.'}), 404
    file_storage.delete_adventure(adventure_id)
    return jsonify({'success': True})


@adventure_routes.route('/api/adventures/<adventure_id>/join', methods=['POST'])
def join_adventure(adventure_id):
    data = request.get_json() or {}
    character_code = data.get('characterCode')

    if not character_code:
        return jsonify({'error': 'Código do personagem é obrigatório.'}), 400

    result, error = adventure_service.join_adventure(adventure_id, character_code)
    if error:
        return jsonify({'error': error}), 400

    return jsonify(result)


@adventure_routes.route('/api/adventures/<adventure_id>/status', methods=['GET'])
def get_status(adventure_id):
    status = adventure_service.get_adventure_status(adventure_id)
    if not status:
        return jsonify({'error': 'Aventura não encontrada.'}), 404
    return jsonify(status)


@adventure_routes.route('/api/adventures/<adventure_id>/start', methods=['POST'])
def start_adventure(adventure_id):
    result, error = adventure_service.start_adventure(adventure_id)
    if error:
        return jsonify({'error': error}), 400
    return jsonify(result)


@adventure_routes.route('/api/adventures/<adventure_id>/state', methods=['GET'])
def get_game_state(adventure_id):
    adventure = file_storage.get_adventure(adventure_id)
    if not adventure:
        return jsonify({'error': 'Aventura não encontrada.'}), 404

    scene = None
    if adventure.get('currentSceneId'):
        scene = file_storage.get_scene(adventure_id, adventure['currentSceneId'])

    characters = file_storage.get_adventure_characters(adventure_id)

    return jsonify({
        'adventure': adventure,
        'scene': scene,
        'characters': characters
    })


@adventure_routes.route('/api/adventures/<adventure_id>/ai-tasks', methods=['GET'])
def get_ai_tasks(adventure_id):
    from services.ai_orchestrator import get_tasks_by_adventure
    tasks = get_tasks_by_adventure(adventure_id)
    return jsonify(tasks)
