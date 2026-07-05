from flask import Blueprint, request, jsonify
from services import file_storage, character_service, catalog_service

character_routes = Blueprint('character_routes', __name__)


@character_routes.route('/api/local-characters', methods=['GET'])
def list_local_characters():
    characters = file_storage.list_local_characters()
    return jsonify(characters)


@character_routes.route('/api/local-characters/create', methods=['POST'])
def create_local_character():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Nome é obrigatório.'}), 400

    race_id = data.get('raceId', '')
    if not race_id:
        return jsonify({'error': 'Selecione uma raça.'}), 400

    attributes = data.get('attributes', {})
    total_points = sum(attributes.values())
    if total_points < 1:
        return jsonify({'error': 'Distribua os pontos de atributo.'}), 400

    weapon_id = data.get('weaponId', '')
    if not weapon_id:
        return jsonify({'error': 'Selecione uma arma inicial.'}), 400

    ability_id = data.get('abilityId', '')
    if not ability_id:
        return jsonify({'error': 'Selecione uma habilidade.'}), 400

    character = character_service.create_local_character(data)
    return jsonify(character), 201


@character_routes.route('/api/local-characters/<character_code>', methods=['GET'])
def get_local_character(character_code):
    character = file_storage.get_local_character(character_code)
    if not character:
        return jsonify({'error': 'Personagem não encontrado.'}), 404
    return jsonify(character)


@character_routes.route('/api/local-characters/<character_code>', methods=['PUT'])
def update_local_character(character_code):
    character = file_storage.get_local_character(character_code)
    if not character:
        return jsonify({'error': 'Personagem não encontrado.'}), 404

    data = request.get_json() or {}
    updated = character_service.update_local_character(character, data)
    file_storage.save_local_character(updated)
    return jsonify(updated)


@character_routes.route('/api/local-characters/<character_code>', methods=['DELETE'])
def delete_local_character(character_code):
    character = file_storage.get_local_character(character_code)
    if not character:
        return jsonify({'error': 'Personagem não encontrado.'}), 404
    file_storage.delete_local_character(character_code)
    return jsonify({'success': True})


@character_routes.route('/api/adventures/<adventure_id>/characters/add', methods=['POST'])
def add_character_to_adventure(adventure_id):
    data = request.get_json() or {}
    character_code = data.get('characterCode')
    if not character_code:
        return jsonify({'error': 'Código do personagem é obrigatório.'}), 400

    server_char, error = character_service.add_character_to_adventure(adventure_id, character_code)
    if error:
        return jsonify({'error': error}), 400
    return jsonify(server_char), 201


@character_routes.route('/api/adventures/<adventure_id>/characters', methods=['GET'])
def get_adventure_characters(adventure_id):
    characters = file_storage.get_adventure_characters(adventure_id)
    return jsonify(characters)


@character_routes.route('/api/adventures/<adventure_id>/characters/<character_code>', methods=['GET'])
def get_adventure_character(adventure_id, character_code):
    character = file_storage.get_adventure_character(adventure_id, character_code)
    if not character:
        return jsonify({'error': 'Personagem não encontrado nesta aventura.'}), 404
    return jsonify(character)
