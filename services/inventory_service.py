from services import file_storage
from services import character_service
from services import scene_service


def add_item(adventure_code, character_code, item):
    return character_service.add_item_to_inventory(adventure_code, character_code, item)


def remove_item(adventure_code, character_code, slot_index):
    return character_service.remove_item_from_inventory(adventure_code, character_code, slot_index)


def use_item(adventure_code, character_code, slot_index):
    char = file_storage.get_adventure_character(adventure_code, character_code)
    if not char:
        return None, 'Personagem não encontrado.'

    inv = char.get('inventory', [None] * 8)
    if slot_index < 0 or slot_index >= len(inv) or inv[slot_index] is None:
        return None, 'Nenhum item neste slot.'

    item = inv[slot_index]

    if item.get('healingPercent') and item['healingPercent'] > 0:
        from services.combat_service import apply_healing
        apply_healing(adventure_code, character_code, item['healingPercent'], item.get('name', 'Item'))
        removed = remove_item(adventure_code, character_code, slot_index)
        return removed, None

    if item.get('type') == 'weapon':
        return item, 'Arma equipada. Use-a em combate.'

    return item, 'Item não consumível.'


def drop_item_to_scene(adventure_code, character_code, slot_index):
    char = file_storage.get_adventure_character(adventure_code, character_code)
    if not char:
        return None, 'Personagem não encontrado.'

    inv = char.get('inventory', [None] * 8)
    if slot_index < 0 or slot_index >= len(inv) or inv[slot_index] is None:
        return None, 'Nenhum item neste slot.'

    item = inv[slot_index]
    removed = remove_item(adventure_code, character_code, slot_index)

    if removed and char.get('currentSceneId'):
        scene_service.add_item_to_scene(adventure_code, char['currentSceneId'], removed)

    return removed, None


def pickup_item_from_scene(adventure_code, character_code, item_id):
    char = file_storage.get_adventure_character(adventure_code, character_code)
    if not char:
        return False, 'Personagem não encontrado.'

    scene_id = char.get('currentSceneId')
    if not scene_id:
        return False, 'Personagem não está em uma cena.'

    scene = file_storage.get_scene(adventure_code, scene_id)
    if not scene:
        return False, 'Cena não encontrada.'

    for i, item in enumerate(scene.get('availableItems', [])):
        if item.get('id') == item_id:
            success = add_item(adventure_code, character_code, item)
            if success:
                scene['availableItems'].pop(i)
                file_storage.save_scene(adventure_code, scene)
                return True, None
            else:
                return False, 'Inventário cheio. Item permanece na cena.'

    return False, 'Item não encontrado na cena.'


def transfer_item(adventure_code, from_code, to_code, slot_index):
    return character_service.transfer_item(adventure_code, from_code, to_code, slot_index)
