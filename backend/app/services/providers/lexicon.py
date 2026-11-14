"""Free, rule-based LLMProvider: curated lexicons instead of a language model.

Recommended together with ``DATA_PROVIDER=dataset`` (real reviews, no API key, no cost, no text
leaving the machine). It is deliberately simple and transparent:

* Sentiment: star rating (60%) blended with a small polarity lexicon on the text (40%), with
  simple negation handling ("not good" counts as negative).
* Pain points: a curated complaint-phrase lexicon (``PAIN_POINTS``), only counted in reviews
  rated 3 stars or less and not directly negated ("didn't leak").
* Pros / cons / opportunities: templated sentences filled from REAL counts of the praise and
  complaint phrases found. Nothing is invented; with no matches the lists are empty or fall back
  to plain star-rating counts.

Limits: English only, no sarcasm or context understanding, phrase coverage is finite.
"""

import re
from collections import Counter

from app.services.providers.base import (
    LLMProvider,
    Review,
    ReviewInsights,
    SentimentResult,
)

# Words, plus clause punctuation as separate tokens so a negator never reaches across a clause.
_TOKEN_RE = re.compile(r"[a-z0-9']+|[.,;:!?]")
_CLAUSE_BREAKS = frozenset(".,;:!?")

STAR_WEIGHT = 0.6
TEXT_WEIGHT = 0.4
POSITIVE_THRESHOLD = 0.2
NEGATIVE_THRESHOLD = -0.2
PAIN_MAX_RATING = 3  # complaints are only mined from reviews rated this or lower
PRAISE_MIN_RATING = 4
MAX_ITEMS = 3

POSITIVE_WORDS = frozenset(
    "great good excellent perfect love loved loves awesome amazing fantastic wonderful "
    "sturdy durable solid reliable recommend recommended quality comfortable easy "
    "quiet powerful efficient fast beautiful happy pleased satisfied worth useful helpful "
    "convenient effective smooth nice best impressed superb flawless handy lightweight "
    "affordable".split()
)
NEGATIVE_WORDS = frozenset(
    "bad poor terrible awful horrible worst disappointed disappointing disappointment "
    "broke broken cheap flimsy useless waste junk defective faulty return returned refund "
    "leaks leaked leaking cracked noisy loud smell smells stinks overpriced difficult "
    "uncomfortable frustrating annoying unreliable weak fails failed failure damaged "
    "regret hate hated worthless misleading".split()
)
NEGATORS = frozenset(
    "not no never don't dont doesn't doesnt didn't didnt isn't isnt wasn't wasnt "
    "wouldn't wouldnt can't cant won't wont without hardly barely".split()
)

# label -> (action used for the "opportunity" sentence, phrases). Phrases are matched as whole
# word sequences. A phrase is ignored when it is directly preceded by a negator.
PAIN_POINTS: dict[str, tuple[str, tuple[str, ...]]] = {
    "breaks easily": (
        "improve durability and build quality",
        ("broke", "broken", "fell apart", "falls apart", "cracked", "snapped", "snaps"),
    ),
    "stopped working": (
        "improve reliability and offer a warranty",
        (
            "stopped working",
            "quit working",
            "stopped functioning",
            "no longer works",
            "died after",
            "doesn't work",
            "doesnt work",
            "does not work",
            "won't turn on",
            "wont turn on",
            "dead on arrival",
            "defective",
        ),
    ),
    "cheap material": (
        "use better materials",
        (
            "cheap material",
            "cheap materials",
            "cheaply made",
            "cheap plastic",
            "flimsy",
            "poor quality",
            "low quality",
            "feels cheap",
            "poorly made",
        ),
    ),
    "too small": (
        "offer larger sizes or clearer sizing information",
        ("too small", "too short", "smaller than expected", "runs small", "tiny"),
    ),
    "too big": (
        "offer smaller sizes or clearer sizing information",
        ("too big", "too large", "too long", "bigger than expected", "runs large", "bulky"),
    ),
    "wrong fit": (
        "improve compatibility and fit information",
        (
            "doesn't fit",
            "doesnt fit",
            "does not fit",
            "wrong size",
            "not compatible",
            "incompatible",
            "wrong part",
        ),
    ),
    "leaks": ("fix sealing and leak resistance", ("leak", "leaks", "leaking", "leaked")),
    "bad smell": (
        "remove odors from the product and packaging",
        ("smell", "smells", "smelly", "odor", "stinks", "stench", "chemical smell"),
    ),
    "noisy": ("reduce operating noise", ("too loud", "noisy", "loud noise", "very loud")),
    "hard to install or use": (
        "improve instructions and ease of setup",
        (
            "hard to install",
            "difficult to install",
            "hard to use",
            "difficult to use",
            "confusing instructions",
            "poor instructions",
            "hard to assemble",
            "difficult to assemble",
        ),
    ),
    "poor customer service": (
        "improve support and returns handling",
        (
            "customer service",
            "no response",
            "never responded",
            "refused to refund",
            "hard to return",
        ),
    ),
    "damaged or missing parts": (
        "improve packaging and quality control",
        (
            "arrived damaged",
            "came damaged",
            "damaged in shipping",
            "missing parts",
            "missing piece",
            "missing pieces",
            "poor packaging",
            "arrived broken",
        ),
    ),
    "not as described": (
        "make listing photos and claims match the product",
        (
            "not as described",
            "not as pictured",
            "not as advertised",
            "misleading",
            "looks different",
            "different than the picture",
        ),
    ),
    "poor battery life": (
        "improve battery capacity",
        ("battery life", "battery dies", "drains quickly", "doesn't hold a charge"),
    ),
    "overpriced": (
        "review pricing against value",
        ("overpriced", "too expensive", "waste of money"),
    ),
}

PRAISE: dict[str, tuple[str, ...]] = {
    "easy to use": (
        "easy to use",
        "easy to install",
        "easy to set up",
        "easy setup",
        "simple to use",
    ),
    "good value": (
        "good value",
        "great value",
        "worth the money",
        "worth every penny",
        "great price",
    ),
    "sturdy and durable": (
        "sturdy",
        "durable",
        "well made",
        "well built",
        "solid build",
        "high quality",
    ),
    "works well": (
        "works great",
        "works well",
        "works perfectly",
        "works as expected",
        "works like",
    ),
    "easy to clean": ("easy to clean", "cleans easily", "easy cleanup"),
    "quiet": ("quiet", "quietly", "barely hear"),
    "good fit": ("fits perfectly", "perfect fit", "fits great", "fit perfectly"),
    "comfortable": ("comfortable", "comfy"),
    "effective": ("effective", "very effective", "made a difference"),
    "long lasting": ("long lasting", "lasts long", "has lasted", "still works"),
}


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower().replace("’", "'"))


def _negated(tokens: list[str], index: int) -> bool:
    """True if a negator sits within 2 words before ``index`` in the same clause."""
    for tok in reversed(tokens[max(0, index - 2) : index]):
        if tok in _CLAUSE_BREAKS:
            return False
        if tok in NEGATORS:
            return True
    return False


def _find_phrase(tokens: list[str], phrase: tuple[str, ...], check_negation: bool) -> bool:
    """True if ``phrase`` occurs in ``tokens`` (not directly preceded by a negator)."""
    n = len(phrase)
    for i in range(len(tokens) - n + 1):
        if tuple(tokens[i : i + n]) != phrase:
            continue
        if check_negation and phrase[0] not in NEGATORS and _negated(tokens, i):
            continue
        return True
    return False


_PAIN_PHRASES: dict[str, list[tuple[str, ...]]] = {
    label: [tuple(_tokens(p)) for p in phrases] for label, (_, phrases) in PAIN_POINTS.items()
}
_PRAISE_PHRASES: dict[str, list[tuple[str, ...]]] = {
    label: [tuple(_tokens(p)) for p in phrases] for label, phrases in PRAISE.items()
}


def _text_of(review: Review) -> list[str]:
    return _tokens(f"{review.title} {review.body}")


def text_polarity(tokens: list[str]) -> float | None:
    """-1..1 from the polarity lexicon (negation flips a hit), or None when nothing matched."""
    pos = neg = 0
    for i, tok in enumerate(tokens):
        if tok not in POSITIVE_WORDS and tok not in NEGATIVE_WORDS:
            continue
        negated = _negated(tokens, i)
        is_pos = (tok in POSITIVE_WORDS) != negated
        if is_pos:
            pos += 1
        else:
            neg += 1
    total = pos + neg
    return None if total == 0 else (pos - neg) / total


def review_score(review: Review) -> float:
    """Sentiment -1..1: stars blended with the text lexicon (stars only if no lexicon hit)."""
    star = (max(1, min(5, review.rating)) - 3) / 2
    polarity = text_polarity(_text_of(review))
    if polarity is None:
        return round(star, 2)
    return round(STAR_WEIGHT * star + TEXT_WEIGHT * polarity, 2)


def _label(score: float) -> str:
    if score > POSITIVE_THRESHOLD:
        return "positive"
    if score < NEGATIVE_THRESHOLD:
        return "negative"
    return "neutral"


def review_pain_points(review: Review) -> list[str]:
    """Complaint labels found in one review (only if it is rated <= 3 stars)."""
    if review.rating > PAIN_MAX_RATING:
        return []
    tokens = _text_of(review)
    return [
        label
        for label, phrases in _PAIN_PHRASES.items()
        if any(_find_phrase(tokens, p, True) for p in phrases)
    ]


def review_praise(review: Review) -> list[str]:
    if review.rating < PRAISE_MIN_RATING:
        return []
    tokens = _text_of(review)
    return [
        label
        for label, phrases in _PRAISE_PHRASES.items()
        if any(_find_phrase(tokens, p, True) for p in phrases)
    ]


class LexiconLLMProvider(LLMProvider):
    """Deterministic, offline sentiment/pain-point/insight provider (no model, no API key)."""

    async def analyze_sentiment(self, reviews: list[Review]) -> SentimentResult:
        if not reviews:
            return SentimentResult(score=0.0, label="neutral")
        score = round(sum(review_score(r) for r in reviews) / len(reviews), 2)
        return SentimentResult(
            score=score, label=_label(score), pain_points=await self.extract_pain_points(reviews)
        )

    async def analyze_sentiment_batch(self, reviews: list[Review]) -> list[SentimentResult]:
        """Score each review individually in one pass; result[i] belongs to reviews[i]."""
        results: list[SentimentResult] = []
        for review in reviews:
            score = review_score(review)
            results.append(
                SentimentResult(
                    score=score, label=_label(score), pain_points=review_pain_points(review)
                )
            )
        return results

    async def summarize(self, text: str, max_words: int = 100) -> str:
        return " ".join(text.split()[:max_words])

    async def extract_pain_points(self, reviews: list[Review], limit: int = 5) -> list[str]:
        counts: Counter[str] = Counter()
        for review in reviews:
            counts.update(review_pain_points(review))
        ranked = sorted(counts, key=lambda k: (-counts[k], k))
        return ranked[:limit]

    async def generate_insights(self, reviews: list[Review]) -> ReviewInsights:
        if not reviews:
            return ReviewInsights()
        total = len(reviews)
        positive = [r for r in reviews if r.rating >= PRAISE_MIN_RATING]
        critical = [r for r in reviews if r.rating <= PAIN_MAX_RATING]

        praise: Counter[str] = Counter()
        for review in positive:
            praise.update(review_praise(review))
        pros = [
            f"{label.capitalize()}: praised in {n} of {len(positive)} positive reviews"
            for label, n in sorted(praise.items(), key=lambda kv: (-kv[1], kv[0]))[:MAX_ITEMS]
        ]
        if not pros and positive:
            pros = [f"{len(positive)} of {total} reviews are rated 4-5 stars"]

        pains: Counter[str] = Counter()
        for review in critical:
            pains.update(review_pain_points(review))
        top = sorted(pains.items(), key=lambda kv: (-kv[1], kv[0]))[:MAX_ITEMS]
        cons = [
            f"{label.capitalize()}: mentioned in {n} of {len(critical)} critical reviews"
            for label, n in top
        ]
        if not cons and critical:
            cons = [f"{len(critical)} of {total} reviews are rated 3 stars or lower"]
        opportunities = [
            f"{PAIN_POINTS[label][0].capitalize()} "
            f"({n} {'complaint' if n == 1 else 'complaints'} about '{label}')"
            for label, n in top
        ]
        return ReviewInsights(pros=pros, cons=cons, opportunities=opportunities)
