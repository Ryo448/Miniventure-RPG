from flask import Blueprint, render_template, request
from services import file_storage

page_routes = Blueprint('pages', __name__)


@page_routes.route('/')
def home():
    return render_template('home.html')


@page_routes.route('/adventures/create')
def create_adventure():
    return render_template('create_adventure.html')


@page_routes.route('/adventures/join')
def join_adventure():
    adventures = file_storage.list_adventures()
    adventure_list = []
    for adv in adventures:
        chars = file_storage.get_adventure_characters(adv['code'])
        real_players = [c for c in chars if not c.get('isBot')]
        if adv.get('status') == 'active':
            status_label = 'Em Andamento'
            css_status = 'started'
        elif len(real_players) >= adv['totalParticipants']:
            status_label = 'Cheia'
            css_status = 'full'
        else:
            status_label = 'Aguardando'
            css_status = 'waiting'
        adventure_list.append({
            'code': adv['code'],
            'status': css_status,
            'status_label': status_label,
            'player_count': len(real_players),
            'max_players': adv['totalParticipants'],
            'created_at': adv.get('createdAt', '')[:10]
        })
    return render_template('join_adventure.html', adventures=adventure_list)


@page_routes.route('/characters')
def characters():
    characters_list = file_storage.list_local_characters()
    processed = []
    for c in characters_list:
        attrs = c.get('attributes', {})
        processed.append({
            'id': c.get('code', ''),
            'nome': c.get('name', ''),
            'raca': c.get('race', ''),
            'genero': c.get('gender', ''),
            'idade': c.get('age', 0),
            'forca': attrs.get('strength', 0),
            'destreza': attrs.get('dexterity', 0),
            'constituicao': attrs.get('constitution', 0),
            'inteligencia': attrs.get('intelligence', 0),
            'sabedoria': attrs.get('wisdom', 0),
            'carisma': attrs.get('charisma', 0)
        })
    return render_template('characters.html', characters=processed)


@page_routes.route('/characters/create')
def create_character():
    return render_template('character_creator.html')


@page_routes.route('/characters/<character_code>/edit')
def edit_character(character_code):
    return render_template('character_creator.html', character_code=character_code, edit_mode=True)


@page_routes.route('/characters/<character_code>')
def view_character(character_code):
    character = file_storage.get_local_character(character_code)
    if not character:
        return render_template('character_view.html', character=None, error=True)
    attrs = character.get('attributes', {})
    physical = character.get('physicalDescription', {})
    weapon = character.get('initialWeaponOrItem', {}) or {}
    ability = character.get('initialSpecialAbility', {}) or {}
    char_data = {
        'code': character.get('code', ''),
        'nome': character.get('name', ''),
        'raca': character.get('race', ''),
        'genero': character.get('gender', ''),
        'idade': character.get('age', 0),
        'forca': attrs.get('strength', 0),
        'destreza': attrs.get('dexterity', 0),
        'constituicao': attrs.get('constitution', 0),
        'inteligencia': attrs.get('intelligence', 0),
        'sabedoria': attrs.get('wisdom', 0),
        'carisma': attrs.get('charisma', 0),
        'furtividade': attrs.get('perception', 0),
        'historia': character.get('story', ''),
        'descricao_fisica': physical.get('customDescription', '') or physical.get('raceBaseDescription', ''),
        'arma': weapon.get('nome', weapon.get('name', '—')),
        'arma_desc': weapon.get('descricao', weapon.get('description', '')),
        'habilidade': ability.get('nome', ability.get('name', '—')),
        'habilidade_desc': ability.get('descricao', ability.get('description', ''))
    }
    return render_template('character_view.html', character=char_data)


@page_routes.route('/adventures/<adventure_id>/waiting-room')
def waiting_room(adventure_id):
    adventure = file_storage.get_adventure(adventure_id)
    if not adventure:
        return render_template('waiting_room.html', adventure_id=adventure_id, adventure={'code': 'DESCONHECIDO'}, error=True)
    characters = file_storage.get_adventure_characters(adventure_id)
    real_players = [c for c in characters if not c.get('isBot')]
    bots = [c for c in characters if c.get('isBot')]
    adventure['max_players'] = adventure.get('totalParticipants', len(characters))
    adventure['players'] = [{
        'nome': c.get('name', ''),
        'code': c.get('code', ''),
        'is_host': c.get('code') == adventure.get('hostCharacterCode'),
        'is_bot': False
    } for c in real_players]
    adventure['bots'] = [{
        'nome': c.get('name', ''),
        'code': c.get('code', ''),
        'is_bot': True
    } for c in bots]
    return render_template('waiting_room.html', adventure=adventure, adventure_id=adventure_id)


@page_routes.route('/adventures/<adventure_id>/game')
def game(adventure_id):
    adventure = file_storage.get_adventure(adventure_id)
    if not adventure:
        return render_template('game.html', adventure={'code': 'DESCONHECIDO'}, character={}, adventure_id=adventure_id, error=True)
    characters = file_storage.get_adventure_characters(adventure_id)
    adventure['players'] = [{
        'nome': c.get('name', ''),
        'code': c.get('code', '')
    } for c in characters if not c.get('isBot')]
    adventure['bots'] = [{
        'nome': c.get('name', ''),
        'code': c.get('code', '')
    } for c in characters if c.get('isBot')]
    char_code_param = request.args.get('char')
    if not char_code_param:
        cookie_name = 'adv_' + adventure_id + '_char'
        cookie_val = request.cookies.get(cookie_name)
        if cookie_val:
            char_code_param = cookie_val
    host_char = {}
    chosen_code = char_code_param or adventure.get('hostCharacterCode')
    if chosen_code:
        for c in characters:
            if c.get('code') == chosen_code:
                host_char = {
                    'nome': c.get('name', ''),
                    'raca': c.get('race', ''),
                    'code': c.get('code', '')
                }
                break
    return render_template('game.html', adventure=adventure, character=host_char, adventure_id=adventure_id)
