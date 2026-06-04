import glob
import logging
import os
import subprocess
import time

from bcut_asr import BcutASR
from bcut_asr.orm import ResultStateEnum
from settings import settings
from tmp import clean_tmp, get_temp_dir

logger = logging.getLogger(__name__)


def get_subtitle_from_bv(bv_number):
    tmp_dir = get_temp_dir()
    command = [
        "yutto",
        "--proxy",
        "no",
        "--auth", f"SESSDATA={settings.sessdata}; bili_jct={settings.bili_jct}",
        "--subtitle-only",
        "-d",
        tmp_dir,
        bv_number,
    ]

    try:
        subprocess.run(command, check=True)
        logger.info("yutto subtitle download succeeded")

        srt_files = glob.glob(os.path.join(tmp_dir, "*.srt"))

        if not srt_files:
            logger.warning(
                "No srt files found in temp dir, falling back to ASR")
            return audio2text(bv_number)

        cn_files = [f for f in srt_files if f.endswith(".中文.srt")]
        srt_file_path = cn_files[0] if cn_files else srt_files[0]

        if len(srt_files) > 1:
            logger.info(
                "Multiple srt files found (%d total), selected: %s",
                len(srt_files), os.path.basename(srt_file_path),
            )

        with open(srt_file_path, "r", encoding="utf-8") as f:
            srt_content = f.read()

        filename = os.path.basename(srt_file_path)
        srt_content = srt_to_plain_text(srt_content)
        return "标题：" + filename + "\n" + srt_content

    except subprocess.CalledProcessError as e:
        logger.error("yutto command failed with return code %s", e.returncode)
        return None
    except FileNotFoundError:
        logger.error(
            "yutto not found. Please install yutto and ensure it's in PATH")
        return None
    except Exception as e:
        logger.exception("Unexpected error in get_subtitle_from_bv")
        return None


def srt_to_plain_text(srt_content):
    if not srt_content:
        return ""

    plain_text_lines = []
    for line in srt_content.splitlines():
        line = line.strip()
        if not line.isdigit() and "-->" not in line and line:
            plain_text_lines.append(line)

    return " ".join(plain_text_lines)


def audio2text(bv_number):
    tmp_dir = get_temp_dir()
    audio_command = [
        "yutto",
        "--proxy",
        "no",
        "--auth", f"SESSDATA={settings.sessdata}; bili_jct={settings.bili_jct}",
        "--audio-only",
        "--no-danmaku",
        "--no-subtitle",
        "--no-cover",
        "-d",
        tmp_dir,
        bv_number,
    ]

    try:
        subprocess.run(audio_command, capture_output=True,
                       text=True, check=True)
        logger.info("Audio download succeeded")

        m4a_files = glob.glob(os.path.join(tmp_dir, "*.m4a"))
        if not m4a_files:
            logger.error("No m4a file found after download")
            return None

        audio_file_path = m4a_files[0]
        audio_filename = os.path.basename(audio_file_path)

        logger.info("Starting bcut_asr for %s", audio_file_path)
        asr = BcutASR(audio_file_path)
        asr.upload()
        asr.create_task()

        max_retries = 300
        retries = 0
        result = None
        while retries < max_retries:
            result = asr.result()
            if result.state == ResultStateEnum.COMPLETE:
                break
            retries += 1
            time.sleep(1)

        if result is None or retries >= max_retries:
            logger.error("ASR task timed out")
            return None

        subtitle = result.parse()
        if subtitle.has_data():
            return "标题" + audio_filename + "\n" + subtitle.to_txt()
        else:
            logger.warning("No subtitle data recognized")
            return ""

    except subprocess.CalledProcessError as e:
        logger.error("Audio download failed: return code %s", e.returncode)
        return None
    except TypeError as e:
        logger.error("TypeError during ASR: %s", e)
        return "连接失败，请检查输入"
    except Exception:
        logger.exception("ASR processing failed")
        return None


if __name__ == "__main__":
    bv = "BV1uyKAeAEiR"
    subtitle_content = get_subtitle_from_bv(bv)

    if subtitle_content:
        logger.info("--- %s 的字幕内容 ---", bv)
        logger.info("%s", subtitle_content)
    else:
        logger.error("获取 %s 字幕失败.", bv)
