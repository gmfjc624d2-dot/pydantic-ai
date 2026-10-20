"""DEVELOPMENT set: used to write and adjust the rules. Not evidence of generalization.

Usage: python fixtures/dev_source.py   (writes dev.jsonl and dev.sha256)

Written after the reserved set was frozen (commit ffb913a) and before the lexicon. Includes format
cases the contract must handle: upper case, NBSP inside multiword cues, an emoji with a variation
selector directly before a cue, CRLF, a decomposed cue, a decomposed non-cue ("sí") that must not
match "si", and words that merely contain cue letters ("sinfonía").
"""

from __future__ import annotations

from _build import build_item, write_set

AUTHOR = 'Claude (AI assistant), request public-review-cues-20261020-02, written after the reserved freeze'

DEV = [
    # ----------------------------------------------------------------- English
    {
        'id': 'd-en-01',
        'lang': 'en',
        'text': 'If it is windy, the kite exhibit will not open.',
        'gold': [('If', 'If it is', ['condition'], ''), ('not', 'will not open', ['negation'], '')],
    },
    {
        'id': 'd-en-02',
        'lang': 'en',
        'text': 'The museum shop is closed on Mondays unless a holiday falls on that day.',
        'gold': [('unless', 'Mondays unless a', ['condition', 'exception'], '')],
    },
    {
        'id': 'd-en-03',
        'lang': 'en',
        'text': 'According to the librarian, the atlas may be missing a page.',
        'gold': [
            ('According to', 'According to the', ['attribution'], ''),
            ('may', 'atlas may be', ['uncertainty'], 'epistemic "may be"'),
        ],
    },
    {
        'id': 'd-en-04',
        'lang': 'en',
        'text': 'Every shelf was dusted except for the top one.',
        'gold': [('except for', 'dusted except for the', ['exception'], '')],
    },
    {
        'id': 'd-en-05',
        'lang': 'en',
        'text': 'The weather station reported that the river had not frozen.',
        'gold': [
            ('reported', 'station reported that', ['attribution'], ''),
            ('not', 'had not frozen', ['negation'], ''),
        ],
    },
    {
        'id': 'd-en-06',
        'lang': 'en',
        'text': 'You may enter the planetarium as long as the lights are off.',
        'gold': [('as long as', 'planetarium as long as the', ['condition'], 'NBSP between words')],
        'distractors': [('may', 'You may enter', 'permission, not a configured topic')],
        'format_features': ['nbsp_inside_multiword_cue'],
    },
    {
        'id': 'd-en-07',
        'lang': 'en',
        'text': "Nobody saw the comet, and the telescope can't be repaired.",
        'gold': [('Nobody', 'Nobody saw', ['negation'], ''), ("n't", "can't be", ['negation'], 'contracted negation')],
    },
    {
        'id': 'd-en-08',
        'lang': 'en',
        'text': 'The poster claims the dinosaur bones are real, but the label says they might be copies.',
        'gold': [
            ('claims', 'poster claims the', ['attribution'], ''),
            ('says', 'label says they', ['attribution'], ''),
            ('might', 'they might be', ['uncertainty'], ''),
        ],
    },
    {
        'id': 'd-en-09',
        'lang': 'en',
        'text': 'There is no map in the box; perhaps it was never printed.',
        'gold': [
            ('no', 'is no map', ['negation'], ''),
            ('perhaps', 'box; perhaps it', ['uncertainty'], ''),
            ('never', 'was never printed', ['negation'], ''),
        ],
    },
    {
        'id': 'd-en-10',
        'lang': 'en',
        'text': 'Tickets must be shown at the door, except for members.',
        'gold': [
            ('must', 'Tickets must be', ['obligation'], ''),
            ('except for', 'door, except for members', ['exception'], ''),
        ],
    },
    {
        'id': 'd-en-11',
        'lang': 'en',
        'text': 'IF THE ALARM RINGS, VISITORS MUST LEAVE.',
        'gold': [
            ('IF', 'IF THE', ['condition'], 'upper case'),
            ('MUST', 'VISITORS MUST LEAVE', ['obligation'], 'upper case'),
        ],
        'format_features': ['upper_case'],
    },
    {
        'id': 'd-en-12',
        'lang': 'en',
        'text': 'The robot exhibit is fun ❤️unless the batteries run out.\r\nOnly if the roof is dry can the panels be cleaned.',
        'gold': [
            ('unless', '️unless the', ['condition', 'exception'], 'emoji + variation selector directly before'),
            ('Only if', 'Only if the roof', ['condition'], ''),
        ],
        'distractors': [('can', 'dry can the', 'ability, not a configured topic')],
        'format_features': ['emoji_vs16_before_cue', 'crlf'],
    },
    # ----------------------------------------------------------------- Spanish
    {
        'id': 'd-es-01',
        'lang': 'es',
        'text': 'Si el museo cierra temprano, no habrá visita guiada ni concierto de la sinfonía.',
        'gold': [
            ('Si', 'Si el museo', ['condition'], ''),
            ('no', ', no habrá', ['negation'], ''),
            ('ni', 'guiada ni concierto', ['negation'], ''),
        ],
        'format_features': ['word_containing_cue_letters'],
    },
    {
        'id': 'd-es-02',
        'lang': 'es',
        'text': 'La tienda abre todos los días a menos que haya tormenta.',
        'gold': [('a menos que', 'días a menos que haya', ['condition', 'exception'], '')],
    },
    {
        'id': 'd-es-03',
        'lang': 'es',
        'text': 'De acuerdo con el guía, el cuadro puede ser una copia.',
        'gold': [
            ('De acuerdo con', 'De acuerdo con el', ['attribution'], ''),
            ('puede', 'cuadro puede ser', ['uncertainty'], 'epistemic "puede ser"'),
        ],
    },
    {
        'id': 'd-es-04',
        'lang': 'es',
        'text': 'Se prestan todos los libros salvo los diccionarios, que están a salvo en la vitrina.',
        'gold': [('salvo', 'libros salvo los', ['exception'], '')],
        'distractors': [('salvo', 'a salvo en', '"a salvo" means "safe"')],
    },
    {
        'id': 'd-es-05',
        'lang': 'es',
        'text': 'La estación informó que el lago no se congeló.',
        'gold': [('informó', 'estación informó que', ['attribution'], ''), ('no', 'lago no se', ['negation'], '')],
    },
    {
        'id': 'd-es-06',
        'lang': 'es',
        'text': 'Los alumnos tienen que traer una regla y quizá un compás.',
        'gold': [
            ('tienen que', 'alumnos tienen que traer', ['obligation'], ''),
            ('quizá', 'y quizá un', ['uncertainty'], ''),
        ],
    },
    {
        'id': 'd-es-07',
        'lang': 'es',
        'text': 'Nadie vio el cometa y el telescopio tampoco funciona.',
        'gold': [
            ('Nadie', 'Nadie vio', ['negation'], ''),
            ('tampoco', 'telescopio tampoco funciona', ['negation'], ''),
        ],
    },
    {
        'id': 'd-es-08',
        'lang': 'es',
        'text': 'El cartel afirma que los huesos son reales, pero la etiqueta dice que podrían ser copias.',
        'gold': [
            ('afirma', 'cartel afirma que', ['attribution'], ''),
            ('dice', 'etiqueta dice que', ['attribution'], ''),
            ('podrían', 'que podrían ser', ['uncertainty'], ''),
        ],
    },
    {
        'id': 'd-es-09',
        'lang': 'es',
        'text': 'No hay mapa en la caja; tal vez nunca se imprimió.',
        'gold': [
            ('No', 'No hay', ['negation'], ''),
            ('tal vez', 'caja; tal vez nunca', ['uncertainty'], 'NBSP between words'),
            ('nunca', 'vez nunca se', ['negation'], ''),
        ],
        'format_features': ['nbsp_inside_multiword_cue'],
    },
    {
        'id': 'd-es-10',
        'lang': 'es',
        'text': 'Hay que mostrar la entrada, excepto los socios.',
        'gold': [
            ('Hay que', 'Hay que mostrar', ['obligation'], ''),
            ('excepto', 'entrada, excepto los', ['exception'], ''),
        ],
    },
    {
        'id': 'd-es-11',
        'lang': 'es',
        'text': 'SI SUENA LA ALARMA, LOS VISITANTES DEBEN SALIR.',
        'gold': [
            ('SI', 'SI SUENA', ['condition'], 'upper case'),
            ('DEBEN', 'VISITANTES DEBEN SALIR', ['obligation'], 'upper case'),
        ],
        'format_features': ['upper_case'],
    },
    {
        'id': 'd-es-12',
        'lang': 'es',
        'text': 'Según el guía, sí hay salida de emergencia, sin escaleras.',
        'gold': [
            ('Según', 'Según el', ['attribution'], 'decomposed accent'),
            ('sin', 'emergencia, sin escaleras', ['negation'], ''),
        ],
        'distractors': [('sí', 'sí hay', 'decomposed "sí" (yes), not the conditional "si"')],
        'format_features': ['decomposed_accent_in_cue', 'decomposed_non_cue'],
    },
]


if __name__ == '__main__':
    items = [build_item(raw, 'dev', AUTHOR, 'dev: used to develop and adjust rules') for raw in DEV]
    print(write_set('dev', items), sum(len(i['gold']) for i in items), 'gold cues')
