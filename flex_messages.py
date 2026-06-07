from linebot.models import (
    FlexSendMessage,
    BubbleContainer,
    ImageComponent,
    BoxComponent,
    TextComponent,
    ButtonComponent,
    URIAction,
    PostbackAction
)

from urllib.parse import quote
from config import BASE_URL


def safe_image_url(image_url):
    if not image_url or not image_url.startswith("http"):
        return "https://via.placeholder.com/300x300.png?text=No+Image"

    return image_url


def format_jpy_price(price):
    """
    把 SNKRDUNK 抓到的價格轉成整數。
    """
    try:
        return int(float(str(price).replace(",", "")))
    except:
        return None


def format_date_text(date):
    """
    把日期縮短，避免 LINE Flex 顯示不完整。
    例如：
    2026/05/20 -> 26/05/20
    2026-05-20 -> 26/05/20
    1日前 -> 1日前
    """
    date_text = str(date).strip()
    date_text = date_text.replace("-", "/")

    if len(date_text) >= 10 and date_text[4] == "/":
        return date_text[2:10]

    return date_text


def format_twd_price(jpy_price, jpy_rate):
    if jpy_price is None or not jpy_rate:
        return None

    return round(jpy_price * jpy_rate)


def calculate_price_stats(prices):
    valid_prices = []

    for p in prices:
        jpy_price = format_jpy_price(p["price"])

        if jpy_price is not None:
            valid_prices.append(jpy_price)

    if not valid_prices:
        return None

    highest = max(valid_prices)
    lowest = min(valid_prices)
    average = round(sum(valid_prices) / len(valid_prices))

    return {
        "highest": highest,
        "average": average,
        "lowest": lowest
    }


def create_cadouka_add_url(product_name, price_stats, jpy_rate, image_url=""):
    """
    產生 Cadouka 新增卡牌頁網址。
    自動帶入：
    - card_name
    - grade = PSA10
    - current_market_price = 平均成交價換算台幣
    - image_url = SNKRDUNK 抓到的商品圖片
    """
    market_price = 0

    if price_stats and jpy_rate:
        market_price = round(price_stats["average"] * jpy_rate)

    base_url = BASE_URL.strip().rstrip("/")

    if not base_url.startswith("http://") and not base_url.startswith("https://"):
        base_url = "https://" + base_url

    return (
        f"{base_url}/cards/add"
        f"?card_name={quote(product_name)}"
        f"&grade=PSA10"
        f"&current_market_price={market_price}"
        f"&image_url={quote(image_url, safe='')}"
    )


def create_price_stat_box(price_stats, jpy_rate=None):
    """
    美化版最高 / 平均 / 最低三欄卡片。
    """
    stat_rows = [
        ("最高", price_stats["highest"]),
        ("平均", price_stats["average"]),
        ("最低", price_stats["lowest"])
    ]

    stat_boxes = []

    for label, jpy_value in stat_rows:
        jpy_text = f"¥{jpy_value:,}"

        twd_value = format_twd_price(jpy_value, jpy_rate)

        if twd_value is not None:
            twd_text = f"NT${twd_value:,}"
        else:
            twd_text = "匯率失敗"

        stat_boxes.append(
            BoxComponent(
                layout="vertical",
                flex=1,
                spacing="xs",
                background_color="#F7F7F7",
                corner_radius="md",
                padding_all="sm",
                contents=[
                    TextComponent(
                        text=label,
                        size="xs",
                        color="#777777",
                        weight="bold",
                        align="center"
                    ),
                    TextComponent(
                        text=jpy_text,
                        size="sm",
                        color="#222222",
                        weight="bold",
                        align="center",
                        wrap=True
                    ),
                    TextComponent(
                        text=twd_text,
                        size="xs",
                        color="#999999",
                        align="center",
                        wrap=True
                    )
                ]
            )
        )

    return BoxComponent(
        layout="horizontal",
        spacing="sm",
        margin="md",
        contents=stat_boxes
    )


def create_price_flex(product, prices, jpy_rate=None):
    product_name = product["name"] if product["name"] else "未命名商品"
    product_url = product["url"]
    image_url = safe_image_url(product["image"])

    # 最高、平均、最低會用全部抓到的 prices 去計算
    price_stats = calculate_price_stats(prices) if prices else None

    # Cadouka 新增卡牌頁網址
    cadouka_add_url = create_cadouka_add_url(
    product_name,
    price_stats,
    jpy_rate,
    image_url
    )

    price_contents = []

    # 表格標題
    price_contents.append(
        BoxComponent(
            layout="horizontal",
            padding_bottom="sm",
            contents=[
                TextComponent(
                    text="Date",
                    size="sm",
                    color="#999999",
                    flex=3,
                    weight="bold"
                ),
                TextComponent(
                    text="Grade",
                    size="sm",
                    color="#999999",
                    flex=2,
                    align="center",
                    weight="bold"
                ),
                TextComponent(
                    text="Price",
                    size="sm",
                    color="#999999",
                    flex=4,
                    align="end",
                    weight="bold"
                )
            ]
        )
    )

    if prices:
        # 成交明細只顯示前 10 筆，避免 Flex 太長或當機
        for idx, p in enumerate(prices[:10]):
            jpy_price = format_jpy_price(p["price"])

            if jpy_price is not None:
                jpy_text = f"¥{jpy_price:,}"

                twd_value = format_twd_price(jpy_price, jpy_rate)

                if twd_value is not None:
                    twd_text = f"NT${twd_value:,}"
                else:
                    twd_text = "匯率取得失敗"
            else:
                jpy_text = f'¥{p["price"]}'
                twd_text = "無法換算台幣"

            price_right_contents = [
                TextComponent(
                    text=jpy_text,
                    size="md",
                    color="#222222",
                    weight="bold",
                    align="end"
                ),
                TextComponent(
                    text=twd_text,
                    size="sm",
                    color="#999999",
                    align="end"
                )
            ]

            row_contents = [
                BoxComponent(
                    layout="horizontal",
                    spacing="sm",
                    padding_top="sm",
                    padding_bottom="sm",
                    contents=[
                        TextComponent(
                            text=format_date_text(p["date"]),
                            size="sm",
                            color="#666666",
                            flex=3,
                            wrap=False
                        ),
                        TextComponent(
                            text=str(p["condition"]),
                            size="sm",
                            color="#666666",
                            flex=2,
                            align="center"
                        ),
                        BoxComponent(
                            layout="vertical",
                            flex=4,
                            contents=price_right_contents
                        )
                    ]
                )
            ]

            # 第一筆不用分隔線，第二筆開始才加淡灰分隔線
            if idx == 0:
                price_contents.append(
                    BoxComponent(
                        layout="vertical",
                        contents=row_contents
                    )
                )
            else:
                price_contents.append(
                    BoxComponent(
                        layout="vertical",
                        separator=True,
                        separator_color="#EEEEEE",
                        contents=row_contents
                    )
                )
    else:
        price_contents.append(
            BoxComponent(
                layout="vertical",
                padding_all="md",
                background_color="#F7F7F7",
                corner_radius="md",
                contents=[
                    TextComponent(
                        text="查無 PSA10 成交紀錄",
                        size="md",
                        color="#666666",
                        wrap=True,
                        align="center"
                    )
                ]
            )
        )

    body_contents = [
        TextComponent(
            text=product_name,
            weight="bold",
            size="lg",
            color="#222222",
            wrap=True
        )
    ]

    # 最高、平均、最低卡片，放在 PSA10 最近成交上方
    if price_stats:
        body_contents.append(
            create_price_stat_box(price_stats, jpy_rate)
        )

    # PSA10 最近成交標題
    body_contents.append(
        TextComponent(
            text="PSA10 最近成交",
            weight="bold",
            size="md",
            color="#444444",
            margin="lg"
        )
    )

    # 即期匯率放在 PSA10 最近成交下面
    if jpy_rate:
        body_contents.append(
            TextComponent(
                text=f"台灣銀行日圓即期匯率：{jpy_rate}",
                size="xs",
                color="#999999",
                wrap=True
            )
        )
    else:
        body_contents.append(
            TextComponent(
                text="日圓匯率取得失敗，僅顯示日幣價格",
                size="xs",
                color="#999999",
                wrap=True
            )
        )

    body_contents.append(
        BoxComponent(
            layout="vertical",
            spacing="none",
            margin="md",
            contents=price_contents
        )
    )

    bubble = BubbleContainer(
        hero=ImageComponent(
            url=image_url,
            size="full",
            aspect_ratio="4:3",
            aspect_mode="fit"
        ),
        body=BoxComponent(
            layout="vertical",
            spacing="sm",
            contents=body_contents
        ),
        footer=BoxComponent(
            layout="vertical",
            spacing="sm",
            contents=[
                ButtonComponent(
                    style="primary",
                    action=URIAction(
                        label="新增到 Cadouka",
                        uri=cadouka_add_url
                    )
                ),
                ButtonComponent(
                    style="secondary",
                    action=URIAction(
                        label="前往商品頁",
                        uri=product_url
                    )
                )
            ]
        )
    )

    return FlexSendMessage(
        alt_text="PSA10 成交價格",
        contents=bubble
    )


def create_product_image_grid_messages(products):
    messages = []

    # LINE 一次 reply 最多 5 則訊息
    # 一則 Flex 顯示 10 個商品：2 欄 x 5 列
    # 所以最多一次顯示 50 個商品
    max_products = min(len(products), 50)
    products = products[:max_products]

    for page_start in range(0, len(products), 10):
        page_products = products[page_start:page_start + 10]

        rows = []

        for row_start in range(0, len(page_products), 2):
            row_products = page_products[row_start:row_start + 2]

            row_contents = []

            for i, product in enumerate(row_products):
                index = page_start + row_start + i
                image_url = safe_image_url(product["image"])

                row_contents.append(
                    BoxComponent(
                        layout="vertical",
                        flex=1,
                        contents=[
                            ImageComponent(
                                url=image_url,
                                size="full",
                                aspect_ratio="1:1",
                                aspect_mode="cover",
                                action=PostbackAction(
                                    label=f"選擇商品 {index + 1}",
                                    data=f"action=select&index={index}"
                                )
                            )
                        ]
                    )
                )

            # 如果最後一排只有 1 張，補空白，避免圖片變形
            while len(row_contents) < 2:
                row_contents.append(
                    BoxComponent(
                        layout="vertical",
                        flex=1,
                        contents=[]
                    )
                )

            rows.append(
                BoxComponent(
                    layout="horizontal",
                    spacing="md",
                    contents=row_contents
                )
            )

        bubble = BubbleContainer(
            size="mega",
            body=BoxComponent(
                layout="vertical",
                spacing="md",
                contents=rows
            )
        )

        messages.append(
            FlexSendMessage(
                alt_text="請點選商品圖片",
                contents=bubble
            )
        )

    return messages