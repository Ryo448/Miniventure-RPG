import uuid
from services import file_storage
from services import ai_orchestrator
from services.ai_orchestrator import generate_timeline_async, generate_bot_async, generate_initial_scene_async
from services import scene_service
from services import character_service


def create_adventure(total_participants, bot_count, bot_character_codes=None):
    if total_participants < 1 or total_participants > 4:
        return None, 'Total de participantes deve ser entre 1 e 4.'
    if bot_count < 0 or bot_count >= total_participants:
        return None, 'Quantidade de bots inválida.'

    if bot_character_codes is not None:
        if len(bot_character_codes) != bot_count:
            return None, 'Quantidade de personagens não corresponde ao número de bots.'
        filled = [c for c in bot_character_codes if c]
        if len(set(filled)) != len(filled):
            return None, 'Personagens de bot não podem se repetir.'

    code = file_storage.generate_adventure_code()
    adventure = file_storage.create_initial_files(code, total_participants, bot_count)

    generate_timeline_async(code)

    if bot_count > 0:
        if bot_character_codes is not None:
            for char_code in bot_character_codes:
                if not char_code:
                    continue
                sc, err = character_service.add_bot_character_to_adventure(code, char_code)
                if err:
                    return None, f'Erro ao anexar bot: {err}'

            filled_count = sum(1 for c in bot_character_codes if c)
            remaining = bot_count - filled_count

            if remaining > 0:
                generate_bot_async(code, remaining)
            else:
                file_storage.update_ai_preparation_stage(code, 'bots', 'completed')
                ai_orchestrator._maybe_kick_initial_scene(code)
        else:
            generate_bot_async(code, bot_count)
    else:
        file_storage.update_ai_preparation_stage(code, 'bots', 'completed')

    file_storage.append_log(code, 'game', f'Aventura criada com {total_participants} participantes e {bot_count} bots.')
    return adventure, None


def get_adventure_status(adventure_code):
    adventure = file_storage.get_adventure(adventure_code)
    if not adventure:
        return None

    characters = file_storage.get_adventure_characters(adventure_code)
    ai_prep = adventure.get('aiPreparation', {})

    all_ai_ready = all(
        v == 'completed' for v in ai_prep.values() if v != 'pending'
    )
    no_ai_failed = all(
        v != 'failed' for v in ai_prep.values()
    )

    real_players = [c for c in characters if not c.get('isBot')]
    bots = [c for c in characters if c.get('isBot')]

    required_real = adventure['totalParticipants'] - adventure['botCount']
    has_host = adventure.get('hostCharacterCode') is not None

    status = {
        'adventure': adventure,
        'aiPreparation': ai_prep,
        'allAiReady': all_ai_ready and no_ai_failed,
        'realPlayerCount': len(real_players),
        'botCount': len(bots),
        'requiredRealPlayers': required_real,
        'isReady': all_ai_ready and no_ai_failed and has_host and len(real_players) >= required_real,
        'characters': [{
            'code': c['code'],
            'name': c.get('name', ''),
            'race': c.get('race', ''),
            'isBot': c.get('isBot', False),
            'life': c.get('life', {})
        } for c in characters]
    }

    return status


def start_adventure(adventure_code):
    adventure = file_storage.get_adventure(adventure_code)
    if not adventure:
        return None, 'Aventura não encontrada.'

    status = get_adventure_status(adventure_code)
    if not status['isReady']:
        required = status['requiredRealPlayers']
        current = status['realPlayerCount']
        ai_ready = status['allAiReady']
        if not ai_ready:
            return None, 'A IA ainda está preparando o mundo. Aguarde...'
        if not adventure.get('hostCharacterCode'):
            return None, 'O host precisa selecionar um personagem antes de iniciar.'
        if current < required:
            return None, f'Aguardando jogadores ({current}/{required}).'

    if adventure['aiPreparation'].get('initialScene') != 'completed':
        if adventure['aiPreparation'].get('initialScene') == 'pending':
            ai_orchestrator.generate_initial_scene_async(adventure_code)
        return None, 'Gerando cena inicial...'

    scene = scene_service.get_current_scene(adventure_code)
    if scene:
        scene_service.init_turn_order(adventure_code, scene['sceneId'])

    ad = file_storage.get_adventure(adventure_code)
    if ad.get('status') != 'active':
        ad['status'] = 'active'
        file_storage.save_adventure(adventure_code, ad)

    return ad, None


def retry_ai_stage(adventure_code, stage):
    adventure = file_storage.get_adventure(adventure_code)
    if not adventure:
        return False, 'Aventura não encontrada.'

    ai_prep = adventure.get('aiPreparation', {})
    if stage not in ai_prep:
        return False, 'Stage desconhecido.'

    current = ai_prep.get(stage)
    if current != 'failed':
        return False, f'Stage {stage} não está em falha (atual: {current}).'

    if stage == 'timeline':
        file_storage.update_ai_preparation_stage(adventure_code, 'timeline', 'pending')
        ai_orchestrator.generate_timeline_async(adventure_code)
        return True, 'Retry da timeline iniciado.'

    if stage == 'initialScene':
        if ai_prep.get('timeline') != 'completed':
            return False, 'Timeline precisa estar completa antes de gerar a cena inicial.'
        if ai_prep.get('bots') not in ('completed', None):
            return False, 'Bots precisam estar prontos antes de gerar a cena inicial.'
        file_storage.update_ai_preparation_stage(adventure_code, 'initialScene', 'pending')
        ai_orchestrator.generate_initial_scene_async(adventure_code)
        return True, 'Retry da cena inicial iniciado.'

    if stage == 'bots':
        characters = file_storage.get_adventure_characters(adventure_code)
        existing_bots = [c for c in characters if c.get('isBot')]
        if existing_bots:
            for bot in existing_bots:
                file_storage.delete_adventure_character(adventure_code, bot['code'])
        file_storage.update_ai_preparation_stage(adventure_code, 'bots', 'pending')
        ai_orchestrator.generate_bot_async(adventure_code, adventure.get('botCount', 0))
        return True, 'Retry de bots iniciado (destruídos e regerados).'

    return False, 'Stage não suportado para retry.'


def join_adventure(adventure_code, character_code):
    adventure = file_storage.get_adventure(adventure_code)
    if not adventure:
        return None, 'Aventura não encontrada.'

    local_char = file_storage.get_local_character(character_code)
    if not local_char:
        return None, 'Personagem local não encontrado neste computador.'

    server_char, error = character_service.add_character_to_adventure(adventure_code, character_code)
    if error:
        return None, error

    return server_char, None
