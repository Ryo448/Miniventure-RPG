import json
import uuid
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from services import ai_client
from services import file_storage
from services import scene_service
from services import character_service
from services import validation_service
from config import Config


_SCENE_SIZE_INSTRUCTIONS = {
    'small': 'A descrição principal (mainDescription) deve ter EXATAMENTE 1 parágrafo curto e direto. Máximo de 60 palavras no total.',
    'medium': 'A descrição principal (mainDescription) deve ter entre 2 e 3 parágrafos. Cada parágrafo deve ter no máximo 80 palavras.',
    'large': 'A descrição principal (mainDescription) deve ter entre 3 e 4 parágrafos. Cada parágrafo deve ter no máximo 80 palavras.',
    'unlimited': '',
}


def _scene_size_instruction():
    size = getattr(Config, 'SCENE_SIZE', 'unlimited')
    return _SCENE_SIZE_INSTRUCTIONS.get(size, '')


_ai_tasks = {}
_ai_tasks_lock = threading.Lock()
_task_ttl = timedelta(minutes=5)
_executor = ThreadPoolExecutor(max_workers=8)


def _prune_old_tasks():
    now = datetime.now()
    with _ai_tasks_lock:
        stale = [tid for tid, t in _ai_tasks.items()
                 if t.get('status') in ('completed', 'failed')
                 and datetime.fromisoformat(t.get('updatedAt', t.get('createdAt', now.isoformat()))) < now - _task_ttl]
        for tid in stale:
            del _ai_tasks[tid]


def _create_task(task_type, adventure_code):
    _prune_old_tasks()
    task_id = uuid.uuid4().hex[:12]
    task = {
        'taskId': task_id,
        'type': task_type,
        'status': 'pending',
        'adventureCode': adventure_code,
        'createdAt': datetime.now().isoformat(),
        'updatedAt': datetime.now().isoformat(),
        'result': None,
        'error': None
    }
    with _ai_tasks_lock:
        _ai_tasks[task_id] = task
    return task_id, task


def _update_task(task_id, status, result=None, error=None):
    adventure_code = None
    with _ai_tasks_lock:
        if task_id in _ai_tasks:
            _ai_tasks[task_id]['status'] = status
            _ai_tasks[task_id]['updatedAt'] = datetime.now().isoformat()
            if result is not None:
                _ai_tasks[task_id]['result'] = result
            if error is not None:
                _ai_tasks[task_id]['error'] = error
            adventure_code = _ai_tasks[task_id].get('adventureCode')

    if adventure_code and status in ('completed', 'failed'):
        try:
            from services.socket_service import emit_to_adventure
            emit_to_adventure(adventure_code, 'task_result', {
                'taskId': task_id,
                'status': status,
                'result': result,
                'error': error
            })
        except Exception:
            pass


def get_task(task_id):
    with _ai_tasks_lock:
        return _ai_tasks.get(task_id)


def get_tasks_by_adventure(adventure_code):
    with _ai_tasks_lock:
        return [t for t in _ai_tasks.values() if t.get('adventureCode') == adventure_code]


def submit_chat(adventure_code, messages):
    task_id, task = _create_task('CHAT', adventure_code)
    _executor.submit(_chat_worker, task_id, adventure_code, messages)
    return task_id


def _chat_worker(task_id, adventure_code, messages):
    _update_task(task_id, 'running')
    try:
        content, error = ai_client.call_ai(messages, adventure_code)
        if error:
            _update_task(task_id, 'failed', error=error)
            return
        parsed = ai_client.parse_ai_json(content)
        if not parsed:
            _update_task(task_id, 'failed', error='Resposta da IA inválida.')
            return
        _update_task(task_id, 'completed', result=parsed)
    except Exception as e:
        _update_task(task_id, 'failed', error=str(e))


_scene_kickoff_lock = threading.Lock()


def _maybe_kick_initial_scene(adventure_code):
    try:
        with _scene_kickoff_lock:
            adventure = file_storage.get_adventure(adventure_code)
            if not adventure:
                return
            ai_prep = adventure.get('aiPreparation', {})
            if (ai_prep.get('timeline') == 'completed'
                    and ai_prep.get('bots') == 'completed'
                    and ai_prep.get('initialScene') == 'pending'):
                file_storage.update_ai_preparation_stage(adventure_code, 'initialScene', 'running')
                generate_initial_scene_async(adventure_code)
    except Exception as e:
        print(f'[orchestrator] _maybe_kick_initial_scene error: {e}', flush=True)


def generate_timeline_async(adventure_code):
    task_id, task = _create_task('GENERATE_TIMELINE', adventure_code)
    _executor.submit(_generate_timeline_worker, task_id, adventure_code)
    return task_id


_TIMELINE_SECTIONS = [
    {
        'key': 'territory',
        'fields': ['kingdoms', 'cities', 'villages', 'naturalFeatures'],
        'prompt': (
            'Gere a parte TERRITÓRIO de um mundo de fantasia para RPG:\n'
            '- 3 reinos com nome, descrição, governo, goals\n'
            '- 6+ cidades com arquitetura, economia, população, landmarks, atmosphere\n'
            '- 4+ vilas\n'
            '- 3+ acidentes naturais (montanhas, rios, florestas) com descrição e ponto narrativo\n'
            'Responda APENAS com JSON válido contendo essas chaves: kingdoms, cities, villages, naturalFeatures'
        )
    },
    {
        'key': 'power',
        'fields': ['factions', 'religions', 'villains'],
        'prompt': (
            'Gere a parte PODER E CONFLITO de um mundo de fantasia para RPG:\n'
            '- 3+ facções/guildas (mercadores, ladrões, ordem religiosa, mercenários, academia de magos) com goals, territory, leadership, relationships\n'
            '- 2+ religiões/sistemas de crença com deidades, rituais, relação com poder político\n'
            '- 2+ arcos de vilão com antagonistas e motivações compreensíveis (vingança, dominação, salvação por meios sombrios) com backstory, atividades atuais, trajetória\n'
            'Responda APENAS com JSON válido contendo essas chaves: factions, religions, villains'
        )
    },
    {
        'key': 'systems',
        'fields': ['economy', 'legalSystems', 'secrets', 'magicSystem'],
        'prompt': (
            'Gere a parte SISTEMAS de um mundo de fantasia para RPG:\n'
            '- economia por reino: produção, importações, moeda, rotas comerciais, bens raros\n'
            '- sistemas legais e consequências de crime para 2+ reinos (um draconiano, um restaurativo/corrupto)\n'
            '- 3+ segredos/mistérios ocultos (civilização perdida, linhagem amaldiçoada, magia proibida, anomalia mágica)\n'
            '- sistema de magia: como é percebido e regulado, comum/raro, reverenciado/temido\n'
            'Responda APENAS com JSON válido contendo essas chaves: economy, legalSystems, secrets, magicSystem'
        )
    },
    {
        'key': 'narrative',
        'fields': ['majorNPCs', 'storyArcs', 'currentEvents'],
        'prompt': (
            'Gere a parte NARRATIVA de um mundo de fantasia para RPG:\n'
            '- 4+ NPCs principais: nome em português, papel, personalidade, motivações secretas, conexões. Pelo menos um aliado e um oponente\n'
            '- 3+ arcos de história não-lineares com título em português, resumo, NPCs chave, clímax, consequências de sucesso/falha\n'
            '- 2+ eventos mundiais atuais acontecendo independentemente dos jogadores (fome, crise de sucessão, migração de monstros)\n'
            'Responda APENAS com JSON válido contendo essas chaves: majorNPCs, storyArcs, currentEvents'
        )
    },
    {
        'key': 'worldlore',
        'fields': ['historicalTimeline', 'culturalDetails', 'environmentalHazards', 'raceRelations'],
        'prompt': (
            'Gere a parte LORE E MUNDO de um mundo de fantasia para RPG:\n'
            '- 5+ eventos históricos que moldaram o mundo (guerras antigas, tratados quebrados, intervenções divinas, reinos caídos)\n'
            '- 2+ detalhes culturais de regiões: festivais, tradições, tabus, culinária, vestimentas\n'
            '- 2+ perigos ambientais (região vulcânica, pântano amaldiçoado, mar de krakens, floresta deslocante)\n'
            '- relações entre raças/espécies: discriminação, alianças, inimizades antigas, coexistência\n'
            'Responda APENAS com JSON válido contendo essas chaves: historicalTimeline, culturalDetails, environmentalHazards, raceRelations'
        )
    }
]


def _generate_timeline_section(adventure_code, section):
    try:
        messages = [
            {'role': 'system', 'content': 'Você é um construtor de mundos de RPG. Responda APENAS com um JSON válido, sem markdown, sem codeblocks, sem texto antes ou depois. Todo conteúdo textual em português brasileiro.'},
            {'role': 'user', 'content': section['prompt']}
        ]
        content, error = ai_client.call_ai(messages, adventure_code, max_tokens=2000, temperature=0.8)
        if error:
            print(f'[timeline/{section["key"]}] Erro: {error}', flush=True)
            return section['key'], None

        parsed = ai_client.parse_ai_json(content)
        if not parsed:
            print(f'[timeline/{section["key"]}] JSON inválido. {len(content) if content else 0} chars.', flush=True)
            return section['key'], None

        result = {}
        for field in section['fields']:
            if field in parsed:
                result[field] = parsed[field]
        if not result:
            print(f'[timeline/{section["key"]}] Nenhum campo esperado encontrado.', flush=True)
            return section['key'], None

        print(f'[timeline/{section["key"]}] OK ({len(content) if content else 0} chars).', flush=True)
        return section['key'], result
    except Exception as e:
        print(f'[timeline/{section["key"]}] Exception: {e}', flush=True)
        return section['key'], None


def _generate_timeline_worker(task_id, adventure_code):
    _update_task(task_id, 'running')
    try:
        file_storage.update_ai_preparation_stage(adventure_code, 'timeline', 'running')

        print(f'[timeline] Iniciando geração paralela de {len(_TIMELINE_SECTIONS)} seções...', flush=True)

        results = {}
        results_lock = threading.Lock()

        def _worker(section):
            key, data = _generate_timeline_section(adventure_code, section)
            with results_lock:
                results[key] = data

        futures = [_executor.submit(_worker, section) for section in _TIMELINE_SECTIONS]
        for f in futures:
            f.result()

        timeline_data = {}
        failed_sections = []
        for section in _TIMELINE_SECTIONS:
            data = results.get(section['key'])
            if data:
                timeline_data.update(data)
            else:
                failed_sections.append(section['key'])

        if not timeline_data:
            msg = 'Falha ao gerar timeline: nenhuma seção produzida.'
            print(f'[timeline] {msg}', flush=True)
            _update_task(task_id, 'failed', error=msg)
            file_storage.update_ai_preparation_stage(adventure_code, 'timeline', 'failed')
            return

        if failed_sections:
            print(f'[timeline] Seções falharam: {failed_sections}. Continuando com as que foram geradas.', flush=True)

        file_storage.save_timeline(adventure_code, timeline_data)
        _update_task(task_id, 'completed', result=f'Timeline gerada ({len(timeline_data)} campos).')
        file_storage.update_ai_preparation_stage(adventure_code, 'timeline', 'completed')
        _maybe_kick_initial_scene(adventure_code)

    except Exception as e:
        print(f'[timeline] Exception: {e}', flush=True)
        _update_task(task_id, 'failed', error=str(e))
        file_storage.append_log(adventure_code, 'ai', f'Timeline worker exception: {e}')
        file_storage.update_ai_preparation_stage(adventure_code, 'timeline', 'failed')


def generate_bot_async(adventure_code, num_bots):
    task_id, task = _create_task('GENERATE_BOTS', adventure_code)
    _executor.submit(_generate_bot_worker, task_id, adventure_code, num_bots)
    return task_id


def _wait_for_timeline(adventure_code, timeout=120):
    import time
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        adventure = file_storage.get_adventure(adventure_code)
        if not adventure:
            return None
        stage = adventure.get('aiPreparation', {}).get('timeline')
        if stage == 'completed':
            return file_storage.get_timeline(adventure_code)
        if stage == 'failed':
            return None
        time.sleep(1)
    return None


_bot_save_lock = threading.Lock()


_BOT_ATTR_EN_TO_PT = {
    'strength': 'forca', 'dexterity': 'destreza', 'constitution': 'constituicao',
    'intelligence': 'inteligencia', 'wisdom': 'sabedoria', 'charisma': 'carisma',
    'magic': 'magia', 'perception': 'furtividade', 'luck': 'sorte'
}
_BOT_ATTR_PT_KEYS = ('forca', 'destreza', 'constituicao', 'inteligencia', 'sabedoria', 'carisma', 'magia', 'furtividade', 'sorte')
_BOT_ATTR_TOTAL = 15
_BOT_ATTR_MAX = 5


def _normalize_bot_attributes(raw):
    attrs = {}
    if not isinstance(raw, dict):
        raw = {}
    for k in _BOT_ATTR_PT_KEYS:
        pt_key = k
        v = raw.get(pt_key, raw.get(next((en for en, pt in _BOT_ATTR_EN_TO_PT.items() if pt == k), None), 0))
        try:
            v = int(v)
        except (TypeError, ValueError):
            v = 0
        attrs[k] = max(0, min(_BOT_ATTR_MAX, v))

    total = sum(attrs.values())
    if total == _BOT_ATTR_TOTAL:
        return attrs

    if total > _BOT_ATTR_TOTAL:
        while sum(attrs.values()) > _BOT_ATTR_TOTAL:
            candidates = [k for k in _BOT_ATTR_PT_KEYS if attrs[k] > 0]
            if not candidates:
                break
            attr = max(candidates, key=lambda k: attrs[k])
            attrs[attr] -= 1
    else:
        while sum(attrs.values()) < _BOT_ATTR_TOTAL:
            candidates = [k for k in _BOT_ATTR_PT_KEYS if attrs[k] < _BOT_ATTR_MAX]
            if not candidates:
                break
            attr = min(candidates, key=lambda k: attrs[k])
            attrs[attr] += 1
    return attrs


def _generate_bot_attributes(bot_data, adventure_code):
    name = bot_data.get('name', '')
    race = bot_data.get('race', '')
    story = bot_data.get('story', '')
    weapon = ''
    inventory = bot_data.get('inventory', [])
    if inventory and isinstance(inventory[0], dict):
        weapon = inventory[0].get('name', '')
    abilities = bot_data.get('specialAbilities', [])
    ability = abilities[0].get('name', '') if abilities else ''

    parts = ['Distribua EXATAMENTE 15 pontos entre os 9 atributos de um RPG de fantasia. Cada atributo entre 0 e 5.']
    if name: parts.append(f'Nome: {name}')
    if race: parts.append(f'Raça: {race}')
    if story: parts.append(f'História: {story[:500]}')
    if weapon: parts.append(f'Arma inicial: {weapon}')
    if ability: parts.append(f'Habilidade especial: {ability}')
    parts.append('Use as chaves em PORTUGUÊS: forca, destreza, constituicao, inteligencia, sabedoria, carisma, magia, furtividade, sorte')
    parts.append('A distribuição deve refletir a classe e personalidade do personagem.')
    parts.append('REGRA OBRIGATÓRIA: a soma dos 9 atributos deve ser EXATAMENTE 15.')
    parts.append('Responda APENAS um JSON válido: {"attributes": {"forca": 0, "destreza": 0, "constituicao": 0, "inteligencia": 0, "sabedoria": 0, "carisma": 0, "magia": 0, "furtividade": 0, "sorte": 0}}')

    messages = [
        {'role': 'system', 'content': 'Você é um mestre de RPG. Responda APENAS com JSON válido, sem markdown, sem codeblocks.'},
        {'role': 'user', 'content': '\n'.join(parts)}
    ]

    content, error = ai_client.call_ai(messages, adventure_code, max_tokens=400, temperature=0.7)
    if error or not content:
        return {k: 1 for k in _BOT_ATTR_PT_KEYS}

    parsed = ai_client.parse_ai_json(content)
    if not parsed or 'attributes' not in parsed:
        return {k: 1 for k in _BOT_ATTR_PT_KEYS}

    return _normalize_bot_attributes(parsed['attributes'])


def _generate_single_bot(adventure_code, bot_index, num_bots, prompt, timeline_ctx):
    messages = [
        {'role': 'system', 'content': prompt},
        {'role': 'user', 'content': f'Crie o bot {bot_index+1} de {num_bots}. Contexto do mundo: {timeline_ctx}. Responda em JSON completo do personagem.'}
    ]

    content, error = ai_client.call_ai(messages, adventure_code, max_tokens=4000)
    if error:
        return None

    bot_data = ai_client.parse_ai_json(content)
    if not bot_data:
        return None

    bot_data['isBot'] = True
    _life = bot_data.get('life', {'currentPercent': 100, 'maxPercent': 100, 'state': 'alive'})
    if not isinstance(_life, dict):
        _life = {'currentPercent': 100, 'maxPercent': 100, 'state': 'alive'}
    bot_data['life'] = _life
    _coins = bot_data.get('coins', {'amount': 30, 'displayName': 'Moedas'})
    if not isinstance(_coins, dict):
        _coins = {'amount': 30, 'displayName': 'Moedas'}
    bot_data['coins'] = _coins
    bot_data['armor'] = bot_data.get('armor', {
        'head': None, 'torso': None, 'hands': None, 'legs': None, 'feet': None
    })
    bot_data['inventory'] = bot_data.get('inventory', [None] * 8)
    if len(bot_data.get('inventory', [])) < 8:
        bot_data['inventory'] = bot_data['inventory'] + [None] * (8 - len(bot_data.get('inventory', [])))
    bot_data['specialAbilities'] = bot_data.get('specialAbilities', [])
    bot_data['temporaryEffects'] = bot_data.get('temporaryEffects', [])
    bot_data['legalStatus'] = bot_data.get('legalStatus', [])
    bot_data['personalLog'] = bot_data.get('personalLog', [])
    bot_data['currentSceneId'] = None

    _attrs = bot_data.get('attributes')
    if not isinstance(_attrs, dict) or not _attrs:
        _attrs = _generate_bot_attributes(bot_data, adventure_code)
    else:
        _attrs = _normalize_bot_attributes(_attrs)
    bot_data['attributes'] = _attrs

    if not bot_data.get('code'):
        bot_data['code'] = uuid.uuid4().hex[:8].upper()

    with _bot_save_lock:
        file_storage.save_adventure_character(adventure_code, bot_data)
        adventure = file_storage.get_adventure(adventure_code)
        if adventure and bot_data['code'] not in adventure.get('connectedCharacters', []):
            adventure.setdefault('connectedCharacters', []).append(bot_data['code'])
            file_storage.save_adventure(adventure_code, adventure)

    return bot_data


def _generate_bot_worker(task_id, adventure_code, num_bots):
    _update_task(task_id, 'running')
    try:
        file_storage.update_ai_preparation_stage(adventure_code, 'bots', 'running')

        prompt = ai_client.load_prompt('bot_character_prompt.txt')

        timeline = _wait_for_timeline(adventure_code)
        timeline_ctx = json.dumps(timeline, ensure_ascii=False)[:1000] if timeline else ''

        bot_futures = [_executor.submit(_generate_single_bot, adventure_code, i, num_bots, prompt, timeline_ctx)
                       for i in range(num_bots)]
        for f in bot_futures:
            f.result()

        file_storage.update_ai_preparation_stage(adventure_code, 'bots', 'completed')
        _update_task(task_id, 'completed', result=f'{num_bots} bots gerados.')
        _maybe_kick_initial_scene(adventure_code)

    except Exception as e:
        print(f'[bots] Exception: {e}', flush=True)
        _update_task(task_id, 'failed', error=str(e))
        file_storage.append_log(adventure_code, 'ai', f'Bot worker exception: {e}')
        file_storage.update_ai_preparation_stage(adventure_code, 'bots', 'failed')


def generate_initial_scene_async(adventure_code):
    task_id, task = _create_task('GENERATE_INITIAL_SCENE', adventure_code)
    _executor.submit(_generate_initial_scene_worker, task_id, adventure_code)
    return task_id


def _generate_initial_scene_worker(task_id, adventure_code):
    _update_task(task_id, 'running')
    try:
        file_storage.update_ai_preparation_stage(adventure_code, 'initialScene', 'running')

        prompt = ai_client.load_prompt('scene_prompt.txt')
        timeline = file_storage.get_timeline(adventure_code)
        characters = file_storage.get_adventure_characters(adventure_code)

        timeline_ctx = json.dumps(timeline, ensure_ascii=False)[:1500] if timeline else ''
        chars_summary = []
        for c in characters:
            chars_summary.append({
                'code': c['code'],
                'name': c.get('name', ''),
                'race': c.get('race', ''),
                'isBot': c.get('isBot', False),
                'weapon': c.get('inventory', [None])[0]
            })

        size_instr = _scene_size_instruction()
        user_content = f'Gere a cena inicial para esta aventura.\n\nContexto do mundo:\n{timeline_ctx}\n\nPersonagens no grupo:\n{json.dumps(chars_summary, ensure_ascii=False)}\n\nResponda em JSON no formato da cena.'
        if size_instr:
            user_content += f'\n\n{size_instr}'

        messages = [
            {'role': 'system', 'content': prompt},
            {'role': 'user', 'content': user_content}
        ]

        content, error = ai_client.call_ai(messages, adventure_code, max_tokens=4000)
        if error:
            _update_task(task_id, 'failed', error=error)
            file_storage.update_ai_preparation_stage(adventure_code, 'initialScene', 'failed')
            return

        scene_data = ai_client.parse_ai_json(content)
        if scene_data:
            scene_data['sceneId'] = 'scene_0001'
            if not scene_data.get('turnOrder'):
                active_chars = [c['code'] for c in characters if isinstance(c.get('life', {}), dict) and c.get('life', {}).get('state') in ('alive', 'unconscious')]
                scene_data['turnOrder'] = active_chars
                if active_chars:
                    scene_data['currentTurnCharacterCode'] = active_chars[0]

            scene_data.setdefault('previousScenePath', None)
            scene_data.setdefault('linkedScenes', [])
            scene_data.setdefault('sceneLog', [])
            scene_data.setdefault('availableEnemies', [])

            if not scene_data.get('currentContext'):
                scene_data['currentContext'] = scene_data.get('mainDescription', '')

            file_storage.save_scene(adventure_code, scene_data)
            scene_service.set_current_scene(adventure_code, 'scene_0001')

            for c in characters:
                c['currentSceneId'] = 'scene_0001'
                file_storage.save_adventure_character(adventure_code, c)

            adventure = file_storage.get_adventure(adventure_code)
            if adventure:
                adventure['status'] = 'active'
                adventure['currentSceneId'] = 'scene_0001'
                file_storage.save_adventure(adventure_code, adventure)

            file_storage.update_ai_preparation_stage(adventure_code, 'initialScene', 'completed')
            _update_task(task_id, 'completed', result='Cena inicial gerada.')
        else:
            _update_task(task_id, 'failed', error='Falha ao analisar JSON da cena.')
            file_storage.update_ai_preparation_stage(adventure_code, 'initialScene', 'failed')

    except Exception as e:
        print(f'[initialScene] Exception: {e}', flush=True)
        _update_task(task_id, 'failed', error=str(e))
        file_storage.append_log(adventure_code, 'ai', f'Scene worker exception: {e}')
        file_storage.update_ai_preparation_stage(adventure_code, 'initialScene', 'failed')


def resolve_player_action(adventure_code, character_code, action):
    task_id, task = _create_task('RESOLVE_ACTION', adventure_code)
    _executor.submit(_resolve_action_worker, task_id, adventure_code, character_code, action)
    return task_id


def resolve_bot_action(adventure_code, bot_code):
    task_id, task = _create_task('BOT_ACTION', adventure_code)
    _executor.submit(_resolve_bot_action_worker, task_id, adventure_code, bot_code)
    return task_id


def _resolve_bot_action_worker(task_id, adventure_code, bot_code):
    _update_task(task_id, 'running')
    try:
        bot = file_storage.get_adventure_character(adventure_code, bot_code)
        if not bot or not bot.get('isBot'):
            _update_task(task_id, 'failed', error='Personagem não é um bot.')
            return

        scene = scene_service.get_current_scene(adventure_code)
        if not scene:
            _update_task(task_id, 'failed', error='Nenhuma cena ativa.')
            return

        action_text, gen_error = _generate_bot_action_text(bot, scene, adventure_code)
        if gen_error or not action_text:
            action_text = f'{bot.get("name", "Bot")} age de acordo com sua personalidade.'

        result = _process_ai_action(adventure_code, bot_code, action_text, task_id)
        if result.get('ambiguous'):
            _update_task(task_id, 'failed', error=result.get('narration', 'Bot gerou resposta sem uma ação clara.'), result={**result, 'retryable': True, 'botCode': bot_code, 'botName': bot.get('name', 'Bot')})
        else:
            _update_task(task_id, 'completed', result=result)
        _emit_state_update(adventure_code)
    except Exception as e:
        _update_task(task_id, 'failed', error=str(e))


def _generate_bot_action_text(bot, scene, adventure_code):
    name = bot.get('name', 'Bot')
    race = bot.get('race', '')
    story = bot.get('story', '')
    attrs = bot.get('attributes', {})
    abilities = bot.get('specialAbilities', [])
    inventory = bot.get('inventory', [])
    life = bot.get('life', {})

    parts = [
        f'Você é {name}, um personagem bot em um RPG de fantasia.',
        f'Raça: {race}',
        f'História: {story[:600]}' if story else '',
        f'Atributos: {json.dumps(attrs, ensure_ascii=False)}' if attrs else '',
        f'Habilidades: {", ".join(a.get("name", "") for a in abilities) if abilities else "nenhuma"}',
        f'Inventário: {", ".join((i.get("name", "") if isinstance(i, dict) else "") for i in inventory[:3]) if inventory else "vazio"}',
        f'Vida: {life.get("currentPercent", 100)}/{life.get("maxPercent", 100)} ({life.get("state", "alive")})' if isinstance(life, dict) else f'Vida: {life}',
    ]
    parts.append(f'Cena atual: {scene.get("title", "")} — {scene.get("currentContext", "")[:400]}')
    parts.append('Decida UMA ação objetiva e coerente com sua personalidade, atributos e situação. Considere inimigos, NPCs, itens disponíveis e o contexto da cena.')
    parts.append('Responda APENAS a descrição da ação em português, em UM parágrafo curto (máximo 40 palavras). Sem JSON, sem formatação, sem prefixos.')
    parts = [p for p in parts if p]

    messages = [
        {'role': 'system', 'content': 'Você é um jogador de RPG interpretando um personagem. Responda apenas com a ação em texto plano, sem JSON nem formatação.'},
        {'role': 'user', 'content': '\n'.join(parts)}
    ]

    content, error = ai_client.call_ai(messages, adventure_code, max_tokens=150, temperature=0.8)
    if error:
        return None, error
    return (content or '').strip(), None


def _resolve_action_worker(task_id, adventure_code, character_code, action):
    _update_task(task_id, 'running')
    try:
        result = _process_ai_action(adventure_code, character_code, action, task_id)
        if result.get('ambiguous'):
            char = file_storage.get_adventure_character(adventure_code, character_code)
            _update_task(task_id, 'failed', error=result.get('narration', 'Ação ambígua.'), result={**result, 'retryable': True, 'characterCode': character_code, 'characterName': char.get('name') if char else character_code})
        else:
            _update_task(task_id, 'completed', result=result)
        _emit_state_update(adventure_code)
    except Exception as e:
        _update_task(task_id, 'failed', error=str(e))


def _emit_state_update(adventure_code):
    try:
        from services.socket_service import emit_to_adventure
        from routes.game_routes import _build_scene_update_payload
        events = _build_scene_update_payload(adventure_code)
        if events:
            for event_name, event_data in events:
                emit_to_adventure(adventure_code, event_name, event_data)
    except Exception as e:
        print(f'[orchestrator] emit_state_update error: {e}', flush=True)


def _process_ai_action(adventure_code, character_code, action, task_id, depth=0, max_depth=5):
    if depth >= max_depth:
        return {'narration': 'A ação não pôde ser processada completamente.', 'commands': [], 'turnResult': {'endTurn': True, 'nextCharacterCode': None}, 'ambiguous': True}

    adventure = file_storage.get_adventure(adventure_code)
    char = file_storage.get_adventure_character(adventure_code, character_code)
    scene = scene_service.get_current_scene(adventure_code)
    global_info = file_storage.get_global_info(adventure_code)

    if not char or not scene:
        return {'narration': 'Erro: dados não encontrados.', 'commands': [], 'turnResult': {'endTurn': True, 'nextCharacterCode': None}}

    prompt = ai_client.load_prompt('game_master_prompt.txt')

    all_chars = file_storage.get_adventure_characters(adventure_code)
    enemy_codes = scene.get('availableEnemies', [])
    enemies_hydrated = [file_storage.get_enemy(adventure_code, ec) for ec in enemy_codes]
    enemies_hydrated = [e for e in enemies_hydrated if e]

    context = {
        'action': action,
        'character': _sanitize_character(char),
        'allCharacters': [_sanitize_character(c) for c in all_chars],
        'scene': {
            'sceneId': scene['sceneId'],
            'title': scene.get('title', ''),
            'currentContext': scene.get('currentContext', ''),
            'availableNPCs': scene.get('availableNPCs', []),
            'availableItems': scene.get('availableItems', []),
            'availableEnemies': enemies_hydrated,
            'legalContext': scene.get('legalContext')
        },
        'globalInfo': global_info,
        'turnOrder': scene.get('turnOrder', []),
        'currentTurn': scene.get('currentTurnCharacterCode')
    }

    size_instr = _scene_size_instruction()
    if size_instr:
        context['narrationSize'] = size_instr

    messages = [
        {'role': 'system', 'content': prompt},
        {'role': 'user', 'content': json.dumps(context, ensure_ascii=False)}
    ]

    content, error = ai_client.call_ai(messages, adventure_code, max_tokens=1500)
    if error:
        return {'narration': f'Erro ao processar ação: {error}', 'commands': [], 'turnResult': {'endTurn': True, 'nextCharacterCode': None}, 'ambiguous': True}

    ai_response = ai_client.parse_ai_json(content)
    if not ai_response:
        return {'narration': 'A ação não produziu resultados claros.', 'commands': [], 'turnResult': {'endTurn': True, 'nextCharacterCode': None}, 'ambiguous': True}

    is_valid, errors = validation_service.validate_ai_response(ai_response)
    if not is_valid:
        file_storage.append_log(adventure_code, 'ai', f'AI response invalid: {errors}')
        ai_response.setdefault('commands', [])

    if ai_response.get('requiresDiceRoll'):
        dice_request = ai_response.get('diceRequest', {})
        attr = dice_request.get('attribute', 'strength')
        difficulty = dice_request.get('difficulty', 12)
        dice_result = _execute_dice_roll(adventure_code, character_code, attr, difficulty)

        messages.append({'role': 'assistant', 'content': json.dumps(ai_response, ensure_ascii=False)})
        messages.append({'role': 'user', 'content': f'Resultado da rolagem de dados:\n{json.dumps(dice_result, ensure_ascii=False)}\n\nUse este resultado para decidir o desfecho da ação do personagem "{char.get("name")}".'})

        content2, error2 = ai_client.call_ai(messages, adventure_code, max_tokens=1500)
        if not error2:
            dice_response = ai_client.parse_ai_json(content2)
            if dice_response:
                ai_response = dice_response

    narration = ai_response.get('narration', '')
    commands = ai_response.get('commands', [])
    chars = file_storage.get_adventure_characters(adventure_code)
    applied_commands = []

    for cmd in commands:
        is_valid, errors = validation_service.validate_command(cmd, adventure, chars)
        if is_valid:
            result = _apply_command(adventure_code, cmd)
            applied_commands.append({'command': cmd, 'applied': True, 'result': result})
        else:
            applied_commands.append({'command': cmd, 'applied': False, 'errors': errors})

    if narration:
        action_label = action.get('description', action) if isinstance(action, dict) else action
        log_entry = f'{char.get("name", character_code)}: {action_label}\n{narration}'
        scene_service.update_scene_context(adventure_code, scene['sceneId'], log_entry, append=True)

    damage_already_applied = any(
        c.get('command', {}).get('type') == 'APPLY_DAMAGE' and c.get('command', {}).get('characterCode') == character_code
        for c in applied_commands if c.get('applied')
    )
    item_already_added = any(
        c.get('command', {}).get('type') == 'ADD_ITEM_TO_CHARACTER' and c.get('command', {}).get('characterCode') == character_code
        for c in applied_commands if c.get('applied')
    )
    enemy_already_created = any(
        c.get('command', {}).get('type') == 'CREATE_ENEMY'
        for c in applied_commands if c.get('applied')
    )

    action_text = action if isinstance(action, str) else (action.get('description', '') if isinstance(action, dict) else '')
    combined_text = (action_text + ' ' + narration).lower()

    if not item_already_added and char:
        pickup_kw = ['pegou', 'pega', 'apanhou', 'coletou', 'pegar', 'recolheu', 'recolhe', 'agarrou', 'encontrou um', 'encontrou uma']
        if any(kw in combined_text for kw in pickup_kw):
            import re
            item_patterns = [
                r'(?:peg(?:ou|a|ar)|apanhou|coletou|recolhe(?:u|)|agarrou)\s+(?:um|uma|o|a)\s+([a-zà-ú]+)',
                r'(?:encontrou|achou)\s+(?:um|uma|o|a)\s+([a-zà-ú]+)'
            ]
            item_name = None
            for pat in item_patterns:
                m = re.search(pat, combined_text)
                if m:
                    item_name = m.group(1)
                    break
            if item_name:
                fallback_item = {
                    'id': uuid.uuid4().hex[:8].upper(),
                    'name': item_name.capitalize(),
                    'description': f'Um(a) {item_name} encontrado(a) na cena.',
                    'type': 'misc',
                    'uses': 1,
                    'damage': 0,
                    'healingPercent': 0
                }
                fallback_cmd = {'type': 'ADD_ITEM_TO_CHARACTER', 'characterCode': character_code, 'item': fallback_item}
                result = _apply_command(adventure_code, fallback_cmd)
                applied_commands.append({'command': fallback_cmd, 'applied': result.get('success', False), 'result': result, 'fallback': True})
                if result.get('success'):
                    file_storage.append_log(adventure_code, 'game', f'Fallback ADD_ITEM_TO_CHARACTER injetado para {character_code}: {item_name} (IA não emitiu comando).')

    if not enemy_already_created:
        enemy_kw = ['goblin', 'orc', 'bandido', 'esqueleto', 'zumbi', 'lobisomem', 'troll', 'ogro', 'dragão', 'criatura', 'monstro', 'inimigo', 'assaltante']
        if any(kw in combined_text for kw in enemy_kw):
            import re
            m = re.search(r'(?:um|uma|o|a)\s+([a-zà-ú]+)', combined_text)
            enemy_name = m.group(1) if m else 'Criatura hostil'
            fallback_enemy = {
                'name': enemy_name.capitalize(),
                'description': f'Um(a) {enemy_name} hostil apareceu na cena.',
                'life': {'currentPercent': 100, 'maxPercent': 100, 'state': 'alive'},
                'attack': 5,
                'defense': 2,
                'attributes': {},
                'loot': {'coins': 0, 'items': []},
                'isBoss': False
            }
            fallback_cmd = {'type': 'CREATE_ENEMY', 'enemyData': fallback_enemy}
            result = _apply_command(adventure_code, fallback_cmd)
            applied_commands.append({'command': fallback_cmd, 'applied': bool(result.get('enemyCode')), 'result': result, 'fallback': True})
            if result.get('enemyCode'):
                file_storage.append_log(adventure_code, 'game', f'Fallback CREATE_ENEMY injetado: {enemy_name} (IA não emitiu comando).')

    npc_already_added = any(
        c.get('command', {}).get('type') == 'ADD_NPC_TO_SCENE'
        for c in applied_commands if c.get('applied')
    )
    if not npc_already_added:
        npc_appear_kw = ['apareceu', 'aproxima', 'chega', 'chegou', 'surge', 'surgiu', 'aproximou']
        if any(kw in combined_text for kw in npc_appear_kw):
            import re
            m = re.search(r'([A-ZÀ-Ú][a-zà-ú]{2,})', action_text + ' ' + narration)
            if m:
                npc_name = m.group(1)
                fallback_npc = {
                    'id': uuid.uuid4().hex[:8].upper(),
                    'name': npc_name,
                    'description': f'Um NPC chamado {npc_name} que apareceu na cena.',
                    'role': 'NPC'
                }
                fallback_cmd = {'type': 'ADD_NPC_TO_SCENE', 'npc': fallback_npc}
                result = _apply_command(adventure_code, fallback_cmd)
                applied_commands.append({'command': fallback_cmd, 'applied': bool(result.get('npcId')), 'result': result, 'fallback': True})
                if result.get('npcId'):
                    file_storage.append_log(adventure_code, 'game', f'Fallback ADD_NPC_TO_SCENE injetado: {npc_name} (IA não emitiu comando).')

    if not damage_already_applied and char and char.get('life', {}).get('state') != 'dead':
        harm_keywords = ['enfiou', 'cortou', 'faca', 'esfaqueou', 'apunhalou', 'feriu', 'machucou', 'queimou', 'caiu', 'penhasco', 'veneno', 'envenenou', 'sangrou', 'auto-mutil', 'mordeu', 'triturou', 'esmagou', 'dano', 'ferimento']
        if any(kw in combined_text for kw in harm_keywords):
            severe_kw = [('morte', 'penhasco', 'suicid', 'saltou do'), ('faca', 'esfaque', 'apunhal', 'enfiou'), ('cortou', 'feriu', 'machucou', 'queimou', 'mordeu'), ('veneno', 'envenen')]
            amount = 0
            if any(k in combined_text for k in severe_kw[0]):
                amount = 35
            elif any(k in combined_text for k in severe_kw[1]):
                amount = 25
            elif any(k in combined_text for k in severe_kw[2]):
                amount = 15
            elif any(k in combined_text for k in severe_kw[3]):
                amount = 20
            if amount > 0:
                fallback_cmd = {'type': 'APPLY_DAMAGE', 'characterCode': character_code, 'amount': amount, 'source': 'consequência direta'}
                result = _apply_command(adventure_code, fallback_cmd)
                applied_commands.append({'command': fallback_cmd, 'applied': True, 'result': result, 'fallback': True})
                file_storage.append_log(adventure_code, 'game', f'Fallback APPLY_DAMAGE injetado para {character_code}: {amount} dano (IA não emitiu comando).')

    if ai_response.get('turnResult', {}).get('endTurn'):
        scene = scene_service.get_current_scene(adventure_code)
        if scene:
            scene_service.advance_turn(adventure_code, scene['sceneId'])

    return {
        'narration': ai_response.get('narration', ''),
        'privateReasoningSummary': ai_response.get('privateReasoningSummary'),
        'commands': applied_commands,
        'requiresDiceRoll': False,
        'turnResult': ai_response.get('turnResult', {'endTurn': True, 'nextCharacterCode': None})
    }


def _execute_dice_roll(adventure_code, character_code, attribute, difficulty):
    from services.dice_service import resolve_roll
    char = file_storage.get_adventure_character(adventure_code, character_code)
    if not char:
        return {'die': 'D24', 'roll': 0, 'attribute': attribute, 'attributeValue': 0, 'total': 0, 'difficulty': difficulty, 'success': False, 'intensity': 'falha'}

    result = resolve_roll(char, attribute, difficulty)
    file_storage.append_log(adventure_code, 'game',
                             f'Rolagem D24: {result["roll"]} + {result["attributeValue"]} ({attribute}) = {result["total"]} vs {difficulty} = {result["intensity"]}')
    return result


def _handle_context_request(adventure_code, ctx_request):
    ctx_type = ctx_request.get('type', '')
    query = ctx_request.get('query', '')

    result = {'type': ctx_type, 'query': query}

    if 'TIMELINE' in ctx_type:
        timeline = file_storage.get_timeline(adventure_code)
        result['data'] = timeline
    elif 'GLOBAL' in ctx_type:
        result['data'] = file_storage.get_global_info(adventure_code)
    elif 'SCENE' in ctx_type:
        scene = scene_service.get_current_scene(adventure_code)
        result['data'] = scene
    elif 'ENEMY' in ctx_type:
        enemy_code = ctx_request.get('enemyCode', '')
        if enemy_code:
            result['data'] = file_storage.get_enemy(adventure_code, enemy_code)
    elif 'CHARACTER' in ctx_type:
        char_code = ctx_request.get('characterCode', '')
        if char_code:
            result['data'] = file_storage.get_adventure_character(adventure_code, char_code)
    else:
        timeline = file_storage.get_timeline(adventure_code)
        result['data'] = timeline

    return result


def _apply_command(adventure_code, cmd):
    cmd_type = cmd.get('type')

    if cmd_type == 'ADD_ITEM_TO_CHARACTER':
        item = cmd.get('item', {})
        char_code = cmd.get('characterCode')
        success = character_service.add_item_to_inventory(adventure_code, char_code, item)
        return {'success': success}

    elif cmd_type == 'REMOVE_ITEM_FROM_CHARACTER':
        char_code = cmd.get('characterCode')
        slot = cmd.get('slotIndex', 0)
        removed = character_service.remove_item_from_inventory(adventure_code, char_code, slot)
        return {'removed': removed is not None}

    elif cmd_type == 'ADD_COINS':
        char_code = cmd.get('characterCode')
        amount = cmd.get('amount', 0)
        result = character_service.update_character_coins(adventure_code, char_code, amount)
        return {'success': result is not None}

    elif cmd_type == 'REMOVE_COINS':
        char_code = cmd.get('characterCode')
        amount = cmd.get('amount', 0)
        result = character_service.update_character_coins(adventure_code, char_code, -amount)
        return {'success': result is not None}

    elif cmd_type == 'TRANSFER_COINS':
        from_code = cmd.get('fromCharacterCode')
        to_code = cmd.get('toCharacterCode')
        amount = cmd.get('amount', 0)
        success = character_service.transfer_coins(adventure_code, from_code, to_code, amount)
        return {'success': success}

    elif cmd_type == 'APPLY_DAMAGE':
        char_code = cmd.get('characterCode')
        amount = cmd.get('amount', 0)
        source = cmd.get('source', '')
        from services.combat_service import apply_damage
        result = apply_damage(adventure_code, char_code, amount, source)
        return {'success': result is not None}

    elif cmd_type == 'APPLY_HEALING':
        char_code = cmd.get('characterCode')
        amount = cmd.get('amount', 0)
        source = cmd.get('source', '')
        from services.combat_service import apply_healing
        result = apply_healing(adventure_code, char_code, amount, source)
        return {'success': result is not None}

    elif cmd_type == 'UPDATE_SCENE_CONTEXT':
        scene_id = cmd.get('sceneId')
        patch = cmd.get('contextPatch', '')
        append = cmd.get('append', True)
        result = scene_service.update_scene_context(adventure_code, scene_id, patch, append)
        return {'success': result is not None}

    elif cmd_type == 'ADD_NPC_TO_SCENE':
        npc = cmd.get('npc', {})
        if not npc.get('id'):
            import uuid
            npc['id'] = uuid.uuid4().hex[:8].upper()
        scene = scene_service.get_current_scene(adventure_code)
        if scene:
            scene_service.add_npc_to_scene(adventure_code, scene['sceneId'], npc)
            return {'npcId': npc.get('id'), 'sceneId': scene['sceneId']}
        return {'success': False}

    elif cmd_type == 'ADD_ITEM_TO_SCENE':
        item = cmd.get('item', {})
        if not item.get('id'):
            import uuid
            item['id'] = uuid.uuid4().hex[:8].upper()
        scene = scene_service.get_current_scene(adventure_code)
        if scene:
            scene.setdefault('availableItems', []).append(item)
            file_storage.save_scene(adventure_code, scene)
            return {'itemId': item.get('id'), 'sceneId': scene['sceneId']}
        return {'success': False}

    elif cmd_type == 'CREATE_SCENE':
        title = cmd.get('title', 'Nova Cena')
        desc = cmd.get('mainDescription', '')
        is_interior = cmd.get('isInterior', False)
        scene = scene_service.get_current_scene(adventure_code)
        prev_id = scene['sceneId'] if scene else None
        npcs = cmd.get('availableNPCs', [])
        items = cmd.get('availableItems', [])
        new_scene = scene_service.create_scene(adventure_code, title, desc, is_interior, prev_id, npcs, items)
        if new_scene:
            scene_service.set_current_scene(adventure_code, new_scene['sceneId'])
        return {'sceneId': new_scene['sceneId'] if new_scene else None}

    elif cmd_type == 'CREATE_ENEMY':
        enemy_data = cmd.get('enemyData', cmd)
        if not enemy_data.get('code'):
            import uuid
            enemy_data['code'] = uuid.uuid4().hex[:8].upper()
        if not enemy_data.get('life'):
            enemy_data['life'] = {'currentPercent': 100, 'maxPercent': 100, 'state': 'alive'}
        if not enemy_data.get('coins'):
            enemy_data['coins'] = {'amount': 0, 'displayName': 'Moedas'}
        file_storage.save_enemy(adventure_code, enemy_data)
        scene = scene_service.get_current_scene(adventure_code)
        if scene:
            scene_service.add_enemy_to_scene(adventure_code, scene['sceneId'], enemy_data['code'])
        return {'enemyCode': enemy_data['code']}

    elif cmd_type == 'REMOVE_ENEMY':
        enemy_code = cmd.get('enemyCode') or cmd.get('code')
        if enemy_code:
            scene = scene_service.get_current_scene(adventure_code)
            if scene:
                scene_service.remove_enemy_from_scene(adventure_code, scene['sceneId'], enemy_code)
            file_storage.delete_enemy(adventure_code, enemy_code)
        return {'enemyCode': enemy_code}

    elif cmd_type == 'REGISTER_CRIME':
        global_info = file_storage.get_global_info(adventure_code)
        if global_info:
            global_info.setdefault('registeredCrimes', []).append({
                'crime': cmd.get('crime', ''),
                'location': cmd.get('location', ''),
                'committedBy': cmd.get('committedBy', []),
                'forgiven': False,
                'consequence': cmd.get('consequence', '')
            })
            file_storage.save_global_info(adventure_code, global_info)
        return {'registered': True}

    elif cmd_type == 'UPDATE_GLOBAL_INFO':
        global_info = file_storage.get_global_info(adventure_code)
        if global_info:
            field = cmd.get('field')
            data = cmd.get('data')
            if field and data is not None:
                global_info[field] = data
                file_storage.save_global_info(adventure_code, global_info)
        return {'updated': True}

    elif cmd_type == 'ADD_TEMPORARY_EFFECT':
        char_code = cmd.get('characterCode')
        effect = cmd.get('effect', {})
        char = file_storage.get_adventure_character(adventure_code, char_code)
        if char:
            char.setdefault('temporaryEffects', []).append(effect)
            file_storage.save_adventure_character(adventure_code, char)
        return {'applied': True}

    elif cmd_type == 'ADD_ABILITY':
        char_code = cmd.get('characterCode')
        ability = cmd.get('ability', {})
        char = file_storage.get_adventure_character(adventure_code, char_code)
        if char:
            char.setdefault('specialAbilities', []).append(ability)
            file_storage.save_adventure_character(adventure_code, char)
        return {'added': True}

    elif cmd_type == 'UPDATE_ARMOR':
        char_code = cmd.get('characterCode')
        slot = cmd.get('slot')
        armor_data = cmd.get('armorData')
        char = file_storage.get_adventure_character(adventure_code, char_code)
        if char and slot in ('head', 'torso', 'hands', 'legs', 'feet'):
            char.setdefault('armor', {})[slot] = armor_data
            file_storage.save_adventure_character(adventure_code, char)
        return {'updated': True}

    elif cmd_type == 'TRANSITION_SCENE':
        target = cmd.get('targetSceneId')
        if target:
            scene_service.set_current_scene(adventure_code, target)
            chars = file_storage.get_adventure_characters(adventure_code)
            for c in chars:
                c['currentSceneId'] = target
                file_storage.save_adventure_character(adventure_code, c)
        return {'transitioned': target is not None}

    return {'unknown': True}


def _sanitize_character(char):
    return {
        'code': char.get('code'),
        'name': char.get('name'),
        'race': char.get('race'),
        'gender': char.get('gender'),
        'age': char.get('age'),
        'isBot': char.get('isBot', False),
        'life': char.get('life'),
        'coins': char.get('coins'),
        'attributes': char.get('attributes', {}),
        'armor': char.get('armor'),
        'specialAbilities': char.get('specialAbilities', []),
        'inventory': char.get('inventory', []),
        'story': char.get('story', ''),
        'physicalDescription': char.get('physicalDescription', {}),
        'legalStatus': char.get('legalStatus', []),
        'temporaryEffects': char.get('temporaryEffects', [])
    }
