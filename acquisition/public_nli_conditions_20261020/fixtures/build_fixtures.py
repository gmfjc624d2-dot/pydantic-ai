"""Author, validate and freeze the synthetic Spanish/English NLI fixtures.

Usage: python fixtures/build_fixtures.py   (writes dev.jsonl, heldout.jsonl, excluded.jsonl, freeze_manifest.json)

Run once, before any prediction exists. After the freeze commit, labels are never edited; any later
observation about an item goes to `errata.md` without changing the frozen files (the scorer refuses
predictions whose recorded fixture hash differs from the manifest).

Conventions (see METHOD.md):
- Labels are strict NLI: `entailment` only if the reference alone guarantees the hypothesis;
  `contradiction` only if both cannot be true of the same situation; otherwise `neutral`.
  A dropped condition, qualifier or attribution makes a hypothesis neutral, not contradictory.
- `reference` is the evidence; `hypothesis` is the claim. They are never merged.
- Spanish and English are paired variants of one item, not independent examples.
- `single_span` (exceptions, reference resolution) is a manually selected one-sentence premise,
  with its own label for what that span alone supports. It is not automatic evidence selection.
- Every `evidence` string must occur exactly once in its premise; offsets are computed, not typed.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
LABELS = ('entailment', 'neutral', 'contradiction')
PHENOMENA = ('condition', 'exception', 'negation', 'modality', 'attribution', 'reference')
ROLES = ('base', 'paraphrase', 'meaning_change', 'missing_qualifier')

# Each group: one reference (es/en), optional single-span selection, four hypotheses.
# Hypothesis tuple: (role, label, es, en, evidence_es, evidence_en, rationale[, span_label, span_rationale])
GROUPS = [
    # ------------------------------------------------------------------ DEV
    {
        'set': 'dev',
        'phenomenon': 'condition',
        'scenario': 'museum courtyard fountain',
        'es': 'Si la temperatura baja de cero grados, la fuente del patio del museo se apaga.',
        'en': 'If the temperature drops below zero, the fountain in the museum courtyard is switched off.',
        'items': [
            (
                'base',
                'contradiction',
                'Si la temperatura baja de cero grados, la fuente del patio del museo sigue encendida.',
                'If the temperature drops below zero, the fountain in the museum courtyard stays on.',
                ['la fuente del patio del museo se apaga'],
                ['the fountain in the museum courtyard is switched off'],
                'Same condition (below zero); the reference says the fountain is switched off, the hypothesis says it stays on. Both cannot hold.',
            ),
            (
                'paraphrase',
                'contradiction',
                'La fuente del patio sigue funcionando incluso cuando la temperatura baja de cero grados.',
                'The courtyard fountain keeps running even when the temperature falls below zero.',
                ['Si la temperatura baja de cero grados, la fuente del patio del museo se apaga.'],
                ['If the temperature drops below zero, the fountain in the museum courtyard is switched off.'],
                'Reworded base: running below zero is incompatible with being switched off below zero.',
            ),
            (
                'meaning_change',
                'entailment',
                'Cuando la temperatura baja de cero grados, la fuente del patio se apaga.',
                'When the temperature falls below zero, the courtyard fountain is turned off.',
                ['Si la temperatura baja de cero grados, la fuente del patio del museo se apaga.'],
                ['If the temperature drops below zero, the fountain in the museum courtyard is switched off.'],
                'Minimal edit of the base consequent (stays on -> turned off) restores the stated rule; "when" for a standing rule is read as "if".',
            ),
            (
                'missing_qualifier',
                'neutral',
                'La fuente del patio del museo está apagada.',
                'The fountain in the museum courtyard is switched off.',
                ['Si la temperatura baja de cero grados'],
                ['If the temperature drops below zero'],
                'The condition is dropped. The reference never says the temperature is below zero, so the fountain may be on or off: neutral, not contradiction.',
            ),
        ],
    },
    {
        'set': 'dev',
        'phenomenon': 'exception',
        'scenario': 'museum photography rule',
        'es': 'Los visitantes pueden tomar fotografías en cualquier lugar del museo. La única excepción es la sala de mapas, donde no se permite fotografiar.',
        'en': 'Visitors may take photographs anywhere in the museum. The only exception is the map room, where photography is not allowed.',
        'single_span': {
            'es': 'Los visitantes pueden tomar fotografías en cualquier lugar del museo.',
            'en': 'Visitors may take photographs anywhere in the museum.',
        },
        'items': [
            (
                'base',
                'entailment',
                'Los visitantes pueden tomar fotografías en la galería de esculturas del museo.',
                "Visitors may take photographs in the museum's sculpture gallery.",
                ['Los visitantes pueden tomar fotografías en cualquier lugar del museo.'],
                ['Visitors may take photographs anywhere in the museum.'],
                'The sculpture gallery is part of the museum and is not the excepted map room.',
                'entailment',
                'The general rule alone covers the sculpture gallery.',
            ),
            (
                'paraphrase',
                'entailment',
                'Está permitido hacer fotos en la galería de esculturas del museo.',
                "Taking pictures is allowed in the museum's sculpture gallery.",
                ['Los visitantes pueden tomar fotografías en cualquier lugar del museo.'],
                ['Visitors may take photographs anywhere in the museum.'],
                'Reworded base (permission to take pictures in the gallery).',
                'entailment',
                'The general rule alone covers the sculpture gallery.',
            ),
            (
                'meaning_change',
                'contradiction',
                'Los visitantes pueden tomar fotografías en la sala de mapas del museo.',
                "Visitors may take photographs in the museum's map room.",
                ['La única excepción es la sala de mapas, donde no se permite fotografiar.'],
                ['The only exception is the map room, where photography is not allowed.'],
                'The second sentence excludes the map room; photography there is not allowed.',
                'entailment',
                'With only the general-rule sentence selected, the exception is invisible and the hypothesis follows. This trial measures selection risk: the span label differs from the full-reference label.',
            ),
            (
                'missing_qualifier',
                'neutral',
                'Los visitantes pueden usar flash en la galería de esculturas del museo.',
                "Visitors may use a flash in the museum's sculpture gallery.",
                ['Los visitantes pueden tomar fotografías en cualquier lugar del museo.'],
                ['Visitors may take photographs anywhere in the museum.'],
                'Permission to photograph says nothing about flash use.',
                'neutral',
                'The span says nothing about flash use either.',
            ),
        ],
    },
    {
        'set': 'dev',
        'phenomenon': 'negation',
        'scenario': 'travel guide maps',
        'es': 'No todos los capítulos de la guía de viaje incluyen un mapa.',
        'en': 'Not all of the chapters in the travel guide include a map.',
        'items': [
            (
                'base',
                'contradiction',
                'Todos los capítulos de la guía de viaje incluyen un mapa.',
                'Every chapter in the travel guide includes a map.',
                ['No todos los capítulos de la guía de viaje incluyen un mapa.'],
                ['Not all of the chapters in the travel guide include a map.'],
                '"Not all" is the negation of "every".',
            ),
            (
                'paraphrase',
                'contradiction',
                'Cada uno de los capítulos de la guía de viaje contiene un mapa.',
                "Each of the travel guide's chapters contains a map.",
                ['No todos los capítulos de la guía de viaje incluyen un mapa.'],
                ['Not all of the chapters in the travel guide include a map.'],
                'Reworded universal claim; still the negation of "not all".',
            ),
            (
                'meaning_change',
                'entailment',
                'Algunos capítulos de la guía de viaje no incluyen un mapa.',
                'Some chapters in the travel guide do not include a map.',
                ['No todos los capítulos de la guía de viaje incluyen un mapa.'],
                ['Not all of the chapters in the travel guide include a map.'],
                '"Not all include" is equivalent to "some do not include" (the guide has chapters).',
            ),
            (
                'missing_qualifier',
                'neutral',
                'Ninguno de los capítulos de la guía de viaje incluye un mapa.',
                'None of the chapters in the travel guide includes a map.',
                ['No todos los capítulos de la guía de viaje incluyen un mapa.'],
                ['Not all of the chapters in the travel guide include a map.'],
                '"Not all" is compatible with "none" but does not entail it (some chapters may have maps): neutral. A negation-word match is not a contradiction here.',
            ),
        ],
    },
    {
        'set': 'dev',
        'phenomenon': 'modality',
        'scenario': 'valley rain forecast',
        'es': 'Mañana probablemente lloverá en el norte del valle.',
        'en': 'Tomorrow it will probably rain in the north of the valley.',
        'items': [
            (
                'base',
                'entailment',
                'Mañana puede llover en el norte del valle.',
                'It may rain in the north of the valley tomorrow.',
                ['probablemente lloverá'],
                ['it will probably rain'],
                'What is probable is possible.',
            ),
            (
                'paraphrase',
                'entailment',
                'Es probable que mañana llueva en el norte del valle.',
                'Rain is likely in the north of the valley tomorrow.',
                ['probablemente lloverá'],
                ['it will probably rain'],
                'Same degree of likelihood, reworded.',
            ),
            (
                'meaning_change',
                'contradiction',
                'Es seguro que mañana no lloverá en el norte del valle.',
                'It is certain that it will not rain in the north of the valley tomorrow.',
                ['probablemente lloverá'],
                ['it will probably rain'],
                'Rain being probable is incompatible with it being certain that it will not rain.',
            ),
            (
                'missing_qualifier',
                'neutral',
                'Mañana lloverá en el norte del valle.',
                'It will rain in the north of the valley tomorrow.',
                ['probablemente lloverá'],
                ['it will probably rain'],
                'The hedge "probably" is dropped: probable rain does not guarantee rain, and rain is not ruled out either.',
            ),
        ],
    },
    {
        'set': 'dev',
        'phenomenon': 'attribution',
        'scenario': 'museum vase sources',
        'es': 'Según el guía, el jarrón tiene dos mil años. Sin embargo, el catálogo del museo indica que el jarrón se fabricó en 1990.',
        'en': "According to the tour guide, the vase is two thousand years old. The museum's catalogue, however, states that the vase was made in 1990.",
        'items': [
            (
                'base',
                'entailment',
                'El guía dice que el jarrón tiene dos mil años.',
                'The tour guide says that the vase is two thousand years old.',
                ['Según el guía, el jarrón tiene dos mil años.'],
                ['According to the tour guide, the vase is two thousand years old.'],
                'The reference attributes this claim to the tour guide.',
            ),
            (
                'paraphrase',
                'entailment',
                'Según el guía, el jarrón tiene veinte siglos.',
                'According to the tour guide, the vase is twenty centuries old.',
                ['Según el guía, el jarrón tiene dos mil años.'],
                ['According to the tour guide, the vase is two thousand years old.'],
                'Two thousand years = twenty centuries; same attribution.',
            ),
            (
                'meaning_change',
                'contradiction',
                'El catálogo del museo indica que el jarrón tiene dos mil años.',
                "The museum's catalogue states that the vase is two thousand years old.",
                ['el catálogo del museo indica que el jarrón se fabricó en 1990'],
                ["The museum's catalogue, however, states that the vase was made in 1990"],
                'Swapping the source: the catalogue dates the vase to 1990, not two thousand years ago.',
            ),
            (
                'missing_qualifier',
                'neutral',
                'El jarrón tiene dos mil años.',
                'The vase is two thousand years old.',
                ['Según el guía, el jarrón tiene dos mil años.', 'el catálogo del museo indica que el jarrón se fabricó en 1990'],
                [
                    'According to the tour guide, the vase is two thousand years old.',
                    "The museum's catalogue, however, states that the vase was made in 1990",
                ],
                'The attribution is dropped. The reference reports two conflicting sources and asserts neither; citing a source is not establishing the fact.',
            ),
        ],
    },
    {
        'set': 'dev',
        'phenomenon': 'reference',
        'scenario': 'curators buy a telescope and globes',
        'es': 'Las conservadoras compraron un telescopio y dos globos terráqueos. Fue fabricado en 1850.',
        'en': 'The curators bought a telescope and two globes. It was made in 1850.',
        'single_span': {'es': 'Fue fabricado en 1850.', 'en': 'It was made in 1850.'},
        'items': [
            (
                'base',
                'entailment',
                'El telescopio fue fabricado en 1850.',
                'The telescope was made in 1850.',
                ['un telescopio', 'Fue fabricado en 1850.'],
                ['a telescope', 'It was made in 1850.'],
                'The only singular inanimate antecedent of "It" / masculine singular "fabricado" is the telescope (curators and globes are plural).',
                'neutral',
                'Strict reading: the selected sentence has an unresolved pronoun / null subject, so it does not say what was made in 1850. Convention-sensitive: annotators who resolve the pronoun to the hypothesis entity would say entailment.',
            ),
            (
                'paraphrase',
                'entailment',
                'El telescopio que compraron las conservadoras data de 1850.',
                'The telescope that the curators bought dates from 1850.',
                ['Las conservadoras compraron un telescopio', 'Fue fabricado en 1850.'],
                ['The curators bought a telescope', 'It was made in 1850.'],
                'Reworded base; "dates from" = was made in.',
                'neutral',
                'Strict reading: the span mentions neither the curators nor a telescope. Convention-sensitive (lenient: entailment).',
            ),
            (
                'meaning_change',
                'contradiction',
                'El telescopio fue fabricado en 1950.',
                'The telescope was made in 1950.',
                ['Fue fabricado en 1850.'],
                ['It was made in 1850.'],
                'Different year for the same object.',
                'neutral',
                'Strict reading: unresolved subject in the span. Convention-sensitive (lenient: contradiction).',
            ),
            (
                'missing_qualifier',
                'neutral',
                'Los globos terráqueos fueron fabricados en 1850.',
                'The globes were made in 1850.',
                ['dos globos terráqueos', 'Fue fabricado en 1850.'],
                ['two globes', 'It was made in 1850.'],
                'The date is stated for the singular antecedent only; nothing is said about the globes. A model that resolves "It" to the globes would wrongly say entailment.',
                'neutral',
                'A singular pronoun cannot refer to the plural globes; neutral under any convention.',
            ),
        ],
    },
    # -------------------------------------------------------------- HELD-OUT
    {
        'set': 'heldout',
        'phenomenon': 'condition',
        'scenario': 'geometry puzzle tiles ("only if")',
        'es': 'En este rompecabezas, una ficha se pinta de azul solo si tiene exactamente cuatro lados.',
        'en': 'In this puzzle, a tile is painted blue only if it has exactly four sides.',
        'items': [
            (
                'base',
                'entailment',
                'Todas las fichas azules de este rompecabezas tienen exactamente cuatro lados.',
                'Every blue tile in this puzzle has exactly four sides.',
                ['una ficha se pinta de azul solo si tiene exactamente cuatro lados'],
                ['a tile is painted blue only if it has exactly four sides'],
                '"Blue only if four sides" means every blue tile has four sides.',
            ),
            (
                'paraphrase',
                'entailment',
                'En este rompecabezas, ninguna ficha se pinta de azul a menos que tenga exactamente cuatro lados.',
                'In this puzzle, no tile is painted blue unless it has exactly four sides.',
                ['una ficha se pinta de azul solo si tiene exactamente cuatro lados'],
                ['a tile is painted blue only if it has exactly four sides'],
                '"Not P unless Q" is "P only if Q".',
            ),
            (
                'meaning_change',
                'contradiction',
                'En este rompecabezas, una ficha azul tiene exactamente tres lados.',
                'In this puzzle, one blue tile has exactly three sides.',
                ['una ficha se pinta de azul solo si tiene exactamente cuatro lados'],
                ['a tile is painted blue only if it has exactly four sides'],
                'A three-sided blue tile violates the "only if" rule.',
            ),
            (
                'missing_qualifier',
                'neutral',
                'Todas las fichas de este rompecabezas con exactamente cuatro lados se pintan de azul.',
                'Every tile in this puzzle with exactly four sides is painted blue.',
                ['solo si tiene exactamente cuatro lados'],
                ['only if it has exactly four sides'],
                'Converse of the rule. "Only if" states a necessary condition, not a sufficient one: four-sided tiles may or may not be blue.',
            ),
        ],
    },
    {
        'set': 'heldout',
        'phenomenon': 'exception',
        'scenario': 'reading room loans',
        'es': 'Todos los libros de la sala de lectura se pueden prestar durante dos semanas. Los diccionarios son la excepción: deben quedarse en la sala.',
        'en': 'All books in the reading room can be borrowed for two weeks. Dictionaries are the exception: they must stay in the room.',
        'single_span': {
            'es': 'Todos los libros de la sala de lectura se pueden prestar durante dos semanas.',
            'en': 'All books in the reading room can be borrowed for two weeks.',
        },
        'items': [
            (
                'base',
                'contradiction',
                'Los diccionarios de la sala de lectura se pueden prestar durante dos semanas.',
                'The dictionaries in the reading room can be borrowed for two weeks.',
                ['Los diccionarios son la excepción: deben quedarse en la sala.'],
                ['Dictionaries are the exception: they must stay in the room.'],
                'The second sentence excepts dictionaries: they must stay in the room, so they cannot be borrowed.',
                'entailment',
                'With only the general-rule sentence selected, dictionaries are books in the reading room and the hypothesis follows. Selection-risk trial: span label differs from the full-reference label.',
            ),
            (
                'paraphrase',
                'contradiction',
                'Los lectores pueden pedir prestados los diccionarios de la sala de lectura durante dos semanas.',
                "Readers are allowed to borrow the reading room's dictionaries for two weeks.",
                ['Los diccionarios son la excepción: deben quedarse en la sala.'],
                ['Dictionaries are the exception: they must stay in the room.'],
                'Reworded base (active voice); the exception still forbids it.',
                'entailment',
                'Span alone: dictionaries are books, books can be borrowed for two weeks. Selection-risk trial.',
            ),
            (
                'meaning_change',
                'entailment',
                'Los diccionarios deben permanecer en la sala de lectura.',
                'The dictionaries must remain in the reading room.',
                ['Los diccionarios son la excepción: deben quedarse en la sala.'],
                ['Dictionaries are the exception: they must stay in the room.'],
                'Restates the exception.',
                'neutral',
                'The general-rule sentence says nothing about dictionaries having to stay.',
            ),
            (
                'missing_qualifier',
                'neutral',
                'Las revistas de la sala de lectura se pueden prestar durante dos semanas.',
                'Magazines in the reading room can be borrowed for two weeks.',
                ['Todos los libros de la sala de lectura se pueden prestar durante dos semanas.'],
                ['All books in the reading room can be borrowed for two weeks.'],
                'The rule covers books; magazines are not books, and nothing is said about them.',
                'neutral',
                'Same: the span covers books only.',
            ),
        ],
    },
    {
        'set': 'heldout',
        'phenomenon': 'negation',
        'scenario': 'weather station snowfall record',
        'es': 'La estación meteorológica no registró ninguna nevada en marzo.',
        'en': 'The weather station did not record any snowfall in March.',
        'items': [
            (
                'base',
                'entailment',
                'Ninguna nevada fue registrada por la estación meteorológica en marzo.',
                'No snowfall was recorded by the weather station in March.',
                ['no registró ninguna nevada en marzo'],
                ['did not record any snowfall in March'],
                'Passive restatement of the same negated record.',
            ),
            (
                'paraphrase',
                'entailment',
                'En marzo, la estación meteorológica no registró nada de nieve.',
                'In March, the weather station recorded no snow at all.',
                ['no registró ninguna nevada en marzo'],
                ['did not record any snowfall in March'],
                'Reworded negation ("no snow at all" = not any snowfall).',
            ),
            (
                'meaning_change',
                'contradiction',
                'La estación meteorológica registró alguna nevada en marzo.',
                'The weather station recorded some snowfall in March.',
                ['no registró ninguna nevada en marzo'],
                ['did not record any snowfall in March'],
                'Removing the negation yields the opposite record.',
            ),
            (
                'missing_qualifier',
                'neutral',
                'En marzo no nevó.',
                'It did not snow in March.',
                ['La estación meteorológica no registró'],
                ['The weather station did not record'],
                'The source qualifier is dropped: the reference reports what the station recorded, not what happened. Snow could have gone unrecorded, so the record does not guarantee no snow.',
            ),
        ],
    },
    {
        'set': 'heldout',
        'phenomenon': 'modality',
        'scenario': 'old map restoration',
        'es': 'La restauración del mapa antiguo podría terminar antes de junio.',
        'en': 'The restoration of the old map might be finished before June.',
        'items': [
            (
                'base',
                'contradiction',
                'Es imposible que la restauración del mapa antiguo termine antes de junio.',
                'It is impossible for the restoration of the old map to be finished before June.',
                ['podría terminar antes de junio'],
                ['might be finished before June'],
                '"Might" asserts possibility; "impossible" denies it.',
            ),
            (
                'paraphrase',
                'contradiction',
                'La restauración del mapa antiguo no puede completarse de ningún modo antes de junio.',
                "The old map's restoration cannot possibly be completed before June.",
                ['podría terminar antes de junio'],
                ['might be finished before June'],
                'Reworded impossibility.',
            ),
            (
                'meaning_change',
                'entailment',
                'Es posible que la restauración del mapa antiguo termine antes de junio.',
                'It is possible that the restoration of the old map will be finished before June.',
                ['podría terminar antes de junio'],
                ['might be finished before June'],
                'Restates the possibility.',
            ),
            (
                'missing_qualifier',
                'neutral',
                'La restauración del mapa antiguo terminará antes de junio.',
                'The restoration of the old map will be finished before June.',
                ['podría terminar antes de junio'],
                ['might be finished before June'],
                'The modal is dropped: possible completion does not guarantee completion, nor rule it out.',
            ),
        ],
    },
    {
        'set': 'heldout',
        'phenomenon': 'attribution',
        'scenario': 'mountain road reports',
        'es': 'El locutor de radio dijo que la carretera de montaña estaba cerrada por el hielo. Sin embargo, el blog del tiempo informó de que la carretera estuvo abierta todo el día.',
        'en': 'The radio announcer said that the mountain road was closed because of ice. The weather blog, however, reported that the road was open all day.',
        'items': [
            (
                'base',
                'contradiction',
                'El blog del tiempo informó de que la carretera de montaña estaba cerrada por el hielo.',
                'The weather blog reported that the mountain road was closed because of ice.',
                ['el blog del tiempo informó de que la carretera estuvo abierta todo el día'],
                ['The weather blog, however, reported that the road was open all day'],
                'Wrong source: the blog reported the road open all day.',
            ),
            (
                'paraphrase',
                'contradiction',
                'Según el blog del tiempo, el hielo había cerrado la carretera de montaña.',
                'According to the weather blog, ice had closed the mountain road.',
                ['el blog del tiempo informó de que la carretera estuvo abierta todo el día'],
                ['The weather blog, however, reported that the road was open all day'],
                'Reworded wrong attribution.',
            ),
            (
                'meaning_change',
                'entailment',
                'El locutor de radio dijo que el hielo había cerrado la carretera de montaña.',
                'The radio announcer said that ice had closed the mountain road.',
                ['El locutor de radio dijo que la carretera de montaña estaba cerrada por el hielo.'],
                ['The radio announcer said that the mountain road was closed because of ice.'],
                'Correct source, reworded content.',
            ),
            (
                'missing_qualifier',
                'neutral',
                'La carretera de montaña estaba cerrada por el hielo.',
                'The mountain road was closed because of ice.',
                [
                    'El locutor de radio dijo que la carretera de montaña estaba cerrada por el hielo.',
                    'el blog del tiempo informó de que la carretera estuvo abierta todo el día',
                ],
                [
                    'The radio announcer said that the mountain road was closed because of ice.',
                    'The weather blog, however, reported that the road was open all day',
                ],
                'The attribution is dropped. Two sources disagree and the reference endorses neither.',
            ),
        ],
    },
    {
        'set': 'heldout',
        'phenomenon': 'reference',
        'scenario': 'students donate a novel and atlases',
        'es': 'Las alumnas donaron una novela y dos atlas. Tiene cuatrocientas páginas.',
        'en': 'The students donated a novel and two atlases. It has four hundred pages.',
        'single_span': {'es': 'Tiene cuatrocientas páginas.', 'en': 'It has four hundred pages.'},
        'items': [
            (
                'base',
                'entailment',
                'La novela tiene cuatrocientas páginas.',
                'The novel has four hundred pages.',
                ['una novela', 'Tiene cuatrocientas páginas.'],
                ['a novel', 'It has four hundred pages.'],
                'The only singular antecedent of "It" / singular "Tiene" is the novel (students and atlases are plural).',
                'neutral',
                'Strict reading: unresolved subject in the span. Convention-sensitive (lenient: entailment).',
            ),
            (
                'paraphrase',
                'entailment',
                'La novela que donaron las alumnas tiene una extensión de cuatrocientas páginas.',
                'The novel that the students donated is four hundred pages long.',
                ['Las alumnas donaron una novela', 'Tiene cuatrocientas páginas.'],
                ['The students donated a novel', 'It has four hundred pages.'],
                'Reworded base.',
                'neutral',
                'Strict reading: the span mentions neither the students nor a novel. Convention-sensitive (lenient: entailment).',
            ),
            (
                'meaning_change',
                'contradiction',
                'La novela tiene cuarenta páginas.',
                'The novel has forty pages.',
                ['Tiene cuatrocientas páginas.'],
                ['It has four hundred pages.'],
                'Different page count for the same book.',
                'neutral',
                'Strict reading: unresolved subject in the span. Convention-sensitive (lenient: contradiction).',
            ),
            (
                'missing_qualifier',
                'neutral',
                'Cada atlas tiene cuatrocientas páginas.',
                'Each atlas has four hundred pages.',
                ['dos atlas', 'Tiene cuatrocientas páginas.'],
                ['two atlases', 'It has four hundred pages.'],
                'The page count is stated for the singular antecedent only. Resolving "It" to the atlases would wrongly yield entailment.',
                'neutral',
                'A singular pronoun cannot refer to the plural atlases; neutral under any convention.',
            ),
        ],
    },
]

# Candidates considered during the ambiguity review and excluded before freezing (preserved, never scored).
EXCLUDED = [
    {
        'draft_id': 'x-generic-hours',
        'phenomenon': 'condition',
        'reference_en': 'On Saturdays the museum opens at eight.',
        'hypothesis_en': 'The museum opens at eight.',
        'reason': 'Generic vs. episodic reading: as a general claim it conflicts with weekday hours (contradiction?), as an existential claim it is supported (entailment?), and weekday hours are unstated (neutral?). No single defensible label.',
    },
    {
        'draft_id': 'x-loan-period',
        'phenomenon': 'exception',
        'reference_en': 'Books can be borrowed for two weeks.',
        'hypothesis_en': 'Books can be borrowed for a month.',
        'reason': 'Whether "two weeks" is a maximum is an implicature, so contradiction vs. neutral depends on the reader.',
    },
    {
        'draft_id': 'x-lighthouse-pronoun',
        'phenomenon': 'reference',
        'reference_en': 'The old lighthouse has a small weather station. It records the wind speed every ten minutes.',
        'hypothesis_en': 'The weather station records the wind speed every ten minutes.',
        'reason': 'Antecedent of "It" is ambiguous (subject continuity favors the lighthouse, plausibility the station). Replaced by number- and gender-marked antecedents.',
    },
    {
        'draft_id': 'x-museum-made',
        'phenomenon': 'reference',
        'reference_en': 'The museum bought a telescope and two globes. It was made in 1850.',
        'hypothesis_en': 'The telescope was made in 1850.',
        'reason': 'In Spanish "Fue fabricado" agrees with both "museo" and "telescopio" (masculine singular); the paired variants would differ in ambiguity. Replaced by plural feminine subject "Las conservadoras".',
    },
    {
        'draft_id': 'x-library-pages',
        'phenomenon': 'reference',
        'reference_en': 'The library received a novel and two atlases. It has four hundred pages.',
        'hypothesis_en': 'The novel has four hundred pages.',
        'reason': 'Singular subject "the library" competes as antecedent; resolution would rest on plausibility only. Replaced by plural subject "The students".',
    },
    {
        'draft_id': 'x-modern-copy',
        'phenomenon': 'attribution',
        'reference_en': 'The guide says the vase is Roman. The catalogue lists it as a modern copy.',
        'hypothesis_en': 'The catalogue says the vase is Roman.',
        'reason': '"Roman" can mean origin or style; a modern copy of a Roman vase is arguably "Roman". Replaced by a date ("made in 1990").',
    },
    {
        'draft_id': 'x-attributed-modality',
        'phenomenon': 'modality',
        'reference_en': 'The forecast says it may snow tomorrow.',
        'hypothesis_en': 'It will certainly not snow tomorrow.',
        'reason': 'Mixes attribution with epistemic modality: the forecast reporting a possibility does not make snow possible in fact. Modality items use unattributed hedges instead.',
    },
    {
        'draft_id': 'x-geometry-knowledge',
        'phenomenon': 'condition',
        'reference_en': 'The tile is a square.',
        'hypothesis_en': 'The tile is a rhombus.',
        'reason': 'Label depends on mathematical background knowledge rather than on the text.',
    },
    {
        'draft_id': 'x-take-home',
        'phenomenon': 'exception',
        'reference_en': 'All books in the reading room can be borrowed for two weeks.',
        'hypothesis_en': "Readers may take the reading room's dictionaries home for two weeks.",
        'reason': '"Take home" is narrower than "borrow"; span-only label would be uncertain. Replaced by "borrow".',
    },
]


def _spans(premise: str, evidence: list[str]) -> list[dict[str, object]]:
    out = []
    for text in evidence:
        assert premise.count(text) == 1, f'evidence {text!r} must occur exactly once in {premise!r}'
        start = premise.index(text)
        out.append({'start': start, 'end': start + len(text), 'text': text})
    return out


def build() -> dict[str, list[dict[str, object]]]:
    sets: dict[str, list[dict[str, object]]] = {'dev': [], 'heldout': []}
    for group in GROUPS:
        prefix = 'd' if group['set'] == 'dev' else 'h'
        group_id = f'{prefix}-{group["phenomenon"]}'
        span = group.get('single_span')
        if span:
            for lang in ('es', 'en'):
                assert group[lang].count(span[lang]) == 1, f'span must be a substring of the {lang} reference'
        for index, entry in enumerate(group['items'], start=1):
            role, label, hyp_es, hyp_en, ev_es, ev_en, rationale, *span_fields = entry
            assert role == ROLES[index - 1] and label in LABELS
            item: dict[str, object] = {
                'item_id': f'{group_id}-{index}',
                'set': group['set'],
                'phenomenon': group['phenomenon'],
                'group_id': group_id,
                'scenario': group['scenario'],
                'role': role,
                'label': label,
                'rationale': rationale,
                'es': {'reference': group['es'], 'hypothesis': hyp_es, 'evidence': _spans(group['es'], ev_es)},
                'en': {'reference': group['en'], 'hypothesis': hyp_en, 'evidence': _spans(group['en'], ev_en)},
                'single_span': None,
            }
            if span:
                span_label, span_rationale = span_fields
                assert span_label in LABELS
                item['single_span'] = {
                    'label': span_label,
                    'rationale': span_rationale,
                    'convention_sensitive': 'Convention-sensitive' in span_rationale,
                    'es': _spans(group['es'], [span['es']])[0],
                    'en': _spans(group['en'], [span['en']])[0],
                }
            else:
                assert not span_fields
            sets[group['set']].append(item)
    for name, items in sets.items():
        assert len(items) == 24, (name, len(items))
        assert Counter(i['phenomenon'] for i in items) == dict.fromkeys(PHENOMENA, 4), name
        assert len({i['item_id'] for i in items}) == 24
    return sets


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> str:
    text = ''.join(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n' for row in rows)
    path.write_text(text, encoding='utf-8')
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def main() -> None:
    sets = build()
    manifest: dict[str, object] = {
        'schema': 'nli-fixtures-freeze/v1',
        'statement': 'Frozen before any classifier or baseline prediction was produced. Labels are not edited after this point.',
        'files': {},
    }
    files: dict[str, object] = {}
    for name, items in sets.items():
        files[f'{name}.jsonl'] = {
            'sha256': _write_jsonl(HERE / f'{name}.jsonl', items),
            'items': len(items),
            'labels': dict(Counter(str(i['label']) for i in items)),
            'single_span_items': sum(1 for i in items if i['single_span']),
            'single_span_labels': dict(Counter(str(i['single_span']['label']) for i in items if i['single_span'])),  # type: ignore[index]
        }
    files['excluded.jsonl'] = {'sha256': _write_jsonl(HERE / 'excluded.jsonl', EXCLUDED), 'items': len(EXCLUDED)}
    manifest['files'] = files
    (HERE / 'freeze_manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
