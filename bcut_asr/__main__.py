import logging
import sys
from argparse import ArgumentParser, FileType

from . import APIError, BcutASR, ResultStateEnum, ffmpeg_render, run_asr_pipeline

logging.basicConfig(
    format="%(asctime)s - [%(levelname)s] %(message)s",
    level=logging.INFO,
)

INFILE_FMT = ["flac", "aac", "m4a", "mp3", "wav"]
OUTFILE_FMT = ["srt", "json", "lrc", "txt"]

parser = ArgumentParser(
    prog="bcut-asr",
    description="必剪语音识别\n",
    epilog=f"支持输入音频格式: {', '.join(INFILE_FMT)}  支持自动调用ffmpeg提取视频伴音",
)
parser.add_argument(
    "-f", "--format", nargs="?", default="srt", choices=OUTFILE_FMT, help="输出字幕格式"
)
parser.add_argument(
    "-i",
    "--interval",
    nargs="?",
    type=float,
    default="1.0",
    metavar="1.0",
    help="任务状态轮询间隔(秒)",
)
parser.add_argument("input", type=FileType("rb"), help="输入媒体文件")
parser.add_argument(
    "output",
    nargs="?",
    type=FileType("w", encoding="utf8"),
    help="输出字幕文件, 可stdout",
)


def main():
    args = parser.parse_args()
    try:
        run_asr_pipeline(args)
    except SystemExit:
        raise
    except APIError as err:
        logging.error("接口错误: %s", err)
        return -1
    return 0


if __name__ == "__main__":
    sys.exit(main())
