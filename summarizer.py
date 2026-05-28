import logging
from pathlib import Path

import aiosqlite
from bilibili_api import video as bili_video
from bilibili_api import Credential
from bilibili_api.opus import Opus

from api_clients import DeepSeekClient, DoubaoClient, LLMClient
from audio2text import get_subtitle_from_bv
from getvideo import download_video
from screenshot import extract_screenshots
from sensitive_filter import sensitive_filter
from tmp import clean_tmp
from prompts import (
    VIDEO_SUMMARY_PROMPT,
    DYNAMIC_SUMMARY_PROMPT,
    MODERATION_PROMPT,
)

logger = logging.getLogger(__name__)

llm_client: LLMClient = DoubaoClient()
moderation_client: LLMClient = DeepSeekClient()


def _parse_moderation_response(response: str) -> tuple[bool, str]:
    is_safe = "安全: 是" in response
    reason = ""
    for line in response.splitlines():
        if line.startswith("理由:"):
            reason = line[3:].strip()
            break
    return is_safe, reason


def _extract_opus_text(info: dict) -> str:
    parts: list[str] = []
    for module in info.get("item", {}).get("modules", []):
        title = module.get("module_title", {}).get("text", "")
        if title:
            parts.append(title)
        if module.get("module_content"):
            for para in module["module_content"].get("paragraphs", []):
                para_type = para.get("para_type", 0)
                if para_type == 1:
                    node_texts = []
                    for node in para.get("text", {}).get("nodes", []):
                        if node.get("word"):
                            node_texts.append(node["word"]["words"])
                        elif node.get("rich"):
                            node_texts.append(node["rich"]["text"])
                    if node_texts:
                        parts.append("".join(node_texts))
                elif para_type == 2:
                    pic_count = len(para.get("pic", {}).get("pics", []))
                    if pic_count:
                        parts.append(f"[图片×{pic_count}]")
    return "\n".join(parts) if parts else "(无文字内容)"


async def _fetch_opus_data(opus_id: int, credential: Credential) -> tuple[str, list[str]]:
    """Fetch dynamic text and image URLs for an opus. Returns (text, image_urls)."""
    op = Opus(opus_id=opus_id, credential=credential)
    try:
        dynamic_text = await op.markdown()
    except KeyError:
        logger.warning("[动态] markdown 解析失败（库bug），从原始数据提取")
        info = await op.get_info()
        dynamic_text = _extract_opus_text(info)
    logger.info(
        "[动态] markdown 获取成功: len=%d 内容前200字=%s",
        len(dynamic_text) if dynamic_text else 0,
        dynamic_text[:200] if dynamic_text else "(空)",
    )

    image_urls: list[str] = []
    try:
        images = await op.get_images()
        image_urls = [img.url for img in images if img.url]
        logger.info("[动态] 获取图片: %d 张", len(image_urls))
    except Exception:
        logger.warning("[动态] 获取图片失败，继续纯文本")

    return dynamic_text, image_urls


async def moderate_summary(
    conn: aiosqlite.Connection, text: str, content_type: str, source_url: str | None = None,
) -> str | None:
    import time
    moderation_result = await moderation_client.generate(
        prompt=MODERATION_PROMPT + text,
        max_tokens=200,
    )
    is_safe, reason = _parse_moderation_response(moderation_result)
    logger.info("[审核] AI %s: %s", "通过" if is_safe else "拦截", reason)

    if not is_safe:
        logger.warning("审核不通过，跳过发送: %s", reason)
        await conn.execute(
            "INSERT INTO rejected_content (created_at, reason, content, content_type, source_url) VALUES (?, ?, ?, ?, ?)",
            (time.time(), reason, text, content_type, source_url),
        )
        await conn.commit()
        return None

    matched, word = sensitive_filter.check(text)
    if matched:
        all_words = sensitive_filter.find_all(text)
        logger.info("[审核] 命中 [%s] → 替换前: %s", ', '.join(all_words), text)
        text = sensitive_filter.replace(text)
        logger.info("词库脱敏: 命中 [%s] → 已替换", ', '.join(all_words))
        logger.info("[审核] 替换后: %s", text)

    return text


async def get_summary_from_video(bv_number: str) -> str:
    subtitle = get_subtitle_from_bv(bv_number)
    if subtitle is None:
        subtitle = ""

    try:
        v = bili_video.Video(bvid=bv_number)
        info = await v.get_info()
        title = info.get("title", "")
        owner = info.get("owner", {}).get("name", "")
        desc = info.get("desc", "")
        cover = info.get("pic", "")
        if cover and cover.startswith("http://"):
            cover = "https://" + cover[7:]
        if cover and not cover.rsplit("/", 1)[-1].split("?")[0].endswith((".jpg", ".jpeg", ".png", ".webp")):
            cover += ".jpg"
        tag_names: list[str] = []
        try:
            tags = await v.get_tags()
            tag_names = [t.get("tag_name", "") for t in tags if t.get("tag_name")]
            logger.info("视频标签: %s", tag_names)
        except Exception:
            logger.warning("获取视频标签失败，继续")

        parts = []
        if title:
            parts.append(f"视频标题：{title}")
        if owner:
            parts.append(f"UP主：{owner}")
        if tag_names:
            parts.append(f"视频标签：{'、'.join(tag_names)}")
        if desc:
            parts.append(f"视频简介：{desc}")
        if subtitle:
            parts.append(f"字幕：{subtitle}")
        context = " ".join(parts) if parts else subtitle
        cover_url = cover or None
    except Exception:
        logger.warning("获取视频信息失败，仅使用字幕")
        context = subtitle
        cover_url = None

    screenshot_uris: list[str] = []
    try:
        video_path = download_video(bv_number)
        if video_path and Path(video_path).exists():
            screenshots = extract_screenshots(video_path)
            if screenshots:
                screenshot_uris = [s["base64"] for s in screenshots]
                timestamp_labels = [s["label"] for s in screenshots]
                context = f"{context} 视频截图时间点: {', '.join(timestamp_labels)}"
    except Exception:
        logger.exception("截图失败，继续仅使用封面")

    images: list[str] = []
    if llm_client.supports_multimodal:
        if cover_url:
            images.append(cover_url)
        images.extend(screenshot_uris)

    prompt = VIDEO_SUMMARY_PROMPT + context
    logger.info(
        "发送给模型: multimodal=%s images=%d context=%s",
        llm_client.supports_multimodal, len(images), context[:200],
    )
    try:
        return await llm_client.generate(prompt, images=images or None)
    finally:
        clean_tmp()


async def get_summary_from_dynamic(dynamic_text: str, image_urls: list[str] | None = None) -> str:
    logger.info("Dynamic text: %s", dynamic_text)
    prompt = DYNAMIC_SUMMARY_PROMPT + dynamic_text

    images: list[str] | None = image_urls if llm_client.supports_multimodal else None
    if images:
        logger.info("[动态] 多模态: images=%d text_len=%d", len(images), len(prompt))

    try:
        return await llm_client.generate(prompt, images=images, max_tokens=2000)
    finally:
        clean_tmp()
