from contextlib import asynccontextmanager
 
from fastapi import FastAPI
 
from app.database import Base, engine
from app.routes import router
 
 
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()
 
 
app = FastAPI(title="Stripe Test", lifespan=lifespan)
app.include_router(router)
