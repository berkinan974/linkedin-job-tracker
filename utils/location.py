from config.settings import ALLOWED_LOCATION_KEYWORDS, ALLOW_REMOTE

# "İ".lower() → "i̇" (noktalı i + birleşik nokta) olduğu için "izmir" eşleşmez;
# Türkçe karakterleri önce ASCII'ye indir.
_TR_TO_ASCII = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
_REMOTE_MARKERS = ("(remote)", "(uzaktan)")


def _normalize(text: str) -> str:
    return text.translate(_TR_TO_ASCII).lower()


def is_allowed_location(location: str | None) -> bool:
    if not location:
        return False
    text = _normalize(location)
    if ALLOW_REMOTE and any(marker in text for marker in _REMOTE_MARKERS):
        return True
    return any(_normalize(keyword) in text for keyword in ALLOWED_LOCATION_KEYWORDS)
