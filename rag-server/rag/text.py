"""텍스트 정규화와 한국어 친화 토크나이저.

형태소 분석기 없이도 한국어 검색 재현율을 확보하기 위해
'조사 제거 단어 토큰 + 한글 글자 bigram'을 함께 색인한다.
- 단어 토큰: "외국인", "관광객"처럼 정확히 일치하면 높은 점수
- bigram: "외국인관광객"처럼 붙여 쓴 복합어도 부분 일치로 검색
"""

import html
import re
import unicodedata

TOKEN_PATTERN = re.compile(r"[0-9]+(?:\.[0-9]+)?|[a-z]+|[가-힣]+")
HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
DOT_LEADER_PATTERN = re.compile(r"[·.…∙・]{4,}")
SPACE_PATTERN = re.compile(r"[ \t 　]+")

# 길이가 긴 조사부터 제거한다.
PARTICLES = (
    "에서는", "으로는", "에게서", "이라는", "까지는",
    "에서", "으로", "에게", "에는", "이랑", "하고", "부터", "까지", "처럼", "보다", "이나", "라는",
    "의", "을", "를", "은", "는", "이", "가", "에", "와", "과", "도", "로", "만",
)
STOP_WORDS = {
    "추천", "추천해줘", "추천해주세요", "알려줘", "알려주세요", "보여줘", "보여주세요", "어디", "어떤", "대해",
    "있는", "좋은", "가볼만한", "정보", "관련", "무엇", "뭐야", "어때", "어떻게", "해줘", "주세요", "그리고",
    "있나요", "있어", "싶어", "궁금해",
}


def normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "").lower()


def strip_particle(word: str) -> str:
    for particle in PARTICLES:
        if word.endswith(particle) and len(word) > len(particle) + 1:
            return word[: -len(particle)]
    return word


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for match in TOKEN_PATTERN.finditer(normalize(text)):
        word = match.group()
        if "가" <= word[0] <= "힣":
            word = strip_particle(word)
            if len(word) >= 2 and word not in STOP_WORDS:
                tokens.append(word)
            if len(word) >= 3:
                tokens.extend(word[i:i + 2] for i in range(len(word) - 1))
        elif len(word) >= 2:
            tokens.append(word)
    return tokens


def clean_html(value: str | None) -> str:
    if not value:
        return ""
    text = HTML_TAG_PATTERN.sub(" ", value)
    return compact(html.unescape(text))


def compact(value: str | None) -> str:
    """연속 공백·줄바꿈·목차 점선을 정리한다."""
    if not value:
        return ""
    text = DOT_LEADER_PATTERN.sub(" ", str(value))
    lines = [SPACE_PATTERN.sub(" ", line).strip() for line in text.replace("\r", "\n").split("\n")]
    return "\n".join(line for line in lines if line)


def one_line(value: str | None, limit: int | None = None) -> str:
    text = " ".join(compact(value).split("\n"))
    if limit and len(text) > limit:
        return text[: limit - 1].rstrip() + "…"
    return text
