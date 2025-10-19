"""最小限の audioop ダミーモジュール。

discord.py が音声機能を初期化する際に audioop を import するため、
Python 3.13 以降で削除された audioop の代わりに空モジュールを提供する。
音声機能は使用しない想定なので、処理は何もしない実装にしてある。
"""


class error(Exception):
    """audioop.error と互換の例外クラス。"""


def _ensure_bytes(fragment):
    if isinstance(fragment, (bytes, bytearray)):
        return bytes(fragment)
    raise error("audioop stub expects bytes-like data")


def add(fragment1, fragment2, width):
    _ensure_bytes(fragment1)
    _ensure_bytes(fragment2)
    return fragment1


def mul(fragment, width, factor):
    _ensure_bytes(fragment)
    return fragment


def bias(fragment, width, bias_value):
    _ensure_bytes(fragment)
    return fragment


def tostereo(fragment, width, *args, **kwargs):
    _ensure_bytes(fragment)
    return fragment


def tomono(fragment, width, *args, **kwargs):
    _ensure_bytes(fragment)
    return fragment


def getsample(fragment, width, index):
    _ensure_bytes(fragment)
    return 0


def max(fragment, width):
    _ensure_bytes(fragment)
    return 0


def minmax(fragment, width):
    _ensure_bytes(fragment)
    return 0, 0


def avg(fragment, width):
    _ensure_bytes(fragment)
    return 0


def rms(fragment, width):
    _ensure_bytes(fragment)
    return 0


def findfactor(fragment, comparison_fragment):
    _ensure_bytes(fragment)
    _ensure_bytes(comparison_fragment)
    return 1.0


def lin2lin(fragment, width, new_width):
    _ensure_bytes(fragment)
    return fragment


def cross(fragment1, fragment2):
    _ensure_bytes(fragment1)
    _ensure_bytes(fragment2)
    return fragment1
