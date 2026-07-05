const CharacterCreator = {
    races: [],
    weapons: [],
    abilities: [],
    attributes: { forca: 0, destreza: 0, constituicao: 0, inteligencia: 0, sabedoria: 0, carisma: 0, magia: 0, furtividade: 0, sorte: 0 },
    maxPoints: 27,
    maxAttrValue: 5,
    selectedRace: null,
    selectedWeapon: null,
    selectedAbility: null,
    editCode: null,

    _ATTR_EN_TO_PT: {
        strength: 'forca', dexterity: 'destreza', constitution: 'constituicao',
        intelligence: 'inteligencia', wisdom: 'sabedoria', charisma: 'carisma',
        magic: 'magia', perception: 'furtividade', luck: 'sorte'
    },

    async init() {
        this.editCode = window.__CHARACTER_CODE__ || null;
        await this.loadCatalog();
        if (this.editCode) {
            await this.loadCharacterForEdit();
        }
        this.setupEventListeners();
        this.updatePointsDisplay();
    },

    async loadCharacterForEdit() {
        try {
            const char = await API.getLocalCharacter(this.editCode);
            if (!char || char.error) return;

            if (char.name) document.getElementById('char-name').value = char.name;
            if (char.gender) document.getElementById('char-gender').value = char.gender;
            if (char.age) document.getElementById('char-age').value = char.age;
            if (char.story) document.getElementById('char-story').value = char.story;
            if (char.physicalDescription && char.physicalDescription.customDescription) {
                document.getElementById('char-physical').value = char.physicalDescription.customDescription;
            }

            if (char.raceId) {
                const raceSelect = document.getElementById('race-select');
                raceSelect.value = char.raceId;
                this.onRaceChange(char.raceId);
            }

            const weapon = char.initialWeaponOrItem;
            if (weapon && weapon.id) {
                const weaponSelect = document.getElementById('weapon-select');
                for (const opt of weaponSelect.options) {
                    if (opt.value === weapon.id) {
                        weaponSelect.value = weapon.id;
                        this.onWeaponChange(weapon.id);
                        break;
                    }
                }
            }

            const ability = char.initialSpecialAbility;
            if (ability && ability.id) {
                const abilitySelect = document.getElementById('ability-select');
                for (const opt of abilitySelect.options) {
                    if (opt.value === ability.id) {
                        abilitySelect.value = ability.id;
                        this.onAbilityChange(ability.id);
                        break;
                    }
                }
            }

            if (char.attributes) {
                const raceBonus = this.selectedRace?.pontos || {};
                const attrs = { ...char.attributes };

                if (attrs.perception === undefined && raceBonus.furtividade) {
                    const leaked = raceBonus.furtividade;
                    if (attrs.dexterity !== undefined) {
                        attrs.dexterity = Math.max(0, attrs.dexterity - leaked);
                    }
                    attrs.perception = leaked;
                }

                for (const [attrEn, val] of Object.entries(attrs)) {
                    const attrPt = this._ATTR_EN_TO_PT[attrEn];
                    if (attrPt) {
                        const bonus = raceBonus[attrPt] || 0;
                        this.attributes[attrPt] = Math.max(0, val - bonus);
                        this.updateAttributeUI(attrPt);
                    }
                }
                this.updatePointsDisplay();
            }
        } catch (err) {
            console.error('Erro ao carregar personagem para edição:', err);
        }
    },

    async loadCatalog() {
        try {
            const [races, weapons, abilities] = await Promise.all([
                API.getRaces(),
                API.getWeapons(),
                API.getAbilities()
            ]);
            this.races = races;
            this.weapons = weapons;
            this.abilities = abilities;
            this.populateSelects();
        } catch (err) {
            this.showError('Erro ao carregar catálogo. Tente novamente.');
            console.error(err);
        }
    },

    populateSelects() {
        const raceSelect = document.getElementById('race-select');
        const weaponSelect = document.getElementById('weapon-select');
        const abilitySelect = document.getElementById('ability-select');

        if (raceSelect) {
            raceSelect.innerHTML = '<option value="">-- Selecione uma raça --</option>';
            this.races.forEach((race) => {
                const opt = document.createElement('option');
                opt.value = race.id;
                opt.textContent = race.nome;
                opt.dataset.desc = race.descricao || '';
                raceSelect.appendChild(opt);
            });
        }

        if (weaponSelect) {
            weaponSelect.innerHTML = '<option value="">-- Selecione uma arma --</option>';
            this.weapons.forEach((weapon) => {
                const opt = document.createElement('option');
                opt.value = weapon.id;
                opt.textContent = weapon.nome;
                opt.dataset.info = JSON.stringify(weapon);
                weaponSelect.appendChild(opt);
            });
        }

        if (abilitySelect) {
            abilitySelect.innerHTML = '<option value="">-- Selecione uma habilidade --</option>';
            this.abilities.forEach((ability) => {
                const opt = document.createElement('option');
                opt.value = ability.id;
                opt.textContent = ability.nome;
                opt.dataset.info = JSON.stringify(ability);
                abilitySelect.appendChild(opt);
            });
        }
    },

    setupEventListeners() {
        const raceSelect = document.getElementById('race-select');
        const weaponSelect = document.getElementById('weapon-select');
        const abilitySelect = document.getElementById('ability-select');
        const form = document.getElementById('character-form');

        if (raceSelect) {
            raceSelect.addEventListener('change', () => this.onRaceChange(raceSelect.value));
        }
        if (weaponSelect) {
            weaponSelect.addEventListener('change', () => this.onWeaponChange(weaponSelect.value));
        }
        if (abilitySelect) {
            abilitySelect.addEventListener('change', () => this.onAbilityChange(abilitySelect.value));
        }

        document.querySelectorAll('.attr-btn').forEach((btn) => {
            btn.addEventListener('click', (e) => {
                const attr = e.target.dataset.attr;
                const delta = e.target.classList.contains('attr-plus') ? 1 : -1;
                this.modifyAttribute(attr, delta);
            });
        });

        if (form) {
            form.addEventListener('submit', (e) => {
                e.preventDefault();
                this.submit();
            });
        }

        document.querySelectorAll('.ai-enhance-btn').forEach((btn) => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                this.enhanceWithAI(btn);
            });
        });
    },

    _getCharacterContext() {
        return {
            name: document.getElementById('char-name')?.value?.trim() || '',
            race: this.selectedRace?.nome || '',
            raceId: this.selectedRace?.id || '',
            gender: document.getElementById('char-gender')?.value || '',
            age: document.getElementById('char-age')?.value || '',
            story: document.getElementById('char-story')?.value?.trim() || '',
            draft: document.getElementById('char-story')?.value?.trim() || '',
            physicalDescription: document.getElementById('char-physical')?.value?.trim() || '',
            weapon: this.selectedWeapon?.nome || '',
            ability: this.selectedAbility?.nome || ''
        };
    },

    async enhanceWithAI(btn) {
        const field = btn.dataset.field;
        if (!field) return;

        if (field === 'physicalDescription') {
            const ctx = this._getCharacterContext();
            ctx.draft = document.getElementById('char-physical')?.value?.trim() || '';
            await this._enhanceText(field, 'char-physical', ctx, btn);
        } else if (field === 'story') {
            const ctx = this._getCharacterContext();
            ctx.draft = document.getElementById('char-story')?.value?.trim() || '';
            await this._enhanceText(field, 'char-story', ctx, btn);
        } else if (field === 'attributes') {
            await this._enhanceAttributes(btn);
        }
    },

    async _enhanceText(field, targetId, context, btn) {
        const originalText = btn.innerHTML;
        btn.disabled = true;
        btn.classList.add('loading');
        btn.innerHTML = '✨ Gerando...';
        try {
            const result = await API.enhanceField(field, context);
            if (result.error) {
                this.showError(result.error);
            } else if (result.content) {
                const el = document.getElementById(targetId);
                if (el) el.value = result.content;
            }
        } catch (err) {
            this.showError(err.message || 'Erro ao aprimorar com IA.');
        } finally {
            btn.disabled = false;
            btn.classList.remove('loading');
            btn.innerHTML = originalText;
        }
    },

    async _enhanceAttributes(btn) {
        const originalText = btn.innerHTML;
        btn.disabled = true;
        btn.classList.add('loading');
        btn.innerHTML = '✨ Sugerindo...';
        try {
            const context = this._getCharacterContext();
            const result = await API.enhanceField('attributes', context);
            if (result.error) {
                this.showError(result.error);
            } else if (result.attributes) {
                this.attributes = { forca: 0, destreza: 0, constituicao: 0, inteligencia: 0, sabedoria: 0, carisma: 0, magia: 0, furtividade: 0, sorte: 0 };
                for (const [k, v] of Object.entries(result.attributes)) {
                    if (k in this.attributes) this.attributes[k] = Math.max(0, Math.min(5, parseInt(v) || 0));
                }
                for (const attr of Object.keys(this.attributes)) {
                    this.updateAttributeUI(attr);
                }
                this.updatePointsDisplay();
            }
        } catch (err) {
            this.showError(err.message || 'Erro ao sugerir atributos.');
        } finally {
            btn.disabled = false;
            btn.classList.remove('loading');
            btn.innerHTML = originalText;
        }
    },

    onRaceChange(raceId) {
        const detailsEl = document.getElementById('race-details');
        const modsEl = document.getElementById('race-modifiers');

        if (!raceId) {
            this.selectedRace = null;
            if (detailsEl) detailsEl.innerHTML = 'Selecione uma raça para ver sua descrição.';
            if (modsEl) modsEl.innerHTML = '';
            return;
        }

        this.selectedRace = this.races.find((r) => r.id == raceId);
        if (!this.selectedRace) return;

        if (detailsEl) {
            detailsEl.innerHTML = `<p>${this.selectedRace.descricao || ''}</p>`;
        }

        if (modsEl && this.selectedRace.pontos) {
            const modEntries = Object.entries(this.selectedRace.pontos);
            modsEl.innerHTML = modEntries.map(([attr, val]) => {
                const sign = val >= 0 ? '+' : '';
                const label = this.getAttributeLabel(attr);
                return `<span class="mod-tag ${val >= 0 ? 'mod-positive' : 'mod-negative'}">${label} ${sign}${val}</span>`;
            }).join('');
        }
    },

    onWeaponChange(weaponId) {
        const detailsEl = document.getElementById('weapon-details');

        if (!weaponId) {
            this.selectedWeapon = null;
            if (detailsEl) detailsEl.style.display = 'none';
            return;
        }

        this.selectedWeapon = this.weapons.find((w) => w.id == weaponId);
        if (!this.selectedWeapon) return;

        if (detailsEl) {
            detailsEl.style.display = 'block';
            detailsEl.innerHTML = `
                <h4>${this.selectedWeapon.nome}</h4>
                <p><strong>Classe:</strong> ${this.selectedWeapon.classeRecomendada || ''}</p>
                <p>${this.selectedWeapon.descricao || ''}</p>
                <p><strong>Dano:</strong> ${this.selectedWeapon.pontos?.dano || 0}</p>
            `;
        }
    },

    onAbilityChange(abilityId) {
        const detailsEl = document.getElementById('ability-details');

        if (!abilityId) {
            this.selectedAbility = null;
            if (detailsEl) detailsEl.style.display = 'none';
            return;
        }

        this.selectedAbility = this.abilities.find((a) => a.id == abilityId);
        if (!this.selectedAbility) return;

        if (detailsEl) {
            detailsEl.style.display = 'block';
            detailsEl.innerHTML = `
                <h4>${this.selectedAbility.nome}</h4>
                <p><strong>Classe:</strong> ${this.selectedAbility.classeRecomendada || ''}</p>
                <p>${this.selectedAbility.descricao || ''}</p>
                <p><strong>Recarga:</strong> ${this.selectedAbility.cooldownTurnos || 0} turnos</p>
            `;
        }
    },

    modifyAttribute(attr, delta) {
        const current = this.attributes[attr];
        const totalSpent = Object.values(this.attributes).reduce((s, v) => s + v, 0);

        if (delta > 0 && totalSpent >= this.maxPoints) return;
        if (delta > 0 && current >= this.maxAttrValue) return;
        if (delta < 0 && current <= 0) return;

        this.attributes[attr] = current + delta;
        this.updateAttributeUI(attr);
        this.updatePointsDisplay();
    },

    updateAttributeUI(attr) {
        const valueEl = document.getElementById(`attr-value-${attr}`);
        const barEl = document.getElementById(`attr-bar-${attr}`);

        if (valueEl) {
            valueEl.textContent = this.attributes[attr];
        }
        if (barEl) {
            const pct = (this.attributes[attr] / this.maxAttrValue) * 100;
            barEl.style.width = `${pct}%`;
        }
    },

    updatePointsDisplay() {
        const totalSpent = Object.values(this.attributes).reduce((s, v) => s + v, 0);
        const remaining = this.maxPoints - totalSpent;

        const remainingEl = document.getElementById('remaining-points');
        if (remainingEl) {
            remainingEl.textContent = remaining;
            remainingEl.classList.toggle('points-low', remaining <= 5);
            remainingEl.classList.toggle('points-zero', remaining === 0);
        }
    },

    getAttributeLabel(attr) {
        const labels = {
            forca: 'Força',
            destreza: 'Destreza',
            constituicao: 'Constituição',
            inteligencia: 'Inteligência',
            sabedoria: 'Sabedoria',
            carisma: 'Carisma',
            magia: 'Magia',
            furtividade: 'Furtividade',
            sorte: 'Sorte'
        };
        return labels[attr] || attr;
    },

    validate() {
        const name = document.getElementById('char-name')?.value?.trim();
        const totalSpent = Object.values(this.attributes).reduce((s, v) => s + v, 0);
        const errors = [];

        if (!name) errors.push('Nome é obrigatório');
        if (!this.selectedRace) errors.push('Selecione uma raça');
        if (totalSpent < 1) errors.push('Distribua os pontos de atributo');
        if (!this.selectedWeapon) errors.push('Selecione uma arma inicial');
        if (!this.selectedAbility) errors.push('Selecione uma habilidade');

        return errors;
    },

    showError(message) {
        const errorEl = document.getElementById('error-messages');
        if (errorEl) {
            errorEl.innerHTML = `<p class="error">${message}</p>`;
            errorEl.style.display = 'block';
        }
    },

    showValidationErrors(errors) {
        const errorEl = document.getElementById('error-messages');
        if (errorEl) {
            errorEl.innerHTML = errors.map((e) => `<p class="error">${e}</p>`).join('');
            errorEl.style.display = 'block';
        }
    },

    async submit() {
        const errors = this.validate();
        if (errors.length > 0) {
            this.showValidationErrors(errors);
            return;
        }

        const name = document.getElementById('char-name').value.trim();
        const gender = document.getElementById('char-gender').value;
        const age = parseInt(document.getElementById('char-age').value) || 25;
        const story = document.getElementById('char-story').value.trim();
        const customDescription = document.getElementById('char-physical').value.trim();
        const raceId = this.selectedRace.id;
        const weaponId = this.selectedWeapon.id;
        const abilityId = this.selectedAbility.id;

        const payload = {
            name, raceId, weaponId, abilityId,
            attributes: { ...this.attributes },
            gender, age, story, customDescription
        };

        const submitBtn = document.getElementById('submit-btn');
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.textContent = this.editCode ? 'Salvando...' : 'Criando personagem...';
        }

        try {
            if (this.editCode) {
                await API.updateLocalCharacter(this.editCode, payload);
            } else {
                await API.createLocalCharacter(payload);
            }

            window.location.href = '/characters';
        } catch (err) {
            this.showError(err.message || 'Erro ao salvar personagem. Tente novamente.');
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.textContent = this.editCode ? 'Salvar Alterações' : 'Criar Personagem';
            }
        }
    },
};

document.addEventListener('DOMContentLoaded', () => {
    CharacterCreator.init();
});
