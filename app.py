from flask import (
    Flask,
    request,
    abort,
    send_file,
    render_template,
    redirect,
    flash,
    session,
    url_for,
    jsonify
)

from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent,
    TextMessage,
    TextSendMessage,
    PostbackEvent,
    QuickReply,
    QuickReplyButton,
    MessageAction,
    URIAction,
    TemplateSendMessage,
    ConfirmTemplate
)

from urllib.parse import parse_qs, unquote
import urllib.request as req
import traceback
import os
import random
import string
from functools import wraps

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from werkzeug.security import generate_password_hash, check_password_hash

from config import LINE_CHANNEL_ACCESS_TOKEN, LINE_CHANNEL_SECRET, headers, BASE_URL

from snkrdunk import (
    search_products,
    getprice,
    get_product_id,
    build_sales_history_url,
    get_prices_by_conditions
)

from flex_messages import (
    create_product_image_grid_messages,
    create_price_flex,
    create_price_flex_carousel,
    create_grade_summary_flex,
    create_history_flex
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
    update_card_market_price,
    delete_card,
    mark_card_as_sold,
    mark_card_as_holding,
    create_user,
    get_user_by_username,
    get_user_by_id,
    get_first_user,
    assign_unowned_cards_to_user,
    update_user_password,
    update_user_display_name,
    update_user_line_bind_code,
    get_user_by_line_bind_code,
    get_user_by_line_user_id,
    bind_line_user_to_account,
    unbind_line_user,
    delete_user_account
)

from calculations import calculate_total_cost

from datetime import datetime, date, timedelta,timezone


app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "cadouka-secret-key")

LINE_LIFF_ID = os.getenv("LINE_LIFF_ID", "")

init_db()
migrate_db()

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)


# 暫存 LINE 使用者搜尋到的商品結果
# key = LINE user_id
# value = 商品列表
user_products = {}


# =========================
# Auth Helpers
# =========================

def current_user_id():
    return session.get("user_id")


def current_user():
    user_id = current_user_id()

    if not user_id:
        return None

    return get_user_by_id(user_id)


def generate_line_bind_code():
    characters = string.ascii_uppercase + string.digits

    for _ in range(20):
        bind_code = "".join(random.choice(characters) for _ in range(6))

        existing_user = get_user_by_line_bind_code(bind_code)

        if not existing_user:
            return bind_code

    return "".join(random.choice(characters) for _ in range(10))


def login_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if not current_user_id():
            flash("請先登入", "warning")
            return redirect(url_for("login_page", next=request.full_path))

        return view_func(*args, **kwargs)

    return wrapped_view


@app.context_processor
def inject_current_user():
    return {
        "current_user": current_user(),
        "line_liff_id": LINE_LIFF_ID
    }

# =========================
# LINE Quick Reply Helpers
# =========================

def get_base_url():
    base_url = BASE_URL.strip().rstrip("/")

    if not base_url.startswith("http://") and not base_url.startswith("https://"):
        base_url = "https://" + base_url

    return base_url


def create_main_quick_reply():
    base_url = get_base_url()

    return QuickReply(
        items=[
            QuickReplyButton(
                action=MessageAction(
                    label="使用教學",
                    text="使用教學"
                )
            ),
            QuickReplyButton(
                action=MessageAction(
                    label="綁定狀態",
                    text="綁定狀態"
                )
            ),
            QuickReplyButton(
                action=MessageAction(
                    label="解除綁定",
                    text="解除綁定"
                )
            ),
            QuickReplyButton(
                action=URIAction(
                    label="卡牌倉庫",
                    uri=f"{base_url}/cards"
                )
            )
        ]
    )


def create_unbound_quick_reply():
    base_url = get_base_url()

    return QuickReply(
        items=[
            QuickReplyButton(
                action=MessageAction(
                    label="查看教學",
                    text="使用教學"
                )
            ),
            QuickReplyButton(
                action=MessageAction(
                    label="綁定狀態",
                    text="綁定狀態"
                )
            ),
            QuickReplyButton(
                action=URIAction(
                    label="開啟 Cadouka",
                    uri=f"{base_url}/profile"
                )
            )
        ]
    )

# =========================
# Calculation Helpers
# =========================

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


def format_jpy_price_for_card(price):
    """
    LINE 後端新增卡牌時，用來把 SNKRDUNK 成交價轉成數字。
    """
    try:
        return int(float(str(price).replace(",", "")))
    except:
        return None


def calculate_market_price_from_prices(prices, jpy_rate):
    """
    用 PSA10 成交紀錄平均價 * 日圓匯率，算出目前市價。
    沒有資料或匯率失敗時回傳 0。
    """
    if not prices or not jpy_rate:
        return 0

    valid_prices = []

    for p in prices:
        jpy_price = format_jpy_price_for_card(p.get("price"))

        if jpy_price is not None:
            valid_prices.append(jpy_price)

    if not valid_prices:
        return 0

    average_jpy = round(sum(valid_prices) / len(valid_prices))

    return round(average_jpy * jpy_rate)

def get_market_price_by_product_url(product_url):
    """
    用 SNKRDUNK 商品網址抓最新 PSA10 平均成交價，並換算成台幣。
    """
    if not product_url:
        return 0

    product_id = get_product_id(product_url)

    if not product_id:
        return 0

    price_url = build_sales_history_url(product_id)

    prices = getprice(price_url)
    jpy_rate = get_jpy_spot_sell()

    current_market_price = calculate_market_price_from_prices(
        prices,
        jpy_rate
    )

    return current_market_price

def get_taiwan_now_text():
    taiwan_time = datetime.now(timezone(timedelta(hours=8)))
    return taiwan_time.strftime("%Y-%m-%d %H:%M:%S")


def should_skip_price_update(price_updated_at, cooldown_hours=6):
    """
    如果這張卡在 cooldown_hours 小時內更新過，就略過。
    """
    if not price_updated_at:
        return False

    try:
        updated_text = str(price_updated_at).split(".")[0]
        updated_at = datetime.strptime(updated_text, "%Y-%m-%d %H:%M:%S")
        now = datetime.now(timezone(timedelta(hours=8))).replace(tzinfo=None)

        diff = now - updated_at

        return diff < timedelta(hours=cooldown_hours)
    except:
        return False

# =========================
# Auth Routes
# =========================

@app.route("/")
def home():
    if current_user_id():
        return redirect("/dashboard")

    return redirect("/login")


@app.route("/register", methods=["GET", "POST"])
def register_page():
    if current_user_id():
        return redirect("/dashboard")

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        if not username or not password:
            flash("請輸入帳號與密碼", "warning")
            return redirect("/register")

        if len(password) < 6:
            flash("密碼至少需要 6 碼", "warning")
            return redirect("/register")

        if password != confirm_password:
            flash("兩次輸入的密碼不一致", "warning")
            return redirect("/register")

        existing_user = get_user_by_username(username)

        if existing_user:
            flash("這個帳號已經被使用", "warning")
            return redirect("/register")

        first_user_before_create = get_first_user()

        password_hash = generate_password_hash(password)
        create_user(username, password_hash)

        user = get_user_by_username(username)

        session["user_id"] = user["id"]
        session["username"] = user["username"]

        # 如果這是第一個註冊者，把帳號系統上線前的舊資料歸給他
        if first_user_before_create is None:
            assign_unowned_cards_to_user(user["id"])

        flash("註冊成功，已自動登入", "success")
        return redirect("/dashboard")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login_page():
    if current_user_id():
        return redirect("/dashboard")

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        next_url = request.form.get("next", "").strip()

        user = get_user_by_username(username)

        if not user:
            flash("帳號或密碼錯誤", "warning")
            return redirect("/login")

        if not check_password_hash(user["password_hash"], password):
            flash("帳號或密碼錯誤", "warning")
            return redirect("/login")

        session["user_id"] = user["id"]
        session["username"] = user["username"]

        flash("登入成功", "success")

        if next_url and next_url.startswith("/"):
            return redirect(next_url)

        return redirect("/dashboard")

    next_url = request.args.get("next", "")
    return render_template("login.html", next_url=next_url)


@app.route("/logout")
def logout_page():
    session.clear()
    flash("已登出", "success")
    return redirect("/login")


@app.route("/profile")
@login_required
def profile_page():
    user = current_user()

    if not user:
        flash("請先登入", "warning")
        return redirect("/login")

    return render_template("profile.html", user=user)


@app.route("/profile/update-display-name", methods=["POST"])
@login_required
def update_display_name_page():
    user = current_user()

    if not user:
        flash("請先登入", "warning")
        return redirect("/login")

    display_name = request.form.get("display_name", "").strip()

    if len(display_name) > 30:
        flash("暱稱最多 30 個字", "warning")
        return redirect("/profile")

    update_user_display_name(user["id"], display_name)

    if display_name:
        flash("暱稱已更新", "success")
    else:
        flash("已清除暱稱", "success")

    return redirect("/profile")


@app.route("/profile/generate-line-bind-code", methods=["POST"])
@login_required
def generate_line_bind_code_page():
    user = current_user()

    if not user:
        flash("請先登入", "warning")
        return redirect("/login")

    bind_code = generate_line_bind_code()


    taiwan_now = datetime.now(timezone(timedelta(hours=8)))
    expires_at = (taiwan_now + timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")

    update_user_line_bind_code(user["id"], bind_code, expires_at)

    flash("LINE 綁定連結已產生，請在 30 分鐘內完成綁定", "success")
    return redirect("/profile")


@app.route("/profile/change-password", methods=["POST"])
@login_required
def change_password_page():
    user = current_user()

    if not user:
        flash("請先登入", "warning")
        return redirect("/login")

    current_password = request.form.get("current_password", "").strip()
    new_password = request.form.get("new_password", "").strip()
    confirm_password = request.form.get("confirm_password", "").strip()

    if not current_password or not new_password or not confirm_password:
        flash("請完整填寫密碼欄位", "warning")
        return redirect("/profile")

    if not check_password_hash(user["password_hash"], current_password):
        flash("目前密碼錯誤", "warning")
        return redirect("/profile")

    if len(new_password) < 6:
        flash("新密碼至少需要 6 碼", "warning")
        return redirect("/profile")

    if new_password != confirm_password:
        flash("兩次輸入的新密碼不一致", "warning")
        return redirect("/profile")

    password_hash = generate_password_hash(new_password)
    update_user_password(user["id"], password_hash)

    flash("密碼已成功更新", "success")
    return redirect("/profile")

@app.route("/profile/delete-account", methods=["POST"])
@login_required
def delete_account_page():
    user = current_user()

    if not user:
        flash("請先登入", "warning")
        return redirect("/login")

    user_id = user["id"]

    delete_user_account(user_id)

    session.clear()

    flash("帳號已刪除", "success")
    return redirect("/login")

@app.route("/forgot-password")
def forgot_password_page():
    return render_template("forgot_password.html")

@app.route("/line/liff-bind")
def line_liff_bind_page():
    return render_template(
        "liff_bind.html",
        line_liff_id=LINE_LIFF_ID
    )


@app.route("/line/liff-bind/confirm", methods=["POST"])
def line_liff_bind_confirm_page():
    data = request.get_json() or {}

    line_user_id = data.get("line_user_id", "").strip()
    bind_code = data.get("bind_code", "").strip().upper()

    if not line_user_id:
        return jsonify({
            "success": False,
            "message": "無法取得 LINE 使用者資訊，請重新開啟綁定頁。"
        }), 400

    if not bind_code:
        return jsonify({
            "success": False,
            "message": "找不到綁定碼，請回 Cadouka 個人資料頁重新產生綁定連結。"
        }), 400

    user = get_user_by_line_bind_code(bind_code)

    if not user:
        return jsonify({
            "success": False,
            "message": "找不到這組綁定碼，請回 Cadouka 個人資料頁重新產生。"
        }), 404

    expires_at_text = user["line_bind_code_expires_at"]

    if expires_at_text:
        try:
            expires_at = datetime.strptime(expires_at_text, "%Y-%m-%d %H:%M:%S")

            taiwan_now = datetime.now(timezone(timedelta(hours=8))).replace(tzinfo=None)

            if taiwan_now > expires_at:
                return jsonify({
                    "success": False,
                    "message": "這組綁定碼已過期，請回 Cadouka 個人資料頁重新產生。"
                }), 400
        except:
            return jsonify({
                "success": False,
                "message": "綁定碼狀態異常，請回 Cadouka 個人資料頁重新產生。"
            }), 400

    existing_line_user = get_user_by_line_user_id(line_user_id)

    if existing_line_user and existing_line_user["id"] != user["id"]:
        return jsonify({
            "success": False,
            "message": "這個 LINE 帳號已經綁定其他 Cadouka 帳號，請先解除綁定。"
        }), 409

    bind_line_user_to_account(user["id"], line_user_id)

    display_name = user["display_name"] or user["username"]

    user_code = user["user_code"] if user.get("user_code") else "-"

    try:
        line_bot_api.push_message(
            line_user_id,
            TextSendMessage(
                text=(
                    "Cadouka 綁定成功！\n\n"
                    f"你的 LINE 已綁定 Cadouka 帳號：{display_name}"
                )
            )
        )
    except Exception as e:
        print("LINE 綁定成功訊息推送失敗：", e)
        traceback.print_exc()

    return jsonify({
        "success": True,
        "message": f"綁定成功！你的 LINE 已綁定 Cadouka 帳號：{display_name}"
    })

# =========================
# Dashboard / Card Routes
# =========================

@app.route("/dashboard")
@login_required
def dashboard_page():
    user_id = current_user_id()

    holding, sold = get_dashboard_full_summary(user_id=user_id)

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

        # =========================
    # Holding Overview Top 3
    # =========================

    holding_card_list = get_all_cards(
        status="holding",
        keyword=None,
        sort=None,
        user_id=user_id
    )

    holding_card_dicts = []

    for card in holding_card_list:
        card_dict = dict(card)
        holding_card_dicts.append(card_dict)

    top_profit_cards = sorted(
        [
            card for card in holding_card_dicts
            if (card.get("unrealized_profit") or 0) > 0
        ],
        key=lambda card: card.get("unrealized_profit") or 0,
        reverse=True
    )[:3]

    top_loss_cards = sorted(
        [
            card for card in holding_card_dicts
            if (card.get("unrealized_profit") or 0) < 0
        ],
        key=lambda card: card.get("unrealized_profit") or 0
    )[:3]

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
        total_roi=total_roi,
        top_profit_cards=top_profit_cards,
        top_loss_cards=top_loss_cards
    )


@app.route("/cards")
@login_required
def card_list_page():
    user_id = current_user_id()

    status = request.args.get("status")
    keyword = request.args.get("keyword", "").strip()
    sort = request.args.get("sort", "").strip()

    try:
        page = int(request.args.get("page", 1))
    except:
        page = 1

    if page < 1:
        page = 1

    per_page = 10

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

    all_cards = get_all_cards(
        status=status,
        keyword=keyword,
        sort=sort,
        user_id=user_id
    )

    # =========================
    # Summary：用全部符合條件的卡牌計算
    # =========================

    list_total_cards = 0
    list_holding_cards = 0
    list_sold_cards = 0
    list_total_cost = 0
    list_market_or_revenue = 0
    list_total_profit = 0

    for card in all_cards:
        card_dict = dict(card)

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

    # =========================
    # Pagination：每頁 10 張
    # =========================

    total_items = len(all_cards)

    if total_items == 0:
        total_pages = 1
    else:
        total_pages = (total_items + per_page - 1) // per_page

    if page > total_pages:
        page = total_pages

    start_index = (page - 1) * per_page
    end_index = start_index + per_page

    page_cards = all_cards[start_index:end_index]

    card_list = []

    for card in page_cards:
        card_dict = dict(card)
        card_dict["holding_days"] = calculate_holding_days_for_card(card_dict)
        card_list.append(card_dict)

    return render_template(
        "card_list.html",
        cards=card_list,
        current_status=status,
        keyword=keyword,
        sort=sort,
        list_summary=list_summary,

        current_page=page,
        total_pages=total_pages,
        total_items=total_items,
        per_page=per_page
    )

def format_created_at_taiwan_time(created_at):
    if not created_at:
        return ""

    try:
        if isinstance(created_at, datetime):
            dt = created_at
        else:
            created_at_text = str(created_at).split(".")[0]
            dt = datetime.strptime(created_at_text, "%Y-%m-%d %H:%M:%S")

        # 資料庫 CURRENT_TIMESTAMP 通常是 UTC
        dt = dt.replace(tzinfo=timezone.utc)
        taiwan_time = dt.astimezone(timezone(timedelta(hours=8)))

        return taiwan_time.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return str(created_at)

@app.route("/cards/export-excel")
@login_required
def export_cards_excel_page():
    user_id = current_user_id()

    cards = get_all_cards(
        status=None,
        keyword=None,
        sort=None,
        user_id=user_id
    )

    wb = Workbook()
    ws = wb.active
    ws.title = "卡牌倉庫"

    headers = [
        "卡牌名稱",
        "顯示名稱",
        "鑑定卡號",
        "鑑定狀態",
        "狀態",
        "購入日期",
        "購入方式",
        "購入價格",
        "目前市價",
        "未實現損益",
        "未實現 ROI",
        "售出日期",
        "實際收入",
        "已實現損益",
        "已實現 ROI",
        "持有天數",
        "商品網址",
        "備註",
        "建立時間"
    ]

    ws.append(headers)

    header_fill = PatternFill("solid", fgColor="DBEAFE")
    header_font = Font(bold=True, color="111827")
    header_alignment = Alignment(horizontal="center", vertical="center")

    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = header_alignment

    for card in cards:
        card_dict = dict(card)

        status_text = "持有中"

        if card_dict.get("status") == "sold":
            status_text = "已售出"
        elif card_dict.get("status") == "holding":
            status_text = "持有中"
        elif card_dict.get("status"):
            status_text = card_dict.get("status")

        holding_days = calculate_holding_days_for_card(card_dict)

        row = [
            card_dict.get("card_name") or "",
            card_dict.get("card_display_name") or "",
            card_dict.get("card_number") or "",
            card_dict.get("grade") or "",
            status_text,
            card_dict.get("buy_date") or "",
            card_dict.get("purchase_method") or "",
            card_dict.get("buy_price") or 0,
            card_dict.get("current_market_price") or 0,
            card_dict.get("unrealized_profit") or 0,
            card_dict.get("roi") or 0,
            card_dict.get("sell_date") or "",
            card_dict.get("net_revenue") or 0,
            card_dict.get("realized_profit") or 0,
            card_dict.get("realized_roi") or 0,
            holding_days,
            card_dict.get("product_url") or "",
            card_dict.get("note") or "",
            format_created_at_taiwan_time(card_dict.get("created_at"))
        ]

        ws.append(row)

    # 欄寬設定
        column_widths = {
        "A": 34,  # 卡牌名稱
        "B": 24,  # 顯示名稱
        "C": 18,  # 鑑定卡號
        "D": 14,  # 鑑定狀態
        "E": 12,  # 狀態
        "F": 14,  # 購入日期
        "G": 18,  # 購入方式
        "H": 14,  # 購入價格
        "I": 14,  # 目前市價
        "J": 16,  # 未實現損益
        "K": 14,  # 未實現 ROI
        "L": 14,  # 售出日期
        "M": 14,  # 實際收入
        "N": 16,  # 已實現損益
        "O": 14,  # 已實現 ROI
        "P": 12,  # 持有天數
        "Q": 42,  # 商品網址
        "R": 30,  # 備註
        "S": 22   # 建立時間
    }

    for column_letter, width in column_widths.items():
        ws.column_dimensions[column_letter].width = width

    # 數字格式
    money_columns = ["H", "I", "J", "M", "N"]

    for column_letter in money_columns:
        for cell in ws[column_letter][1:]:
            cell.number_format = '#,##0'

    percent_columns = ["K", "O"]

    for column_letter in percent_columns:
        for cell in ws[column_letter][1:]:
            cell.number_format = '0.00'

    # 文字垂直置中
    for row in ws.iter_rows():
        for cell in row:
            cell.alignment = Alignment(vertical="center")

    # 凍結表頭
    ws.freeze_panes = "A2"

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"cadouka_cards_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@app.route("/cards/add", methods=["GET", "POST"])
@login_required
def add_card_page():
    user_id = current_user_id()

    if request.method == "POST":
        card_name = request.form.get("card_name", "").strip()
        card_display_name = request.form.get("card_display_name", "").strip()
        card_number = request.form.get("card_number", "").strip()
        grade = request.form.get("grade", "").strip()
        purchase_method = request.form.get("purchase_method", "").strip()

        buy_date = request.form.get("buy_date", "").strip()
        buy_price = float(request.form.get("buy_price") or 0)
        current_market_price = float(request.form.get("current_market_price") or 0)

        product_url = request.form.get("product_url", "").strip()
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

        unrealized_profit, roi = calculate_unrealized_by_buy_price(
            current_market_price,
            buy_price
        )

        card_data = {
            "user_id": user_id,

            "card_name": card_name,
            "card_display_name": card_display_name,
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
            "product_url": product_url,
            "note": note
        }

        add_card(card_data)

        flash("卡牌新增成功", "success")
        return redirect("/cards")

    prefill = {
        "card_name": request.args.get("card_name", "").strip(),
        "card_display_name": request.args.get("card_display_name", "").strip(),
        "card_number": request.args.get("card_number", "").strip(),
        "grade": request.args.get("grade", "").strip(),
        "purchase_method": "",
        "buy_date": request.args.get("buy_date", "").strip(),
        "buy_price": request.args.get("buy_price", "").strip(),
        "current_market_price": request.args.get("current_market_price", "").strip(),
        "image_url": request.args.get("image_url", "").strip(),
        "product_url": request.args.get("product_url", "").strip(),
        "note": request.args.get("note", "").strip()
    }

    return render_template("add_card.html", prefill=prefill)


@app.route("/cards/<int:card_id>")
@login_required
def card_detail_page(card_id):
    user_id = current_user_id()

    card = get_card_by_id(card_id, user_id=user_id)

    if not card:
        return "找不到這張卡牌", 404

    card_dict = dict(card)
    card_dict["holding_days"] = calculate_holding_days_for_card(card_dict)

    return render_template("card_detail.html", card=card_dict)


@app.route("/cards/<int:card_id>/edit", methods=["GET", "POST"])
@login_required
def edit_card_page(card_id):
    user_id = current_user_id()

    card = get_card_by_id(card_id, user_id=user_id)

    if not card:
        return "找不到這張卡牌", 404

    if request.method == "POST":
        card_name = request.form.get("card_name", "").strip()
        card_display_name = request.form.get("card_display_name", "").strip()
        card_number = request.form.get("card_number", "").strip()
        grade = request.form.get("grade", "").strip()
        purchase_method = request.form.get("purchase_method", "").strip()

        buy_date = request.form.get("buy_date", "").strip()
        buy_price = float(request.form.get("buy_price") or 0)
        current_market_price = float(request.form.get("current_market_price") or 0)

        product_url = request.form.get("product_url", "").strip()
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

        unrealized_profit, roi = calculate_unrealized_by_buy_price(
            current_market_price,
            buy_price
        )

        card_data = {
            "card_name": card_name,
            "card_display_name": card_display_name,
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
            "product_url": product_url,
            "note": note
        }

        update_card(card_id, card_data, user_id=user_id)

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

            mark_card_as_sold(card_id, sell_data, user_id=user_id)

        flash("卡牌資料已更新", "success")
        return redirect("/cards")

    return render_template("edit_card.html", card=card)


@app.route("/cards/<int:card_id>/delete", methods=["POST"])
@login_required
def delete_card_page(card_id):
    user_id = current_user_id()

    card = get_card_by_id(card_id, user_id=user_id)

    if not card:
        return "找不到這張卡牌", 404

    delete_card(card_id, user_id=user_id)

    flash("卡牌已刪除", "success")
    return redirect("/cards")

@app.route("/cards/bulk-delete", methods=["POST"])
@login_required
def bulk_delete_cards_page():
    user_id = current_user_id()

    card_ids = request.form.getlist("card_ids")

    if not card_ids:
        flash("請先選擇要刪除的卡牌", "warning")
        return redirect(request.referrer or "/cards")

    deleted_count = 0

    for card_id in card_ids:
        try:
            delete_card(int(card_id), user_id=user_id)
            deleted_count += 1
        except Exception as e:
            print("批量刪除錯誤：", e)
            traceback.print_exc()
            continue

    flash(f"已刪除 {deleted_count} 張卡牌", "success")
    return redirect("/cards")

@app.route("/cards/<int:card_id>/sell", methods=["GET", "POST"])
@login_required
def sell_card_page(card_id):
    user_id = current_user_id()

    card = get_card_by_id(card_id, user_id=user_id)

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

        mark_card_as_sold(card_id, sell_data, user_id=user_id)

        if card["status"] == "sold":
            flash("售出資料已更新", "success")
        else:
            flash("已標記為已售出", "success")

        return redirect(request.referrer or f"/cards/{card_id}")

    return render_template("sell_card.html", card=card)


@app.route("/cards/<int:card_id>/unsell", methods=["POST"])
@login_required
def unsell_card_page(card_id):
    user_id = current_user_id()

    card = get_card_by_id(card_id, user_id=user_id)

    if not card:
        return "找不到這張卡牌", 404

    mark_card_as_holding(card_id, user_id=user_id)

    flash("已標記回持有中", "success")
    return redirect(request.referrer or f"/cards/{card_id}")

@app.route("/cards/<int:card_id>/refresh-price", methods=["POST"])
@login_required
def refresh_single_card_price_page(card_id):
    user_id = current_user_id()

    card = get_card_by_id(card_id, user_id=user_id)

    if not card:
        flash("找不到這張卡牌", "warning")
        return redirect("/cards")

    card_dict = dict(card)

    if card_dict.get("status") != "holding":
        flash("已售出的卡牌不需要更新市價", "warning")
        return redirect(request.referrer or f"/cards/{card_id}")

    product_url = card_dict.get("product_url") or ""

    if not product_url:
        flash("這張卡尚未設定商品網址，無法更新市價", "warning")
        return redirect(request.referrer or f"/cards/{card_id}")

    COOLDOWN_HOURS = 6

    if should_skip_price_update(
        card_dict.get("price_updated_at"),
        cooldown_hours=COOLDOWN_HOURS
    ):
        flash("這張卡近期已更新過", "success")
        return redirect(request.referrer or f"/cards/{card_id}")

    try:
        current_market_price = get_market_price_by_product_url(product_url)

        if current_market_price <= 0:
            flash("更新失敗，請確認商品網址是否正確", "warning")
            return redirect(request.referrer or f"/cards/{card_id}")

        buy_price = card_dict.get("buy_price") or 0

        unrealized_profit, roi = calculate_unrealized_by_buy_price(
            current_market_price,
            buy_price
        )

        price_updated_at = get_taiwan_now_text()

        update_card_market_price(
            card_id,
            current_market_price,
            unrealized_profit,
            roi,
            price_updated_at,
            user_id=user_id
        )

        flash("已更新此卡市價", "success")
        return redirect(request.referrer or f"/cards/{card_id}")

    except Exception as e:
        print("更新單張市價錯誤：", e)
        traceback.print_exc()

        flash("更新市價時發生錯誤，請稍後再試", "warning")
        return redirect(request.referrer or f"/cards/{card_id}")

@app.route("/cards/refresh-all-prices", methods=["POST"])
@login_required
def refresh_all_card_prices_page():
    user_id = current_user_id()

    cards = get_all_cards(
        status="holding",
        keyword=None,
        sort=None,
        user_id=user_id
    )

    if not cards:
        flash("目前沒有持有中的卡牌可以更新", "warning")
        return redirect(request.referrer or "/cards")

    MAX_REFRESH_COUNT = 10
    COOLDOWN_HOURS = 6

    success_count = 0
    fail_count = 0
    skipped_count = 0

    candidate_cards = []

    for card in cards:
        card_dict = dict(card)

        product_url = card_dict.get("product_url") or ""

        # 沒有商品網址，算失敗
        if not product_url:
            fail_count += 1
            continue

        # 6 小時內更新過，略過
        if should_skip_price_update(
            card_dict.get("price_updated_at"),
            cooldown_hours=COOLDOWN_HOURS
        ):
            skipped_count += 1
            continue

        candidate_cards.append(card_dict)

    # 優先更新最久沒更新的卡牌
    # price_updated_at 空白的會排最前面
    candidate_cards = sorted(
        candidate_cards,
        key=lambda card: card.get("price_updated_at") or ""
    )

    # 一次最多更新 10 張，其餘略過
    cards_to_update = candidate_cards[:MAX_REFRESH_COUNT]
    skipped_count += max(0, len(candidate_cards) - MAX_REFRESH_COUNT)

    for card in cards_to_update:
        try:
            product_url = card.get("product_url") or ""

            current_market_price = get_market_price_by_product_url(product_url)

            if current_market_price <= 0:
                fail_count += 1
                continue

            buy_price = card.get("buy_price") or 0

            unrealized_profit, roi = calculate_unrealized_by_buy_price(
                current_market_price,
                buy_price
            )

            price_updated_at = get_taiwan_now_text()

            update_card_market_price(
                card["id"],
                current_market_price,
                unrealized_profit,
                roi,
                price_updated_at,
                user_id=user_id
            )

            success_count += 1

        except Exception as e:
            print("更新單張市價錯誤：", e)
            traceback.print_exc()
            fail_count += 1
            continue

    if success_count == 0 and skipped_count > 0 and fail_count == 0:
        flash(f"近期已更新過，已略過 {skipped_count} 張卡牌", "success")
    elif fail_count == 0:
        flash(f"已更新 {success_count} 張，略過 {skipped_count} 張", "success")
    else:
        flash(f"已更新 {success_count} 張，略過 {skipped_count} 張，失敗 {fail_count} 張", "warning")

    return redirect(request.referrer or "/cards")

# =========================
# LINE Callback / Image Tools
# =========================

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
    line_user_id = event.source.user_id

    # =========================
    # LINE Account Binding Commands
    # =========================

    if card_id.startswith("綁定 "):
        bind_code = card_id.replace("綁定 ", "", 1).strip().upper()

        if not bind_code:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="請輸入綁定碼，例如：綁定 A8K29Q")
            )
            return

        user = get_user_by_line_bind_code(bind_code)

        if not user:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="找不到這組綁定碼，請確認是否輸入正確。")
            )
            return

        expires_at_text = user["line_bind_code_expires_at"]

        if expires_at_text:
            try:
                expires_at = datetime.strptime(expires_at_text, "%Y-%m-%d %H:%M:%S")

                taiwan_now = datetime.now(timezone(timedelta(hours=8))).replace(tzinfo=None)

                if taiwan_now > expires_at:
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text="這組綁定碼已過期，請回 Cadouka 個人資料頁重新產生。")
                    )
                    return
            except:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="綁定碼狀態異常，請回 Cadouka 個人資料頁重新產生。")
                )
                return

        existing_line_user = get_user_by_line_user_id(line_user_id)

        if existing_line_user and existing_line_user["id"] != user["id"]:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="這個 LINE 帳號已經綁定其他 Cadouka 帳號，請先解除綁定。")
            )
            return

        bind_line_user_to_account(user["id"], line_user_id)

        display_name = user["display_name"] or user["username"]

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"綁定成功！你的 LINE 已綁定 Cadouka 帳號：{display_name}")
        )
        return

    if card_id == "綁定狀態":
        user = get_user_by_line_user_id(line_user_id)

        if not user:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="你目前尚未綁定 Cadouka 帳號。")
            )
            return

        display_name = user["display_name"] or user["username"]

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"你目前已綁定 Cadouka 帳號：{display_name}")
        )
        return

    # 第一次輸入解除綁定，只做確認，不直接解除
    if card_id == "解除綁定":
        user = get_user_by_line_user_id(line_user_id)

        if not user:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="你目前沒有綁定任何 Cadouka 帳號。")
            )
            return

        line_bot_api.reply_message(
            event.reply_token,
            TemplateSendMessage(
                alt_text="解除綁定確認",
                template=ConfirmTemplate(
                    text=(
                        "確定要解除綁定嗎？\n"
                        "解除後，將無法從 LINE 直接加入 Cadouka。"
                    ),
                    actions=[
                        MessageAction(
                            label="取消",
                            text="取消解除綁定"
                        ),
                        MessageAction(
                            label="確認解除",
                            text="確認解除綁定"
                        )
                    ]
                )
            )
        )
        return

    if card_id == "取消解除綁定":
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="已取消解除綁定。")
        )
        return

    # 第二次確認，才真正解除綁定
    if card_id == "確認解除綁定":
        user = get_user_by_line_user_id(line_user_id)

        if not user:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="你目前沒有綁定任何 Cadouka 帳號。")
            )
            return

        unbind_line_user(line_user_id)

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="已解除 LINE 與 Cadouka 帳號的綁定。")
        )
        return

    if card_id == "功能":
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text="Cadouka 常用功能\n請選擇你要使用的功能：",
                quick_reply=create_main_quick_reply()
            )
        )
        return

    if card_id == "使用教學":
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=(
                    "Cadouka 使用教學\n"

                    "【一、建立 Cadouka 帳號】\n"
                    "1. 進入 Cadouka 網站。\n"
                    "2. 註冊帳號並登入。\n\n"

                    "【二、LINE 一鍵綁定】\n\n"
                    "1. 登入 Cadouka 網站。\n"
                    "2. 點右上角帳號名稱，進入「個人資料」。\n"
                    "3. 在 LINE 帳號綁定區按「產生綁定連結」。\n"
                    "4. 按「LINE 一鍵綁定」。\n"
                    "5. 系統會開啟 LINE 並自動完成綁定。\n\n"

                    "如果一鍵綁定無法使用，也可以使用備用綁定碼：\n"
                    "複製畫面上的「綁定 XXXXXX」，到 LINE 貼上送出即可完成綁定。\n\n"

                    "【三、LINE 查價】\n"
                    "在 LINE 直接輸入關鍵字，例如：\n"
                    "Pikachu\n"
                    "系列名稱：M2 SV2a...\n"
                    "MUR\n"
                    "卡牌左下角編號：XXX XXX\n\n"

                    "【四、加入卡牌倉庫】\n"
                    "在 LINE 查價結果中，按「加入 Cadouka」，即可把該商品加入你的卡牌倉庫。\n\n"
                    "加入後可到網站編輯：\n"
                    "卡牌名稱、鑑定卡號、購入價格...等\n\n"

                    "【五、市價更新】\n"
                    "如果卡牌有商品網址，可以更新市價。\n"
                    "持有中的卡牌才會更新市價，已售出的卡牌不會更新。\n\n"
                    "卡牌倉庫中，持有中卡牌右側的更新符號可以更新單張卡牌市價。\n"
                    "上方的「更新市價」可以批量更新持有中的卡牌。\n\n"

                    "【六、常用指令】\n"
                    "綁定狀態：查看目前 LINE 是否已綁定 Cadouka 帳號\n"
                    "解除綁定：解除目前 LINE 綁定\n"
                    "使用教學：查看 Cadouka 使用方式"
                ),
                quick_reply=create_main_quick_reply()
            )
        )
        return

    # =========================
    # Search SNKRDUNK Products
    # =========================

    try:
        products = search_products(card_id)

        if not products:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="查無商品，請換一個卡號試試看。")
            )
            return

        user_products[line_user_id] = products

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
    line_user_id = event.source.user_id
    data = event.postback.data

    try:
        params = parse_qs(data)

        action = params.get("action", [""])[0]

        products = user_products.get(line_user_id)

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

            prices_by_conditions = get_prices_by_conditions(product_id)

            jpy_rate = get_jpy_spot_sell()

            price_flex_message = create_grade_summary_flex(
                product,
                prices_by_conditions,
                jpy_rate,
                index
            )

            line_bot_api.reply_message(
                event.reply_token,
                price_flex_message
            )
            return

        if action == "history":
            index = int(params.get("index", [0])[0])
            selected_grade = params.get("grade", ["PSA10"])[0]

            if index >= len(products):
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="商品選擇錯誤，請重新搜尋。")
                )
                return

            product = products[index]
            product_url = product["url"]

            product_id = get_product_id(product_url)
            price_url = build_sales_history_url(
                product_id,
                condition=selected_grade,
                page=1,
                per_page=20
            )

            prices = getprice(price_url)
            jpy_rate = get_jpy_spot_sell()

            history_flex_message = create_history_flex(
                product,
                prices,
                selected_grade,
                jpy_rate,
                index
            )

            line_bot_api.reply_message(
                event.reply_token,
                history_flex_message
            )
            return

        if action == "add_card":
            index = int(params.get("index", [0])[0])
            selected_grade = params.get("grade", [""])[0]

            if index >= len(products):
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="商品選擇錯誤，請重新搜尋。")
                )
                return

            user = get_user_by_line_user_id(line_user_id)

            if not user:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(
                        text=(
                            "你尚未綁定 Cadouka 帳號。\n\n"
                            "請先登入 Cadouka，進入個人資料頁產生 LINE 綁定連結，"
                            "再完成 LINE 一鍵綁定。"
                        ),
                        quick_reply=create_unbound_quick_reply()
                    )
                )
                return

            product = products[index]
            product_name = product["name"] if product.get("name") else "未命名商品"
            image_url = product.get("image") or ""

            product_url = product["url"]

            product_id = get_product_id(product_url)

            if selected_grade:
                price_url = build_sales_history_url(product_id, condition=selected_grade)
            else:
                price_url = build_sales_history_url(product_id)

            prices = getprice(price_url)
            jpy_rate = get_jpy_spot_sell()

            current_market_price = calculate_market_price_from_prices(
                prices,
                jpy_rate
            )

            buy_price = 0
            total_cost = 0

            unrealized_profit, roi = calculate_unrealized_by_buy_price(
                current_market_price,
                buy_price
            )

            card_data = {
                "user_id": user["id"],

                "card_name": product_name,
                "card_display_name": "",
                "card_number": "",
                "series_name": "",
                "rarity": "",
                "grade": selected_grade,
                "purchase_method": "",

                "buy_price": buy_price,
                "shipping_fee": 0,
                "tax_fee": 0,
                "platform_fee": 0,
                "other_fee": 0,

                "total_cost": total_cost,
                "current_market_price": current_market_price,
                "unrealized_profit": unrealized_profit,
                "roi": roi,

                "status": "holding",
                "buy_date": "",
                "image_url": image_url,
                "product_url": product_url,
                "note": ""
            }

            add_card(card_data)

            display_name = user["display_name"] or user["username"]

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=(
                        "已新增到卡牌倉庫！\n"
                        f"帳號：{display_name}\n"
                        f"卡牌：{product_name}\n"
                        f"鑑定狀態：{selected_grade or '未填'}\n"
                        f"目前市價：NT${current_market_price:,}\n\n"
                        "之後可到網站編輯購入價格、購入日期、鑑定卡號與鑑定狀態。"
                    )
                )
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