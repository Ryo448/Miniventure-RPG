VALID_COMMAND_TYPES = [
    'ADD_ITEM_TO_CHARACTER',
    'REMOVE_ITEM_FROM_CHARACTER',
    'ADD_COINS',
    'REMOVE_COINS',
    'TRANSFER_COINS',
    'UPDATE_SCENE_CONTEXT',
    'CREATE_SCENE',
    'CREATE_ENEMY',
    'APPLY_DAMAGE',
    'APPLY_HEALING',
    'REGISTER_CRIME',
    'UPDATE_GLOBAL_INFO',
    'TRANSITION_SCENE',
    'ADD_TEMPORARY_EFFECT',
    'ADD_ABILITY',
    'UPDATE_ARMOR'
]


def validate_ai_response(json_data):
    errors = []
    if not isinstance(json_data, dict):
        return False, ['Resposta da IA não é um objeto JSON válido.']

    if 'narration' not in json_data and 'commands' not in json_data:
        errors.append('Resposta da IA deve conter "narration" ou "commands".')

    if 'commands' in json_data and not isinstance(json_data['commands'], list):
        errors.append('"commands" deve ser uma lista.')

    if 'requiresDiceRoll' in json_data and not isinstance(json_data['requiresDiceRoll'], bool):
        errors.append('"requiresDiceRoll" deve ser booleano.')

    if json_data.get('requiresDiceRoll') and not json_data.get('diceRequest'):
        errors.append('Quando requiresDiceRoll é true, diceRequest deve estar presente.')

    if json_data.get('diceRequest'):
        dice = json_data['diceRequest']
        if not dice.get('die') or not dice.get('attribute') or not dice.get('characterCode'):
            errors.append('diceRequest deve conter die, attribute, e characterCode.')
        if not isinstance(dice.get('difficulty', 0), (int, float)):
            errors.append('difficulty deve ser numérico.')

    if 'requiresAdditionalContext' in json_data:
        if json_data['requiresAdditionalContext'] and not json_data.get('contextRequest'):
            errors.append('Quando requiresAdditionalContext é true, contextRequest deve estar presente.')

    return len(errors) == 0, errors


def validate_command(command, adventure_data, characters_data):
    errors = []
    cmd_type = command.get('type')

    if cmd_type not in VALID_COMMAND_TYPES:
        return False, [f'Tipo de comando desconhecido: {cmd_type}']

    char_map = {c['code']: c for c in characters_data}

    if cmd_type == 'ADD_ITEM_TO_CHARACTER':
        char_code = command.get('characterCode')
        if char_code not in char_map:
            errors.append(f'Personagem {char_code} não encontrado.')
        else:
            char = char_map[char_code]
            inv = char.get('inventory', [])
            free_slots = sum(1 for s in inv if s is None)
            if free_slots <= 0:
                errors.append(f'Inventário de {char_code} está cheio.')

    elif cmd_type == 'REMOVE_ITEM_FROM_CHARACTER':
        char_code = command.get('characterCode')
        if char_code not in char_map:
            errors.append(f'Personagem {char_code} não encontrado.')
        else:
            slot = command.get('slotIndex')
            inv = char_map[char_code].get('inventory', [])
            if slot is None or slot < 0 or slot >= len(inv):
                errors.append(f'Slot {slot} inválido.')
            elif inv[slot] is None:
                errors.append(f'Slot {slot} está vazio.')

    elif cmd_type == 'ADD_COINS':
        char_code = command.get('characterCode')
        amount = command.get('amount', 0)
        if char_code not in char_map:
            errors.append(f'Personagem {char_code} não encontrado.')
        if not isinstance(amount, (int, float)) or amount < 0:
            errors.append('Quantidade de moedas deve ser numérica e não-negativa.')

    elif cmd_type == 'REMOVE_COINS':
        char_code = command.get('characterCode')
        amount = command.get('amount', 0)
        if char_code not in char_map:
            errors.append(f'Personagem {char_code} não encontrado.')
        elif not isinstance(amount, (int, float)) or amount < 0:
            errors.append('Quantidade de moedas deve ser numérica e não-negativa.')
        else:
            current = char_map[char_code].get('coins', {}).get('amount', 0)
            if amount > current:
                errors.append(f'Personagem {char_code} não tem moedas suficientes ({current}/{amount}).')

    elif cmd_type == 'TRANSFER_COINS':
        from_code = command.get('fromCharacterCode')
        to_code = command.get('toCharacterCode')
        amount = command.get('amount', 0)
        if from_code not in char_map:
            errors.append(f'Personagem de origem {from_code} não encontrado.')
        if to_code not in char_map:
            errors.append(f'Personagem de destino {to_code} não encontrado.')
        if not isinstance(amount, (int, float)) or amount < 0:
            errors.append('Quantidade de moedas deve ser numérica e não-negativa.')
        elif from_code in char_map:
            current = char_map[from_code].get('coins', {}).get('amount', 0)
            if amount > current:
                errors.append(f'Personagem {from_code} não tem moedas suficientes ({current}/{amount}).')

    elif cmd_type == 'APPLY_DAMAGE':
        char_code = command.get('characterCode')
        amount = command.get('amount', 0)
        if char_code not in char_map:
            errors.append(f'Personagem {char_code} não encontrado.')
        elif char_map[char_code].get('life', {}).get('state') == 'dead':
            errors.append(f'Personagem {char_code} já está morto.')

    elif cmd_type == 'APPLY_HEALING':
        char_code = command.get('characterCode')
        if char_code not in char_map:
            errors.append(f'Personagem {char_code} não encontrado.')
        elif char_map[char_code].get('life', {}).get('state') == 'dead':
            errors.append(f'Não é possível curar um personagem morto ({char_code}).')

    elif cmd_type == 'ADD_ABILITY':
        char_code = command.get('characterCode')
        if char_code not in char_map:
            errors.append(f'Personagem {char_code} não encontrado.')
        ability = command.get('ability')
        if not ability or not ability.get('id'):
            errors.append('Habilidade deve conter um ID.')

    elif cmd_type in ('CREATE_SCENE', 'CREATE_ENEMY', 'UPDATE_SCENE_CONTEXT',
                       'UPDATE_GLOBAL_INFO', 'REGISTER_CRIME', 'TRANSITION_SCENE',
                       'ADD_TEMPORARY_EFFECT', 'UPDATE_ARMOR'):
        pass

    return len(errors) == 0, errors


def validate_inventory_slot(character_data, slot_index):
    inv = character_data.get('inventory', [])
    if slot_index < 0 or slot_index >= len(inv):
        return False, f'Slot {slot_index} inválido.'
    return True, None


def validate_coins(character_data, amount):
    current = character_data.get('coins', {}).get('amount', 0)
    if amount > current:
        return False, f'Moedas insuficientes ({current}/{amount}).'
    return True, None


def validate_cooldown(ability):
    remaining = ability.get('remainingCooldownTurns', 0)
    if remaining > 0:
        return False, f'Habilidade em recarga ({remaining} turnos restantes).'
    return True, None


def validate_life_state(character_data):
    state = character_data.get('life', {}).get('state', 'alive')
    if state == 'dead':
        return False, 'Personagem está morto.'
    if state == 'unconscious':
        return False, 'Personagem está inconsciente.'
    return True, None


def validate_turn(adventure_data, character_code):
    scene_id = adventure_data.get('currentSceneId')
    if not scene_id:
        return False, 'Nenhuma cena ativa.'

    from services.file_storage import get_scene
    scene = get_scene(adventure_data['code'], scene_id)
    if not scene:
        return False, 'Cena não encontrada.'

    current_turn = scene.get('currentTurnCharacterCode')
    if current_turn != character_code:
        return False, f'Não é o turno de {character_code}. Turno atual: {current_turn}'

    return True, None


def validate_item_exists(item_id, catalog):
    for item in catalog:
        if item.get('id') == item_id:
            return True, item
    return False, f'Item {item_id} não encontrado no catálogo.'
