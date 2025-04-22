from .factory import ParserFactory
from .lec import LECParser

# Register parsers
ParserFactory.register_parser('LEC', LECParser)
