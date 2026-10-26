import time

from starlette.types import ASGIApp, Message, Receive, Scope, Send


class ProcessTimeMiddleware:
    """응답 헤더에 서버 처리 시간(X-Process-Time, ms)을 남긴다.

    BaseHTTPMiddleware 대신 순수 ASGI로 구현해 요청마다 추가 태스크·스트림 래핑 비용이 없다.
    브라우저 개발자 도구나 curl -i로 느린 endpoint를 바로 확인하는 프로파일링 용도다.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started = time.perf_counter()

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                elapsed_ms = (time.perf_counter() - started) * 1000
                headers = list(message.get("headers", []))
                headers.append((b"x-process-time", f"{elapsed_ms:.1f}".encode()))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)
