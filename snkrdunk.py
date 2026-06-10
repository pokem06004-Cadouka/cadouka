import ssl
ssl._create_default_https_context = ssl._create_unverified_context

import urllib.request as req
from urllib.parse import quote, urlparse
import json
import bs4

from config import headers


# =========================
# SNKRDUNK Condition Settings
# =========================

CONDITION_ID_MAP = {
    "A": 18,
    "B": 19,
    "PSA10": 22,
    "PSA9": 23,
    "PSA8以下": 24
}

BASE_CONDITIONS = ["PSA10", "PSA9", "PSA8以下"]

PRO_CONDITIONS = ["A", "B", "PSA10", "PSA9", "PSA8以下"]


# =========================
# Search Products
# =========================

def search_products(card_id):
    keyword = quote(card_id, safe="")
    url = f"https://snkrdunk.com/search?keywords={keyword}"

    request_obj = req.Request(url, headers=headers)

    with req.urlopen(request_obj) as response:
        data = response.read().decode("utf-8")

    root = bs4.BeautifulSoup(data, "html.parser")

    container = root.find(
        "div",
        class_="styles-module-scss-module__LqnJBW__scrollContainer"
    )

    products = []

    if container:
        a_tags = container.find_all("a")

        for a in a_tags:
            href = a.get("href")

            if href and not href.startswith("http"):
                href = "https://snkrdunk.com" + href

            img = a.find("img")
            src = img.get("src") if img else None

            title_row = a.find(
                "div",
                class_=lambda c: c and "titleRow" in c
            )

            if title_row:
                span = title_row.find("span")
                label = span.get_text(strip=True) if span else ""
            else:
                label = a.get("aria-label", "")

            if href:
                products.append({
                    "name": label,
                    "url": href,
                    "image": src
                })

    return products


# =========================
# Sales History
# =========================

def getprice(price_url):
    request_obj = req.Request(price_url, headers=headers)

    with req.urlopen(request_obj) as response:
        result = response.read().decode("utf-8")

    data = json.loads(result)

    items = data.get("history", [])

    prices = []

    for item in items:
        prices.append({
            "date": item.get("date"),
            "price": item.get("price"),
            "condition": item.get("condition")
        })

    return prices


def get_product_id(product_url):
    parsed = urlparse(product_url)
    parts = parsed.path.strip("/").split("/")

    if "apparels" in parts:
        index = parts.index("apparels")

        if index + 1 < len(parts):
            return parts[index + 1]

    return product_url.rstrip("/").split("/")[-1]


def build_sales_history_url(product_id, condition="PSA10", page=1, per_page=20):
    condition_id = CONDITION_ID_MAP.get(condition)

    if condition_id is None:
        condition_id = CONDITION_ID_MAP["PSA10"]

    return (
        f"https://snkrdunk.com/v1/apparels/{product_id}/sales-history"
        f"?page={page}&per_page={per_page}&condition_id={condition_id}"
    )


def get_prices_by_conditions(product_id, conditions=None):
    """
    conditions 沒有傳入時，預設只抓一般版：
    PSA10 / PSA9 / PSA8以下

    Pro 會員要抓 A / B 時，請從 app.py 傳入：
    conditions=PRO_CONDITIONS
    """
    if conditions is None:
        conditions = BASE_CONDITIONS

    result = {}

    for condition in conditions:
        price_url = build_sales_history_url(
            product_id,
            condition=condition,
            page=1,
            per_page=20
        )

        try:
            prices = getprice(price_url)
        except Exception as e:
            print(f"{condition} 成交資料抓取失敗：", e)
            prices = []

        result[condition] = prices

    return result


def get_base_conditions():
    return BASE_CONDITIONS


def get_pro_conditions():
    return PRO_CONDITIONS