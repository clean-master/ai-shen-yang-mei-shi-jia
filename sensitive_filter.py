import logging
from pathlib import Path

from pysenseword import DFA, load_keywords

logger = logging.getLogger(__name__)

LEXICON_DIR = Path(__file__).parent / "Vocabulary"


class SensitiveFilter:
    def __init__(self):
        self._dfa: DFA | None = None
        self._words: dict[str, list[str]] = {}
        self._total_words = 0
        self._load()

    def _load(self):
        if not LEXICON_DIR.exists():
            logger.warning("词库目录不存在: %s", LEXICON_DIR)
            return

        raw_words: set[str] = set()
        for txt_file in LEXICON_DIR.glob("*.txt"):
            try:
                words = load_keywords(str(txt_file))
                raw_words.update(words)
            except Exception:
                logger.warning("读取词库文件失败: %s", txt_file)

        keyword_list = list(raw_words)
        self._total_words = len(keyword_list)
        logger.info("加载敏感词库: %d 词条", self._total_words)

        self._dfa = DFA(keyword_list)

        for word in raw_words:
            first_char = word[0]
            if first_char not in self._words:
                self._words[first_char] = []
            self._words[first_char].append(word)

    def check(self, text: str) -> tuple[bool, str]:
        if not self._dfa or not text:
            return False, ""

        result = self._dfa.sensitive_word(text)
        if result["find"]:
            return True, result["word"]
        return False, ""

    def find_all(self, text: str) -> list[str]:
        if not self._words or not text:
            return []

        matched: list[str] = []
        seen: set[str] = set()
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
                    matched.append(word)
        return matched

    def replace(self, text: str) -> str:
        seen: set[str] = set()
        hits: list[tuple[int, int]] = []

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

    @property
    def word_count(self) -> int:
        return self._total_words


sensitive_filter = SensitiveFilter()
