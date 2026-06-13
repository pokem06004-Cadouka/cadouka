import io
import os
import uuid
import urllib.request as req
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager, rcParams

from PIL import Image, ImageChops, ImageDraw, ImageFont

from config import headers

def crop_white_border(image_bytes, tolerance=15):
    """
    自動裁掉圖片四周白邊或透明邊。
    適合一般商品圖。
    如果圖片本身有透明背景，會先鋪成白底，避免變黑。
    """
    image = Image.open(io.BytesIO(image_bytes))

    # 如果是透明背景圖片，先用 alpha 找內容範圍
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

        # 裁白邊
        bg = Image.new("RGB", image.size, (255, 255, 255))
        diff = ImageChops.difference(image, bg)
        diff = ImageChops.add(diff, diff, 2.0, -tolerance)

        bbox = diff.getbbox()

        if bbox:
            image = image.crop(bbox)

    output = io.BytesIO()
    image.save(output, format="JPEG", quality=95)
    output.seek(0)

    return output

GENERATED_DIR = os.path.join("static", "generated")


def ensure_generated_dir():
    os.makedirs(GENERATED_DIR, exist_ok=True)


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

    if "[" in text:
        text = text.split("[", 1)[0].strip()

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


def generate_price_chart_image(prices, selected_grade="PSA10"):
    """
    回傳 PIL Image（乾淨純折線圖）
    - 使用抓到的全部筆數
    - 不顯示日期刻度
    - 不做大面積填色
    - 只保留簡化座標軸與乾淨折線
    """
    valid_items = []

    # API 多半是新到舊，這裡反轉成舊到新，折線才會是時間往右走
    for item in reversed(prices or []):
        jpy_price = parse_jpy_price(item.get("price"))

        if jpy_price is None:
            continue

        valid_items.append(jpy_price)

    fig, ax = plt.subplots(figsize=(8.8, 4.4), dpi=200)

    if valid_items:
        x_values = list(range(1, len(valid_items) + 1))
        y_values = valid_items

        # 純折線，不做大面積填色
        ax.plot(
            x_values,
            y_values,
            linewidth=3.0,
            solid_capstyle="round",
            solid_joinstyle="round"
        )

        # 只標最後一個點，讓圖乾淨
        last_x = x_values[-1]
        last_y = y_values[-1]

        ax.scatter(
            [last_x],
            [last_y],
            s=34,
            zorder=3
        )

        ax.annotate(
            f"¥{last_y:,}",
            xy=(last_x, last_y),
            xytext=(8, 0),
            textcoords="offset points",
            fontsize=10,
            va="center"
        )

        # 不顯示日期刻度
        ax.set_xticks([])

        # Y 軸簡化：只留少量刻度
        ax.tick_params(axis="y", labelsize=8, length=0, colors="#777777")
        ax.tick_params(axis="x", length=0)

        # 淡淡的水平參考線
        ax.grid(axis="y", alpha=0.16, linewidth=0.8)
        ax.grid(axis="x", visible=False)

        # 拿掉多餘邊框
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["bottom"].set_color("#DDDDDD")
        ax.spines["left"].set_color("#DDDDDD")

        # 讓線不要貼邊
        ax.margins(x=0.04, y=0.18)

        # 不放標題，標題改由外面的圖卡負責
        ax.set_xlabel("")
        ax.set_ylabel("")

    else:
        ax.text(
            0.5,
            0.5,
            f"查無 {selected_grade} 成交資料",
            ha="center",
            va="center",
            fontsize=13,
            color="#777777"
        )
        ax.set_xticks([])
        ax.set_yticks([])

        for spine in ax.spines.values():
            spine.set_visible(False)

    fig.tight_layout(pad=0.6)

    output = io.BytesIO()
    fig.savefig(output, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig)

    output.seek(0)
    chart_image = Image.open(output).convert("RGB")
    return chart_image


def generate_market_card_image(product, prices, selected_grade="PSA10", jpy_rate=None):
    """
    產生市場圖卡，存到 static/generated/
    回傳檔名（不是完整 URL）

    版面：
    - 左側大商品圖
    - 右上商品名稱
    - 右側第二列：等級 + 最高 / 平均 / 最低
    - 右側中間：乾淨折線圖
    - 底部：台銀匯率 + 資料來源
    """
    ensure_generated_dir()

    product_name = format_product_name_for_card(product.get("name"))
    image_url = product.get("image") or ""
    stats = calculate_price_stats_for_card(prices)

    canvas_width = 1400
    canvas_height = 840

    card = Image.new("RGB", (canvas_width, canvas_height), "#F4F6FA")
    draw = ImageDraw.Draw(card)

    # 字型
    title_font = get_font(38, bold=True)
    grade_font = get_font(24, bold=True)

    stat_label_font = get_font(20, bold=True)
    stat_jpy_font = get_font(30, bold=True)
    stat_twd_font = get_font(17, bold=False)

    footer_font = get_font(22, bold=False)
    small_font = get_font(18, bold=False)

    # 外層白色卡片
    outer_box = (24, 24, canvas_width - 24, canvas_height - 24)
    draw.rounded_rectangle(
        outer_box,
        radius=28,
        fill="white"
    )

    # =========================
    # 左側商品圖
    # =========================
    left_box = (58, 88, 500, 690)

    draw.rounded_rectangle(
        left_box,
        radius=24,
        fill="#FAFAFA",
        outline="#E9ECF2",
        width=2
    )

    product_image_bytes = download_image_bytes(image_url)

    if product_image_bytes:
        try:
            cropped_output = crop_white_border(product_image_bytes)
            product_image = Image.open(cropped_output).convert("RGB")
        except Exception as e:
            print("商品圖裁切失敗：", e)
            product_image = None
    else:
        product_image = None

    if product_image:
        product_box = create_contain_image(
            product_image,
            (360, 500),
            bg_color=(250, 250, 250)
        )

        paste_x = left_box[0] + ((left_box[2] - left_box[0]) - product_box.width) // 2
        paste_y = left_box[1] + ((left_box[3] - left_box[1]) - product_box.height) // 2

        card.paste(product_box, (paste_x, paste_y))
    else:
        placeholder_font = get_font(28, bold=True)
        draw.text(
            (left_box[0] + 110, left_box[1] + 190),
            "No Image",
            fill="#999999",
            font=placeholder_font
        )

    # =========================
    # 右上商品名稱 header
    # =========================
    right_x = 540
    right_w = 800


    title_lines = wrap_text_by_width(
        draw=draw,
        text=product_name,
        font=title_font,
        max_width=right_w - 44,
        max_lines=1
    )

    title_text = title_lines[0] if title_lines else product_name

    draw.text(
        (right_x, 92),
        product_name,
        fill="#222222",
        font=title_font
    )

    # =========================
    # Grade badge
    # =========================

    draw.text(
        (right_x, 160),
        selected_grade,
        fill="#2F5FE8",   # 如果你要保留藍字
        font=grade_font
    )

    grade_font = get_font(30, bold=True)
    # =========================
    # 最高 / 平均 / 最低
    # =========================
    stat_start_x = right_x + 130
    stat_y = 145
    stat_gap = 18
    stat_w = 185
    stat_h = 105

    stat_items = [
        ("最高", stats["highest"]),
        ("平均", stats["average"]),
        ("最低", stats["lowest"])
    ]

    for idx, (label, value) in enumerate(stat_items):
        x1 = stat_start_x + idx * (stat_w + stat_gap)
        y1 = stat_y
        x2 = x1 + stat_w
        y2 = y1 + stat_h

        draw.rounded_rectangle(
            (x1, y1, x2, y2),
            radius=16,
            fill="#FFFFFF",
            outline="#E9ECF2",
            width=1
        )

        # label
        label_w = text_width(draw, label, stat_label_font)
        draw.text(
            (x1 + (stat_w - label_w) / 2, y1 + 8),
            label,
            fill="#777777",
            font=stat_label_font
        )

        # 日幣
        jpy_text = format_jpy_text(value)
        jpy_w = text_width(draw, jpy_text, stat_jpy_font)
        draw.text(
            (x1 + (stat_w - jpy_w) / 2, y1 + 28),
            jpy_text,
            fill="#222222",
            font=stat_jpy_font
        )

        # 台幣小字
        twd_text = format_twd_text(value, jpy_rate)
        twd_w = text_width(draw, twd_text, stat_twd_font)
        draw.text(
            (x1 + (stat_w - twd_w) / 2, y1 + 55),
            twd_text,
            fill="#999999",
            font=stat_twd_font
        )

    # =========================
    # 折線圖區
    # =========================
    chart_bg_box = (right_x, 275, right_x + right_w, 705)

    draw.rounded_rectangle(
        chart_bg_box,
        radius=22,
        fill="#FFFFFF",
        outline="#E9ECF2",
        width=1
    )

    chart_image = generate_price_chart_image(
        prices,
        selected_grade=selected_grade
    )

    chart_image = create_contain_image(
        chart_image,
        (760, 360),
        bg_color=(255, 255, 255)
    )

    card.paste(chart_image, (right_x + 18, 300))

    # =========================
    # 底部資訊
    # =========================
    if jpy_rate:
        rate_text = f"台灣銀行日圓即期匯率：{jpy_rate}"
    else:
        rate_text = "台灣銀行日圓即期匯率：取得失敗"

    draw.text(
        (58, 740),
        rate_text,
        fill="#444444",
        font=footer_font
    )

    draw.text(
        (540, 740),
        "資料來源：SNKRDUNK",
        fill="#777777",
        font=footer_font
    )

    if stats["has_data"]:
        count_text = f"成交筆數：{stats['count']} 筆"
    else:
        count_text = "成交筆數：0 筆"

    draw.text(
        (1130, 742),
        count_text,
        fill="#999999",
        font=small_font
    )

    filename = f"market_card_{uuid.uuid4().hex}.png"
    output_path = os.path.join(GENERATED_DIR, filename)
    card.save(output_path, format="PNG")

    return filename