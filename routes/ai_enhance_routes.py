from flask import Blueprint, request, jsonify
from services import ai_client

ai_enhance_routes = Blueprint('ai_enhance_routes', __name__)


@ai_enhance_routes.route('/api/ai/enhance', methods=['POST'])
def enhance_field():
    data = request.get_json() or {}
    field = data.get('field')
    context = data.get('context', {})

    if field not in ('story', 'physicalDescription', 'attributes'):
        return jsonify({'error': 'Campo não suportado para aprimoramento.'}), 400

    if field == 'attributes':
        prompt = _build_attributes_prompt(context)
    elif field == 'story':
        prompt = _build_story_prompt(context)
    else:
        prompt = _build_physical_prompt(context)

    messages = [
        {'role': 'system', 'content': 'Você é um escritor de RPG que cria fichas de personagem ricas e imersivas em português. Responda APENAS com o conteúdo solicitado, sem comentários, sem markdown, sem codeblocks.'},
        {'role': 'user', 'content': prompt}
    ]

    content, error = ai_client.call_ai(messages, max_tokens=1500, temperature=0.9)
    if error:
        return jsonify({'error': f'Erro da IA: {error}'}), 500

    if field == 'attributes':
        parsed = ai_client.parse_ai_json(content)
        if not parsed or 'attributes' not in parsed:
            return jsonify({'error': 'IA não retornou atributos válidos.'}), 500
        attrs = _normalize_attributes(parsed['attributes'])
        return jsonify({'attributes': attrs})

    return jsonify({'content': content.strip()})


def _build_story_prompt(context):
    name = context.get('name', '')
    race = context.get('race', '')
    gender = context.get('gender', '')
    age = context.get('age', '')
    draft = context.get('draft', '')
    physical = context.get('physicalDescription', '')
    weapon = context.get('weapon', '')
    ability = context.get('ability', '')

    parts = [f'Escreva uma história de personagem envolvente para um RPG de fantasia.']
    if name: parts.append(f'Nome: {name}')
    if race: parts.append(f'Raça: {race}')
    if gender: parts.append(f'Gênero: {gender}')
    if age: parts.append(f'Idade: {age}')
    if physical: parts.append(f'Descrição física: {physical}')
    if weapon: parts.append(f'Arma inicial: {weapon}')
    if ability: parts.append(f'Habilidade especial: {ability}')
    if draft: parts.append(f'Rascunho do jogador (use como inspiração): {draft}')
    parts.append('A história deve ter entre 3 e 5 parágrafos, MÁXIMO 450 palavras, no máximo 1500 caracteres. Em português, com motivações, origem e um evento marcante. Não ultrapasse o limite ou será cortado.')
    return '\n'.join(parts)


def _build_physical_prompt(context):
    name = context.get('name', '')
    race = context.get('race', '')
    gender = context.get('gender', '')
    age = context.get('age', '')
    story = context.get('story', '')
    draft = context.get('draft', '')
    weapon = context.get('weapon', '')
    ability = context.get('ability', '')

    parts = [f'Descreva detalhes físicos extra notáveis para um personagem de RPG de fantasia.']
    if name: parts.append(f'Nome: {name}')
    if race: parts.append(f'Raça: {race}')
    if gender: parts.append(f'Gênero: {gender}')
    if age: parts.append(f'Idade: {age}')
    if story: parts.append(f'História: {story}')
    if weapon: parts.append(f'Arma inicial: {weapon}')
    if ability: parts.append(f'Habilidade especial: {ability}')
    if draft: parts.append(f'Rascunho do jogador (use como inspiração): {draft}')
    parts.append('Foque em cicatrizes, tatuagens, marcas distintas, jeitos de andar ou accessories. MÁXIMO 3 frases, no máximo 200 palavras. Em português. Não ultrapasse o limite.')
    return '\n'.join(parts)


_ATTRS_KEYS = ('forca', 'destreza', 'constituicao', 'inteligencia', 'sabedoria', 'carisma', 'magia', 'furtividade', 'sorte')
_ATTRS_TOTAL = 27
_ATTRS_MAX = 5


def _normalize_attributes(raw):
    attrs = {}
    for k in _ATTRS_KEYS:
        v = raw.get(k, 0) if isinstance(raw, dict) else 0
        try:
            v = int(v)
        except (TypeError, ValueError):
            v = 0
        attrs[k] = max(0, min(_ATTRS_MAX, v))

    total = sum(attrs.values())
    if total == _ATTRS_TOTAL:
        return attrs

    if total > _ATTRS_TOTAL:
        while sum(attrs.values()) > _ATTRS_TOTAL:
            candidates = [k for k in _ATTRS_KEYS if attrs[k] > 0 and _ATTRS_MAX - attrs[k] >= 0 and attrs[k] > 0]
            if not candidates:
                break
            attr = max(candidates, key=lambda k: attrs[k])
            attrs[attr] -= 1
    else:
        while sum(attrs.values()) < _ATTRS_TOTAL:
            candidates = [k for k in _ATTRS_KEYS if attrs[k] < _ATTRS_MAX]
            if not candidates:
                break
            attr = min(candidates, key=lambda k: attrs[k])
            attrs[attr] += 1

    return attrs


def _build_attributes_prompt(context):
    name = context.get('name', '')
    race = context.get('race', '')
    story = context.get('story', '')
    gender = context.get('gender', '')
    weapon = context.get('weapon', '')
    ability = context.get('ability', '')
    available = 27

    parts = [f'Distribua EXATAMENTE {available} pontos entre os 9 atributos de um RPG. Cada atributo entre 0 e 5.']
    if name: parts.append(f'Nome: {name}')
    if race: parts.append(f'Raça: {race}')
    if gender: parts.append(f'Gênero: {gender}')
    if story: parts.append(f'História: {story}')
    if weapon: parts.append(f'Arma inicial: {weapon}')
    if ability: parts.append(f'Habilidade especial: {ability}')
    parts.append('Atributos: forca, destreza, constituicao, inteligencia, sabedoria, carisma, magia, furtividade, sorte')
    parts.append(f'REGRA OBRIGATÓRIA: a soma de todos os 9 atributos deve ser EXATAMENTE {available}. Nem mais, nem menos.')
    parts.append(f'Exemplo válido (9 atributos, soma={available}): forca=3, destreza=4, constituicao=2, inteligencia=2, sabedoria=2, carisma=2, magia=4, furtividade=3, sorte=5')
    parts.append('Responda APENAS um JSON válido: {"attributes": {"forca": 0, "destreza": 0, "constituicao": 0, "inteligencia": 0, "sabedoria": 0, "carisma": 0, "magia": 0, "furtividade": 0, "sorte": 0}}')
    return '\n'.join(parts)
