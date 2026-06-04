import logging
import time

import aiosqlite
from bilibili_api import Credential, comment
from bilibili_api.comment import CommentResourceType
from bilibili_api.session import EventType, send_msg

logger = logging.getLogger(__name__)


async def send_comment_safe(
    conn: aiosqlite.Connection,
    text: str,
    type_: CommentResourceType,
    oid: str,
    credential: Credential,
    dry_run: bool,
    pic=None,
):
    if dry_run:
        logger.info("[DRY RUN] 跳过发送评论")
        print(f"\n{'─' * 50}")
        print(f"[DRY RUN] 将发送评论:\n{text}")
        if pic:
            print(f"[DRY RUN] 附带图片: {pic.width}x{pic.height} {pic.imageType}")
        print(f"{'─' * 50}\n")
        return
    resp = await comment.send_comment(
        text=text,
        type_=type_,
        oid=oid,
        credential=credential,
        pic=pic,
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
    await send_msg(
        credential=credential,
        receiver_id=receiver_id,
        msg_type=EventType.TEXT,
        content=content,
    )
