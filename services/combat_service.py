from services import file_storage
from services import character_service
from services import validation_service
from services import dice_service
from services.dice_service import roll_d24, resolve_roll
import json


def start_combat(adventure_code, enemies_data):
    for enemy in enemies_data:
        file_storage.save_enemy(adventure_code, enemy)
        file_storage.append_log(adventure_code, 'game', f"Inimigo {enemy.get('name')} apareceu na aventura.")


def apply_damage(adventure_code, character_code, amount, source=''):
    char = character_service.update_character_life(adventure_code, character_code, -amount)
    if char:
        state_text = char['life']['state']
        file_storage.append_log(adventure_code, 'game',
                                f"{character_code} sofreu {amount} de dano de {source}. Vida: {char['life']['currentPercent']}% ({state_text})")
    return char


def apply_healing(adventure_code, character_code, amount, source=''):
    char = character_service.update_character_life(adventure_code, character_code, amount)
    if char:
        file_storage.append_log(adventure_code, 'game',
                                f"{character_code} foi curado em {amount} por {source}. Vida: {char['life']['currentPercent']}%")
    return char


def apply_damage_to_enemy(adventure_code, enemy_code, amount):
    enemy = file_storage.get_enemy(adventure_code, enemy_code)
    if not enemy:
        return None

    current = enemy['life']['currentPercent']
    new_val = max(0, current - amount)
    enemy['life']['currentPercent'] = new_val

    if new_val <= 0:
        enemy['life']['state'] = 'dead'
        enemy['defeatSummary'] = f"Derrotado com {amount} de dano."

    file_storage.save_enemy(adventure_code, enemy)
    return enemy


def get_combat_result(adventure_code, character_code, attribute, difficulty):
    char = file_storage.get_adventure_character(adventure_code, character_code)
    if not char:
        return None

    result = resolve_roll(char, attribute, difficulty)
    return result


def distribute_loot(adventure_code, enemy_code, character_code):
    enemy = file_storage.get_enemy(adventure_code, enemy_code)
    if not enemy:
        return []

    char = file_storage.get_adventure_character(adventure_code, character_code)
    if not char:
        return []

    loot_results = []

    enemy_coins = enemy.get('coins', {}).get('amount', 0)
    if enemy_coins > 0:
        character_service.update_character_coins(adventure_code, character_code, enemy_coins)
        enemy['coins']['amount'] = 0
        loot_results.append(f"+{enemy_coins} moedas")

    for item in enemy.get('inventory', []):
        if item is not None:
            success = character_service.add_item_to_inventory(adventure_code, character_code, item)
            if success:
                loot_results.append(f"+{item.get('name', 'item')}")
            else:
                scene_id = char.get('currentSceneId')
                if scene_id:
                    scene = file_storage.get_scene(adventure_code, scene_id)
                    if scene:
                        scene.setdefault('availableItems', []).append(item)
                        file_storage.save_scene(adventure_code, scene)

    file_storage.save_enemy(adventure_code, enemy)
    return loot_results
