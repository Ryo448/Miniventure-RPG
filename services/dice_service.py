import random


def roll_d24():
    return random.randint(1, 24)


def get_result_intensity(total, difficulty):
    diff = total - difficulty
    if diff < -6:
        return 'desastre'
    elif diff < 0:
        return 'falha'
    elif diff <= 1:
        return 'parcial'
    elif diff <= 5:
        return 'sucesso'
    else:
        return 'excelente'


def resolve_roll(character_data, attribute_name, difficulty):
    roll = roll_d24()
    attr_value = character_data.get('attributes', {}).get(attribute_name, 0)
    total = roll + attr_value
    success = total >= difficulty
    intensity = get_result_intensity(total, difficulty)
    return {
        'die': 'D24',
        'roll': roll,
        'attribute': attribute_name,
        'attributeValue': attr_value,
        'total': total,
        'difficulty': difficulty,
        'success': success,
        'intensity': intensity
    }
