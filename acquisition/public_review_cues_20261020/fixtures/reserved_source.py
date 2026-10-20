"""RESERVED evaluation set. Written before any lexicon or matching code existed; frozen by commit.

Usage: python fixtures/reserved_source.py   (writes reserved.jsonl and reserved.sha256)

Never used to develop or tune rules. Run against the tool exactly once, after the rules are frozen.
Some items deliberately contain cue wordings a small lexicon may lack, and format features
(CRLF inside a multiword cue, an emoji directly before a cue, a decomposed accent).
"""

from __future__ import annotations

from _build import build_item, write_set

AUTHOR = 'Claude (AI assistant), request public-review-cues-20261020-02, written before rules existed'

RESERVED = [
    # ----------------------------------------------------------------- English
    {
        'id': 'r-en-01',
        'lang': 'en',
        'text': 'If the gallery floods, the paintings will probably be moved upstairs.',
        'gold': [
            ('If', 'If the gallery', ['condition'], ''),
            ('probably', 'will probably be', ['uncertainty'], ''),
        ],
    },
    {
        'id': 'r-en-02',
        'lang': 'en',
        'text': 'Visitors must not touch the clay vases, unless a guide is present.',
        'gold': [
            ('must', 'Visitors must not', ['obligation'], ''),
            ('not', 'must not touch', ['negation'], ''),
            ('unless', 'unless a guide', ['condition', 'exception'], ''),
        ],
    },
    {
        'id': 'r-en-03',
        'lang': 'en',
        'text': '\U0001f4ccAccording to the curator, the map was likely drawn in winter.',
        'gold': [
            ('According to', 'According to the curator', ['attribution'], 'emoji directly before the cue'),
            ('likely', 'was likely drawn', ['uncertainty'], ''),
        ],
        'format_features': ['emoji_before_cue'],
    },
    {
        'id': 'r-en-04',
        'lang': 'en',
        'text': 'All rooms are open on Sunday, except the attic, which stays closed.',
        'gold': [('except', 'except the attic', ['exception'], '')],
    },
    {
        'id': 'r-en-05',
        'lang': 'en',
        'text': 'The forecast says snow might fall, but nobody is sure.',
        'gold': [
            ('says', 'forecast says snow', ['attribution'], ''),
            ('might', 'snow might fall', ['uncertainty'], ''),
            ('nobody', 'but nobody is', ['negation'], ''),
        ],
    },
    {
        'id': 'r-en-06',
        'lang': 'en',
        'text': 'Readers can borrow two books, provided\r\nthat they return them by Friday.',
        'gold': [('provided\r\nthat', 'provided\r\nthat they', ['condition'], 'multiword cue across a CRLF line break')],
        'distractors': [('can', 'Readers can borrow', 'permission, not a configured topic')],
        'format_features': ['crlf_inside_multiword_cue'],
    },
    {
        'id': 'r-en-07',
        'lang': 'en',
        'text': "The triangle isn't drawn to scale and its angles shouldn't be measured.",
        'gold': [
            ("n't", "isn't drawn", ['negation'], 'contracted negation'),
            ('should', "shouldn't be", ['obligation', 'uncertainty'], ''),
            ("n't", "shouldn't be", ['negation'], 'contracted negation'),
        ],
    },
    {
        'id': 'r-en-08',
        'lang': 'en',
        'text': 'In May the museum reopened; no tickets were sold online.',
        'gold': [('no', 'reopened; no tickets', ['negation'], '')],
        'distractors': [('May', 'In May the', 'month name, not a modal')],
    },
    {
        'id': 'r-en-09',
        'lang': 'en',
        'text': 'Assuming the bus is on time, the class will arrive before noon.',
        'gold': [('Assuming', 'Assuming the bus', ['condition'], '')],
    },
    {
        'id': 'r-en-10',
        'lang': 'en',
        'text': 'The guide reportedly said that the statue was never moved.',
        'gold': [
            ('reportedly', 'guide reportedly said', ['attribution', 'uncertainty'], ''),
            ('said', 'reportedly said that', ['attribution'], ''),
            ('never', 'was never moved', ['negation'], ''),
        ],
    },
    {
        'id': 'r-en-11',
        'lang': 'en',
        'text': 'Children under ten have to be accompanied; the rule does not apply to school groups.',
        'gold': [
            ('have to', 'ten have to be', ['obligation'], ''),
            ('does not apply to', 'rule does not apply to school', ['exception'], 'overlaps the negation span'),
            ('not', 'does not apply', ['negation'], ''),
        ],
    },
    {
        'id': 'r-en-12',
        'lang': 'en',
        'text': 'The blue square has four equal sides and sits next to a red circle.',
        'gold': [],
    },
    # ----------------------------------------------------------------- Spanish
    {
        'id': 'r-es-01',
        'lang': 'es',
        'text': 'Si llueve mañana, la excursión al museo probablemente se cancelará.',
        'gold': [
            ('Si', 'Si llueve', ['condition'], ''),
            ('probablemente', 'museo probablemente se', ['uncertainty'], ''),
        ],
    },
    {
        'id': 'r-es-02',
        'lang': 'es',
        'text': 'Los visitantes no deben tocar las esculturas, salvo que un guía lo autorice.',
        'gold': [
            ('no', 'visitantes no deben', ['negation'], ''),
            ('deben', 'no deben tocar', ['obligation'], ''),
            ('salvo que', 'salvo que un', ['exception', 'condition'], ''),
        ],
    },
    {
        'id': 'r-es-03',
        'lang': 'es',
        'text': 'Según la bibliotecaria, el libro quizás se imprimió en 1920.',
        'gold': [
            ('Según', 'Según la', ['attribution'], ''),
            ('quizás', 'libro quizás se', ['uncertainty'], ''),
        ],
    },
    {
        'id': 'r-es-04',
        'lang': 'es',
        'text': 'Todas las salas abren el domingo excepto la del sótano.',
        'gold': [('excepto', 'domingo excepto la', ['exception'], '')],
    },
    {
        'id': 'r-es-05',
        'lang': 'es',
        'text': 'El pronóstico dice que podría nevar, aunque nadie lo sabe con certeza.',
        'gold': [
            ('dice', 'pronóstico dice que', ['attribution'], ''),
            ('podría', 'que podría nevar', ['uncertainty'], ''),
            ('nadie', 'aunque nadie lo', ['negation'], ''),
        ],
    },
    {
        'id': 'r-es-06',
        'lang': 'es',
        'text': 'Los lectores pueden llevarse dos libros siempre y cuando los devuelvan el viernes.',
        'gold': [('siempre y cuando', 'libros siempre y cuando los', ['condition'], '')],
        'distractors': [('pueden', 'lectores pueden llevarse', 'permission, not a configured topic')],
    },
    {
        'id': 'r-es-07',
        'lang': 'es',
        'text': 'El niño nada en la piscina del museo de ciencias y no se cansa.',
        'gold': [('no', 'y no se', ['negation'], '')],
        'distractors': [('nada', 'niño nada en', 'verb "nadar" (swims), not the negative pronoun')],
    },
    {
        'id': 'r-es-08',
        'lang': 'es',
        'text': 'En el supuesto de que falte el guía, la visita se aplazará.',
        'gold': [('En el supuesto de que', 'En el supuesto de que falte', ['condition'], '')],
    },
    {
        'id': 'r-es-09',
        'lang': 'es',
        'text': 'Al parecer, el reloj de la torre nunca funcionó bien.',
        'gold': [
            ('Al parecer', 'Al parecer,', ['uncertainty', 'attribution'], ''),
            ('nunca', 'torre nunca funcionó', ['negation'], ''),
        ],
    },
    {
        'id': 'r-es-10',
        'lang': 'es',
        'text': 'Según el informe del tiempo, hay que llevar paraguas.',
        'gold': [
            ('Según', 'Según el', ['attribution'], 'decomposed accent (u + U+0301)'),
            ('hay que', 'tiempo, hay que llevar', ['obligation'], ''),
        ],
        'format_features': ['decomposed_accent_in_cue'],
    },
    {
        'id': 'r-es-11',
        'lang': 'es',
        'text': 'Las fichas rojas deben quedarse en la caja; no obstante, las azules se pueden usar.',
        'gold': [('deben', 'rojas deben quedarse', ['obligation'], '')],
        'distractors': [
            ('no obstante', 'caja; no obstante,', 'concessive connective ("nevertheless"), not negation'),
            ('pueden', 'se pueden usar', 'permission, not a configured topic'),
        ],
    },
    {
        'id': 'r-es-12',
        'lang': 'es',
        'text': 'El cuadrado azul tiene cuatro lados iguales y está junto a un círculo rojo.',
        'gold': [],
    },
]


if __name__ == '__main__':
    items = [build_item(raw, 'reserved', AUTHOR, 'reserved: written before rules; never used for development') for raw in RESERVED]
    print(write_set('reserved', items), sum(len(i['gold']) for i in items), 'gold cues')
