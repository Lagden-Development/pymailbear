from jsmin import jsmin
from rcssmin import cssmin
import logging

logger = logging.getLogger(__name__)


def minify_js(js_content: str) -> str:
    """Minify JavaScript content."""
    try:
        return jsmin(js_content)
    except Exception as e:
        logger.error(f"Error minifying JavaScript: {str(e)}")
        return js_content  # Return original content on error


def minify_css(css_content: str) -> str:
    """Minify CSS content."""
    try:
        return cssmin(css_content)
    except Exception as e:
        logger.error(f"Error minifying CSS: {str(e)}")
        return css_content  # Return original content on error
