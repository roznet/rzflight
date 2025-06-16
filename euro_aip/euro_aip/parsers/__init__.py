from .aip_factory import AIPParserFactory, DEFAULT_AUTHORITY as AIP_DEFAULT_AUTHORITY
from .aip_lec import LECAIPParser
from .aip_default import DefaultAIPParser
from .aip_ebc import EBCAIPParser
from .aip_esc import ESCAIPParser
from .aip_lfc import LFCAIPParser
from .aip_lic import LICAIPParser
from .procedure_factory import ProcedureParserFactory, DEFAULT_AUTHORITY as PROCEDURE_DEFAULT_AUTHORITY
from .procedure_default import DefaultProcedureParser
from .procedure_lfc import LFCProcedureParser

# Register the AIP parsers
AIPParserFactory.register_parser('LEC', LECAIPParser)
AIPParserFactory.register_parser('EBC', EBCAIPParser)
AIPParserFactory.register_parser('ESC', ESCAIPParser)
AIPParserFactory.register_parser('LFC', LFCAIPParser)
AIPParserFactory.register_parser('LIC', LICAIPParser)
AIPParserFactory.register_parser(AIP_DEFAULT_AUTHORITY, DefaultAIPParser)

# Register the procedure parsers
ProcedureParserFactory.register_parser(PROCEDURE_DEFAULT_AUTHORITY, DefaultProcedureParser)
ProcedureParserFactory.register_parser('LFC', LFCProcedureParser)

__all__ = [
    'AIPParserFactory',
    'AIP_DEFAULT_AUTHORITY',
    'LECAIPParser',
    'DefaultAIPParser',
    'EBCAIPParser',
    'ESCAIPParser',
    'ProcedureParserFactory',
    'PROCEDURE_DEFAULT_AUTHORITY',
    'DefaultProcedureParser',
    'LFCProcedureParser'
]
