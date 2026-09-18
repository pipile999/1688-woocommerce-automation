"""Fact-only initial names and evidence-gated SEO title recommendations."""
from app.keyword_research import candidates


def build_title(facts, primary_keyword):
    """Unverified initial English name, never a claim of measured SEO demand."""
    if primary_keyword not in candidates(facts):
        raise ValueError('Primary keyword is not supported by product facts')
    title = primary_keyword.title()
    for field in ('material', 'size', 'structure'):
        value = facts.get(field)
        if value and value.casefold() not in primary_keyword.casefold():
            return title + ' - ' + value
    return title


def build_researched_title(current_title, ranked_keywords, evidenced_options, current_primary=None):
    """Default SEO path: insufficient evidence always keeps the current title."""
    from .google_keyword_planner import recommend_title
    return recommend_title(current_title, ranked_keywords, evidenced_options, current_primary)
