"""Dev server startup wrapper — forces SelectorEventLoop on Windows for asyncpg compatibility."""
import sys

if sys.platform == "win32":
    import asyncio

    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8001, reload=False, loop="none")
