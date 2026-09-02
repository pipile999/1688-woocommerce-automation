import re
from bs4 import BeautifulSoup


BLOCKED_PATTERNS = [
    r"(?:公司|有限公司|工厂|厂家|供应商)",
    r"(?:微信|wechat|whatsapp|电话|手机|tel|phone)",
    r"(?:邮箱|email|e-mail)",
    r"(?:https?://|www\.)\S+",
    r"(?:OEM|ODM).{0,30}(?:欢迎|联系|咨询|定制)",
]


def clean_description(html: str) -> str:
    """Conservatively remove supplier/company/contact promotion from description text.

    This is deterministic by design. SKU/variation data never passes through this cleaner.
    """
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style", "iframe"]):
        tag.decompose()

    lines = []
    for raw in soup.get_text("\n").splitlines():
        line = " ".join(raw.split()).strip()
        if not line:
            continue
        if any(re.search(pattern, line, flags=re.I) for pattern in BLOCKED_PATTERNS):
            continue
        lines.append(line)
    return "\n".join(lines)
