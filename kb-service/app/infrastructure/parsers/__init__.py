"""Parser package bootstrap helpers."""

_REGISTRY_LOADED = False


def load_parser_registry() -> None:
    """Import parser modules once so PARSER_DISPATCH registrations execute.

    Each extractor module registers itself into ``PARSER_DISPATCH`` at import
    time (a side-effect ``PARSER_DISPATCH[mime] = ParserClass`` at module
    scope). This function imports every extractor exactly once so the dispatch
    table is fully populated before the router resolves a MIME type. Imports
    are kept inside the function (not at module top) so importing the parsers
    package does not eagerly drag in every parser's heavy dependencies.
    """
    global _REGISTRY_LOADED
    if _REGISTRY_LOADED:
        return

    from app.infrastructure.parsers.extractors import docx as _docx  # noqa: F401
    from app.infrastructure.parsers.extractors import excel as _excel  # noqa: F401
    from app.infrastructure.parsers.extractors import pdf_native as _pdf_native  # noqa: F401
    from app.infrastructure.parsers.extractors import pptx as _pptx  # noqa: F401

    _REGISTRY_LOADED = True
