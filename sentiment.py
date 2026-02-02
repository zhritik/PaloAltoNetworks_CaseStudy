# Sentiment (VADER) and theme extraction for journal entries.
import re
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_analyzer = SentimentIntensityAnalyzer()

STOPWORDS = frozenset([
    'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', 'your', 'yours',
    'yourself', 'yourselves', 'he', 'him', 'his', 'himself', 'she', 'her', 'hers', 'herself',
    'it', 'its', 'itself', 'they', 'them', 'their', 'theirs', 'themselves', 'what', 'which',
    'who', 'whom', 'this', 'that', 'these', 'those', 'am', 'is', 'are', 'was', 'were', 'be',
    'been', 'being', 'have', 'has', 'had', 'having', 'do', 'does', 'did', 'doing', 'a', 'an',
    'the', 'and', 'but', 'if', 'or', 'because', 'as', 'until', 'while', 'of', 'at', 'by',
    'for', 'with', 'about', 'against', 'between', 'into', 'through', 'during', 'before',
    'after', 'above', 'below', 'to', 'from', 'up', 'down', 'in', 'out', 'on', 'off', 'over',
    'under', 'again', 'further', 'then', 'once', 'here', 'there', 'when', 'where', 'why',
    'how', 'all', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not',
    'only', 'own', 'same', 'so', 'than', 'too', 'very', 's', 't', 'can', 'will', 'just',
    'don', 'should', 'now', 'd', 'll', 'm', 'o', 're', 've', 'y', 'ain', 'aren', 'couldn',
    'didn', 'doesn', 'hadn', 'hasn', 'haven', 'isn', 'ma', 'mightn', 'mustn', 'needn',
    'shan', 'shouldn', 'wasn', 'weren', 'won', 'wouldn', 'day', 'days', 'today', 'tomorrow',
    'way', 'one', 'back', 'still', 'maybe', 'just', 'really', 'feel', 'feels', 'felt', 'feeling', 'feelings',
    'time', 'times', 'moment', 'moments', 'thought', 'thoughts', 'mind', 'like', 'right', 'wrong',
    'long', 'short', 'new', 'old', 'first', 'last', 'same', 'different', 'whole', 'real', 'sure',
    'much', 'many', 'little', 'few', 'lot', 'bit', 'yesterday', 'thing', 'things', 'something', 'nothing',
    'kind', 'sort', 'actually', 'probably', 'perhaps', 'already', 'even', 'again', 'once',
    'always', 'never', 'often', 'sometimes', 'usually', 'someone', 'everything', 'anything',
])



MAX_THEMES_PER_ENTRY = 8
MIN_WORD_LENGTH = 2


def analyze_sentiment(text: str) -> dict:
    if not (text or "").strip():
        return {"score": 0, "comparative": 0, "label": "neutral"}
    s = _analyzer.polarity_scores(text.strip())
    score = s["compound"] * 5
    comparative = s["compound"]
    label = "neutral"
    if comparative > 0.1:
        label = "positive"
    elif comparative < -0.1:
        label = "negative"
    return {"score": score, "comparative": comparative, "label": label}


def _normalize(word: str) -> str:
    return word.lower().replace("'", "").strip()


def extract_themes(text: str) -> list:
    if not (text or "").strip():
        return []
    text = text.strip()
    words = re.findall(r"[a-zA-Z'][a-zA-Z0-9']*|[a-zA-Z]{2,}", text)
    terms = []
    stop = STOPWORDS 
    for w in words:
        n = _normalize(w)
        if len(n) >= MIN_WORD_LENGTH and n not in stop:
            terms.append(n)
    counts = {}
    for t in terms:
        counts[t] = counts.get(t, 0) + 1
    sorted_terms = sorted(counts.items(), key=lambda x: -x[1])[:MAX_THEMES_PER_ENTRY]
    return [t for t, _ in sorted_terms]


def aggregate_themes(entries: list) -> list:
    counts = {}
    for e in entries:
        for t in (e.get("themes") or []):
            key = t.lower()
            counts[key] = counts.get(key, 0) + 1
    return sorted([{"theme": k, "count": v} for k, v in counts.items() if v >= 1], key=lambda x: -x["count"])
