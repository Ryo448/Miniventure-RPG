import os
import json
import uuid
import tempfile
from datetime import datetime


_file_cache = {}
_file_cache_lock = __import__('threading').Lock()


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def read_json(filepath):
    if not os.path.exists(filepath):
        with _file_cache_lock:
            _file_cache.pop(filepath, None)
        return None
    try:
        mtime = os.path.getmtime(filepath)
        with _file_cache_lock:
            cached = _file_cache.get(filepath)
        if cached and cached[0] == mtime:
            return cached[1]
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        with _file_cache_lock:
            _file_cache[filepath] = (mtime, data)
        return data
    except (json.JSONDecodeError, IOError):
        return None


def write_json(filepath, data):
    ensure_dir(os.path.dirname(filepath))
    tmp_fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(filepath), suffix='.tmp')
    try:
        with os.fdopen(tmp_fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, filepath)
        mtime = os.path.getmtime(filepath)
        with _file_cache_lock:
            _file_cache[filepath] = (mtime, data)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def generate_adventure_code():
    code = uuid.uuid4().hex[:6].upper()
    return code


def resolve_adventure_path(adventure_code):
    from config import ADVENTURES_DIR
    return os.path.join(ADVENTURES_DIR, f'aventura #{adventure_code}')


def resolve_character_path(character_code):
    from config import LOCAL_CHARACTERS_DIR
    return os.path.join(LOCAL_CHARACTERS_DIR, f'{character_code}.json')


def delete_adventure(adventure_code):
    import shutil
    path = resolve_adventure_path(adventure_code)
    if os.path.exists(path):
        shutil.rmtree(path)
        return True
    return False


def delete_local_character(character_code):
    path = resolve_character_path(character_code)
    if os.path.exists(path):
        os.remove(path)
        return True
    return False


def list_adventures():
    from config import ADVENTURES_DIR
    ensure_dir(ADVENTURES_DIR)
    adventures = []
    if not os.path.exists(ADVENTURES_DIR):
        return adventures
    for entry in os.listdir(ADVENTURES_DIR):
        full_path = os.path.join(ADVENTURES_DIR, entry)
        if os.path.isdir(full_path) and entry.startswith('aventura #'):
            adventure_data = read_json(os.path.join(full_path, 'adventure.json'))
            if adventure_data:
                adventures.append(adventure_data)
    return adventures


def create_adventure_folder(adventure_code):
    base = resolve_adventure_path(adventure_code)
    ensure_dir(base)
    ensure_dir(os.path.join(base, 'characters'))
    ensure_dir(os.path.join(base, 'enemies'))
    ensure_dir(os.path.join(base, 'scenes'))
    ensure_dir(os.path.join(base, 'logs'))
    return base


def create_adventure_json(adventure_code, total_participants, bot_count):
    data = {
        'code': adventure_code,
        'totalParticipants': total_participants,
        'botCount': bot_count,
        'hostCharacterCode': None,
        'status': 'setup',
        'createdAt': datetime.now().isoformat(),
        'currentSceneId': None,
        'connectedCharacters': [],
        'aiPreparation': {
            'timeline': 'pending',
            'bots': 'pending',
            'initialScene': 'pending'
        }
    }
    base = resolve_adventure_path(adventure_code)
    write_json(os.path.join(base, 'adventure.json'), data)
    return data


def create_global_info():
    return {
        'completedActions': [],
        'registeredCrimes': [],
        'enemies': [],
        'groupHonor': 0,
        'worldStateSummary': ''
    }


def create_empty_timeline():
    return {
        'worldBackground': '',
        'kingdoms': [],
        'cities': [],
        'villages': [],
        'factions': [],
        'guilds': [],
        'religiousGroups': [],
        'politicalTensions': [],
        'allies': [],
        'rivals': [],
        'possibleVillains': [],
        'possibleStoryArcs': [],
        'importantHistoricalEvents': [],
        'routes': [],
        'hiddenSecrets': [],
        'majorNPCs': [],
        'possibleConflicts': [],
        'economy': {},
        'coinUsage': {},
        'shops': {},
        'tradeCustoms': {},
        'legalSystems': {},
        'crimeConsequences': {},
        'rewardSystems': {}
    }


def create_initial_files(adventure_code, total_participants, bot_count):
    base = create_adventure_folder(adventure_code)
    adventure_data = create_adventure_json(adventure_code, total_participants, bot_count)
    write_json(os.path.join(base, 'global_info.json'), create_global_info())
    write_json(os.path.join(base, 'timeline.json'), create_empty_timeline())
    return adventure_data


def append_log(adventure_code, log_type, message):
    base = resolve_adventure_path(adventure_code)
    log_dir = os.path.join(base, 'logs')
    ensure_dir(log_dir)
    filename = 'ai_calls.log' if log_type == 'ai' else 'game_events.log'
    filepath = os.path.join(log_dir, filename)
    timestamp = datetime.now().isoformat()
    line = f'[{timestamp}] {message}\n'
    with open(filepath, 'a', encoding='utf-8') as f:
        f.write(line)


def list_local_characters():
    from config import LOCAL_CHARACTERS_DIR
    ensure_dir(LOCAL_CHARACTERS_DIR)
    characters = []
    if not os.path.exists(LOCAL_CHARACTERS_DIR):
        return characters
    for entry in os.listdir(LOCAL_CHARACTERS_DIR):
        if entry.endswith('.json'):
            data = read_json(os.path.join(LOCAL_CHARACTERS_DIR, entry))
            if data:
                characters.append(data)
    return characters


def get_adventure_characters(adventure_code):
    base = resolve_adventure_path(adventure_code)
    chars_dir = os.path.join(base, 'characters')
    characters = []
    if not os.path.exists(chars_dir):
        return characters
    for entry in os.listdir(chars_dir):
        if entry.endswith('.json'):
            data = read_json(os.path.join(chars_dir, entry))
            if data:
                characters.append(data)
    return characters


def get_adventure_character(adventure_code, character_code):
    base = resolve_adventure_path(adventure_code)
    filepath = os.path.join(base, 'characters', f'{character_code}.json')
    return read_json(filepath)


def get_local_character(character_code):
    filepath = resolve_character_path(character_code)
    return read_json(filepath)


def save_local_character(character_data):
    filepath = resolve_character_path(character_data['code'])
    write_json(filepath, character_data)


def save_adventure_character(adventure_code, character_data):
    base = resolve_adventure_path(adventure_code)
    filepath = os.path.join(base, 'characters', f"{character_data['code']}.json")
    write_json(filepath, character_data)


def get_scene(adventure_code, scene_id):
    base = resolve_adventure_path(adventure_code)
    filepath = os.path.join(base, 'scenes', f'{scene_id}.json')
    return read_json(filepath)


def save_scene(adventure_code, scene_data):
    base = resolve_adventure_path(adventure_code)
    scenes_dir = os.path.join(base, 'scenes')
    ensure_dir(scenes_dir)
    filepath = os.path.join(scenes_dir, f"{scene_data['sceneId']}.json")
    write_json(filepath, scene_data)


def get_enemy(adventure_code, enemy_code):
    base = resolve_adventure_path(adventure_code)
    filepath = os.path.join(base, 'enemies', f'{enemy_code}.json')
    return read_json(filepath)


def save_enemy(adventure_code, enemy_data):
    base = resolve_adventure_path(adventure_code)
    enemies_dir = os.path.join(base, 'enemies')
    ensure_dir(enemies_dir)
    filepath = os.path.join(enemies_dir, f"{enemy_data['code']}.json")
    write_json(filepath, enemy_data)


def delete_enemy(adventure_code, enemy_code):
    base = resolve_adventure_path(adventure_code)
    filepath = os.path.join(base, 'enemies', f'{enemy_code}.json')
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
        except OSError:
            pass


def get_global_info(adventure_code):
    base = resolve_adventure_path(adventure_code)
    return read_json(os.path.join(base, 'global_info.json'))


def save_global_info(adventure_code, data):
    base = resolve_adventure_path(adventure_code)
    write_json(os.path.join(base, 'global_info.json'), data)


def get_timeline(adventure_code):
    base = resolve_adventure_path(adventure_code)
    return read_json(os.path.join(base, 'timeline.json'))


def save_timeline(adventure_code, data):
    base = resolve_adventure_path(adventure_code)
    write_json(os.path.join(base, 'timeline.json'), data)


def get_adventure(adventure_code):
    base = resolve_adventure_path(adventure_code)
    return read_json(os.path.join(base, 'adventure.json'))


def save_adventure(adventure_code, data):
    base = resolve_adventure_path(adventure_code)
    write_json(os.path.join(base, 'adventure.json'), data)


import threading
_ai_prep_locks = {}
_ai_prep_locks_guard = threading.Lock()


def _get_ai_prep_lock(adventure_code):
    with _ai_prep_locks_guard:
        lock = _ai_prep_locks.get(adventure_code)
        if lock is None:
            lock = threading.Lock()
            _ai_prep_locks[adventure_code] = lock
        return lock


def update_ai_preparation_stage(adventure_code, stage, status):
    lock = _get_ai_prep_lock(adventure_code)
    with lock:
        base = resolve_adventure_path(adventure_code)
        filepath = os.path.join(base, 'adventure.json')
        adventure = read_json(filepath)
        if adventure is None:
            return None
        ai_prep = adventure.setdefault('aiPreparation', {})
        ai_prep[stage] = status
        write_json(filepath, adventure)
        return adventure
