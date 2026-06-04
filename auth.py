import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def save_cookies_to_env(cookies: dict) -> None:
    env_path = Path(".env")
    cookie_map = {
        "BILI_SESSDATA": cookies.get("SESSDATA", ""),
        "BILI_JCT": cookies.get("bili_jct", ""),
        "BILI_BUVID3": cookies.get("buvid3", ""),
    }
    if "DedeUserID" in cookies:
        cookie_map["BILI_DEDEUSERID"] = cookies["DedeUserID"]

    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines(keepends=True)
        updated: set[str] = set()
        result: list[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                result.append(line)
                continue
            matched = False
            for key, value in cookie_map.items():
                if stripped.startswith(f"{key}=") or stripped.startswith(f'{key}="'):
                    result.append(f'{key}="{value}"\n')
                    updated.add(key)
                    matched = True
                    break
            if not matched:
                result.append(line)
        for key, value in cookie_map.items():
            if key not in updated:
                result.append(f'{key}="{value}"\n')
        env_path.write_text("".join(result), encoding="utf-8")
    else:
        lines = ["# Bilibili Cookie 配置\n"]
        for key, value in cookie_map.items():
            lines.append(f'{key}="{value}"\n')
        env_path.write_text("".join(lines), encoding="utf-8")


async def do_login() -> None:
    from bilibili_api import login_v2

    qr = login_v2.QrCodeLogin(platform=login_v2.QrCodeLoginChannel.WEB)
    await qr.generate_qrcode()

    print("\n请使用 Bilibili 客户端扫描以下二维码登录：\n")
    print(qr.get_qrcode_terminal())
    print("\n等待扫描...")

    while not qr.has_done():
        state = await qr.check_state()
        logger.info("扫码状态: %s", state)
        await asyncio.sleep(1)

    credential = qr.get_credential()
    cookies = credential.get_cookies()
    logger.info("获取到 Cookie: %s", {
                k: v[:10] + "..." for k, v in cookies.items()})

    save_cookies_to_env(cookies)
    print("\n登录成功！凭据已保存到 .env 文件。")
