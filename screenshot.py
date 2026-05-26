"""视频随机截图工具。

从视频中随机截取关键帧，返回截图路径、base64 编码和时间戳信息。
"""

import base64
import logging
import os
import random
import subprocess

from tmp import get_temp_dir

logger = logging.getLogger(__name__)


def _get_video_duration(video_path: str) -> float:
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError) as e:
        logger.warning("获取视频时长失败: %s，回退到 0", e)
        return 0.0


def _format_timestamp(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _generate_timestamps(duration: float) -> list[float]:
    if duration <= 0:
        return [0.0]

    if duration < 60:
        return [duration / 2]

    base_positions = [0.10, 0.50, 0.90]
    timestamps: list[float] = []
    for ratio in base_positions:
        jitter = (random.uniform(-0.05, 0.05)) * duration
        ts = max(1.0, min(duration - 1.0, ratio * duration + jitter))
        timestamps.append(ts)
    return sorted(timestamps)


def extract_screenshots(video_path: str) -> list[dict]:
    duration = _get_video_duration(video_path)
    logger.info("视频时长: %.1f 秒", duration)

    timestamps = _generate_timestamps(duration)
    logger.info("截图时间点: %s", [_format_timestamp(t) for t in timestamps])

    tmp_dir = get_temp_dir()
    screenshots: list[dict] = []

    for ts in timestamps:
        label = _format_timestamp(ts)
        safe_label = label.replace(":", "-")
        out_path = os.path.join(tmp_dir, f"screenshot_{safe_label}.jpg")

        cmd = [
            "ffmpeg",
            "-ss", str(ts),
            "-i", video_path,
            "-vframes", "1",
            "-q:v", "3",
            "-y",
            out_path,
        ]

        try:
            subprocess.run(cmd, capture_output=True, check=True)
            logger.info("截图已保存: %s (时间点 %s)", out_path, label)

            with open(out_path, "rb") as f:
                img_data = base64.b64encode(f.read()).decode("ascii")
            base64_uri = f"data:image/jpeg;base64,{img_data}"

            screenshots.append({
                "path": out_path,
                "base64": base64_uri,
                "timestamp": ts,
                "label": label,
            })
        except subprocess.CalledProcessError as e:
            logger.error("截图失败 (时间点 %s): %s", label, e.stderr.decode(errors="replace")[:200])
        except FileNotFoundError:
            logger.error("ffmpeg 未安装，无法截图")
            break

    logger.info("共截取 %d 张截图", len(screenshots))
    return screenshots


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print(f"用法: python {sys.argv[0]} <video_path>")
        sys.exit(1)

    results = extract_screenshots(sys.argv[1])
    for r in results:
        logger.info("%s → %s (base64: %d chars)", r['label'], r['path'], len(r['base64']))
