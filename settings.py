import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class Settings:
    def __init__(self):
        self.sessdata = os.environ.get("BILI_SESSDATA")
        self.bili_jct = os.environ.get("BILI_JCT")
        self.buvid3 = os.environ.get("BILI_BUVID3")
        self.doubao_api_key = os.environ.get("DOUBAO_API_KEY")
        self.deepseek_api_key = os.environ.get("DEEPSEEK_API_KEY")
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY")
        self.doubao_model = os.environ.get("DOUBAO_MODEL", "")
        self.deepseek_model = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro")
        self.max_at_count = int(os.environ.get("MAX_AT_COUNT", "3"))

    @property
    def is_configured(self) -> bool:
        return bool(self.sessdata and self.bili_jct and self.doubao_api_key)

    def validate(self):
        required = {
            "sessdata": self.sessdata,
            "bili_jct": self.bili_jct,
            "doubao_api_key": self.doubao_api_key,
            "doubao_model": self.doubao_model,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            logger.error("缺少必需配置项: %s", ', '.join(missing))
            logger.error("请设置对应的环境变量，或在 .env 文件中配置。")
            logger.error("或运行 python main.py --login 扫码登录获取 B站凭据。")
            sys.exit(1)


settings = Settings()
