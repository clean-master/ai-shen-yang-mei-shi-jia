import logging
from pathlib import Path

from pcre import compile as pcre_compile
from pysenseword import DFA, load_keywords

logger = logging.getLogger(__name__)

VOCABULARY_DIR = Path(__file__).parent / "vocabulary"
DFA_DIR = VOCABULARY_DIR / "dfa"
PCRE_DIR = VOCABULARY_DIR / "pcre"


class SensitiveFilter:
    def __init__(self):
        self._dfa: DFA | None = None
        self._words: dict[str, list[str]] = {}
        self._total_words = 0
        self._pcre_patterns: list[tuple[str, object]] = []
        self._total_regexes = 0
        self._load()

    # ── loading ──────────────────────────────────────────────────────────

    def _load(self):
        self._load_dfa()
        self._load_pcre()
        logger.info(
            "敏感词库加载完成: DFA %d 词条 + PCRE %d 正则 = 共 %d 条",
            self._total_words,
            self._total_regexes,
            self._total_words + self._total_regexes,
        )

    def _load_dfa(self):
        if not DFA_DIR.exists():
            logger.warning("DFA词库目录不存在: %s", DFA_DIR)
            return

        raw_words: set[str] = set()
        for txt_file in DFA_DIR.glob("*.txt"):
            try:
                words = load_keywords(str(txt_file))
                raw_words.update(words)
            except Exception:
                logger.warning("读取DFA词库文件失败: %s", txt_file)

        keyword_list = list(raw_words)
        self._total_words = len(keyword_list)

        self._dfa = DFA(keyword_list)

        for word in raw_words:
            first_char = word[0]
            if first_char not in self._words:
                self._words[first_char] = []
            self._words[first_char].append(word)

    def _load_pcre(self):
        if not PCRE_DIR.exists():
            logger.warning("PCRE词库目录不存在: %s", PCRE_DIR)
            return

        for txt_file in sorted(PCRE_DIR.glob("*.txt")):
            try:
                with open(txt_file, encoding="utf-8") as f:
                    lines = f.readlines()
            except Exception:
                logger.warning("读取PCRE词库文件失败: %s", txt_file)
                continue

            count = 0
            for line in lines:
                line = line.strip()
                if (
                    not line
                    or line.startswith("#")
                    or line.startswith("---")
                    or line.startswith("===")
                ):
                    continue
                try:
                    compiled = pcre_compile(line)
                    self._pcre_patterns.append((line, compiled))
                    count += 1
                except Exception:
                    logger.warning(
                        "PCRE正则编译失败 [%s]: %s", txt_file.name, line[:80]
                    )

        self._total_regexes = len(self._pcre_patterns)

    # ── PCRE helpers ─────────────────────────────────────────────────────

    def _check_pcre(self, text: str) -> tuple[bool, str]:
        for _pattern_str, compiled in self._pcre_patterns:
            m = compiled.search(text)
            if m:
                return True, m.group()
        return False, ""

    # ── public API ───────────────────────────────────────────────────────

    def check(self, text: str) -> tuple[bool, str]:
        if not text:
            return False, ""

        if self._dfa:
            result = self._dfa.sensitive_word(text)
            if result["find"]:
                return True, result["word"]

        return self._check_pcre(text)

    def find_all(self, text: str) -> list[str]:
        if not text:
            return []

        seen: set[str] = set()
        dfa_matched: list[str] = []
        pcre_matched: list[str] = []

        if self._words:
            for i, char in enumerate(text):
                candidates = self._words.get(char)
                if not candidates:
                    continue
                for word in candidates:
                    if word in seen:
                        continue
                    seen.add(word)
                    start = text.find(word, i)
                    if start != -1 and start <= i + len(word):
                        dfa_matched.append(word)

        for _pattern_str, compiled in self._pcre_patterns:
            for m in compiled.finditer(text):
                match_text = m.group()
                if match_text not in seen:
                    seen.add(match_text)
                    pcre_matched.append(match_text)

        if dfa_matched:
            logger.info("[DFA]  命中: %s", ", ".join(dfa_matched))
        if pcre_matched:
            logger.info("[PCRE] 命中: %s", ", ".join(pcre_matched))

        return dfa_matched + pcre_matched

    def replace(self, text: str) -> str:
        if not text:
            return text

        seen: set[str] = set()
        hits: list[tuple[int, int]] = []

        if self._words:
            for i, char in enumerate(text):
                candidates = self._words.get(char)
                if not candidates:
                    continue
                for word in candidates:
                    if word in seen:
                        continue
                    seen.add(word)
                    pos = 0
                    while True:
                        start = text.find(word, pos)
                        if start == -1:
                            break
                        hits.append((start, start + len(word)))
                        pos = start + 1

        for _pattern_str, compiled in self._pcre_patterns:
            for m in compiled.finditer(text):
                hits.append(m.span())

        if not hits:
            return text

        hits.sort()
        merged: list[tuple[int, int]] = []
        for start, end in hits:
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))

        chars = list(text)
        for start, end in merged:
            for j in range(start, end):
                chars[j] = "█"

        return "".join(chars)

    # ── properties ───────────────────────────────────────────────────────

    @property
    def word_count(self) -> int:
        return self._total_words

    @property
    def regex_count(self) -> int:
        return self._total_regexes


sensitive_filter = SensitiveFilter()
