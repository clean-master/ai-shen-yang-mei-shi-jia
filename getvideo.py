import glob
import logging
import os
import subprocess

from tmp import get_temp_dir

logger = logging.getLogger(__name__)


def get_video_from_bv(bv_number: str) -> str | None:
    tmp_dir = get_temp_dir()
    command = [
        "yutto",
        "--proxy",
        "no",
        "--video-only",
        "--no-danmaku",
        "--no-subtitle",
        "--no-cover",
        "-d",
        tmp_dir,
        bv_number,
    ]

    try:
        subprocess.run(command, check=True)
        logger.info("yutto video download succeeded")

        mp4_files = glob.glob(os.path.join(tmp_dir, "*.mp4"))

        if not mp4_files:
            logger.error("No mp4 file found after download")
            return None
        if len(mp4_files) > 1:
            logger.warning("Multiple mp4 files found, using the first one")

        return mp4_files[0]

    except subprocess.CalledProcessError as e:
        logger.error("yutto command failed with return code %s", e.returncode)
        return None
    except FileNotFoundError:
        logger.error(
            "yutto not found. Please install yutto and ensure it's in PATH")
        return None
    except Exception:
        logger.exception("Unexpected error in get_video_from_bv")
        return None


def download_video(bv_number: str) -> str | None:
    return get_video_from_bv(bv_number)


if __name__ == "__main__":
    bv = "BV1uyKAeAEiR"
    result = get_video_from_bv(bv)

    if result:
        logger.info("--- %s 的视频内容 ---", bv)
        logger.info("%s", result)
    else:
        logger.error("获取 %s 视频失败.", bv)
