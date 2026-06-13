import ssl
ssl._create_default_https_context = ssl._create_unverified_context

import os
import urllib.request as req
import urllib.error
import bs4
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

    # 如果 3 小時內已經成功抓過，就先用快取，避免每次查價都打台銀。
    if _LAST_JPY_RATE and _LAST_JPY_RATE_AT:
        if datetime.now() - _LAST_JPY_RATE_AT < timedelta(hours=3):
            return _LAST_JPY_RATE

    url = "https://rate.bot.com.tw/xrt?Lang=zh-TW"

    try:
        request = req.Request(url, headers=headers)

        with req.urlopen(request, timeout=8) as response:
            result = response.read().decode("utf-8")

        root = bs4.BeautifulSoup(result, "html.parser")

        japan_img = root.find("img", class_=lambda c: c and "japan" in c)

        if not japan_img:
            print("取得日圓匯率失敗：找不到 japan img")
            return _LAST_JPY_RATE or get_fallback_jpy_rate()

        japan_tr = japan_img.find_parent("tr")

        if not japan_tr:
            print("取得日圓匯率失敗：找不到 JPY row")
            return _LAST_JPY_RATE or get_fallback_jpy_rate()

        spot_sell_td = japan_tr.find("td", attrs={"data-table": "本行即期賣出"})

        if not spot_sell_td:
            print("取得日圓匯率失敗：找不到即期賣出欄位")
            return _LAST_JPY_RATE or get_fallback_jpy_rate()

        rate_text = spot_sell_td.get_text(strip=True)
        rate = float(rate_text)

        _LAST_JPY_RATE = rate
        _LAST_JPY_RATE_AT = datetime.now()

        return rate

    except urllib.error.HTTPError as e:
        print(f"取得日圓匯率失敗，HTTPError {e.code}，使用備用匯率：", e)
        return _LAST_JPY_RATE or get_fallback_jpy_rate()

    except Exception as e:
        print("取得日圓匯率失敗，使用備用匯率：", e)
        return _LAST_JPY_RATE or get_fallback_jpy_rate()