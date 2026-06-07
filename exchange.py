import ssl
ssl._create_default_https_context = ssl._create_unverified_context

import urllib.request as req
import bs4
headers={
        "Content-Type":"application/json",
        "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
        }

def get_jpy_spot_sell():
    url = "https://rate.bot.com.tw/xrt?Lang=zh-TW"

    request = req.Request(url, headers=headers)

    with req.urlopen(request) as response:
        result = response.read().decode("utf-8")

    root = bs4.BeautifulSoup(result, "html.parser")

    japan_img = root.find("img", class_=lambda c: c and "japan" in c)

    if not japan_img:
        return None

    japan_tr = japan_img.find_parent("tr")

    if not japan_tr:
        return None

    spot_sell_td = japan_tr.find("td", attrs={"data-table": "本行即期賣出"})

    if not spot_sell_td:
        return None

    rate_text = spot_sell_td.get_text(strip=True)

    return float(rate_text)