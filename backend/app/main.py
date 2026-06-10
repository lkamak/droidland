import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router
from .context import AppContext, build_context

logging.basicConfig(level=logging.INFO)


def create_app(context: AppContext | None = None, start_background: bool = True) -> FastAPI:
    ctx = context or build_context()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if start_background and ctx.poller.connectors:
            ctx.poller.start()
        if start_background and ctx.settings.factory_enabled:
            ctx.observability.start()
        try:
            yield
        finally:
            await ctx.poller.stop()
            await ctx.observability.stop()

    app = FastAPI(title="Droidland", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.ctx = ctx
    app.include_router(router)
    return app


app = create_app()
