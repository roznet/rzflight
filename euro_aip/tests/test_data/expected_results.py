"""Expected results for AIP parser tests."""

EXPECTED_RESULTS = {
    'LFPO': {  # Paris Orly
        'sections': {
            'admin': 4,
            'operational': 6,
            'handling': 3,
            'passenger': 2
        },
        'items': [
            {
                'ident': 'LFPO',
                'section': 'admin',
                'field': 'Name',
                'value': 'Paris Orly'
            },
            {
                'ident': 'LFPO',
                'section': 'admin',
                'field': 'ICAO',
                'value': 'LFPO'
            }
        ]
    },
    'EGLL': {  # London Heathrow
        'sections': {
            'admin': 4,
            'operational': 6,
            'handling': 3,
            'passenger': 2
        },
        'items': [
            {
                'ident': 'EGLL',
                'section': 'admin',
                'field': 'Name',
                'value': 'London Heathrow'
            },
            {
                'ident': 'EGLL',
                'section': 'admin',
                'field': 'ICAO',
                'value': 'EGLL'
            }
        ]
    }
} 