import io
from PIL import Image, ImageChops


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