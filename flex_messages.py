from linebot.models import (
    FlexSendMessage,
    BubbleContainer,
    CarouselContainer,
    ImageComponent,
    BoxComponent,
    TextComponent,
    ButtonComponent,
    URIAction,
    PostbackAction
)

from urllib.parse import quote
from config import BASE_URL

def format_product_name_for_line(product_name):
    """
    LINE 顯示用商品名稱：
    只保留 [ 以前的文字。
    例如：
    ピカチュウ [PSA10] xxx
    -> ピカチュウ
    """
    text = str(product_name or "未命名商品").strip()

    if "[" in text:
        text = text.split("[", 1)[0].strip()

    return text or "未命名商品"

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

def is_within_24h(date_text):
    """
    判斷 SNKRDUNK 顯示的成交時間是否屬於 24 小時內。
    支援：
    - 幾分前 / 分前
    - 幾分鐘前
    - 幾時間前
    - 幾小時前
    """
    text = str(date_text).strip()

    if not text:
        return False

    if "分前" in text or "分鐘前" in text:
        return True

    if "時間前" in text or "小時前" in text:
        number_text = ""

        for ch in text:
            if ch.isdigit():
                number_text += ch

        try:
            hours = int(number_text)
            return hours <= 24
        except:
            return True

    return False


def count_24h_sales(prices):
    if not prices:
        return 0

    count = 0

    for p in prices:
        if is_within_24h(p.get("date")):
            count += 1

    return count

def create_cadouka_add_url(product_name, price_stats, jpy_rate, image_url=""):
    """
    舊版用：產生 Cadouka 新增卡牌頁網址。

    目前 LINE 新增會改走 Postback 後端直接新增，
    這個 function 先保留，避免其他地方如果還有用到會壞掉。
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
                        wrap=False
                    ),
                    TextComponent(
                        text=twd_text,
                        size="xxs",
                        color="#999999",
                        align="center",
                        wrap=False
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

def create_grade_summary_section(product_index, condition_label, prices, jpy_rate=None):
    price_stats = calculate_price_stats(prices) if prices else None
    sales_24h = count_24h_sales(prices)

    section_contents = []

    # 標題列：左邊 grade，右邊 24h 成交
    section_contents.append(
        BoxComponent(
            layout="horizontal",
            align_items="center",
            contents=[
                TextComponent(
                    text=condition_label,
                    size="md",
                    weight="bold",
                    color="#222222",
                    flex=2,
                    align="start"
                ),
                TextComponent(
                    text=f"24h 成交 {sales_24h} 筆",
                    size="xs",
                    color="#777777",
                    align="end",
                    flex=3
                )
            ]
        )
    )

    # 最高 / 平均 / 最低三格
    if price_stats:
        section_contents.append(
            create_price_stat_box(price_stats, jpy_rate)
        )
    else:
        section_contents.append(
            BoxComponent(
                layout="vertical",
                padding_all="md",
                background_color="#F7F7F7",
                corner_radius="md",
                margin="md",
                contents=[
                    TextComponent(
                        text=f"查無 {condition_label} 成交紀錄",
                        size="sm",
                        color="#666666",
                        align="center",
                        wrap=True
                    )
                ]
            )
        )

    history_action_data = f"action=history&index={product_index}&grade={quote(condition_label)}"
    add_card_action_data = f"action=add_card&index={product_index}&grade={quote(condition_label)}"

    # 按鈕列
    section_contents.append(
        BoxComponent(
            layout="horizontal",
            spacing="sm",
            margin="md",
            contents=[
                ButtonComponent(
                    style="secondary",
                    height="sm",
                    action=PostbackAction(
                        label="歷史成交",
                        data=history_action_data,
                        display_text=f"{condition_label} 歷史成交"
                    ),
                    flex=1
                ),
                ButtonComponent(
                    style="primary",
                    height="sm",
                    action=PostbackAction(
                        label="加入",
                        data=add_card_action_data,
                        display_text="加入"
                    ),
                    flex=1
                )
            ]
        )
    )

    return BoxComponent(
        layout="vertical",
        spacing="sm",
        margin="lg",
        padding_all="md",
        background_color="#FFFFFF",
        corner_radius="md",
        contents=section_contents
    )

def get_condition_order(prices_by_conditions=None, condition_order=None):
    """
    決定 LINE Flex 要顯示哪些 condition。

    Free：
    - PSA10 / PSA9 / PSA8以下

    Pro：
    - A / B / PSA10 / PSA9 / PSA8以下

    app.py 如果有傳 condition_order，就優先使用 app.py 傳入的順序。
    如果沒有傳，則根據 prices_by_conditions 裡有沒有 A / B 自動判斷。
    """
    base_conditions = ["PSA10", "PSA9", "PSA8以下"]
    pro_conditions = ["PSA10", "PSA9", "PSA8以下", "A", "B"]

    if condition_order:
        return condition_order

    if prices_by_conditions:
        if "A" in prices_by_conditions or "B" in prices_by_conditions:
            return pro_conditions

    return base_conditions


def create_grade_summary_flex(
    product,
    prices_by_conditions,
    jpy_rate=None,
    product_index=None,
    condition_order=None
):
    raw_product_name = product["name"] if product["name"] else "未命名商品"
    product_name = format_product_name_for_line(raw_product_name)

    product_url = product["url"]
    image_url = safe_image_url(product["image"])

    body_contents = [
        BoxComponent(
            layout="horizontal",
            spacing="md",
            margin="none",
            contents=[
                BoxComponent(
                    layout="vertical",
                    flex=2,
                    contents=[
                        ImageComponent(
                            url=image_url,
                            size="full",
                            aspect_ratio="1:1",
                            aspect_mode="cover",
                            corner_radius="md"
                        )
                    ]
                ),
                BoxComponent(
                    layout="vertical",
                    flex=3,
                    justify_content="center",
                    contents=[
                        TextComponent(
                            text=product_name,
                            weight="bold",
                            size="md",
                            color="#222222",
                            wrap=True
                        )
                    ]
                )
            ]
        )
    ]

    for condition_label in get_condition_order(
        prices_by_conditions=prices_by_conditions,
        condition_order=condition_order
    ):
        prices = prices_by_conditions.get(condition_label, [])

        body_contents.append(
            create_grade_summary_section(
                product_index=product_index,
                condition_label=condition_label,
                prices=prices,
                jpy_rate=jpy_rate
            )
        )

    bubble = BubbleContainer(
        size="giga",
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
        alt_text="等級行情比較",
        contents=bubble
    )

def create_history_flex(product, prices, condition_label, jpy_rate=None, product_index=None, display_limit=5):
    product_name = product["name"] if product["name"] else "未命名商品"
    product_url = product["url"]

    price_contents = []

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
        for idx, p in enumerate(prices[:display_limit]):
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
                            text=str(p.get("condition") or condition_label),
                            size="sm",
                            color="#666666",
                            flex=2,
                            align="center"
                        ),
                        BoxComponent(
                            layout="vertical",
                            flex=4,
                            contents=[
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
                        )
                    ]
                )
            ]

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
                        text=f"查無 {condition_label} 成交紀錄",
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
            text=f"{condition_label} 歷史成交",
            weight="bold",
            size="lg",
            color="#222222",
            wrap=True
        ),
        TextComponent(
            text=product_name,
            size="sm",
            color="#666666",
            wrap=True,
            margin="sm"
        )
    ]

    if jpy_rate:
        body_contents.append(
            TextComponent(
                text=f"台灣銀行日圓即期匯率：{jpy_rate}",
                size="xs",
                color="#999999",
                wrap=True,
                margin="sm"
            )
        )
    else:
        body_contents.append(
            TextComponent(
                text="日圓匯率取得失敗，僅顯示日幣價格",
                size="xs",
                color="#999999",
                wrap=True,
                margin="sm"
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

    if product_index is not None:
        add_card_action_data = f"action=add_card&index={product_index}&grade={quote(condition_label)}"
    else:
        add_card_action_data = f"action=add_card&grade={quote(condition_label)}"

    bubble = BubbleContainer(
        size="giga",
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
                    action=PostbackAction(
                        label="加入 Cadouka",
                        data=add_card_action_data,
                        display_text="加入 Cadouka"
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
        alt_text=f"{condition_label} 歷史成交",
        contents=bubble
    )

def create_price_bubble_for_condition(product, prices, condition_label, jpy_rate=None, product_index=None):
    product_name = product["name"] if product["name"] else "未命名商品"
    product_url = product["url"]
    image_url = safe_image_url(product["image"])

    price_stats = calculate_price_stats(prices) if prices else None

    price_contents = []

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
                            text=str(p.get("condition") or condition_label),
                            size="sm",
                            color="#666666",
                            flex=2,
                            align="center"
                        ),
                        BoxComponent(
                            layout="vertical",
                            flex=4,
                            contents=[
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
                        )
                    ]
                )
            ]

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
                        text=f"查無 {condition_label} 成交紀錄",
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

    if price_stats:
        body_contents.append(
            create_price_stat_box(price_stats, jpy_rate)
        )

    body_contents.append(
        TextComponent(
            text=f"{condition_label} 最近成交",
            weight="bold",
            size="md",
            color="#444444",
            margin="lg"
        )
    )

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

    if product_index is not None:
        add_card_action_data = f"action=add_card&index={product_index}&grade={quote(condition_label)}"
    else:
        add_card_action_data = f"action=add_card&grade={quote(condition_label)}"

    return BubbleContainer(
        size="giga",
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
                    action=PostbackAction(
                        label="加入 Cadouka",
                        data=add_card_action_data,
                        display_text="加入 Cadouka"
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

def create_price_flex(product, prices, jpy_rate=None, product_index=None):
    """
    建立 PSA10 成交價格 Flex。

    product_index：
    - LINE 使用者點選商品時的 index
    - 之後按「加入 Cadouka 」會把 index 傳回 app.py
    - app.py 再用這個 index 從 user_products[line_user_id] 找到原商品資料
    """
    product_name = product["name"] if product["name"] else "未命名商品"
    product_url = product["url"]
    image_url = safe_image_url(product["image"])

    # 最高、平均、最低會用全部抓到的 prices 去計算
    price_stats = calculate_price_stats(prices) if prices else None

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

    # 加入 Cadouka 按鈕：
    # 改成 PostbackAction，讓 LINE 後端直接新增，不再打開網站新增頁。
    if product_index is not None:
        add_card_action_data = f"action=add_card&index={product_index}"
    else:
        add_card_action_data = "action=add_card"

    bubble = BubbleContainer(
        size="giga",
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
                    action=PostbackAction(
                        label="加入 Cadouka",
                        data=add_card_action_data,
                        display_text="加入 Cadouka"
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

def create_price_flex_carousel(
    product,
    prices_by_conditions,
    jpy_rate=None,
    product_index=None,
    condition_order=None
):
    bubbles = []

    for condition_label in get_condition_order(
        prices_by_conditions=prices_by_conditions,
        condition_order=condition_order
    ):
        prices = prices_by_conditions.get(condition_label, [])

        bubble = create_price_bubble_for_condition(
            product=product,
            prices=prices,
            condition_label=condition_label,
            jpy_rate=jpy_rate,
            product_index=product_index
        )

        bubbles.append(bubble)

    carousel = CarouselContainer(
        contents=bubbles
    )

    return FlexSendMessage(
        alt_text="成交價格分析",
        contents=carousel
    )

def create_product_image_grid_messages(products):
    messages = []

    # LINE 一次 reply 最多 5 則訊息
    # 這裡維持最多顯示 30 個商品
    # 一則 Flex：4 欄 x 5 排 = 20 個商品
    max_products = min(len(products), 30)
    display_products = products[:max_products]

    items_per_message = 20
    items_per_row = 4

    for page_start in range(0, len(display_products), items_per_message):
        page_products = display_products[page_start:page_start + items_per_message]

        rows = []

        for row_start in range(0, len(page_products), items_per_row):
            row_products = page_products[row_start:row_start + items_per_row]

            row_contents = []

            for i, product in enumerate(row_products):
                index = page_start + row_start + i
                image_url = safe_image_url(product["image"])

                row_contents.append(
                    BoxComponent(
                        layout="vertical",
                        flex=1,
                        padding_all="xs",
                        background_color="#FFFFFF",
                        corner_radius="md",
                        contents=[
                            ImageComponent(
                                url=image_url,
                                size="full",
                                aspect_ratio="1:1",
                                aspect_mode="cover",
                                corner_radius="sm",
                                action=PostbackAction(
                                    label=f"選擇商品 {index + 1}",
                                    data=f"action=select&index={index}"
                                )
                            )
                        ]
                    )
                )

            # 如果最後一排不足 4 張，補空白，避免圖片被拉大
            while len(row_contents) < items_per_row:
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
                    spacing="xs",
                    contents=row_contents
                )
            )

        bubble = BubbleContainer(
            size="giga",
            body=BoxComponent(
                layout="vertical",
                background_color="#F3F4F6",
                padding_all="md",
                spacing="sm",
                contents=[
                    BoxComponent(
                        layout="vertical",
                        padding_top="sm",
                        padding_bottom="xs",
                        contents=[
                            TextComponent(
                                text="Cadouka Search",
                                size="lg",
                                weight="bold",
                                color="#374151",
                                align="center",
                                wrap=True
                            )
                        ]
                    ),
                    BoxComponent(
                        layout="vertical",
                        spacing="xs",
                        margin="md",
                        contents=rows
                        
                    )
                ]
            )
        )

        messages.append(
            FlexSendMessage(
                alt_text="請點選商品圖片",
                contents=bubble
            )
        )

    return messages

def create_market_image_card_flex(
    product,
    card_image_url,
    product_index,
    selected_grade="PSA10",
    is_pro=False
):
    product_url = product["url"]

    grade_buttons = [
        ButtonComponent(
            style="secondary",
            height="sm",
            action=PostbackAction(
                label="PSA9",
                data=f"action=select&index={product_index}&grade=PSA9",
                display_text="查看 PSA9"
            ),
            flex=1
        ),
        ButtonComponent(
            style="secondary",
            height="sm",
            action=PostbackAction(
                label="PSA8↓",
                data=f"action=select&index={product_index}&grade={quote('PSA8以下')}",
                display_text="查看 PSA8以下"
            ),
            flex=1
        )
    ]

    if is_pro:
        grade_buttons.extend([
            ButtonComponent(
                style="secondary",
                height="sm",
                action=PostbackAction(
                    label="A",
                    data=f"action=select&index={product_index}&grade=A",
                    display_text="查看 A"
                ),
                flex=1
            ),
            ButtonComponent(
                style="secondary",
                height="sm",
                action=PostbackAction(
                    label="B",
                    data=f"action=select&index={product_index}&grade=B",
                    display_text="查看 B"
                ),
                flex=1
            )
        ])

    bubble = BubbleContainer(
        size="giga",
        hero=ImageComponent(
            url=card_image_url,
            size="full",
            background_color="#F3F4F6",
            aspect_ratio="5:3",
            aspect_mode="fit"
        ),
        footer=BoxComponent(
            layout="vertical",
            spacing="sm",
            background_color="#F3F4F6",
            contents=[
                BoxComponent(
                    layout="horizontal",
                    spacing="sm",
                    contents=grade_buttons
                ),
                BoxComponent(
                    layout="horizontal",
                    spacing="sm",
                    contents=[
                        ButtonComponent(
                            style="primary",
                            height="sm",
                            action=PostbackAction(
                                label="加入倉庫",
                                data=f"action=add_card&index={product_index}&grade={quote(selected_grade)}",
                                display_text="加入倉庫"
                            ),
                            flex=1
                        ),
                        ButtonComponent(
                            style="secondary",
                            height="sm",
                            action=URIAction(
                                label="前往商品頁",
                                uri=product_url
                            ),
                            flex=1
                        )
                    ]
                )
            ]
        )
    )

    return FlexSendMessage(
        alt_text=f"{selected_grade} 折線圖卡片",
        contents=bubble
    )