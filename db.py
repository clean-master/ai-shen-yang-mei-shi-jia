import logging

import aiosqlite

logger = logging.getLogger(__name__)


async def init_db():
    conn = await aiosqlite.connect("data.db")
    cursor = await conn.cursor()
    await cursor.execute(
        "CREATE TABLE IF NOT EXISTS used_ids (id INTEGER PRIMARY KEY)"
    )
    await cursor.execute(
        "CREATE TABLE IF NOT EXISTS sent_comments "
        "(rpid INTEGER PRIMARY KEY, sent_at REAL, oid TEXT, oid_type INTEGER)"
    )
    await cursor.execute(
        "CREATE TABLE IF NOT EXISTS rejected_content "
        "(id INTEGER PRIMARY KEY AUTOINCREMENT, created_at REAL, reason TEXT, content TEXT, content_type TEXT, source_url TEXT)"
    )
    await conn.commit()
    return conn


async def is_processed(conn: aiosqlite.Connection, aid: str) -> bool:
    """纯检查：aid 是否已处理过，不产生副作用。"""
    cursor = await conn.execute("SELECT 1 FROM used_ids WHERE id = ?", (aid,))
    row = await cursor.fetchone()
    return row is not None


async def check_and_mark_processed(conn: aiosqlite.Connection, aid: str) -> bool:
    """检查并标记 aid 为已处理。返回 True 表示已处理过（含本次标记）。"""
    cursor = await conn.execute("SELECT 1 FROM used_ids WHERE id = ?", (aid,))
    row = await cursor.fetchone()
    if row:
        return True

    await conn.execute("INSERT INTO used_ids (id) VALUES (?)", (aid,))
    await conn.commit()
    return False
