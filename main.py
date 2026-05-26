import argparse
import asyncio
import logging
import sys

from bilibili_api import Credential, session
from bilibili_api.comment import CommentResourceType
from bilibili_api.opus import Opus
from bilibili_api.session import EventType

from api_clients import APIError
from auth import do_login
from db import init_db, is_already_processed, send_comment_safe, send_msg_safe
from prompts import FALLBACK_SUMMARY
from settings import settings
from summarizer import _fetch_opus_data, get_summary_from_dynamic, get_summary_from_video, moderate_summary
from tmp import clean_tmp

import video_id_transform

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def _make_credential() -> Credential:
    return Credential(
        sessdata=settings.sessdata,
        bili_jct=settings.bili_jct,
        buvid3=settings.buvid3 or None,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bilibili 自动回复机器人",
        epilog="无参数时以正常模式轮询 @消息",
    )
    parser.add_argument(
        "--dry-run",
        "-d",
        action="store_true",
        help="测试模式：跑通所有流程但不发送评论和私信",
    )
    parser.add_argument(
        "--bv",
        metavar="BVID",
        help="直接处理指定 BV 号视频（不轮询 @消息）",
    )
    parser.add_argument(
        "--dynamic-text",
        metavar="TEXT",
        help="直接处理指定动态文本（不轮询 @消息）",
    )
    parser.add_argument(
        "--opus",
        metavar="OPUS_ID",
        type=int,
        help="直接处理指定 opus ID（不轮询 @消息）",
    )
    parser.add_argument(
        "--uid",
        type=int,
        default=0,
        metavar="UID",
        help="指定接收私信的用户 UID（与 --bv / --opus / --dynamic-text 配合使用）",
    )
    parser.add_argument(
        "--login",
        action="store_true",
        help="扫码登录 Bilibili，将凭据保存到 .env 文件",
    )
    return parser


async def process_video(
    conn,
    credential: Credential,
    bvid: str,
    user_nickname: str,
    dry_run: bool,
    target_uid: int = 0,
):
    aid = video_id_transform.note_query_2_aid(bvid)
    logger.info("处理视频: %s aid=%s user=%s", bvid, aid, user_nickname)

    if not dry_run and await is_already_processed(conn, aid):
        logger.info("aid=%s 已处理过，跳过", aid)
        return
    summary = await get_summary_from_video(bvid)
    summary = await moderate_summary(conn, summary, "video")
    if summary is None:
        summary = FALLBACK_SUMMARY
    summary = f"{summary}\n@{user_nickname} 问的。"

    await send_comment_safe(
        conn,
        text=summary,
        type_=CommentResourceType.VIDEO,
        oid=bvid,
        credential=credential,
        dry_run=dry_run,
    )

    summary = f"{summary}\nhttps://www.bilibili.com/video/{bvid}"
    await send_msg_safe(
        credential=credential,
        receiver_id=target_uid,
        content=summary,
        dry_run=dry_run,
    )


async def process_dynamic(
    conn,
    credential: Credential,
    opus_id: int,
    user_nickname: str,
    dynamic_text: str,
    dry_run: bool,
    target_uid: int = 0,
    image_urls: list[str] | None = None,
):
    op = Opus(opus_id=opus_id, credential=credential)
    logger.info("[动态] process_dynamic: 开始 get_rid opus_id=%d", opus_id)
    aid = await op.get_rid()
    logger.info("[动态] get_rid 成功: opus_id=%d → aid=%s", opus_id, aid)

    if not dry_run and await is_already_processed(conn, aid):
        logger.info("aid=%s 已处理过，跳过", aid)
        return
    summary = await get_summary_from_dynamic(dynamic_text, image_urls=image_urls)
    summary = await moderate_summary(conn, summary, "dynamic")
    if summary is None:
        summary = FALLBACK_SUMMARY
    summary = f"{summary}\n@{user_nickname} 问的。"

    await send_comment_safe(
        conn,
        text=summary,
        type_=CommentResourceType.DYNAMIC_DRAW,
        oid=aid,
        credential=credential,
        dry_run=dry_run,
    )
    await send_comment_safe(
        conn,
        text=summary,
        type_=CommentResourceType.DYNAMIC,
        oid=aid,
        credential=credential,
        dry_run=dry_run,
    )

    summary = f"{summary}\nhttps://t.bilibili.com/{opus_id}"
    await send_msg_safe(
        credential=credential,
        receiver_id=target_uid,
        content=summary,
        dry_run=dry_run,
    )


async def main_loop(dry_run: bool = False):
    conn = await init_db()
    try:
        credential = _make_credential()

        while True:
            try:
                clean_tmp()
                logger.info("[轮询] 开始获取 @消息 ...")
                sessions = await session.get_at(credential=credential)
                items = sessions.get("items", [])
                logger.info("[轮询] @消息获取成功: items_count=%d keys=%s",
                            len(items), list(sessions.keys())[:10])
                if not items:
                    await asyncio.sleep(10)
                    continue

                first_item = items[0]
                user_nickname = first_item["user"]["nickname"]
                source_content = first_item["item"]["source_content"]
                uri = first_item["item"]["uri"]
                mid = first_item["user"]["mid"]
                logger.info(
                    "[轮询] 处理消息: user=%s mid=%s uri=%s source_content_len=%d item_keys=%s",
                    user_nickname, mid, uri,
                    len(source_content) if source_content else 0,
                    list(first_item["item"].keys())[:10],
                )

                at_count = source_content.count("@") if source_content else 0
                if settings.max_at_count > 0 and at_count > settings.max_at_count:
                    logger.info(
                        "[轮询] 跳过: @数量=%d 超过限制=%d user=%s",
                        at_count, settings.max_at_count, user_nickname,
                    )
                    await asyncio.sleep(10)
                    continue

                if "BV" in uri:
                    bvid = "BV" + uri.split("BV")[1]
                    await process_video(
                        conn, credential, bvid, user_nickname, dry_run, target_uid=mid
                    )
                elif "opus/" in uri or "https://t.bilibili.com/" in uri:
                    if "opus/" in uri:
                        opus_id_num = int(uri.rsplit("opus/", 1)[-1].split("?")[0])
                    else:
                        opus_id_str = uri.split("https://t.bilibili.com/")[1]
                        opus_id_num = int(opus_id_str.strip("/").split("/")[-1])
                    logger.info("[动态] uri=%s → opus_id=%d", uri, opus_id_num)
                    dynamic_text, image_urls = await _fetch_opus_data(opus_id_num, credential)
                    await process_dynamic(
                        conn, credential, opus_id_num, user_nickname, dynamic_text,
                        dry_run, target_uid=mid, image_urls=image_urls or None,
                    )
                else:
                    continue

                await asyncio.sleep(10)

            except asyncio.CancelledError:
                raise
            except APIError as exc:
                logger.error("API call failed: %s", exc)
                await asyncio.sleep(20)
            except TimeoutError as exc:
                logger.error("Request timeout: %s", exc)
                await asyncio.sleep(20)
            except Exception as exc:
                if "500 Server Error" in str(exc):
                    logger.warning("Bilibili 500 error, skipping")
                else:
                    logger.exception("Unhandled error in main loop")
                await asyncio.sleep(20)

    finally:
        await conn.close()


async def main_bv(bvid: str, dry_run: bool = False, target_uid: int = 0):
    conn = await init_db()
    try:
        credential = _make_credential()
        await process_video(
            conn, credential, bvid, "CLI用户", dry_run, target_uid=target_uid
        )
    finally:
        await conn.close()


async def main_dynamic(text: str, dry_run: bool = False, target_uid: int = 0):
    conn = await init_db()
    try:
        credential = _make_credential()
        await process_dynamic(
            conn, credential, 0, "CLI用户", text, dry_run, target_uid=target_uid
        )
    finally:
        await conn.close()


async def main_opus(opus_id: int, dry_run: bool = False, target_uid: int = 0):
    conn = await init_db()
    try:
        credential = _make_credential()
        dynamic_text, image_urls = await _fetch_opus_data(opus_id, credential)
        await process_dynamic(
            conn, credential, opus_id, "CLI用户", dynamic_text,
            dry_run, target_uid=target_uid, image_urls=image_urls or None,
        )
    finally:
        await conn.close()


async def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.login:
        await do_login()
        return

    if not settings.is_configured:
        settings.validate()

    if args.bv and args.dynamic_text:
        logger.error("不能同时指定 --bv 和 --dynamic-text")
        sys.exit(1)
    if args.opus and (args.bv or args.dynamic_text):
        logger.error("--opus 不能与 --bv / --dynamic-text 同时指定")
        sys.exit(1)

    if args.opus:
        await main_opus(args.opus, dry_run=args.dry_run, target_uid=args.uid)
    elif args.bv:
        await main_bv(args.bv, dry_run=args.dry_run, target_uid=args.uid)
    elif args.dynamic_text:
        await main_dynamic(args.dynamic_text, dry_run=args.dry_run, target_uid=args.uid)
    else:
        await main_loop(dry_run=args.dry_run)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user, exiting")
        sys.exit(0)
