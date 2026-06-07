import ssl
ssl._create_default_https_context = ssl._create_unverified_context

import urllib.request as req
from urllib.parse import quote
import json
import bs4

from config import headers


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


def getprice(price_url):
    request_obj = req.Request(price_url, headers=headers)

    with req.urlopen(request_obj) as response:
        result = response.read().decode("utf-8")

    data = json.loads(result)

    items = data.get("history", [])

    prices = []

    for item in items:
        if item.get("condition") == "PSA10":
            prices.append({
                "date": item.get("date"),
                "price": item.get("price"),
                "condition": item.get("condition")
            })

    return prices


def get_product_id(product_url):
    return product_url.rstrip("/").split("/")[-1]


def build_sales_history_url(product_id):
    return f"https://snkrdunk.com/v1/apparels/{product_id}/sales-history?size_id=0&page=1&per_page=20"