"""Expected results for AIP parser tests."""

EXPECTED_RESULTS = {
    'EGKB': {  # Biggin Hill
        'sections': {
            'admin': 8,
            'operational': 12,
            'handling': 7,
            'passenger': 7
        },
        'items': [
            {
                'ident': 'EGKB',
                'section': 'admin',
                'field': 'Name',
                'value': 'Biggin Hill'
            },
            {
                'ident': 'EGKB',
                'section': 'admin',
                'field': 'ICAO',
                'value': 'EGKB'
            }
        ]
    },
} 