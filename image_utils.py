import io
import os
import uuid
import urllib.request as req
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager, rcParams
from matplotlib.ticker import MaxNLocator

from PIL import Image, ImageChops, ImageDraw, ImageFont

from config import headers

def crop_white_border(
    image_bytes,
    tolerance=15,
    crop_left=0,
    crop_top=0,
    crop_right=0,
    crop_bottom=0,
    auto_crop=True
):
    """
    裁切商品圖。

    功能：
    1. auto_crop=True 時，先自動裁掉透明邊 / 白邊。
    2. 再依照 crop_left / crop_top / crop_right / crop_bottom
       手動裁掉指定像素。

    參數意思：
    crop_left   = 左邊再裁掉多少 px
    crop_top    = 上面再裁掉多少 px
    crop_right  = 右邊再裁掉多少 px
    crop_bottom = 下面再裁掉多少 px
    auto_crop   = 是否先自動裁白邊
    """
    image = Image.open(io.BytesIO(image_bytes))

    # =========================
    # 1. 先自動裁透明邊 / 白邊
    # =========================
    if auto_crop:
        # 透明背景：先用 alpha 找內容範圍
        if image.mode in ("RGBA", "LA") or "transparency" in image.info:
            image = image.convert("RGBA")

            alpha = image.getchannel("A")
            bbox = alpha.getbbox()

            if bbox:
                image = image.crop(bbox)

            # 透明背景鋪成白底，避免變黑
            white_bg = Image.new("RGBA", image.size, (255, 255, 255, 255))
            white_bg.paste(image, (0, 0), image)
            image = white_bg.convert("RGB")

        else:
            image = image.convert("RGB")

            # 自動裁白邊
            bg = Image.new("RGB", image.size, (255, 255, 255))
            diff = ImageChops.difference(image, bg)
            diff = ImageChops.add(diff, diff, 2.0, -tolerance)

            bbox = diff.getbbox()

            if bbox:
                image = image.crop(bbox)

    else:
        image = image.convert("RGB")

    # =========================
    # 2. 再手動裁上下左右
    # =========================
    width, height = image.size

    left = max(0, int(crop_left or 0))
    top = max(0, int(crop_top or 0))
    right = max(0, int(crop_right or 0))
    bottom = max(0, int(crop_bottom or 0))

    crop_x1 = left
    crop_y1 = top
    crop_x2 = width - right
    crop_y2 = height - bottom

    # 避免裁到壞掉
    if crop_x2 > crop_x1 and crop_y2 > crop_y1:
        image = image.crop((crop_x1, crop_y1, crop_x2, crop_y2))

    output = io.BytesIO()
    image.save(output, format="PNG", quality=95)
    output.seek(0)

    return output

GENERATED_DIR = os.path.join("static", "generated")


def ensure_generated_dir():
    os.makedirs(GENERATED_DIR, exist_ok=True)

def save_debug_image(image_data, filename):
    """
    把 debug 圖片存到 static/generated/
    image_data 可以是：
    - bytes
    - BytesIO
    - PIL Image
    """
    ensure_generated_dir()

    output_path = os.path.join(GENERATED_DIR, filename)

    try:
        if isinstance(image_data, Image.Image):
            image = image_data.convert("RGB")

        elif isinstance(image_data, io.BytesIO):
            image_data.seek(0)
            image = Image.open(image_data).convert("RGB")

        else:
            image = Image.open(io.BytesIO(image_data)).convert("RGB")

        image.save(output_path, format="PNG")

        print("DEBUG 圖片已輸出：", output_path, flush=True)

        return output_path

    except Exception as e:
        print("DEBUG 圖片輸出失敗：", e, flush=True)
        return None

def download_image_bytes(image_url):
    if not image_url or not str(image_url).startswith("http"):
        return None

    try:
        request_obj = req.Request(image_url, headers=headers)
        with req.urlopen(request_obj, timeout=15) as response:
            return response.read()
    except Exception as e:
        print("下載商品圖片失敗：", e)
        return None


BASE_DIR = Path(__file__).resolve().parent
FONT_DIR = BASE_DIR / "fonts"


def get_font(size=24, bold=False):
    if bold:
        font_names = [
            "NotoSansTC-Bold.ttf",
            "NotoSansCJKtc-Bold.otf",
            "NotoSansCJKjp-Bold.otf"
        ]
        system_fonts = [
            "C:/Windows/Fonts/msjhbd.ttc",
            "C:/Windows/Fonts/meiryo.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        ]
    else:
        font_names = [
            "NotoSansTC-Regular.ttf",
            "NotoSansCJKtc-Regular.otf",
            "NotoSansCJKjp-Regular.otf"
        ]
        system_fonts = [
            "C:/Windows/Fonts/msjh.ttc",
            "C:/Windows/Fonts/meiryo.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        ]

    for font_name in font_names:
        font_path = FONT_DIR / font_name

        try:
            if font_path.exists():
                return ImageFont.truetype(str(font_path), size=size)
        except Exception as e:
            print("Pillow 字型載入失敗：", font_path, e, flush=True)

    for font_path in system_fonts:
        try:
            return ImageFont.truetype(font_path, size=size)
        except:
            continue

    return ImageFont.load_default()


def setup_matplotlib_font():
    font_names = [
        "NotoSansTC-Regular.ttf",
        "NotoSansCJKtc-Regular.otf",
        "NotoSansCJKjp-Regular.otf"
    ]

    for font_name in font_names:
        font_path = FONT_DIR / font_name

        try:
            if font_path.exists():
                font_manager.fontManager.addfont(str(font_path))
                font_prop = font_manager.FontProperties(fname=str(font_path))
                font_name = font_prop.get_name()

                rcParams["font.family"] = font_name
                rcParams["axes.unicode_minus"] = False

                print("matplotlib 使用字型：", font_name, flush=True)
                return
        except Exception as e:
            print("matplotlib 字型載入失敗：", font_path, e, flush=True)

    rcParams["axes.unicode_minus"] = False
    print("matplotlib 找不到 CJK 字型，使用預設字型", flush=True)


setup_matplotlib_font()


def text_width(draw, text, font):
    bbox = draw.textbbox((0, 0), str(text), font=font)
    return bbox[2] - bbox[0]


def wrap_text_by_width(draw, text, font, max_width, max_lines=3):
    text = str(text or "").strip()

    if not text:
        return ["未命名商品"]

    lines = []
    current = ""

    for ch in text:
        trial = current + ch

        if text_width(draw, trial, font) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = ch

            if len(lines) >= max_lines:
                break

    if current and len(lines) < max_lines:
        lines.append(current)

    if len(lines) > max_lines:
        lines = lines[:max_lines]

    if len(lines) == max_lines and text:
        last = lines[-1]
        if len(last) >= 2:
            lines[-1] = last[:-1] + "…"
        else:
            lines[-1] = last + "…"

    return lines


def format_product_name_for_card(product_name):
    text = str(product_name or "未命名商品").strip()

    # 顯示到 ]，包含 ]
    if "]" in text:
        text = text.split("]", 1)[0].strip() + "]"

    return text or "未命名商品"


def parse_jpy_price(price):
    try:
        return int(float(str(price).replace(",", "").replace("¥", "").strip()))
    except:
        return None

def format_jpy_text(value):
    try:
        return f"¥{int(value):,}"
    except:
        return "¥-"


def format_twd_text(jpy_value, jpy_rate):
    if not jpy_rate:
        return "約 NT$-"

    try:
        twd_value = round(int(jpy_value) * float(jpy_rate))
        return f"約 NT${twd_value:,}"
    except:
        return "約 NT$-"


def calculate_price_stats_for_card(prices):
    valid_prices = []

    for item in prices or []:
        jpy_price = parse_jpy_price(item.get("price"))

        if jpy_price is not None:
            valid_prices.append(jpy_price)

    if not valid_prices:
        return {
            "has_data": False,
            "highest": 0,
            "average": 0,
            "lowest": 0,
            "latest": 0,
            "count": 0
        }

    return {
        "has_data": True,
        "highest": max(valid_prices),
        "average": round(sum(valid_prices) / len(valid_prices)),
        "lowest": min(valid_prices),
        "latest": valid_prices[0],
        "count": len(valid_prices)
    }

def short_date_text(date_text):
    text = str(date_text or "").strip().replace("-", "/")

    if len(text) >= 10 and text[4] == "/":
        return text[2:10]

    return text


def create_contain_image(image, target_size, bg_color=(255, 255, 255)):
    target_w, target_h = target_size
    canvas = Image.new("RGB", (target_w, target_h), bg_color)

    image = image.convert("RGB")
    image.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)

    paste_x = (target_w - image.width) // 2
    paste_y = (target_h - image.height) // 2
    canvas.paste(image, (paste_x, paste_y))

    return canvas


def generate_price_chart_image(prices, selected_grade="PSA10", y_tick_font_size=26):
    """
    回傳 PIL Image（日期切換點 + 單一月份標示版本）

    功能：
    - 使用抓到的全部筆數
    - 每筆資料在線上有一個點
    - X 軸只標「日期切換點」
    - X 軸只顯示「日期」或 API 回傳的簡短時間文字
    - 只顯示第一個月份，放在第一個 X 軸日期左邊
    - 日期切換點往上畫淡虛線
    - 顯示 X / Y 軸線
    - 不做大面積填色
    - 不顯示折線旁價格文字
    """
    valid_items = []

    # API 多半是新到舊，這裡反轉成舊到新
    for item in reversed(prices or []):
        jpy_price = parse_jpy_price(item.get("price"))

        if jpy_price is None:
            continue

        raw_date = item.get("date")
        date_text = short_date_text(raw_date)  # 例如 26/06/10、06/10、1日前

        month_text = ""
        day_text = ""
        full_date_key = date_text

        parts = date_text.split("/")

        # 預期像 26/06/10
        if len(parts) == 3:
            month_text = parts[1]
            day_text = parts[2]

        # 預期像 06/10
        elif len(parts) == 2:
            month_text = parts[0]
            day_text = parts[1]

        else:
            # 如果 API 回傳 1日前、11時間前，就直接顯示原文字
            day_text = date_text

        valid_items.append({
            "price": jpy_price,
            "date_key": full_date_key,
            "month": month_text,
            "day": day_text or "-"
        })

    # 圖表本體加大，讓下方統計搬走後的空間可以被折線圖吃掉
    fig, ax = plt.subplots(figsize=(11.2, 6.0), dpi=200)

    if valid_items:
        x_values = list(range(1, len(valid_items) + 1))
        y_values = [item["price"] for item in valid_items]

        # 折線 + 每筆資料的小圓點
        ax.plot(
            x_values,
            y_values,
            linewidth=2.8,
            marker="o",
            markersize=5,
            markeredgewidth=1.1,
            solid_capstyle="round",
            solid_joinstyle="round",
            zorder=3
        )

        # =========================
        # 找日期切換點（一天一個）
        # =========================
        date_tick_positions = []
        date_tick_labels = []
        previous_date_key = None

        for index, item in enumerate(valid_items):
            current_date_key = item["date_key"]

            if index == 0 or current_date_key != previous_date_key:
                date_tick_positions.append(index + 1)
                date_tick_labels.append(item["day"])

            previous_date_key = current_date_key

        # 如果日期切換點太多，最多顯示 6 個，避免太擠
        max_tick_count = 6

        if len(date_tick_positions) > max_tick_count:
            selected_indexes = []

            for i in range(max_tick_count):
                selected_index = round(
                    i * (len(date_tick_positions) - 1) / (max_tick_count - 1)
                )
                selected_indexes.append(selected_index)

            selected_indexes = sorted(set(selected_indexes))
            date_tick_positions = [date_tick_positions[i] for i in selected_indexes]
            date_tick_labels = [date_tick_labels[i] for i in selected_indexes]

        # X 軸顯示日期
        ax.set_xticks(date_tick_positions)
        ax.set_xticklabels(date_tick_labels, fontsize=22, color="#777777")
        ax.tick_params(
            axis="x",
            length=0,
            pad=9,
            colors="#777777"
        )

        # 日期切換點：淡淡的垂直虛線
        for tick_x in date_tick_positions:
            ax.axvline(
                x=tick_x,
                linestyle="--",
                linewidth=0.9,
                alpha=0.20,
                color="#9CA3AF",
                zorder=1
            )

        # 只顯示第一個月份，放在第一個 X 軸日期左邊，不顯示 7月 / 8月
        first_month = valid_items[0]["month"] if valid_items and valid_items[0]["month"] else ""

        if first_month and date_tick_positions:
            first_tick_x = date_tick_positions[0]
            ax.text(
                first_tick_x - 0.35,
                -0.08,
                f"{first_month}月",
                transform=ax.get_xaxis_transform(),
                fontsize=22,
                color="#777777",
                ha="right",
                va="top"
            )

        # Y 軸數字與刻度數量
        ax.yaxis.set_major_locator(MaxNLocator(nbins=5, min_n_ticks=4))
        ax.tick_params(
            axis="y",
            labelsize=y_tick_font_size,
            length=0,
            colors="#666666"
        )

        # 淡淡水平線
        ax.grid(axis="y", alpha=0.12, linewidth=0.8)
        ax.grid(axis="x", visible=False)

        # 顯示 X / Y 軸線
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        ax.spines["bottom"].set_visible(True)
        ax.spines["bottom"].set_color("#D5DAE1")
        ax.spines["bottom"].set_linewidth(1.0)

        ax.spines["left"].set_visible(True)
        ax.spines["left"].set_color("#D5DAE1")
        ax.spines["left"].set_linewidth(1.0)

        ax.set_xlabel("")
        ax.set_ylabel("")

        # 留一點邊界
        ax.margins(x=0.04, y=0.16)
        ax.set_axisbelow(True)

    else:
        ax.text(
            0.5,
            0.5,
            f"查無 {selected_grade} 成交資料",
            ha="center",
            va="center",
            fontsize=20,
            color="#777777"
        )
        ax.set_xticks([])
        ax.set_yticks([])

        for spine in ax.spines.values():
            spine.set_visible(False)

    fig.subplots_adjust(left=0.15, bottom=0.20, right=0.98, top=0.96)

    output = io.BytesIO()
    fig.savefig(output, format="png", bbox_inches="tight", facecolor="True")
    plt.close(fig)

    output.seek(0)
    chart_image = Image.open(output).convert("RGB")
    return chart_image


def generate_market_card_image(product, prices, selected_grade="PSA10", jpy_rate=None):
    """
    產生市場圖卡，存到 static/generated/
    回傳檔名（不是完整 URL）

    版面：
    - 左側商品圖維持目前大小
    - 上方只放商品名稱
    - 折線圖放大並往上移
    - PSA / 最高 / 平均 / 最低 移到下方資訊區
    - 右下角只保留匯率與資料來源
    """
    ensure_generated_dir()

    product_name = format_product_name_for_card(product.get("name"))
    image_url = product.get("image") or ""
    stats = calculate_price_stats_for_card(prices)

    canvas_width = 1520
    canvas_height = 940

    card = Image.new("RGB", (canvas_width, canvas_height), "#F4F6FA")
    draw = ImageDraw.Draw(card)

    # 字型
    title_font = get_font(52, bold=True)
    grade_font = get_font(44, bold=True)
    stat_label_font = get_font(34, bold=True)
    stat_jpy_font = get_font(42, bold=True)
    stat_twd_font = get_font(30, bold=False)
    footer_font = get_font(20, bold=False)

    # 外層白色卡片：圓角更乾淨
    outer_box = (8, 8, canvas_width - 8, canvas_height - 8)
    draw.rounded_rectangle(
        outer_box,
        radius=18,
        fill="white"
    )

    # =========================
    # 左側商品圖：維持目前圖片大小
    # =========================
    left_box = (58, 88, 500, 690)

    draw.rounded_rectangle(
        left_box,
        radius=12,
        fill="#FAFAFA"
    )

    product_image_bytes = download_image_bytes(image_url)

    if product_image_bytes:
        try:
            cropped_output = crop_white_border(
                product_image_bytes,
                crop_left=0,
                crop_top=0,
                crop_right=0,
                crop_bottom=0,
                auto_crop=True
            )

            product_image = Image.open(cropped_output).convert("RGB")

        except Exception as e:
            print("商品圖裁切失敗：", e, flush=True)
            product_image = None
    else:
        product_image = None

    if product_image:
        target_w = 420
        target_h = 590

        try:
            resample_filter = Image.Resampling.LANCZOS
        except AttributeError:
            resample_filter = Image.LANCZOS

        # 允許圖片放大，保持比例塞進左側區塊
        original_w, original_h = product_image.size

        scale = min(
            target_w / original_w,
            target_h / original_h
        )

        new_w = int(original_w * scale)
        new_h = int(original_h * scale)

        product_image = product_image.resize(
            (new_w, new_h),
            resample_filter
        )

        paste_x = left_box[0] + ((left_box[2] - left_box[0]) - product_image.width) // 2
        paste_y = left_box[1] + ((left_box[3] - left_box[1]) - product_image.height) // 2

        card.paste(product_image, (paste_x, paste_y))

    else:
        placeholder_font = get_font(30, bold=True)
        draw.text(
            (left_box[0] + 120, left_box[1] + 250),
            "No Image",
            fill="#999999",
            font=placeholder_font
        )

    # =========================
    # 右側座標
    # =========================
    right_x = 520
    right_w = 930

    # 商品名稱：加大，若太長就自動微縮，避免超出右側
    title_x = right_x
    title_y = 72
    title_font_size = 52
    title_font_dynamic = title_font

    while text_width(draw, product_name, title_font_dynamic) > right_w and title_font_size > 40:
        title_font_size -= 2
        title_font_dynamic = get_font(title_font_size, bold=True)

    draw.text(
        (title_x, title_y),
        product_name,
        fill="#222222",
        font=title_font_dynamic
    )

    # =========================
    # 放大後的折線圖：往上移，吃掉原本統計區空間
    # =========================
    chart_image = generate_price_chart_image(
        prices,
        selected_grade=selected_grade,
        y_tick_font_size=26
    )

    chart_image = create_contain_image(
        chart_image,
        (950, 585),
        bg_color=(255, 255, 255)
    )

    card.paste(chart_image, (right_x + 6, 180))

    # =========================
    # 下方統計區：PSA10 / 最高 / 平均 / 最低
    # =========================
    bottom_stat_y = 715

    draw.text((90, bottom_stat_y + 26), selected_grade, fill="#2F5FE8", font=grade_font)

    stat_start_x = 680
    stat_gap = 60
    stat_w = 220

    stat_items = [
        ("最高", stats["highest"]),
        ("平均", stats["average"]),
        ("最低", stats["lowest"])
    ]

    for idx, (label, value) in enumerate(stat_items):
        x1 = stat_start_x + idx * (stat_w + stat_gap)
        y1 = bottom_stat_y

        # label
        label_w = text_width(draw, label, stat_label_font)
        draw.text((x1 + (stat_w - label_w) / 2, y1), label, fill="#777777", font=stat_label_font)

        jpy_text = format_jpy_text(value)
        jpy_w = text_width(draw, jpy_text, stat_jpy_font)
        draw.text((x1 + (stat_w - jpy_w) / 2, y1 + 40), jpy_text, fill="#222222", font=stat_jpy_font)

        twd_text = format_twd_text(value, jpy_rate)
        twd_w = text_width(draw, twd_text, stat_twd_font)
        draw.text((x1 + (stat_w - twd_w) / 2, y1 + 102), twd_text, fill="#999999", font=stat_twd_font)

    # =========================
    # 右下角資訊：同一排左右放
    # 左邊：資料來源；右邊：台灣銀行日圓即期匯率
    # 匯率不強制補小數位，保留抓到的原始值
    # =========================
   # 右下角資訊：同一排，整組靠右下
    footer_font = get_font(20, bold=False)
    footer_color = "#666666"

    if jpy_rate:
        rate_text = f"台灣銀行日圓即期匯率：{jpy_rate}"
    else:
        rate_text = "台灣銀行日圓即期匯率：取得失敗"

    source_text = "資料來源：SNKRDUNK"

    # 上下位置：數字越大越往下
    footer_y = 900

    # 整組最右邊的位置
    footer_right_x = canvas_width - 55

    # 兩段文字中間距離
    footer_gap = 36

    rate_w = text_width(draw, rate_text, footer_font)
    source_w = text_width(draw, source_text, footer_font)

    # 右邊：匯率，右對齊
    rate_x = footer_right_x - rate_w

    # 左邊：資料來源，貼著匯率左邊
    source_x = rate_x - footer_gap - source_w

    draw.text(
        (source_x, footer_y),
        source_text,
        fill=footer_color,
        font=footer_font
    )

    draw.text(
        (rate_x, footer_y),
        rate_text,
        fill=footer_color,
        font=footer_font
    )

    filename = f"market_card_{uuid.uuid4().hex}.png"
    output_path = os.path.join(GENERATED_DIR, filename)
    card.save(output_path, format="PNG")

    return filename
