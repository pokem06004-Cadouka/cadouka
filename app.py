from flask import Flask, request, abort, send_file, render_template, redirect, flash

from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent,
    TextMessage,
    TextSendMessage,
    PostbackEvent
)

from urllib.parse import parse_qs, unquote
import urllib.request as req
import traceback

from config import LINE_CHANNEL_ACCESS_TOKEN, LINE_CHANNEL_SECRET, headers

from snkrdunk import (
    search_products,
    getprice,
    get_product_id,
    build_sales_history_url
)

from flex_messages import (
    create_product_image_grid_messages,
    create_price_flex
)

from exchange import get_jpy_spot_sell
from image_utils import crop_white_border

from models import (
    init_db,
    migrate_db,
    add_card,
    get_all_cards,
    get_dashboard_full_summary,
    get_card_by_id,
    update_card,
    delete_card,
    mark_card_as_sold,
    mark_card_as_holding
)

from calculations import calculate_total_cost

from datetime import datetime, date


app = Flask(__name__)
app.secret_key = "cadouka-secret-key"
init_db()
migrate_db()

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)


# 暫存 LINE 使用者搜尋到的商品結果
# key = user_id
# value = 商品列表
user_products = {}


def calculate_holding_days_for_card(card):
    """
    持有中：今天 - 購入日期
    已售出：售出日期 - 購入日期
    沒有購入日期：回傳 "-"
    """
    buy_date_text = card.get("buy_date") if isinstance(card, dict) else card["buy_date"]

    if not buy_date_text:
        return "-"

    try:
        buy_date = datetime.strptime(buy_date_text, "%Y-%m-%d").date()
    except:
        return "-"

    status = card.get("status") if isinstance(card, dict) else card["status"]

    if status == "sold":
        sell_date_text = card.get("sell_date") if isinstance(card, dict) else card["sell_date"]

        if sell_date_text:
            try:
                end_date = datetime.strptime(sell_date_text, "%Y-%m-%d").date()
            except:
                end_date = date.today()
        else:
            end_date = date.today()
    else:
        end_date = date.today()

    days = (end_date - buy_date).days

    if days < 0:
        days = 0

    return f"{days} 天"


def calculate_unrealized_by_buy_price(current_market_price, buy_price):
    """
    未實現損益 = 目前市價 - 購入價格
    未實現 ROI = 未實現損益 / 購入價格 * 100%
    """
    unrealized_profit = current_market_price - buy_price

    if buy_price == 0:
        roi = 0
    else:
        roi = (unrealized_profit / buy_price) * 100

    return unrealized_profit, roi


def calculate_realized_by_buy_price(net_revenue, buy_price):
    """
    已實現損益 = 實際收入 - 購入價格
    已實現 ROI = 已實現損益 / 購入價格 * 100%
    """
    realized_profit = net_revenue - buy_price

    if buy_price == 0:
        realized_roi = 0
    else:
        realized_roi = (realized_profit / buy_price) * 100

    return realized_profit, realized_roi


@app.route("/")
def home():
    return redirect("/dashboard")


@app.route("/dashboard")
def dashboard_page():
    holding, sold = get_dashboard_full_summary()

    holding_cards = holding["total_cards"] or 0
    holding_cost = holding["total_cost"] or 0
    holding_market_value = holding["total_market_value"] or 0
    holding_unrealized_profit = holding["total_unrealized_profit"] or 0

    if holding_cost == 0:
        holding_roi = 0
    else:
        holding_roi = (holding_unrealized_profit / holding_cost) * 100

    sold_cards = sold["total_cards"] or 0
    sold_cost = sold["total_cost"] or 0
    sold_net_revenue = sold["total_net_revenue"] or 0
    sold_realized_profit = sold["total_realized_profit"] or 0

    if sold_cost == 0:
        sold_roi = 0
    else:
        sold_roi = (sold_realized_profit / sold_cost) * 100

    total_cost = holding_cost + sold_cost
    total_profit = holding_unrealized_profit + sold_realized_profit

    if total_cost == 0:
        total_roi = 0
    else:
        total_roi = (total_profit / total_cost) * 100

    return render_template(
        "dashboard.html",

        holding_cards=holding_cards,
        holding_cost=holding_cost,
        holding_market_value=holding_market_value,
        holding_unrealized_profit=holding_unrealized_profit,
        holding_roi=holding_roi,

        sold_cards=sold_cards,
        sold_cost=sold_cost,
        sold_net_revenue=sold_net_revenue,
        sold_realized_profit=sold_realized_profit,
        sold_roi=sold_roi,

        total_cost=total_cost,
        total_profit=total_profit,
        total_roi=total_roi
    )


@app.route("/cards")
def card_list_page():
    status = request.args.get("status")
    keyword = request.args.get("keyword", "").strip()
    sort = request.args.get("sort", "").strip()

    if status not in ["holding", "sold"]:
        status = None

    allowed_sorts = [
        "date_desc",
        "date_asc",
        "cost_desc",
        "cost_asc",
        "profit_desc",
        "profit_asc",
        "roi_desc",
        "roi_asc"
    ]

    if sort not in allowed_sorts:
        sort = ""

    cards = get_all_cards(status, keyword, sort)

    card_list = []

    list_total_cards = 0
    list_holding_cards = 0
    list_sold_cards = 0
    list_total_cost = 0
    list_market_or_revenue = 0
    list_total_profit = 0

    for card in cards:
        card_dict = dict(card)
        card_dict["holding_days"] = calculate_holding_days_for_card(card_dict)
        card_list.append(card_dict)

        list_total_cards += 1

        buy_price = card_dict.get("buy_price") or 0
        list_total_cost += buy_price

        if card_dict.get("status") == "sold":
            list_sold_cards += 1
            net_revenue = card_dict.get("net_revenue") or 0
            realized_profit = card_dict.get("realized_profit") or 0

            list_market_or_revenue += net_revenue
            list_total_profit += realized_profit
        else:
            list_holding_cards += 1
            current_market_price = card_dict.get("current_market_price") or 0
            unrealized_profit = card_dict.get("unrealized_profit") or 0

            list_market_or_revenue += current_market_price
            list_total_profit += unrealized_profit

    if list_total_cost == 0:
        list_total_roi = 0
    else:
        list_total_roi = (list_total_profit / list_total_cost) * 100

    list_summary = {
        "total_cards": list_total_cards,
        "holding_cards": list_holding_cards,
        "sold_cards": list_sold_cards,
        "total_cost": list_total_cost,
        "market_or_revenue": list_market_or_revenue,
        "total_profit": list_total_profit,
        "total_roi": list_total_roi
    }

    return render_template(
        "card_list.html",
        cards=card_list,
        current_status=status,
        keyword=keyword,
        sort=sort,
        list_summary=list_summary
    )


@app.route("/cards/add", methods=["GET", "POST"])
def add_card_page():
    if request.method == "POST":
        card_name = request.form.get("card_name", "").strip()
        card_number = request.form.get("card_number", "").strip()
        grade = request.form.get("grade", "").strip()
        purchase_method = request.form.get("purchase_method", "").strip()

        buy_date = request.form.get("buy_date", "").strip()
        buy_price = float(request.form.get("buy_price") or 0)
        current_market_price = float(request.form.get("current_market_price") or 0)

        note = request.form.get("note", "").strip()

        # 目前表單已簡化，所以這些成本固定為 0
        shipping_fee = 0
        tax_fee = 0
        platform_fee = 0
        other_fee = 0

        # LINE/SNKRDUNK 新增時會帶入圖片網址；手動新增則可能為空
        image_url = request.form.get("image_url", "").strip()

        total_cost = calculate_total_cost(
            buy_price,
            shipping_fee,
            tax_fee,
            platform_fee,
            other_fee
        )

        # 未實現損益 = 目前市價 - 購入價格
        # 未實現 ROI = 未實現損益 / 購入價格 * 100%
        unrealized_profit, roi = calculate_unrealized_by_buy_price(
            current_market_price,
            buy_price
        )

        card_data = {
            "card_name": card_name,
            "card_number": card_number,
            "series_name": "",
            "rarity": "",
            "grade": grade,
            "purchase_method": purchase_method,

            "buy_price": buy_price,
            "shipping_fee": shipping_fee,
            "tax_fee": tax_fee,
            "platform_fee": platform_fee,
            "other_fee": other_fee,

            "total_cost": total_cost,
            "current_market_price": current_market_price,
            "unrealized_profit": unrealized_profit,
            "roi": roi,

            "status": "holding",
            "buy_date": buy_date,
            "image_url": image_url,
            "note": note
        }

        add_card(card_data)

        flash("卡牌新增成功", "success")
        return redirect("/cards")

    # GET：讓網址參數可以自動帶入新增表單
    prefill = {
        "card_name": request.args.get("card_name", "").strip(),
        "card_number": request.args.get("card_number", "").strip(),
        "grade": request.args.get("grade", "").strip(),
        "purchase_method": "",
        "buy_date": request.args.get("buy_date", "").strip(),
        "buy_price": request.args.get("buy_price", "").strip(),
        "current_market_price": request.args.get("current_market_price", "").strip(),
        "image_url": request.args.get("image_url", "").strip(),
        "note": request.args.get("note", "").strip()
    }

    return render_template("add_card.html", prefill=prefill)


@app.route("/cards/<int:card_id>")
def card_detail_page(card_id):
    card = get_card_by_id(card_id)

    if not card:
        return "找不到這張卡牌", 404

    card_dict = dict(card)
    card_dict["holding_days"] = calculate_holding_days_for_card(card_dict)

    return render_template("card_detail.html", card=card_dict)


@app.route("/cards/<int:card_id>/edit", methods=["GET", "POST"])
def edit_card_page(card_id):
    card = get_card_by_id(card_id)

    if not card:
        return "找不到這張卡牌", 404

    if request.method == "POST":
        card_name = request.form.get("card_name", "").strip()
        card_number = request.form.get("card_number", "").strip()
        grade = request.form.get("grade", "").strip()
        purchase_method = request.form.get("purchase_method", "").strip()

        buy_date = request.form.get("buy_date", "").strip()
        buy_price = float(request.form.get("buy_price") or 0)
        current_market_price = float(request.form.get("current_market_price") or 0)

        note = request.form.get("note", "").strip()

        # 目前表單已簡化，所以這些成本固定為 0
        shipping_fee = 0
        tax_fee = 0
        platform_fee = 0
        other_fee = 0

        # 編輯時保留原本 image_url，不顯示給使用者修改
        image_url = card["image_url"] or ""

        total_cost = calculate_total_cost(
            buy_price,
            shipping_fee,
            tax_fee,
            platform_fee,
            other_fee
        )

        # 未實現損益 = 目前市價 - 購入價格
        # 未實現 ROI = 未實現損益 / 購入價格 * 100%
        unrealized_profit, roi = calculate_unrealized_by_buy_price(
            current_market_price,
            buy_price
        )

        card_data = {
            "card_name": card_name,
            "card_number": card_number,
            "series_name": "",
            "rarity": "",
            "grade": grade,
            "purchase_method": purchase_method,

            "buy_price": buy_price,
            "shipping_fee": shipping_fee,
            "tax_fee": tax_fee,
            "platform_fee": platform_fee,
            "other_fee": other_fee,

            "total_cost": total_cost,
            "current_market_price": current_market_price,
            "unrealized_profit": unrealized_profit,
            "roi": roi,

            "buy_date": buy_date,
            "image_url": image_url,
            "note": note
        }

        update_card(card_id, card_data)

        # 如果這張卡已經售出，購入價格改變後，
        # 已實現損益與已實現 ROI 也要重新計算。
        if card["status"] == "sold":
            net_revenue = card["net_revenue"] or card["sell_price"] or 0

            realized_profit, realized_roi = calculate_realized_by_buy_price(
                net_revenue,
                buy_price
            )

            sell_data = {
                "sell_price": card["sell_price"] or net_revenue,
                "sell_fee": card["sell_fee"] or 0,
                "sell_shipping_fee": card["sell_shipping_fee"] or 0,
                "sell_other_fee": card["sell_other_fee"] or 0,
                "net_revenue": net_revenue,
                "realized_profit": realized_profit,
                "realized_roi": realized_roi,
                "sell_date": card["sell_date"] or ""
            }

            mark_card_as_sold(card_id, sell_data)

        flash("卡牌資料已更新", "success")
        return redirect(f"/cards/{card_id}")

    return render_template("edit_card.html", card=card)


@app.route("/cards/<int:card_id>/delete", methods=["POST"])
def delete_card_page(card_id):
    card = get_card_by_id(card_id)

    if not card:
        return "找不到這張卡牌", 404

    delete_card(card_id)

    flash("卡牌已刪除", "success")
    return redirect("/cards")


@app.route("/cards/<int:card_id>/sell", methods=["GET", "POST"])
def sell_card_page(card_id):
    card = get_card_by_id(card_id)

    if not card:
        return "找不到這張卡牌", 404

    if request.method == "POST":
        sell_date = request.form.get("sell_date", "").strip()

        # 現在這個欄位代表「實際收入」
        sell_price = float(request.form.get("sell_price") or 0)

        # 目前售出表單已簡化，所以售出成本固定為 0
        sell_fee = 0
        sell_shipping_fee = 0
        sell_other_fee = 0

        # 實際收入 = 使用者填寫的金額
        net_revenue = sell_price

        # 已實現損益 = 實際收入 - 購入價格
        # 已實現 ROI = 已實現損益 / 購入價格 * 100%
        buy_price = card["buy_price"] or 0

        realized_profit, realized_roi = calculate_realized_by_buy_price(
            net_revenue,
            buy_price
        )

        sell_data = {
            "sell_price": sell_price,
            "sell_fee": sell_fee,
            "sell_shipping_fee": sell_shipping_fee,
            "sell_other_fee": sell_other_fee,
            "net_revenue": net_revenue,
            "realized_profit": realized_profit,
            "realized_roi": realized_roi,
            "sell_date": sell_date
        }

        mark_card_as_sold(card_id, sell_data)

        if card["status"] == "sold":
            flash("售出資料已更新", "success")
        else:
            flash("已標記為已售出", "success")
        return redirect(f"/cards/{card_id}")

    return render_template("sell_card.html", card=card)


@app.route("/cards/<int:card_id>/unsell", methods=["POST"])
def unsell_card_page(card_id):
    card = get_card_by_id(card_id)

    if not card:
        return "找不到這張卡牌", 404

    mark_card_as_holding(card_id)

    flash("已標記回持有中", "success")
    return redirect(f"/cards/{card_id}")


@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("簽章驗證失敗，請檢查 Channel secret")
        abort(400)
    except Exception as e:
        print("callback 錯誤：", e)
        traceback.print_exc()
        abort(500)

    return "OK"


@app.route("/crop-image")
def crop_image():
    image_url = request.args.get("url", "")

    if not image_url:
        return "Missing image url", 400

    try:
        image_url = unquote(image_url)

        request_obj = req.Request(image_url, headers=headers)

        with req.urlopen(request_obj) as response:
            image_bytes = response.read()

        cropped_image = crop_white_border(image_bytes)

        return send_file(
            cropped_image,
            mimetype="image/jpeg"
        )

    except Exception as e:
        print("圖片裁切錯誤：", e)
        traceback.print_exc()
        return "Image processing error", 500


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    card_id = event.message.text.strip()
    user_id = event.source.user_id

    try:
        products = search_products(card_id)

        if not products:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="查無商品，請換一個卡號試試看。")
            )
            return

        user_products[user_id] = products

        flex_message = create_product_image_grid_messages(products)

        line_bot_api.reply_message(
            event.reply_token,
            flex_message
        )

    except Exception as e:
        print("搜尋錯誤：", e)
        traceback.print_exc()

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="搜尋時發生錯誤，請稍後再試。")
        )


@handler.add(PostbackEvent)
def handle_postback(event):
    user_id = event.source.user_id
    data = event.postback.data

    try:
        params = parse_qs(data)

        action = params.get("action", [""])[0]

        products = user_products.get(user_id)

        if not products:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="找不到搜尋結果，請重新輸入。")
            )
            return

        if action == "select":
            index = int(params.get("index", [0])[0])

            if index >= len(products):
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="商品選擇錯誤，請重新搜尋。")
                )
                return

            product = products[index]
            product_url = product["url"]

            product_id = get_product_id(product_url)
            price_url = build_sales_history_url(product_id)

            prices = getprice(price_url)

            jpy_rate = get_jpy_spot_sell()

            price_flex_message = create_price_flex(product, prices, jpy_rate)

            line_bot_api.reply_message(
                event.reply_token,
                price_flex_message
            )
            return

    except Exception as e:
        print("選擇商品錯誤：", e)
        traceback.print_exc()

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="查詢時發生錯誤，請稍後再試。")
        )


if __name__ == "__main__":
    app.run(port=5000, debug=True)