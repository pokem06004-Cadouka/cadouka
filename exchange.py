import ssl
ssl._create_default_https_context = ssl._create_unverified_context

import os
import urllib.request as req
import urllib.error
import bs4
import json
from datetime import datetime, timedelta


headers = {
    "Content-Type": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/148.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8,ja;q=0.7",
    "Referer": "https://rate.bot.com.tw/xrt?Lang=zh-TW",
    "Connection": "keep-alive"
}


_LAST_JPY_RATE = None
_LAST_JPY_RATE_AT = None


def get_fallback_jpy_rate():
    """
    備用匯率。
    可在 Render Environment Variables 設定：
    JPY_FALLBACK_RATE=0.2000
    """
    try:
        return float(os.getenv("JPY_FALLBACK_RATE", "0.2000"))
    except:
        return 0.2000


def get_jpy_spot_sell():
    global _LAST_JPY_RATE
    global _LAST_JPY_RATE_AT

    # 3 小時內已有成功取得的匯率，直接使用記憶體快取
    if _LAST_JPY_RATE and _LAST_JPY_RATE_AT:
        if datetime.now() - _LAST_JPY_RATE_AT < timedelta(hours=3):
            print(
                f"使用日圓匯率快取：{_LAST_JPY_RATE}",
                flush=True
            )
            return _LAST_JPY_RATE

    url = "https://open.er-api.com/v6/latest/JPY"

    try:
        request = req.Request(
            url,
            headers={
                "User-Agent": "Cadouka/1.0",
                "Accept": "application/json"
            }
        )

        with req.urlopen(request, timeout=10) as response:
            result = response.read().decode("utf-8")

        data = json.loads(result)

        if data.get("result") != "success":
            raise ValueError(
                f"匯率 API 回傳失敗：{data.get('error-type', 'unknown')}"
            )

        rates = data.get("rates", {})
        rate = float(rates.get("TWD", 0))

        if rate <= 0:
            raise ValueError("匯率 API 未提供有效的 TWD 匯率")

        _LAST_JPY_RATE = rate
        _LAST_JPY_RATE_AT = datetime.now()

        print(
            f"成功取得日圓兌新臺幣參考匯率：1 JPY = {rate} TWD",
            flush=True
        )

        return rate

    except urllib.error.HTTPError as e:
        fallback_rate = _LAST_JPY_RATE or get_fallback_jpy_rate()

        print(
            f"取得日圓參考匯率失敗，HTTPError {e.code}，"
            f"使用備用匯率：{fallback_rate}",
            flush=True
        )

        return fallback_rate

    except Exception as e:
        fallback_rate = _LAST_JPY_RATE or get_fallback_jpy_rate()

        print(
            f"取得日圓參考匯率失敗：{e}，"
            f"使用備用匯率：{fallback_rate}",
            flush=True
        )

        return fallback_rate