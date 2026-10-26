import json
from datetime import date

from anyio import to_thread
from openai import AsyncOpenAI
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.cache import TTLCache
from app.core.config import get_settings
from app.db.models import FestivalSchedule, Location
from app.schemas.ai_insight import TodayInsightResponse


settings = get_settings()


class AIInsightConfigError(RuntimeError):
    """서버 설정(OPENAI_API_KEY) 문제. 사용자 입력 오류가 아니므로 503으로 응답한다."""


class AIInsightDataError(RuntimeError):
    """인사이트를 만들 관광 데이터가 없다."""


class AIInsightResponseError(RuntimeError):
    """OpenAI 응답이 비었거나 JSON Schema·이미지 규칙을 지키지 않았다."""


SYSTEM_PROMPT = """
너는 Soulrip 서비스의 서울 관광 데이터 분석 AI다.

입력된 관광 데이터를 분석하여 혼자 여행하는 사용자를 위한
"오늘의 AI 인사이트"를 생성한다.

규칙
- 입력 데이터만 사용한다.
- 없는 정보는 추측하지 않는다.
- 혼자 여행하기 좋은 관점에서 추천한다.
- 각 항목의 headline은 15자 이내로 작성한다.
- description은 반드시 1문장으로 작성한다.
- image_url은 반드시 입력 데이터에 포함된 이미지 URL 중 하나를 그대로 사용한다.
- 이미지 URL을 새로 만들거나 일부를 수정하지 않는다.
- 각 인사이트 내용과 가장 관련 있는 이미지를 선택한다.
- 가능하면 네 항목에 서로 다른 이미지를 사용한다.
- 출력은 반드시 지정된 JSON Schema만 사용한다.
""".strip()


TODAY_INSIGHT_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "label": {
            "type": "string",
        },
        "headline": {
            "type": "string",
        },
        "description": {
            "type": "string",
        },
        "image_url": {
            "type": "string",
        },
    },
    "required": [
        "label",
        "headline",
        "description",
        "image_url",
    ],
    "additionalProperties": False,
}


TODAY_INSIGHT_SCHEMA = {
    "type": "object",
    "properties": {
        "today": TODAY_INSIGHT_ITEM_SCHEMA,
        "time": TODAY_INSIGHT_ITEM_SCHEMA,
        "place": TODAY_INSIGHT_ITEM_SCHEMA,
        "tip": TODAY_INSIGHT_ITEM_SCHEMA,
    },
    "required": [
        "today",
        "time",
        "place",
        "tip",
    ],
    "additionalProperties": False,
}


class AIInsightService:
    def __init__(self) -> None:
        # 모듈 import 시점에 키를 검사하면 키가 없을 때 앱 전체가 기동하지 못한다.
        # 클라이언트는 첫 요청에서 만들고, 키가 없으면 해당 요청만 503으로 실패시킨다.
        self._client: AsyncOpenAI | None = None
        self._cache = TTLCache("ai-insight", maxsize=4, ttl=settings.ai_insight_cache_ttl_seconds)

    @property
    def client(self) -> AsyncOpenAI:
        if not settings.openai_api_key:
            raise AIInsightConfigError("OPENAI_API_KEY가 설정되지 않았습니다.")
        if self._client is None:
            self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        return self._client

    async def create_today_insight(
        self,
        db: Session,
    ) -> TodayInsightResponse:
        client = self.client
        cache_key = date.today().isoformat()
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        # 동기 SQLAlchemy 조회는 이벤트 루프를 막지 않도록 스레드에서 실행한다.
        compact_places, compact_festivals = await to_thread.run_sync(self._load_tourism_data, db)
        result = await self._generate(client, compact_places, compact_festivals)
        self._cache.set(cache_key, result)
        return result

    @staticmethod
    def _load_tourism_data(db: Session) -> tuple[list[dict], list[dict]]:
        # 이미지가 있는 일반 관광지 중 랜덤 8개
        places = (
            db.query(Location)
            .filter(
                Location.content_type_id != 15,
                Location.first_image.is_not(None),
                Location.first_image != "",
            )
            .order_by(func.random())
            .limit(8)
            .all()
        )

        # 현재 진행 중이거나 앞으로 열릴 축제 중 랜덤 4개
        festivals = (
            db.query(FestivalSchedule)
            .join(FestivalSchedule.location)
            .options(
                joinedload(FestivalSchedule.location)
            )
            .filter(
                FestivalSchedule.end_date >= date.today(),
                Location.first_image.is_not(None),
                Location.first_image != "",
            )
            .order_by(func.random())
            .limit(4)
            .all()
        )

        compact_places = [
            {
                "name": place.title,
                "content_type": place.content_type,
                "address": " ".join(
                    part
                    for part in [
                        place.addr1,
                        place.addr2,
                    ]
                    if part
                ),
                "district": place.district,
                "description": (
                    place.description[:150]
                    if place.description
                    else None
                ),
                "solo_score": place.solo_score,
                "category": (
                    place.cat3
                    or place.cat2
                    or place.cat1
                    or place.lcls3
                    or place.lcls2
                    or place.lcls1
                ),
                "image_url": place.first_image,
            }
            for place in places
        ]

        compact_festivals = [
            {
                "name": festival.location.title,
                "address": " ".join(
                    part
                    for part in [
                        festival.location.addr1,
                        festival.location.addr2,
                    ]
                    if part
                ),
                "district": festival.location.district,
                "start_date": festival.start_date.isoformat(),
                "end_date": festival.end_date.isoformat(),
                "category": festival.category,
                "description": (
                    (
                        festival.description
                        or festival.location.description
                    )[:150]
                    if (
                        festival.description
                        or festival.location.description
                    )
                    else None
                ),
                "image_url": festival.location.first_image,
            }
            for festival in festivals
        ]

        return compact_places, compact_festivals

    async def _generate(
        self,
        client: AsyncOpenAI,
        compact_places: list[dict],
        compact_festivals: list[dict],
    ) -> TodayInsightResponse:
        tourism_data = {
            "analysis_date": date.today().isoformat(),
            "places": compact_places,
            "festivals": compact_festivals,
        }

        if not compact_places and not compact_festivals:
            raise AIInsightDataError(
                "이미지가 포함된 관광 데이터가 없습니다."
            )

        tourism_json = json.dumps(
            tourism_data,
            ensure_ascii=False,
            default=str,
        )

        user_prompt = f"""
다음 서울 관광 데이터만 사용하여 오늘의 AI 인사이트를 생성하라.

관광 데이터:
{tourism_json}

항목별 작성 기준

1. today
- 입력된 장소와 축제 중 오늘 혼자 가볼 만한 대상 하나를 추천한다.
- label은 "오늘 추천"처럼 작성한다.
- headline에는 추천 대상의 핵심 특징을 15자 이내로 작성한다.
- description에는 오늘 추천하는 이유를 1문장으로 작성한다.
- 입력 데이터에 존재하는 장소명 또는 축제명만 사용한다.
- image_url은 추천 대상의 image_url과 반드시 일치해야 한다.

2. time
- 현재 날짜와 축제 시작일, 종료일을 근거로 작성한다.
- 진행 중인 축제가 있으면 우선 소개한다.
- 진행 중인 축제가 없다면 가장 가까운 예정 축제를 소개한다.
- 축제 데이터가 없다면 입력된 장소 중 하나를 추천한다.
- 운영시간이나 혼잡 시간은 추측하지 않는다.
- image_url은 선택한 축제 또는 장소의 image_url을 사용한다.

3. place
- solo_score, 장소 유형, 주소, 설명을 참고하여
  혼자 방문하기 좋은 장소 하나를 추천한다.
- 입력 데이터에 존재하는 장소명만 사용한다.
- image_url은 추천한 장소의 image_url과 반드시 일치해야 한다.

4. tip
- today, time, place 항목에서 선택한 장소나 축제를 바탕으로
  혼자 여행하는 사용자를 위한 실용적인 팁을 작성한다.
- 운영시간, 혼잡도, 날씨, 교통 상황처럼
  입력 데이터에 없는 내용은 추측하지 않는다.
- 주소 또는 지역 정보를 활용한 동선 팁은 작성할 수 있다.
- image_url은 팁의 근거가 된 장소 또는 축제 이미지를 사용한다.

이미지 규칙
- image_url은 입력 데이터에 있는 값을 그대로 사용한다.
- URL의 문자를 변경하거나 새로운 URL을 생성하지 않는다.
- 빈 문자열을 사용하지 않는다.
- 가능하면 네 항목에서 서로 다른 이미지를 사용한다.
""".strip()

        response = await client.responses.create(
            model=settings.openai_model,
            instructions=SYSTEM_PROMPT,
            input=user_prompt,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "today_insight_response",
                    "strict": True,
                    "schema": TODAY_INSIGHT_SCHEMA,
                }
            },
        )

        output_text = response.output_text.strip()

        if not output_text:
            raise AIInsightResponseError(
                "OpenAI 응답 내용이 비어 있습니다."
            )

        try:
            result = json.loads(output_text)
        except json.JSONDecodeError as error:
            raise AIInsightResponseError(
                "OpenAI 응답을 JSON으로 변환하지 못했습니다."
            ) from error

        allowed_image_urls = {
            item["image_url"]
            for item in (
                compact_places
                + compact_festivals
            )
            if item.get("image_url")
        }

        for key in [
            "today",
            "time",
            "place",
            "tip",
        ]:
            item = result.get(key)

            if not isinstance(item, dict):
                raise AIInsightResponseError(
                    f"{key} 항목이 응답에 없습니다."
                )

            image_url = item.get("image_url")

            if image_url not in allowed_image_urls:
                raise AIInsightResponseError(
                    f"{key} 항목의 이미지 URL이 "
                    "입력 데이터에 없습니다."
                )

        return TodayInsightResponse.model_validate(
            result
        )


ai_insight_service = AIInsightService()