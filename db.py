import logging
import time

import aiosqlite
from bilibili_api import session
from bilibili_api.comment import CommentResourceType
from bilibili_api import comment
from bilibili_api.session import EventType
from bilibili_api import Credential

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


async def is_already_processed(conn: aiosqlite.Connection, aid: str) -> bool:
    """Returns True if aid was already processed. If not, marks it as processed and returns False."""
    cursor = await conn.execute("SELECT 1 FROM used_ids WHERE id = ?", (aid,))
    row = await cursor.fetchone()
    if row:
        return True

    await conn.execute("INSERT INTO used_ids (id) VALUES (?)", (aid,))
    await conn.commit()
    return False


async def send_comment_safe(
    conn: aiosqlite.Connection,
    text: str,
    type_: CommentResourceType,
    oid: str,
    credential: Credential,
    dry_run: bool,
):
    if dry_run:
        logger.info("[DRY RUN] 跳过发送评论")
        print(f"\n{'─' * 50}")
        print(f"[DRY RUN] 将发送评论:\n{text}")
        print(f"{'─' * 50}\n")
        return
    resp = await comment.send_comment(
        text=text,
        type_=type_,
        oid=oid,
        credential=credential,
    )
    rpid = resp.get("rpid")
    if rpid:
        await conn.execute(
            "INSERT OR REPLACE INTO sent_comments (rpid, sent_at, oid, oid_type) VALUES (?, ?, ?, ?)",
            (rpid, time.time(), oid, type_.value),
        )
        await conn.commit()
        logger.info("评论已发送 rpid=%s oid=%s", rpid, oid)
    return resp


async def send_msg_safe(
    credential: Credential,
    receiver_id: int,
    content: str,
    dry_run: bool,
):
    if dry_run:
        logger.info("[DRY RUN] 跳过发送私信")
        print(f"\n{'─' * 50}")
        print(f"[DRY RUN] 将发送私信:\n{content}")
        print(f"{'─' * 50}\n")
        return
    await session.send_msg(
        credential=credential,
        receiver_id=receiver_id,
        msg_type=EventType.TEXT,
        content=content,
    )
