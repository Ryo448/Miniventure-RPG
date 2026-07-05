from services import file_storage
from services import character_service


def get_coins(adventure_code, character_code):
    char = file_storage.get_adventure_character(adventure_code, character_code)
    if not char:
        return None
    return char.get('coins', {'amount': 0, 'displayName': 'Moedas'})


def add_coins(adventure_code, character_code, amount):
    return character_service.update_character_coins(adventure_code, character_code, amount)


def remove_coins(adventure_code, character_code, amount):
    char = file_storage.get_adventure_character(adventure_code, character_code)
    if not char:
        return None, 'Personagem não encontrado.'

    current = char.get('coins', {}).get('amount', 0)
    if amount > current:
        return None, f'Moedas insuficientes ({current}/{amount}).'

    result = character_service.update_character_coins(adventure_code, character_code, -amount)
    return result, None


def transfer_coins(adventure_code, from_code, to_code, amount):
    success = character_service.transfer_coins(adventure_code, from_code, to_code, amount)
    return success


def validate_transaction(adventure_code, from_code, amount):
    char = file_storage.get_adventure_character(adventure_code, from_code)
    if not char:
        return False, 'Personagem não encontrado.'

    current = char.get('coins', {}).get('amount', 0)
    if amount > current:
        return False, f'Moedas insuficientes ({current}/{amount}).'

    return True, None
