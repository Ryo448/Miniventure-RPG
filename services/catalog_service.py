import json
import os
from services import file_storage
from config import DATA_DIR


_catalogs_cache = {}


def _load_catalog(filename):
    if filename in _catalogs_cache:
        return _catalogs_cache[filename]
    filepath = os.path.join(DATA_DIR, filename)
    data = file_storage.read_json(filepath)
    if data is not None:
        _catalogs_cache[filename] = data
    return data if data else []


def get_weapons():
    return _load_catalog('weapons_catalog.json')


def get_abilities():
    return _load_catalog('abilities_catalog.json')


def get_races():
    return _load_catalog('races_catalog.json')


def get_weapon_by_id(weapon_id):
    for w in get_weapons():
        if w.get('id') == weapon_id:
            return w
    return None


def get_ability_by_id(ability_id):
    for a in get_abilities():
        if a.get('id') == ability_id:
            return a
    return None


def get_race_by_id(race_id):
    for r in get_races():
        if r.get('id') == race_id:
            return r
    return None


def get_weapons_by_class(class_name):
    return [w for w in get_weapons() if w.get('classeRecomendada') == class_name]


def get_abilities_by_class(class_name):
    return [a for a in get_abilities() if a.get('classeRecomendada') == class_name]


def clear_cache():
    global _catalogs_cache
    _catalogs_cache = {}
