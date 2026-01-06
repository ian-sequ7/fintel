"""
JSON API response types.

Structured responses for web API consumption.
Can be used with FastAPI, Flask, or any web framework.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from domain import (
    StockPick,
    Risk,
    ScoredNewsItem,
    MacroIndicator,
    ConvictionScore,
)
from .report import ReportData


# ============================================================================
# Response Models
# ============================================================================

class PaginationMetadata(BaseModel):
    """Pagination metadata for API responses."""
    total: int
    offset: int
    limit: int
    has_more: bool


class StockPickResponse(BaseModel):
    """API response for a stock pick."""
    ticker: str
    timeframe: str
    conviction_score: float
    thesis: str
    risk_factors: list[str]
    entry_price: float | None = None
    target_price: float | None = None
    upside_percent: float | None = None


class MacroRiskResponse(BaseModel):
    """API response for a macro risk."""
    name: str
    category: str
    description: str
    severity: float
    probability: float
    risk_score: float
    source_indicator: str | None = None


class MacroIndicatorResponse(BaseModel):
    """API response for a macro indicator."""
    name: str
    series_id: str | None = None
    current_value: float
    previous_value: float | None = None
    unit: str
    trend: str
    impact: str
    change_percent: float | None = None


class NewsItemResponse(BaseModel):
    """API response for a news item."""
    title: str
    source: str
    url: str | None = None
    published: datetime
    relevance_score: float
    priority: str
    category: str
    sector: str | None = None
    tickers_mentioned: list[str]
    keywords: list[str]


class ConvictionScoreResponse(BaseModel):
    """API response for conviction score breakdown."""
    overall: float
    valuation_score: float
    growth_score: float
    quality_score: float
    momentum_score: float
    macro_adjustment: float
    confidence: float
    factors_used: list[str]


class PaginatedPicksResponse(BaseModel):
    """Paginated stock picks response."""
    data: list[StockPickResponse]
    pagination: PaginationMetadata


class PaginatedNewsResponse(BaseModel):
    """Paginated news response."""
    data: list[NewsItemResponse]
    pagination: PaginationMetadata


class ReportResponse(BaseModel):
    """Full report API response."""
    generated_at: datetime
    title: str

    # Macro section
    macro_indicators: list[MacroIndicatorResponse]
    macro_risks: list[MacroRiskResponse]

    # Picks by timeframe
    short_term_picks: list[StockPickResponse]
    medium_term_picks: list[StockPickResponse]
    long_term_picks: list[StockPickResponse]

    # News
    market_news: list[NewsItemResponse]
    company_news: list[NewsItemResponse]

    # Metadata
    watchlist: list[str]
    total_picks: int
    total_news: int


# ============================================================================
# Conversion Functions
# ============================================================================

def _pick_to_response(pick: StockPick) -> StockPickResponse:
    """Convert StockPick to API response."""
    upside = None
    if pick.entry_price and pick.target_price:
        upside = ((pick.target_price - pick.entry_price) / pick.entry_price) * 100

    return StockPickResponse(
        ticker=pick.ticker,
        timeframe=pick.timeframe.value,
        conviction_score=pick.conviction_score,
        thesis=pick.thesis,
        risk_factors=pick.risk_factors,
        entry_price=pick.entry_price,
        target_price=pick.target_price,
        upside_percent=round(upside, 2) if upside else None,
    )


def _risk_to_response(risk: Risk) -> MacroRiskResponse:
    """Convert Risk to API response."""
    return MacroRiskResponse(
        name=risk.name,
        category=risk.category.value,
        description=risk.description,
        severity=risk.severity,
        probability=risk.probability,
        risk_score=risk.risk_score,
        source_indicator=risk.source_indicator,
    )


def _indicator_to_response(ind: MacroIndicator) -> MacroIndicatorResponse:
    """Convert MacroIndicator to API response."""
    return MacroIndicatorResponse(
        name=ind.name,
        series_id=ind.series_id,
        current_value=ind.current_value,
        previous_value=ind.previous_value,
        unit=ind.unit,
        trend=ind.trend.value,
        impact=ind.impact_assessment.value,
        change_percent=ind.change_percent,
    )


def _news_to_response(item: ScoredNewsItem) -> NewsItemResponse:
    """Convert ScoredNewsItem to API response."""
    return NewsItemResponse(
        title=item.title,
        source=item.source,
        url=item.url,
        published=item.published,
        relevance_score=item.relevance_score,
        priority=item.priority.value,
        category=item.category.value,
        sector=item.sector,
        tickers_mentioned=item.tickers_mentioned,
        keywords=item.keywords_found,
    )


def to_api_response(data: ReportData) -> ReportResponse:
    """
    Convert ReportData to API response.

    Args:
        data: Report data from analyzers

    Returns:
        Structured API response
    """
    short_picks = [_pick_to_response(p) for p in data.short_term_picks]
    medium_picks = [_pick_to_response(p) for p in data.medium_term_picks]
    long_picks = [_pick_to_response(p) for p in data.long_term_picks]

    return ReportResponse(
        generated_at=data.generated_at,
        title=data.title,
        macro_indicators=[_indicator_to_response(i) for i in data.macro_indicators],
        macro_risks=[_risk_to_response(r) for r in data.macro_risks],
        short_term_picks=short_picks,
        medium_term_picks=medium_picks,
        long_term_picks=long_picks,
        market_news=[_news_to_response(n) for n in data.market_news],
        company_news=[_news_to_response(n) for n in data.company_news],
        watchlist=data.watchlist,
        total_picks=len(short_picks) + len(medium_picks) + len(long_picks),
        total_news=len(data.market_news) + len(data.company_news),
    )


def to_json(data: ReportData) -> dict[str, Any]:
    """
    Convert ReportData to JSON-serializable dict.

    Args:
        data: Report data

    Returns:
        JSON-serializable dictionary
    """
    response = to_api_response(data)
    return response.model_dump(mode="json")


def get_paginated_picks(
    data: ReportData,
    timeframe: str,
    offset: int = 0,
    limit: int = 20,
) -> PaginatedPicksResponse:
    """
    Get paginated stock picks for a specific timeframe.

    Args:
        data: Report data
        timeframe: Timeframe to filter ('short', 'medium', 'long', or 'all')
        offset: Number of picks to skip (default: 0)
        limit: Maximum picks to return (default: 20)

    Returns:
        Paginated picks response with metadata
    """
    # Select picks based on timeframe
    if timeframe == "short":
        picks = data.short_term_picks
    elif timeframe == "medium":
        picks = data.medium_term_picks
    elif timeframe == "long":
        picks = data.long_term_picks
    elif timeframe == "all":
        picks = data.short_term_picks + data.medium_term_picks + data.long_term_picks
    else:
        picks = []

    total = len(picks)
    paginated_picks = picks[offset:offset + limit]
    has_more = offset + limit < total

    return PaginatedPicksResponse(
        data=[_pick_to_response(p) for p in paginated_picks],
        pagination=PaginationMetadata(
            total=total,
            offset=offset,
            limit=limit,
            has_more=has_more,
        ),
    )


def get_paginated_news(
    data: ReportData,
    category: str,
    offset: int = 0,
    limit: int = 20,
) -> PaginatedNewsResponse:
    """
    Get paginated news items for a specific category.

    Args:
        data: Report data
        category: News category ('market', 'company', or 'all')
        offset: Number of news items to skip (default: 0)
        limit: Maximum news items to return (default: 20)

    Returns:
        Paginated news response with metadata
    """
    # Select news based on category
    if category == "market":
        news = data.market_news
    elif category == "company":
        news = data.company_news
    elif category == "all":
        news = data.market_news + data.company_news
    else:
        news = []

    total = len(news)
    paginated_news = news[offset:offset + limit]
    has_more = offset + limit < total

    return PaginatedNewsResponse(
        data=[_news_to_response(n) for n in paginated_news],
        pagination=PaginationMetadata(
            total=total,
            offset=offset,
            limit=limit,
            has_more=has_more,
        ),
    )
