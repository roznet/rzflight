from .factory import ParserFactory, DEFAULT_AUTHORITY
from .lec import LECParser
from .default import DefaultParser

# Register the parsers
ParserFactory.register_parser('LEC', LECParser)
ParserFactory.register_parser(DEFAULT_AUTHORITY, DefaultParser)

__all__ = ['ParserFactory', 'DEFAULT_AUTHORITY', 'LECParser', 'DefaultParser']
