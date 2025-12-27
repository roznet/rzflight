from .aip_factory import AIPParserFactory, DEFAULT_AUTHORITY as AIP_DEFAULT_AUTHORITY
from .aip_lec import LECAIPParser
from .aip_default import DefaultAIPParser
from .aip_ebc import EBCAIPParser
from .aip_esc import ESCAIPParser
from .aip_lfc import LFCAIPParser, LFCHTMLParser
from .aip_lic import LICAIPParser
from .aip_lkc import LKCAIPParser
from .aip_ekc import EKCAIPParser
from .aip_egc import EGCAIPParser
from .aip_enc import ENCAIPParser
from .aip_dual import DualFormatAIPParser
from .bordercrossing import BorderCrossingParser
from .procedure_factory import ProcedureParserFactory, DEFAULT_AUTHORITY as PROCEDURE_DEFAULT_AUTHORITY
from .procedure_default import DefaultProcedureParser
from .procedure_lfc import LFCProcedureParser
from .procedure_egc import EGCProcedureParser

# Register the general AIP parsers
AIPParserFactory.register_pdf_parser('LEC', LECAIPParser)
AIPParserFactory.register_pdf_parser('EBC', EBCAIPParser)
AIPParserFactory.register_pdf_parser('ESC', ESCAIPParser)
AIPParserFactory.register_pdf_parser('LFC', LFCAIPParser)
AIPParserFactory.register_html_parser('LFC', LFCHTMLParser)
AIPParserFactory.register_pdf_parser('LIC', LICAIPParser)
AIPParserFactory.register_pdf_parser('LKC', LKCAIPParser)
AIPParserFactory.register_pdf_parser('EKC', EKCAIPParser)
AIPParserFactory.register_pdf_parser(AIP_DEFAULT_AUTHORITY, DefaultAIPParser)

# Register HTML and PDF parsers for EGC (UK)
AIPParserFactory.register_html_parser('EGC', EGCAIPParser)
AIPParserFactory.register_pdf_parser('EGC', DefaultAIPParser)

# Register HTML parser for ENC (Norway) - same Eurocontrol format as UK
AIPParserFactory.register_html_parser('ENC', ENCAIPParser)
AIPParserFactory.register_pdf_parser('ENC', DefaultAIPParser)

# Register the procedure parsers
ProcedureParserFactory.register_parser(PROCEDURE_DEFAULT_AUTHORITY, DefaultProcedureParser)
ProcedureParserFactory.register_parser('LFC', LFCProcedureParser)
ProcedureParserFactory.register_parser('EGC', EGCProcedureParser)
ProcedureParserFactory.register_parser('ENC', EGCProcedureParser)  # Norway uses same format as UK

__all__ = [
    'AIPParserFactory',
    'AIP_DEFAULT_AUTHORITY',
    'LECAIPParser',
    'DefaultAIPParser',
    'EBCAIPParser',
    'ESCAIPParser',
    'LFCAIPParser',
    'LICAIPParser',
    'LKCAIPParser',
    'EKCAIPParser',
    'EGCAIPParser',
    'ENCAIPParser',
    'DualFormatAIPParser',
    'BorderCrossingParser',
    'ProcedureParserFactory',
    'PROCEDURE_DEFAULT_AUTHORITY',
    'DefaultProcedureParser',
    'LFCProcedureParser'
]
