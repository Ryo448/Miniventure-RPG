import uuid
from services import file_storage
from services import catalog_service


def generate_character_code():
    return uuid.uuid4().hex[:8].upper()


_ATTRS_MAP = {
    'forca': 'strength', 'destreza': 'dexterity', 'constituicao': 'constitution',
    'inteligencia': 'intelligence', 'sabedoria': 'wisdom', 'carisma': 'charisma',
    'magia': 'magic', 'furtividade': 'perception', 'sorte': 'luck', 'perception': 'perception'
}


def _map_attributes(raw_attrs, race_data=None):
    mapped = {}
    for k, v in raw_attrs.items():
        mapped_key = _ATTRS_MAP.get(k, k)
        mapped[mapped_key] = v

    if race_data and race_data.get('pontos'):
        for attr_pt, bonus in race_data['pontos'].items():
            attr_en = _ATTRS_MAP.get(attr_pt, attr_pt)
            mapped[attr_en] = mapped.get(attr_en, 0) + bonus

    return mapped


def create_local_character(data):
    code = generate_character_code()
    race_data = catalog_service.get_race_by_id(data.get('raceId', ''))
    weapon_data = catalog_service.get_weapon_by_id(data.get('weaponId', ''))
    ability_data = catalog_service.get_ability_by_id(data.get('abilityId', ''))

    mapped_attrs = _map_attributes(data.get('attributes', {}), race_data)

    character = {
        'code': code,
        'name': data.get('name', ''),
        'gender': data.get('gender', 'masculino'),
        'age': data.get('age', 25),
        'race': race_data.get('nome', data.get('raceId', '')) if race_data else data.get('raceId', ''),
        'raceId': data.get('raceId', ''),
        'attributes': mapped_attrs,
        'story': data.get('story', ''),
        'physicalDescription': {
            'raceBaseDescription': race_data.get('baseDescription', '') if race_data else '',
            'customDescription': data.get('customDescription', '')
        },
        'initialWeaponOrItem': weapon_data or {},
        'initialSpecialAbility': ability_data or {}
    }

    file_storage.save_local_character(character)
    return character


def update_local_character(existing, data):
    race_data = catalog_service.get_race_by_id(data.get('raceId', '')) if data.get('raceId') else None

    if 'name' in data:
        existing['name'] = data['name']
    if 'gender' in data:
        existing['gender'] = data['gender']
    if 'age' in data:
        existing['age'] = data['age']
    if 'story' in data:
        existing['story'] = data['story']
    if 'customDescription' in data:
        existing.setdefault('physicalDescription', {})['customDescription'] = data['customDescription']

    if 'raceId' in data:
        existing['raceId'] = data['raceId']
        if race_data:
            existing['race'] = race_data.get('nome', data['raceId'])
            existing.setdefault('physicalDescription', {})['raceBaseDescription'] = race_data.get('baseDescription', '')

    if 'attributes' in data:
        existing['attributes'] = _map_attributes(data['attributes'], race_data)

    if 'weaponId' in data:
        weapon_data = catalog_service.get_weapon_by_id(data['weaponId'])
        existing['initialWeaponOrItem'] = weapon_data or {}

    if 'abilityId' in data:
        ability_data = catalog_service.get_ability_by_id(data['abilityId'])
        existing['initialSpecialAbility'] = ability_data or {}

    return existing


def create_server_character(local_char_data, adventure_code, is_bot=False):
    weapon = local_char_data.get('initialWeaponOrItem', {})
    ability = local_char_data.get('initialSpecialAbility', {})

    server_char = {
        'code': local_char_data['code'],
        'name': local_char_data['name'],
        'gender': local_char_data.get('gender', 'male'),
        'age': local_char_data.get('age', 25),
        'race': local_char_data.get('race', ''),
        'isBot': is_bot,
        'life': {
            'currentPercent': 100,
            'maxPercent': 100,
            'state': 'alive'
        },
        'coins': {
            'amount': 30,
            'displayName': 'Moedas'
        },
        'attributes': local_char_data.get('attributes', {}),
        'armor': {
            'head': None,
            'torso': None,
            'hands': None,
            'legs': None,
            'feet': None
        },
        'specialAbilities': [],
        'inventory': [None] * 8,
        'story': local_char_data.get('story', ''),
        'physicalDescription': local_char_data.get('physicalDescription', {}),
        'currentSceneId': None,
        'temporaryEffects': [],
        'legalStatus': [],
        'personalLog': []
    }

    if weapon:
        server_char['inventory'][0] = {
            'id': weapon.get('id', ''),
            'name': weapon.get('nome', ''),
            'description': weapon.get('descricao', ''),
            'type': 'weapon',
            'uses': [],
            'damage': weapon.get('pontos', {}).get('dano', 0),
            'healingPercent': None
        }

    if ability:
        server_char['specialAbilities'].append({
            'id': ability.get('id', ''),
            'name': ability.get('nome', ''),
            'type': ability.get('tipo', 'other'),
            'description': ability.get('descricao', ''),
            'cooldownTurns': ability.get('cooldownTurnos', 3),
            'remainingCooldownTurns': 0,
            'requiredAttribute': ability.get('atributoPrincipal', 'strength'),
            'requiredLevel': 0,
            'points': ability.get('pontos', {})
        })

    file_storage.save_adventure_character(adventure_code, server_char)
    return server_char


def add_character_to_adventure(adventure_code, character_code):
    local_char = file_storage.get_local_character(character_code)
    if not local_char:
        return None, 'Personagem local não encontrado.'

    adventure = file_storage.get_adventure(adventure_code)
    if not adventure:
        return None, 'Aventura não encontrada.'

    existing = file_storage.get_adventure_characters(adventure_code)
    char_codes = [c['code'] for c in existing]

    if character_code in char_codes:
        server_char = file_storage.get_adventure_character(adventure_code, character_code)
        return server_char, None

    if len(existing) >= adventure['totalParticipants']:
        return None, 'Aventura já está cheia.'

    server_char = create_server_character(local_char, adventure_code)

    adventure['connectedCharacters'].append(character_code)
    if not adventure.get('hostCharacterCode'):
        adventure['hostCharacterCode'] = character_code
    file_storage.save_adventure(adventure_code, adventure)

    file_storage.append_log(adventure_code, 'game', f'Personagem {local_char["name"]} ({character_code}) entrou na aventura.')

    return server_char, None


def add_bot_character_to_adventure(adventure_code, character_code):
    local_char = file_storage.get_local_character(character_code)
    if not local_char:
        return None, 'Personagem local não encontrado.'

    adventure = file_storage.get_adventure(adventure_code)
    if not adventure:
        return None, 'Aventura não encontrada.'

    existing = file_storage.get_adventure_characters(adventure_code)
    char_codes = [c['code'] for c in existing]

    if character_code in char_codes:
        return None, 'Personagem já está na aventura.'

    if len(existing) >= adventure['totalParticipants']:
        return None, 'Aventura já está cheia.'

    server_char = create_server_character(local_char, adventure_code, is_bot=True)

    adventure = file_storage.get_adventure(adventure_code)
    adventure['connectedCharacters'].append(character_code)
    file_storage.save_adventure(adventure_code, adventure)

    file_storage.append_log(adventure_code, 'game', f'Bot {local_char["name"]} ({character_code}) entrou na aventura.')

    return server_char, None


def update_character_life(adventure_code, character_code, delta):
    char = file_storage.get_adventure_character(adventure_code, character_code)
    if not char:
        return None

    current = char['life']['currentPercent']
    new_val = max(0, min(100, current + delta))
    char['life']['currentPercent'] = new_val

    if new_val <= 0:
        char['life']['state'] = 'dead'
    elif new_val <= 20:
        char['life']['state'] = 'unconscious'
    else:
        char['life']['state'] = 'alive'

    file_storage.save_adventure_character(adventure_code, char)
    return char


def update_character_coins(adventure_code, character_code, delta):
    char = file_storage.get_adventure_character(adventure_code, character_code)
    if not char:
        return None

    new_amount = char['coins']['amount'] + delta
    if new_amount < 0:
        return None
    char['coins']['amount'] = new_amount
    file_storage.save_adventure_character(adventure_code, char)
    return char


def add_item_to_inventory(adventure_code, character_code, item):
    char = file_storage.get_adventure_character(adventure_code, character_code)
    if not char:
        return False

    inv = char.get('inventory', [None] * 8)
    if len(inv) < 8:
        inv = inv + [None] * (8 - len(inv))

    for i in range(8):
        if inv[i] is None:
            inv[i] = item
            char['inventory'] = inv
            file_storage.save_adventure_character(adventure_code, char)
            return True
    return False


def remove_item_from_inventory(adventure_code, character_code, slot_index):
    char = file_storage.get_adventure_character(adventure_code, character_code)
    if not char:
        return None

    inv = char.get('inventory', [None] * 8)
    if slot_index < 0 or slot_index >= 8:
        return None

    item = inv[slot_index]
    inv[slot_index] = None
    char['inventory'] = inv
    file_storage.save_adventure_character(adventure_code, char)
    return item


def transfer_item(adventure_code, from_code, to_code, slot_index):
    item = remove_item_from_inventory(adventure_code, from_code, slot_index)
    if not item:
        return False

    success = add_item_to_inventory(adventure_code, to_code, item)
    if not success:
        add_item_to_inventory(adventure_code, from_code, item)
        return False
    return True


def transfer_coins(adventure_code, from_code, to_code, amount):
    from_char = file_storage.get_adventure_character(adventure_code, from_code)
    to_char = file_storage.get_adventure_character(adventure_code, to_code)
    if not from_char or not to_char:
        return False

    if from_char['coins']['amount'] < amount:
        return False

    from_char['coins']['amount'] -= amount
    to_char['coins']['amount'] += amount

    file_storage.save_adventure_character(adventure_code, from_char)
    file_storage.save_adventure_character(adventure_code, to_char)
    return True


def reduce_cooldowns(adventure_code, character_code):
    char = file_storage.get_adventure_character(adventure_code, character_code)
    if not char:
        return

    for ability in char.get('specialAbilities', []):
        if ability.get('remainingCooldownTurns', 0) > 0:
            ability['remainingCooldownTurns'] -= 1

    file_storage.save_adventure_character(adventure_code, char)


def set_ability_cooldown(adventure_code, character_code, ability_id, turns):
    char = file_storage.get_adventure_character(adventure_code, character_code)
    if not char:
        return

    for ability in char.get('specialAbilities', []):
        if ability.get('id') == ability_id:
            ability['remainingCooldownTurns'] = turns
            break

    file_storage.save_adventure_character(adventure_code, char)
