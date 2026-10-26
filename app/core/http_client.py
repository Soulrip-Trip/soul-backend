"""외부 HTTP 호출용 공유 AsyncClient.

요청마다 httpx 클라이언트를 새로 만들면 매번 TCP/TLS 연결을 새로 맺는다.
앱 수명 동안 클라이언트 하나를 재사용해 keep-alive 연결 풀을 활용한다.
"""

import httpx

_client: httpx.AsyncClient | None = None


def _create_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=httpx.Timeout(30.0, connect=5.0),
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
    )


async def startup() -> None:
    global _client
    if _client is None:
        _client = _create_client()


async def shutdown() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def get_http_client() -> httpx.AsyncClient:
    """lifespan 밖(스크립트·테스트)에서 호출돼도 동작하도록 필요 시 지연 생성한다."""
    global _client
    if _client is None:
        _client = _create_client()
    return _client
