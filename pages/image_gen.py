"""
DEPRECATED.

This app must not call OpenAI directly from Streamlit.
All model/tool calls go through n8n.
"""


def generate_poster_image(*args, **kwargs):  # type: ignore
    raise RuntimeError(
        "backend.image_gen.generate_poster_image is deprecated. "
        "Use n8n via backend.n8n_client.call_n8n_generate_image instead."
    )
