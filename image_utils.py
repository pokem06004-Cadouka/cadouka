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
    回傳 PIL Image（折線圖）
    """
    valid_items = []

    # 通常 API 回來多半是新到舊，這裡反轉成舊到新
    for item in reversed(prices or []):
        jpy_price = parse_jpy_price(item.get("price"))
        date_text = short_date_text(item.get("date"))

        if jpy_price is None:
            continue

        valid_items.append({
            "date": date_text or "-",
            "price": jpy_price
        })

    fig, ax = plt.subplots(figsize=(7.4, 3.1), dpi=180)

    if valid_items:
        x_values = list(range(1, len(valid_items) + 1))
        y_values = [item["price"] for item in valid_items]

        ax.plot(x_values, y_values, linewidth=2.2, marker="o", markersize=4)
        ax.fill_between(x_values, y_values, alpha=0.12)

        tick_indexes = []
        if len(valid_items) == 1:
            tick_indexes = [0]
        elif len(valid_items) == 2:
            tick_indexes = [0, 1]
        else:
            tick_indexes = [0, len(valid_items) // 2, len(valid_items) - 1]

        tick_positions = [i + 1 for i in tick_indexes]
        tick_labels = [valid_items[i]["date"] for i in tick_indexes]

        ax.set_xticks(tick_positions)
        ax.set_xticklabels(tick_labels, fontsize=8)

        ax.set_title(f"{selected_grade} 成交走勢", fontsize=12)
        ax.set_ylabel("JPY", fontsize=9)
        ax.grid(alpha=0.25)

        last_x = x_values[-1]
        last_y = y_values[-1]
        ax.annotate(
            f"¥{last_y:,}",
            xy=(last_x, last_y),
            xytext=(6, 6),
            textcoords="offset points",
            fontsize=9
        )

    else:
        ax.text(
            0.5,
            0.5,
            f"查無 {selected_grade} 成交資料",
            ha="center",
            va="center",
            fontsize=12
        )
        ax.set_xticks([])
        ax.set_yticks([])

    fig.tight_layout()

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
    """
    ensure_generated_dir()

    product_name = format_product_name_for_card(product.get("name"))
    image_url = product.get("image") or ""

    canvas_width = 1200
    canvas_height = 760

    card = Image.new("RGB", (canvas_width, canvas_height), "#F3F5F8")
    draw = ImageDraw.Draw(card)

    # 外框
    draw.rounded_rectangle(
        (24, 24, canvas_width - 24, canvas_height - 24),
        radius=28,
        fill="white"
    )

    # 左側商品圖區
    draw.rounded_rectangle(
        (56, 56, 356, 356),
        radius=24,
        fill="#F8F8F8"
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
        product_box = create_contain_image(product_image, (260, 260), bg_color=(248, 248, 248))
        card.paste(product_box, (76, 76))
    else:
        placeholder_font = get_font(26, bold=True)
        draw.text((120, 185), "No Image", fill="#999999", font=placeholder_font)

    # 標題
    title_font = get_font(34, bold=True)
    subtitle_font = get_font(22, bold=False)
    badge_font = get_font(22, bold=True)
    footer_font = get_font(22, bold=False)
    small_font = get_font(18, bold=False)

    title_lines = wrap_text_by_width(
        draw=draw,
        text=product_name,
        font=title_font,
        max_width=720,
        max_lines=3
    )

    title_y = 70
    for line in title_lines:
        draw.text((400, title_y), line, fill="#222222", font=title_font)
        title_y += 44

    # grade badge
    badge_text = f"目前顯示：{selected_grade}"
    badge_x1 = 400
    badge_y1 = max(title_y + 10, 180)
    badge_x2 = badge_x1 + 220
    badge_y2 = badge_y1 + 44

    draw.rounded_rectangle(
        (badge_x1, badge_y1, badge_x2, badge_y2),
        radius=18,
        fill="#EEF3FF"
    )
    draw.text((badge_x1 + 16, badge_y1 + 10), badge_text, fill="#315EFB", font=badge_font)

    # chart 區塊
    chart_bg_box = (400, 250, 1138, 570)
    draw.rounded_rectangle(chart_bg_box, radius=24, fill="#FFFFFF", outline="#E8EAF0")

    chart_image = generate_price_chart_image(prices, selected_grade=selected_grade)
    chart_image = create_contain_image(chart_image, (700, 270), bg_color=(255, 255, 255))
    card.paste(chart_image, (420, 275))

    # footer 匯率
    if jpy_rate:
        rate_text = f"台灣銀行日圓即期匯率：{jpy_rate}"
    else:
        rate_text = "台灣銀行日圓即期匯率：取得失敗"

    draw.text((60, 640), rate_text, fill="#444444", font=footer_font)
    draw.text((60, 682), "資料來源：SNKRDUNK", fill="#888888", font=small_font)

    filename = f"market_card_{uuid.uuid4().hex}.png"
    output_path = os.path.join(GENERATED_DIR, filename)
    card.save(output_path, format="PNG")

    return filename