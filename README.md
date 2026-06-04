# AI 沈阳美食家

> B站智能 @ 回复机器人，自动检测 @ 提醒，解析视频和动态内容，以「笑点解析」风格生成 AI 回复并发送评论和私信。

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-BSD%202--Clause-green)](LICENSE)

## 功能

- **自动检测 @ 提醒** — 轮询 B站新提醒，去重处理，避免重复回复
- **多来源解析** — 支持 BV 号视频、Opus 动态 ID 和纯文本动态
- **视频转写** — 优先下载字幕，无字幕时自动使用必剪 ASR 语音识别兜底
- **多模态 AI 生成** — 调用豆包、DeepSeek 或 Gemini，生成「笑点解析」风格回复
- **内容审核** — AI 安全审查 + DFA 78k 词条 + PCRE 正则 3k，双引擎并行过滤
- **消息去重** — SQLite 记录已处理 ID，防止重复回复
- **测试模式** — 本地跑通完整流程，不实际发送任何评论或私信

## 前置依赖

- Python 3.10+
- [yutto](https://github.com/SigureMo/yutto) — B站视频/字幕/音频下载工具
- ffmpeg — 语音识别的音频处理

## 快速开始

### 1. 安装依赖

```bash
pip install yutto
pip install -e .
```

### 2. 配置凭据

复制环境变量模板并填入真实值：

```bash
cp .env.example .env
```

| 变量 | 说明 | 是否必填 |
|---|---|---|
| `BILI_SESSDATA` | B站会话 Cookie | 必填 |
| `BILI_JCT` | B站 CSRF Token | 必填 |
| `BILI_BUVID3` | B站设备 ID | 选填 |
| `DOUBAO_API_KEY` | 火山引擎豆包 API Key（主要 LLM） | 必填 |
| `DOUBAO_MODEL` | 火山引擎模型端点 ID | 必填 |
| `DEEPSEEK_API_KEY` | DeepSeek API Key | 选填 |
| `DEEPSEEK_MODEL` | DeepSeek 模型名称（默认 `deepseek-v4-pro`） | 选填 |
| `GEMINI_API_KEY` | Google Gemini API Key（多模态备选） | 选填 |
| `MAX_AT_COUNT` | 单条消息允许的最大 @ 数量，超出则忽略（防滥用）；`0` 表示不限制，默认 `3` | 选填 |

> [!TIP]
> 执行 `python main.py --login` 可通过扫码登录，凭据会自动写入 `.env`。

> [!WARNING]
> 切勿将 `.env` 提交到版本控制。该文件已加入 `.gitignore`。

### 3. 启动

```bash
python main.py
```

机器人开始轮询 @ 提醒，生成 AI 摘要，并发送评论和私信。

## 用法

### 轮询模式（默认）

```bash
python main.py
```

### CLI 测试模式

跳过轮询，直接处理指定内容：

```bash
# 处理指定视频（测试模式，不发送）
python main.py --bv BV1xxxxx -d

# 处理指定 Opus 动态（测试模式，不发送）
python main.py --opus 123456789 -d

# 处理指定文本动态（测试模式，不发送）
python main.py --dynamic-text "这是一条测试动态" -d
```

### 所有参数

```
python main.py [选项]

  --login                  扫码登录，将凭据保存到 .env
  --dry-run, -d            跑通完整流程，但跳过发送评论/私信
  --bv BVID                直接处理指定 BV 号视频（跳过轮询）
  --dynamic-text TEXT      直接处理指定文本动态（跳过轮询）
  --opus OPUS_ID           直接处理指定 Opus ID 动态（跳过轮询）
  --uid UID                指定私信接收者 UID（配合以上三项使用）
  --display                测试模式下用 display 命令展示裁剪后的封面图（需安装 ImageMagick）
```

### 行为速查

| 命令 | 行为 |
|---|---|
| `python main.py` | 轮询 @ 提醒 → 生成摘要 → 发送评论 + 私信 |
| `python main.py -d` | 轮询 @ 提醒 → 生成摘要 → 跳过发送 |
| `python main.py --bv BV1xxx` | 处理指定视频 → 发送评论 + 私信 |
| `python main.py --bv BV1xxx -d` | 处理指定视频 → 跳过发送 |
| `python main.py --opus 123456789 -d` | 处理 Opus 动态 → 跳过发送 |
| `python main.py --login` | 扫码登录 → 写入 `.env` |

## 处理流程

```
检测到 @ 提醒
      │
      ▼
@ 数量超过 MAX_AT_COUNT？→ 是 → 跳过（防滥用）
      │ 否
      ▼
判断内容类型（BV 视频 / Opus 动态 / 文本）
      │
      ├─ 视频 ──→ 下载字幕或语音识别转写 → 提取视频截图
      └─ 动态 ──→ 获取文本 + 图片
      │
      ▼
LLM 生成「笑点解析」回复
      ▼
AI 安全审查 + 敏感词过滤
      │
      ▼
发送评论和私信（测试模式下跳过）
      │
      ▼
将 ID 标记为已处理，写入 SQLite
```

## 项目结构

```
.
├── main.py               # 入口：CLI 解析、消息路由、主循环
├── settings.py           # 配置管理（环境变量 > .env）
├── prompts.py            # LLM Prompt 模板
├── summarizer.py         # 摘要生成 + 内容审核
├── api_clients.py        # LLM API 封装（豆包、DeepSeek、Gemini）
├── auth.py               # 扫码登录 + 凭据存储
├── db.py                 # SQLite 操作（去重、日志记录）
├── audio2text.py         # 字幕下载 + ASR 语音识别
├── getvideo.py           # yutto 视频下载
├── screenshot.py         # ffmpeg 视频截帧
├── sensitive_filter.py   # DFA + PCRE 双引擎敏感词过滤
├── video_id_transform.py # BV 号与 AV 号互转
├── bcut_asr/             # 必剪语音识别模块
├── vocabulary/           # 敏感词库（需自行准备，见下方说明）
├── .env.example          # 环境变量模板
└── pyproject.toml        # 包元数据与依赖声明
```

## 敏感词库

`vocabulary/` 目录下分两个子目录，双引擎并行工作：

- `dfa/` — DFA 精确匹配词库（`.txt`，每行一个词），使用 pysenseword 的 DFA 算法
- `pcre/` — PCRE 正则匹配词库（`.txt`，每行一条 PCRE 正则），使用 PyPcre 引擎

`check()` 先走 DFA（快速），未命中再走 PCRE。匹配优先级 DFA > PCRE。

**本仓库不包含词库文件**，需自行准备。可参考以下来源：

- 各平台公开的敏感词库（腾讯、网易等）
- 自行整理的业务相关词汇
- 网易游戏聊天过滤正则词库

将 `.txt` 文件放入对应子目录即可，`sensitive_filter.py` 会自动加载。
