from flask import Blueprint, request, jsonify
from services import file_storage, scene_service, ai_orchestrator
from services import character_service, inventory_service, coin_service
from services import validation_service
from services.dice_service import resolve_roll
import json

game_routes = Blueprint('game_routes', __name__)


@game_routes.route('/api/adventures/<adventure_id>/scene/current', methods=['GET'])
def get_current_scene(adventure_id):
    scene = scene_service.get_current_scene(adventure_id)
    if not scene:
        return jsonify({'error': 'Nenhuma cena ativa.'}), 404
    result = dict(scene)
    result['sceneLog'] = scene.get('sceneLog', [])
    return jsonify(result)


@game_routes.route('/api/adventures/<adventure_id>/turn/action', methods=['POST'])
def post_action(adventure_id):
    data = request.get_json() or {}
    character_code = data.get('characterCode')
    action = data.get('action', '').strip()

    if not character_code or not action:
        return jsonify({'error': 'Código do personagem e ação são obrigatórios.'}), 400

    adventure = file_storage.get_adventure(adventure_id)
    if not adventure:
        return jsonify({'error': 'Aventura não encontrada.'}), 404

    char = file_storage.get_adventure_character(adventure_id, character_code)
    if not char:
        return jsonify({'error': 'Personagem não encontrado.'}), 404

    is_valid, error_msg = validation_service.validate_life_state(char)
    if not is_valid:
        return jsonify({'error': error_msg}), 400

    is_valid, error_msg = validation_service.validate_turn(adventure, character_code)
    if not is_valid:
        return jsonify({'error': error_msg}), 400

    task_id = ai_orchestrator.resolve_player_action(adventure_id, character_code, action)
    return jsonify({'taskId': task_id, 'status': 'processing', 'message': 'Ação enviada. Aguardando resposta do Mestre...'})


@game_routes.route('/api/adventures/<adventure_id>/bot/act', methods=['POST'])
def bot_act(adventure_id):
    data = request.get_json() or {}
    bot_code = data.get('botCode')

    if not bot_code:
        return jsonify({'error': 'Código do bot é obrigatório.'}), 400

    adventure = file_storage.get_adventure(adventure_id)
    if not adventure:
        return jsonify({'error': 'Aventura não encontrada.'}), 404

    bot = file_storage.get_adventure_character(adventure_id, bot_code)
    if not bot:
        return jsonify({'error': 'Bot não encontrado.'}), 404
    if not bot.get('isBot'):
        return jsonify({'error': 'Personagem não é um bot.'}), 400

    is_valid, error_msg = validation_service.validate_turn(adventure, bot_code)
    if not is_valid:
        return jsonify({'error': error_msg}), 400

    task_id = ai_orchestrator.resolve_bot_action(adventure_id, bot_code)
    return jsonify({'taskId': task_id, 'status': 'processing', 'message': 'Bot decidindo ação...'})


@game_routes.route('/api/adventures/<adventure_id>/turn/pass', methods=['POST'])
def pass_turn(adventure_id):
    data = request.get_json() or {}
    character_code = data.get('characterCode')

    if not character_code:
        return jsonify({'error': 'Código do personagem é obrigatório.'}), 400

    adventure = file_storage.get_adventure(adventure_id)
    if not adventure:
        return jsonify({'error': 'Aventura não encontrada.'}), 404

    is_valid, error_msg = validation_service.validate_turn(adventure, character_code)
    if not is_valid:
        return jsonify({'error': error_msg}), 400

    scene = scene_service.get_current_scene(adventure_id)
    if scene:
        scene_service.advance_turn(adventure_id, scene['sceneId'])
        from services.socket_service import emit_scene_update
        emit_scene_update(adventure_id)

    return jsonify({'message': 'Turno passado com sucesso.'})


@game_routes.route('/api/adventures/<adventure_id>/dice/roll', methods=['POST'])
def roll_dice(adventure_id):
    data = request.get_json() or {}
    character_code = data.get('characterCode')
    attribute = data.get('attribute', 'strength')
    difficulty = data.get('difficulty', 12)
    reason = data.get('reason', '')

    char = file_storage.get_adventure_character(adventure_id, character_code)
    if not char:
        return jsonify({'error': 'Personagem não encontrado.'}), 404

    result = resolve_roll(char, attribute, difficulty)
    file_storage.append_log(adventure_id, 'game',
                             f'Rolagem solicitada: {reason} - Resultado: {result["roll"]}+{result["attributeValue"]}={result["total"]} vs {difficulty} = {result["intensity"]}')

    return jsonify(result)


@game_routes.route('/api/adventures/<adventure_id>/item/drop', methods=['POST'])
def drop_item(adventure_id):
    data = request.get_json() or {}
    character_code = data.get('characterCode')
    slot_index = data.get('slotIndex')

    if slot_index is None:
        return jsonify({'error': 'Slot é obrigatório.'}), 400

    item, error = inventory_service.drop_item_to_scene(adventure_id, character_code, slot_index)
    if error:
        return jsonify({'error': error}), 400
    return jsonify({'message': 'Item descartado.', 'item': item})


@game_routes.route('/api/adventures/<adventure_id>/item/use', methods=['POST'])
def use_item(adventure_id):
    data = request.get_json() or {}
    character_code = data.get('characterCode')
    slot_index = data.get('slotIndex')

    if slot_index is None:
        return jsonify({'error': 'Slot é obrigatório.'}), 400

    item, error = inventory_service.use_item(adventure_id, character_code, slot_index)
    if error:
        return jsonify({'error': error}), 400
    return jsonify({'message': 'Item usado.', 'item': item})


@game_routes.route('/api/adventures/<adventure_id>/coins/transfer', methods=['POST'])
def transfer_coins(adventure_id):
    data = request.get_json() or {}
    from_code = data.get('fromCharacterCode')
    to_code = data.get('toCharacterCode')
    amount = data.get('amount', 0)

    if not from_code or not to_code:
        return jsonify({'error': 'Códigos dos personagens são obrigatórios.'}), 400
    if amount <= 0:
        return jsonify({'error': 'Quantidade deve ser positiva.'}), 400

    is_valid, error = coin_service.validate_transaction(adventure_id, from_code, amount)
    if not is_valid:
        return jsonify({'error': error}), 400

    success = coin_service.transfer_coins(adventure_id, from_code, to_code, amount)
    if not success:
        return jsonify({'error': 'Falha na transferência.'}), 400
    return jsonify({'message': f'{amount} moedas transferidas com sucesso.'})


@game_routes.route('/api/adventures/<adventure_id>/heal', methods=['POST'])
def heal(adventure_id):
    data = request.get_json() or {}
    character_code = data.get('characterCode')
    target_code = data.get('targetCode', character_code)
    ability_id = data.get('abilityId')

    if not character_code:
        return jsonify({'error': 'Código do personagem é obrigatório.'}), 400

    char = file_storage.get_adventure_character(adventure_id, character_code)
    if not char:
        return jsonify({'error': 'Personagem não encontrado.'}), 404

    if ability_id:
        ability = None
        for a in char.get('specialAbilities', []):
            if a.get('id') == ability_id:
                ability = a
                break
        if not ability:
            return jsonify({'error': 'Habilidade não encontrada.'}), 400

        is_valid, error_msg = validation_service.validate_cooldown(ability)
        if not is_valid:
            return jsonify({'error': error_msg}), 400

    from services.combat_service import apply_healing
    amount = data.get('amount', 10)
    result = apply_healing(adventure_id, target_code, amount, character_code)
    if not result:
        return jsonify({'error': 'Falha ao curar.'}), 400

    return jsonify(result)


@game_routes.route('/api/adventures/<adventure_id>/trade/request', methods=['POST'])
def request_trade(adventure_id):
    data = request.get_json() or {}
    from_code = data.get('fromCharacterCode')
    to_code = data.get('toCharacterCode')

    if not from_code or not to_code:
        return jsonify({'error': 'Códigos dos personagens são obrigatórios.'}), 400

    from_char = file_storage.get_adventure_character(adventure_id, from_code)
    to_char = file_storage.get_adventure_character(adventure_id, to_code)
    if not from_char or not to_char:
        return jsonify({'error': 'Personagem não encontrado.'}), 404

    offer_items = data.get('offerItems', [])
    offer_coins = data.get('offerCoins', 0)
    request_items = data.get('requestItems', [])
    request_coins = data.get('requestCoins', 0)

    trade = {
        'id': file_storage.generate_adventure_code(),
        'fromCharacterCode': from_code,
        'toCharacterCode': to_code,
        'offerItems': offer_items,
        'offerCoins': offer_coins,
        'requestItems': request_items,
        'requestCoins': request_coins,
        'status': 'pending',
        'fromConfirmed': False,
        'toConfirmed': False
    }

    base = file_storage.resolve_adventure_path(adventure_id)
    trades_path = base + '/active_trades.json'
    trades = file_storage.read_json(trades_path) or []
    trades.append(trade)
    file_storage.write_json(trades_path, trades)

    return jsonify(trade), 201


@game_routes.route('/api/adventures/<adventure_id>/trade/respond', methods=['POST'])
def respond_trade(adventure_id):
    data = request.get_json() or {}
    trade_id = data.get('tradeId')
    accept = data.get('accept', False)

    base = file_storage.resolve_adventure_path(adventure_id)
    trades_path = base + '/active_trades.json'
    trades = file_storage.read_json(trades_path) or []

    trade = None
    for t in trades:
        if t['id'] == trade_id:
            trade = t
            break

    if not trade:
        return jsonify({'error': 'Troca não encontrada.'}), 404

    if accept:
        trade['toConfirmed'] = True
    else:
        trade['status'] = 'rejected'
        trades = [t for t in trades if t['id'] != trade_id]
        file_storage.write_json(trades_path, trades)
        return jsonify({'message': 'Troca recusada.'})

    file_storage.write_json(trades_path, trades)
    return jsonify(trade)


@game_routes.route('/api/adventures/<adventure_id>/trade/confirm', methods=['POST'])
def confirm_trade(adventure_id):
    data = request.get_json() or {}
    trade_id = data.get('tradeId')

    base = file_storage.resolve_adventure_path(adventure_id)
    trades_path = base + '/active_trades.json'
    trades = file_storage.read_json(trades_path) or []

    trade = None
    trade_idx = -1
    for i, t in enumerate(trades):
        if t['id'] == trade_id:
            trade = t
            trade_idx = i
            break

    if not trade:
        return jsonify({'error': 'Troca não encontrada.'}), 404

    if not trade.get('toConfirmed'):
        return jsonify({'error': 'Troca ainda não foi aceita.'}), 400

    from_code = trade['fromCharacterCode']
    to_code = trade['toCharacterCode']

    for slot_idx in trade.get('offerItems', []):
        inventory_service.transfer_item(adventure_id, from_code, to_code, slot_idx)

    for slot_idx in trade.get('requestItems', []):
        inventory_service.transfer_item(adventure_id, to_code, from_code, slot_idx)

    offer_coins = trade.get('offerCoins', 0)
    request_coins = trade.get('requestCoins', 0)

    if offer_coins > 0:
        coin_service.transfer_coins(adventure_id, from_code, to_code, offer_coins)
    if request_coins > 0:
        coin_service.transfer_coins(adventure_id, to_code, from_code, request_coins)

    trade['status'] = 'completed'
    trades.pop(trade_idx)
    file_storage.write_json(trades_path, trades)

    return jsonify({'message': 'Troca concluída com sucesso!'})


@game_routes.route('/api/adventures/<adventure_id>/npc/chat', methods=['POST'])
def chat_npc(adventure_id):
    data = request.get_json() or {}
    character_code = data.get('characterCode')
    npc_code = data.get('npcCode')
    message = data.get('message', '')

    if not character_code or not npc_code:
        return jsonify({'error': 'Código do personagem e NPC são obrigatórios.'}), 400

    scene = scene_service.get_current_scene(adventure_id)
    if not scene:
        return jsonify({'error': 'Nenhuma cena ativa.'}), 404

    npcs = scene.get('availableNPCs', [])
    npc = None
    for n in npcs:
        if n.get('code') == npc_code or n.get('id') == npc_code or n.get('name') == npc_code:
            npc = n
            break

    if not npc:
        return jsonify({'error': 'NPC não encontrado nesta cena.'}), 404

    char = file_storage.get_adventure_character(adventure_id, character_code)
    global_info = file_storage.get_global_info(adventure_id)
    timeline = file_storage.get_timeline(adventure_id)

    from services.ai_client import load_prompt, call_ai, parse_ai_json
    import json

    prompt = load_prompt('game_master_prompt.txt')
    npc_context = {
        'action': f'Conversar com NPC: {npc.get("name", npc_code)}',
        'character': {'code': char['code'], 'name': char.get('name'), 'race': char.get('race'), 'charisma': char.get('attributes', {}).get('charisma', 0)},
        'npc': npc,
        'message': message,
        'sceneContext': scene.get('currentContext', ''),
        'globalInfo': global_info
    }

    messages = [
        {'role': 'system', 'content': prompt + '\n\nVocê está gerenciando uma conversa com NPC. Responda apenas como o NPC, em português, no formato JSON com narração.'},
        {'role': 'user', 'content': json.dumps(npc_context, ensure_ascii=False)}
    ]

    task_id = ai_orchestrator.submit_chat(adventure_id, messages)
    return jsonify({'taskId': task_id})


@game_routes.route('/api/adventures/<adventure_id>/bot/chat', methods=['POST'])
def chat_bot(adventure_id):
    data = request.get_json() or {}
    character_code = data.get('characterCode')
    bot_code = data.get('botCode')
    message = data.get('message', '')

    if not character_code or not bot_code:
        return jsonify({'error': 'Código do personagem e bot são obrigatórios.'}), 400

    char = file_storage.get_adventure_character(adventure_id, character_code)
    bot = file_storage.get_adventure_character(adventure_id, bot_code)
    if not char or not bot:
        return jsonify({'error': 'Personagem não encontrado.'}), 404

    if not bot.get('isBot'):
        return jsonify({'error': 'Personagem alvo não é um bot.'}), 400

    from services.ai_client import load_prompt
    import json

    prompt = load_prompt('game_master_prompt.txt')
    bot_personality = bot.get('story', '')
    bot_name = bot.get('name', 'Bot')

    context = {
        'action': f'Conversar com o companheiro bot: {bot_name}',
        'character': {'code': char['code'], 'name': char.get('name'), 'race': char.get('race')},
        'bot': {'code': bot['code'], 'name': bot_name, 'race': bot.get('race'), 'personality': bot_personality},
        'message': message
    }

    messages = [
        {'role': 'system', 'content': prompt + f'\n\nVocê está interpretando o bot "{bot_name}". Responda como o bot falaria, baseado em sua personalidade. Responda em JSON com narração.'},
        {'role': 'user', 'content': json.dumps(context, ensure_ascii=False)}
    ]

    task_id = ai_orchestrator.submit_chat(adventure_id, messages)
    return jsonify({'taskId': task_id})


@game_routes.route('/api/adventures/<adventure_id>/item/pickup', methods=['POST'])
def pickup_item(adventure_id):
    data = request.get_json() or {}
    character_code = data.get('characterCode')
    item_id = data.get('itemId')

    if not character_code or not item_id:
        return jsonify({'error': 'Código do personagem e ID do item são obrigatórios.'}), 400

    success, error = inventory_service.pickup_item_from_scene(adventure_id, character_code, item_id)
    if error:
        return jsonify({'error': error}), 400
    return jsonify({'message': 'Item coletado.'})


@game_routes.route('/api/adventures/<adventure_id>/enemy/attack', methods=['POST'])
def attack_enemy(adventure_id):
    data = request.get_json() or {}
    character_code = data.get('characterCode')
    enemy_code = data.get('enemyCode')
    amount = data.get('amount', 0)

    if not character_code or not enemy_code:
        return jsonify({'error': 'Código do personagem e do inimigo são obrigatórios.'}), 400

    from services.combat_service import apply_damage_to_enemy
    result = apply_damage_to_enemy(adventure_id, enemy_code, amount)
    if not result:
        return jsonify({'error': 'Inimigo não encontrado.'}), 404
    return jsonify(result)


@game_routes.route('/api/adventures/<adventure_id>/enemy/loot', methods=['POST'])
def loot_enemy(adventure_id):
    data = request.get_json() or {}
    character_code = data.get('characterCode')
    enemy_code = data.get('enemyCode')

    if not character_code or not enemy_code:
        return jsonify({'error': 'Código do personagem e do inimigo são obrigatórios.'}), 400

    from services.combat_service import distribute_loot
    loot = distribute_loot(adventure_id, enemy_code, character_code)
    return jsonify({'loot': loot})


@game_routes.route('/api/adventures/<adventure_id>/enemies/<enemy_code>', methods=['GET'])
def get_enemy(adventure_id, enemy_code):
    enemy = file_storage.get_enemy(adventure_id, enemy_code)
    if not enemy:
        return jsonify({'error': 'Inimigo não encontrado.'}), 404
    return jsonify(enemy)


@game_routes.route('/api/adventures/<adventure_id>/scene/transition/confirm', methods=['POST'])
def confirm_scene_transition(adventure_id):
    data = request.get_json() or {}
    character_code = data.get('characterCode')
    scene_id = data.get('sceneId')
    accept = data.get('accept', True)

    if not character_code:
        return jsonify({'error': 'Código do personagem é obrigatório.'}), 400

    base = file_storage.resolve_adventure_path(adventure_id)
    trans_path = base + '/pending_transitions.json'
    transitions = file_storage.read_json(trans_path) or []

    found = None
    for t in transitions:
        if t.get('sceneId') == scene_id:
            found = t
            break

    if not found:
        return jsonify({'error': 'Nenhuma transição pendente para esta cena.'}), 404

    if character_code not in found.get('confirmations', {}):
        found.setdefault('confirmations', {})[character_code] = accept

    all_confirmed = True
    any_rejected = False
    characters = file_storage.get_adventure_characters(adventure_id)
    active = [c['code'] for c in characters if c.get('life', {}).get('state') in ('alive', 'unconscious') and not c.get('isBot')]

    for code in active:
        confirmation = found.get('confirmations', {}).get(code)
        if confirmation is None:
            all_confirmed = False
        elif confirmation is False:
            any_rejected = True

    if any_rejected:
        transitions = [t for t in transitions if t.get('sceneId') != scene_id]
        file_storage.write_json(trans_path, transitions)
        return jsonify({'message': 'Transição recusada. O grupo permanece na cena atual.'})

    if all_confirmed:
        scene_service.set_current_scene(adventure_id, scene_id)
        chars = file_storage.get_adventure_characters(adventure_id)
        for c in chars:
            c['currentSceneId'] = scene_id
            file_storage.save_adventure_character(adventure_id, c)
        transitions = [t for t in transitions if t.get('sceneId') != scene_id]
        file_storage.write_json(trans_path, transitions)
        return jsonify({'message': 'Transição de cena aprovada por todos!'})

    file_storage.write_json(trans_path, transitions)
    return jsonify({'message': 'Confirmação registrada. Aguardando demais jogadores...'})


_last_snapshots = {}


def _build_scene_update_payload(adventure_id):
    adventure = file_storage.get_adventure(adventure_id)
    if not adventure:
        return None
    scene = scene_service.get_current_scene(adventure_id) if adventure.get('currentSceneId') else None
    characters = file_storage.get_adventure_characters(adventure_id)
    snapshot = _state_snapshot(adventure, scene, characters)
    snapshot['adventure_id'] = adventure_id
    prev = _last_snapshots.get(adventure_id)
    events = _snapshot_to_events(snapshot, characters, prev)
    _last_snapshots[adventure_id] = snapshot
    return events


def _state_snapshot(adventure, scene, characters):
    return {
        'adventure_id': '',
        'adventure_status': adventure.get('status'),
        'adventure_scene_id': adventure.get('currentSceneId'),
        'scene_id': scene.get('sceneId') if scene else None,
        'scene_title': scene.get('title', '') if scene else '',
        'scene_context': scene.get('currentContext') or scene.get('mainDescription', '') if scene else '',
        'scene_turn_char': scene.get('currentTurnCharacterCode') if scene else None,
        'scene_npcs': scene.get('availableNPCs', []) if scene else [],
        'scene_enemies': scene.get('availableEnemies', []) if scene else [],
        'scene_log': scene.get('sceneLog', []) if scene else [],
        'characters': [{
            'code': c['code'],
            'name': c.get('name', ''),
            'isBot': c.get('isBot', False),
            'life': c.get('life'),
            'coins': c.get('coins'),
            'currentSceneId': c.get('currentSceneId'),
            'inventory': c.get('inventory', []),
            'specialAbilities': c.get('specialAbilities', [])
        } for c in characters]
    }


def _snapshot_to_events(snapshot, characters, prev=None):
    events = []

    def _changed(key):
        if prev is None:
            return True
        return prev.get(key) != snapshot.get(key)

    if _changed('adventure_status') or _changed('adventure_scene_id') or _changed('scene_id') or \
       _changed('scene_title') or _changed('scene_context') or _changed('scene_log') or \
       _changed('scene_turn_char') or _changed('scene_npcs') or _changed('scene_enemies'):
        enemies_hydrated = []
        for ec in snapshot['scene_enemies']:
            e = file_storage.get_enemy(snapshot.get('adventure_id', ''), ec)
            if e:
                enemies_hydrated.append(e)
        scene_event = {
            'type': 'state_update',
            'adventure': {
                'status': snapshot['adventure_status'],
                'currentSceneId': snapshot['adventure_scene_id']
            },
            'scene': {
                'sceneId': snapshot['scene_id'],
                'title': snapshot['scene_title'],
                'description': snapshot['scene_context'],
                'sceneLog': snapshot['scene_log'],
                'currentTurnCharacterCode': snapshot['scene_turn_char'],
                'availableNPCs': snapshot['scene_npcs'],
                'availableEnemies': enemies_hydrated
            } if snapshot['scene_id'] else None,
            'characters': snapshot['characters']
        }
        events.append(('scene_update', scene_event))

    if (_changed('scene_turn_char') or prev is None) and snapshot['scene_turn_char']:
        turn_char = next((c for c in characters if c['code'] == snapshot['scene_turn_char']), None)
        events.append(('turn_change', {
            'characterCode': snapshot['scene_turn_char'],
            'characterName': turn_char.get('name', '') if turn_char else ''
        }))

    old_chars = {c['code']: c for c in (prev['characters'] if prev else [])}
    for c in snapshot['characters']:
        code = c['code']
        old_c = old_chars.get(code, {})
        if old_c.get('inventory') != c.get('inventory') or prev is None:
            events.append(('inventory_update', {'characterCode': code, 'items': c.get('inventory', [])}))
        if old_c.get('coins') != c.get('coins') or prev is None:
            events.append(('coins_update', {'characterCode': code, 'coins': c.get('coins', {})}))
        if old_c.get('life') != c.get('life') or prev is None:
            events.append(('life_update', {'characterCode': code, 'life': c.get('life', {})}))

    if (_changed('scene_enemies') or prev is None) and snapshot['scene_enemies']:
        enemies = []
        for ec in snapshot['scene_enemies']:
            enemy = file_storage.get_enemy(snapshot.get('adventure_id', ''), ec)
            if enemy:
                enemies.append(enemy)
        if enemies:
            events.append(('enemy_update', {'enemies': enemies}))

    return events


@game_routes.route('/api/adventures/<adventure_id>/task-results', methods=['GET'])
def get_task_results(adventure_id):
    from services.ai_orchestrator import get_tasks_by_adventure
    tasks = get_tasks_by_adventure(adventure_id)
    return jsonify(tasks)


@game_routes.route('/api/adventures/<adventure_id>/task/<task_id>', methods=['GET'])
def get_single_task(adventure_id, task_id):
    from services.ai_orchestrator import get_task
    task = get_task(task_id)
    if not task or task.get('adventureCode') != adventure_id:
        return jsonify({'error': 'Task não encontrada.'}), 404
    return jsonify(task)
