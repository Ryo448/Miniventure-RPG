import os
from services import file_storage
from datetime import datetime


def create_scene(adventure_code, title, main_description, is_interior=False,
                  previous_scene_id=None, available_npcs=None, available_items=None):
    scenes = _list_scene_files(adventure_code)
    scene_num = len(scenes) + 1
    scene_id = f'scene_{scene_num:04d}'

    scene = {
        'sceneId': scene_id,
        'title': title,
        'mainDescription': main_description,
        'isInterior': is_interior,
        'canQuit': True,
        'previousScenePath': previous_scene_id,
        'linkedScenes': [],
        'currentContext': main_description,
        'availableNPCs': available_npcs or [],
        'availableItems': available_items or [],
        'availableEnemies': [],
        'legalContext': None,
        'turnOrder': [],
        'currentTurnCharacterCode': None,
        'sceneLog': []
    }

    file_storage.save_scene(adventure_code, scene)
    file_storage.append_log(adventure_code, 'game', f'Cena criada: {scene_id} - {title}')
    return scene


def update_scene_context(adventure_code, scene_id, context_patch, append=True):
    scene = file_storage.get_scene(adventure_code, scene_id)
    if not scene:
        return None

    if append:
        scene['currentContext'] = scene.get('currentContext', '') + '\n' + context_patch
    else:
        scene['currentContext'] = context_patch

    scene['sceneLog'].append({
        'timestamp': datetime.now().isoformat(),
        'message': context_patch
    })

    file_storage.save_scene(adventure_code, scene)
    return scene


def set_current_scene(adventure_code, scene_id):
    adventure = file_storage.get_adventure(adventure_code)
    if not adventure:
        return None

    adventure['currentSceneId'] = scene_id
    file_storage.save_adventure(adventure_code, adventure)
    return adventure


def get_current_scene(adventure_code):
    adventure = file_storage.get_adventure(adventure_code)
    if not adventure or not adventure.get('currentSceneId'):
        return None
    return file_storage.get_scene(adventure_code, adventure['currentSceneId'])


def init_turn_order(adventure_code, scene_id):
    scene = file_storage.get_scene(adventure_code, scene_id)
    if not scene:
        return None

    characters = file_storage.get_adventure_characters(adventure_code)
    active = [c['code'] for c in characters if isinstance(c.get('life', {}), dict) and c.get('life', {}).get('state') in ('alive', 'unconscious')]

    scene['turnOrder'] = active
    if active:
        scene['currentTurnCharacterCode'] = active[0]

    file_storage.save_scene(adventure_code, scene)
    return scene


def advance_turn(adventure_code, scene_id):
    scene = file_storage.get_scene(adventure_code, scene_id)
    if not scene:
        return None

    turn_order = scene.get('turnOrder', [])
    current = scene.get('currentTurnCharacterCode')

    characters = file_storage.get_adventure_characters(adventure_code)
    active = [c['code'] for c in characters if c.get('life', {}).get('state') in ('alive', 'unconscious')]

    active_order = [c for c in turn_order if c in active]
    missing = [c for c in active if c not in active_order]
    if missing:
        active_order.extend(missing)
        scene['turnOrder'] = active_order

    if not active_order:
        scene['currentTurnCharacterCode'] = None
        file_storage.save_scene(adventure_code, scene)
        return scene

    if current in active_order:
        idx = active_order.index(current)
        next_idx = (idx + 1) % len(active_order)
    else:
        next_idx = 0

    next_char = active_order[next_idx]
    scene['currentTurnCharacterCode'] = next_char

    from services import character_service
    character_service.reduce_cooldowns(adventure_code, next_char)

    file_storage.save_scene(adventure_code, scene)
    return scene


def add_item_to_scene(adventure_code, scene_id, item):
    scene = file_storage.get_scene(adventure_code, scene_id)
    if not scene:
        return None
    scene.setdefault('availableItems', []).append(item)
    file_storage.save_scene(adventure_code, scene)
    return scene


def remove_item_from_scene(adventure_code, scene_id, item_id):
    scene = file_storage.get_scene(adventure_code, scene_id)
    if not scene:
        return None
    items = scene.get('availableItems', [])
    for i, item in enumerate(items):
        if item.get('id') == item_id:
            removed = items.pop(i)
            file_storage.save_scene(adventure_code, scene)
            return removed
    return None


def add_npc_to_scene(adventure_code, scene_id, npc):
    scene = file_storage.get_scene(adventure_code, scene_id)
    if not scene:
        return None
    scene.setdefault('availableNPCs', []).append(npc)
    file_storage.save_scene(adventure_code, scene)
    return scene


def add_enemy_to_scene(adventure_code, scene_id, enemy_code):
    scene = file_storage.get_scene(adventure_code, scene_id)
    if not scene:
        return None
    scene.setdefault('availableEnemies', []).append(enemy_code)
    file_storage.save_scene(adventure_code, scene)
    return scene


def remove_enemy_from_scene(adventure_code, scene_id, enemy_code):
    scene = file_storage.get_scene(adventure_code, scene_id)
    if not scene:
        return None
    scene['availableEnemies'] = [e for e in scene.get('availableEnemies', []) if e != enemy_code]
    file_storage.save_scene(adventure_code, scene)
    return scene


def remove_npc_from_scene(adventure_code, scene_id, npc_id):
    scene = file_storage.get_scene(adventure_code, scene_id)
    if not scene:
        return None
    scene['availableNPCs'] = [n for n in scene.get('availableNPCs', []) if n.get('id') != npc_id]
    file_storage.save_scene(adventure_code, scene)
    return scene


def _list_scene_files(adventure_code):
    base = file_storage.resolve_adventure_path(adventure_code)
    scenes_dir = os.path.join(base, 'scenes')
    if not os.path.exists(scenes_dir):
        return []
    import os
    return [f for f in os.listdir(scenes_dir) if f.endswith('.json')]

