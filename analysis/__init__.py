# analysis/__init__.py
# Makes 'analysis' a package and exposes all public functions

from .logo_fetchers import (
    fetch_logo_free,
    fetch_logo_from_google,
    fetch_and_encode_logo,
    get_google_logo
)
from .api_client import openrouter_chat
from .wiki_utils import (
    get_wikipedia_summary,
    get_wikipedia_subsidiaries
)
from .event_analyzer import generate_corporate_events
from .summary_generator import generate_summary
from .description_generator import generate_description
from .management_analyzer import get_top_management
from .subsidiary_analyzer import generate_subsidiary_data

__all__ = [
    "fetch_logo_free", "fetch_logo_from_google", "fetch_and_encode_logo", "get_google_logo",
    "openrouter_chat",
    "get_wikipedia_summary", "get_wikipedia_subsidiaries",
    "generate_corporate_events",
    "generate_summary",
    "generate_description",
    "get_top_management",
    "generate_subsidiary_data"
]