import os
import sqlite3
from datetime import datetime, timedelta

import psycopg2
import psycopg2.extras


DB_NAME = "cards.db"
DATABASE_URL = os.getenv("DATABASE_URL")


def is_postgres():
    return DATABASE_URL is not None and DATABASE_URL.strip() != ""


def get_connection():
    if is_postgres():
        conn = psycopg2.connect(
            DATABASE_URL,
            cursor_factory=psycopg2.extras.RealDictCursor
        )
        return conn

    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def execute_sql(cursor, sql, params=None):
    """
    讓同一份 SQL 可以同時支援：
    SQLite：?
    PostgreSQL：%s
    """
    if params is None:
        params = []

    if is_postgres():
        sql = sql.replace("?", "%s")

    cursor.execute(sql, params)


# =========================
# Database Init
# =========================

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    if is_postgres():
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            user_code TEXT UNIQUE,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT,
            is_admin INTEGER DEFAULT 0,
            membership_level TEXT DEFAULT 'free',
            line_user_id TEXT,
            line_bind_code TEXT,
            line_bind_code_expires_at TEXT,
            terms_accepted_at TEXT,
            privacy_accepted_at TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS cards (
            id SERIAL PRIMARY KEY,

            user_id INTEGER,

            card_name TEXT NOT NULL,
            card_display_name TEXT,
            card_number TEXT,
            series_name TEXT,
            rarity TEXT,
            grade TEXT,

            purchase_method TEXT,

            buy_price REAL DEFAULT 0,
            shipping_fee REAL DEFAULT 0,
            tax_fee REAL DEFAULT 0,
            platform_fee REAL DEFAULT 0,
            other_fee REAL DEFAULT 0,

            total_cost REAL DEFAULT 0,
            current_market_price REAL DEFAULT 0,
            price_updated_at TEXT,
                       
            unrealized_profit REAL DEFAULT 0,
            roi REAL DEFAULT 0,

            status TEXT DEFAULT 'holding',

            sell_price REAL DEFAULT 0,
            sell_fee REAL DEFAULT 0,
            sell_shipping_fee REAL DEFAULT 0,
            sell_other_fee REAL DEFAULT 0,
            net_revenue REAL DEFAULT 0,
            realized_profit REAL DEFAULT 0,
            realized_roi REAL DEFAULT 0,

            buy_date TEXT,
            sell_date TEXT,
            image_url TEXT,
            product_url TEXT,
            note TEXT,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS line_logs (
            id SERIAL PRIMARY KEY,
            line_user_id TEXT,
            user_id INTEGER,
            action TEXT,
            result TEXT,
            message TEXT,
            raw_keyword TEXT,
            resolved_keyword TEXT,
            product_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS search_aliases (
            id SERIAL PRIMARY KEY,
            alias_keyword TEXT UNIQUE NOT NULL,
            search_keyword TEXT NOT NULL,
            note TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
    else:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_code TEXT UNIQUE,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT,
            is_admin INTEGER DEFAULT 0,
            membership_level TEXT DEFAULT 'free',
            line_user_id TEXT,
            line_bind_code TEXT,
            line_bind_code_expires_at TEXT,
            terms_accepted_at TEXT,
            privacy_accepted_at TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            user_id INTEGER,

            card_name TEXT NOT NULL,
            card_display_name TEXT,
            card_number TEXT,
            series_name TEXT,
            rarity TEXT,
            grade TEXT,

            purchase_method TEXT,

            buy_price REAL DEFAULT 0,
            shipping_fee REAL DEFAULT 0,
            tax_fee REAL DEFAULT 0,
            platform_fee REAL DEFAULT 0,
            other_fee REAL DEFAULT 0,

            total_cost REAL DEFAULT 0,
            current_market_price REAL DEFAULT 0,
            price_updated_at TEXT,
                       
            unrealized_profit REAL DEFAULT 0,
            roi REAL DEFAULT 0,

            status TEXT DEFAULT 'holding',

            sell_price REAL DEFAULT 0,
            sell_fee REAL DEFAULT 0,
            sell_shipping_fee REAL DEFAULT 0,
            sell_other_fee REAL DEFAULT 0,
            net_revenue REAL DEFAULT 0,
            realized_profit REAL DEFAULT 0,
            realized_roi REAL DEFAULT 0,

            buy_date TEXT,
            sell_date TEXT,
            image_url TEXT,
            product_url TEXT,
            note TEXT,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS line_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            line_user_id TEXT,
            user_id INTEGER,
            action TEXT,
            result TEXT,
            message TEXT,
            raw_keyword TEXT,
            resolved_keyword TEXT,
            product_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS search_aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alias_keyword TEXT UNIQUE NOT NULL,
            search_keyword TEXT NOT NULL,
            note TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

    conn.commit()
    conn.close()


# =========================
# User Functions
# =========================

def generate_user_code(user_id):
    return f"CDK{int(user_id):05d}"

def create_user(username, password_hash, terms_accepted_at="", privacy_accepted_at=""):
    conn = get_connection()
    cursor = conn.cursor()

    if is_postgres():
        sql = """
            INSERT INTO users (
                username,
                password_hash,
                terms_accepted_at,
                privacy_accepted_at
            )
            VALUES (?, ?, ?, ?)
            RETURNING id
        """

        execute_sql(cursor, sql, [
            username,
            password_hash,
            terms_accepted_at or "",
            privacy_accepted_at or ""
        ])

        new_user = cursor.fetchone()
        user_id = new_user["id"]

    else:
        sql = """
            INSERT INTO users (
                username,
                password_hash,
                terms_accepted_at,
                privacy_accepted_at
            )
            VALUES (?, ?, ?, ?)
        """

        execute_sql(cursor, sql, [
            username,
            password_hash,
            terms_accepted_at or "",
            privacy_accepted_at or ""
        ])

        user_id = cursor.lastrowid

    user_code = generate_user_code(user_id)

    update_sql = """
        UPDATE users
        SET user_code = ?
        WHERE id = ?
    """

    execute_sql(cursor, update_sql, [
        user_code,
        user_id
    ])

    conn.commit()
    conn.close()


def get_user_by_username(username):
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        SELECT * FROM users
        WHERE username = ?
    """

    execute_sql(cursor, sql, [username])
    user = cursor.fetchone()

    conn.close()
    return user


def get_user_by_id(user_id):
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        SELECT * FROM users
        WHERE id = ?
    """

    execute_sql(cursor, sql, [user_id])
    user = cursor.fetchone()

    conn.close()
    return user

def get_user_by_user_code(user_code):
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        SELECT * FROM users
        WHERE user_code = ?
    """

    execute_sql(cursor, sql, [user_code])
    user = cursor.fetchone()

    conn.close()
    return user

def update_user_password(user_id, password_hash):
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        UPDATE users
        SET password_hash = ?
        WHERE id = ?
    """

    execute_sql(cursor, sql, [
        password_hash,
        user_id
    ])

    conn.commit()
    conn.close()


def update_user_display_name(user_id, display_name):
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        UPDATE users
        SET display_name = ?
        WHERE id = ?
    """

    execute_sql(cursor, sql, [
        display_name,
        user_id
    ])

    conn.commit()
    conn.close()

def update_user_admin_status(user_id, is_admin):
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        UPDATE users
        SET is_admin = ?
        WHERE id = ?
    """

    execute_sql(cursor, sql, [
        1 if is_admin else 0,
        user_id
    ])

    conn.commit()
    conn.close()

def update_user_membership_level(user_id, membership_level):
    allowed_levels = ["free", "pro"]

    if membership_level not in allowed_levels:
        membership_level = "free"

    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        UPDATE users
        SET membership_level = ?
        WHERE id = ?
    """

    execute_sql(cursor, sql, [
        membership_level,
        user_id
    ])

    conn.commit()
    conn.close()

def update_user_line_bind_code(user_id, bind_code, expires_at):
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        UPDATE users
        SET
            line_bind_code = ?,
            line_bind_code_expires_at = ?
        WHERE id = ?
    """

    execute_sql(cursor, sql, [
        bind_code,
        expires_at,
        user_id
    ])

    conn.commit()
    conn.close()


def get_user_by_line_bind_code(bind_code):
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        SELECT * FROM users
        WHERE line_bind_code = ?
    """

    execute_sql(cursor, sql, [bind_code])
    user = cursor.fetchone()

    conn.close()
    return user


def get_user_by_line_user_id(line_user_id):
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        SELECT * FROM users
        WHERE line_user_id = ?
    """

    execute_sql(cursor, sql, [line_user_id])
    user = cursor.fetchone()

    conn.close()
    return user

def get_admin_users(limit=None, offset=0):
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        SELECT
            u.id,
            u.user_code,
            u.username,
            u.display_name,
            u.is_admin,
            u.membership_level,
            u.line_user_id,
            u.created_at,

            COUNT(c.id) AS total_cards,

            COALESCE(SUM(
                CASE
                    WHEN c.status = 'holding' THEN 1
                    ELSE 0
                END
            ), 0) AS holding_cards,

            COALESCE(SUM(
                CASE
                    WHEN c.status = 'sold' THEN 1
                    ELSE 0
                END
            ), 0) AS sold_cards

        FROM users u
        LEFT JOIN cards c
            ON u.id = c.user_id

        GROUP BY
            u.id,
            u.user_code,
            u.username,
            u.display_name,
            u.is_admin,
            u.membership_level,
            u.line_user_id,
            u.created_at

        ORDER BY u.id DESC
    """

    params = []

    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])

    execute_sql(cursor, sql, params)
    users = cursor.fetchall()

    conn.close()
    return users


def count_admin_users():
    conn = get_connection()
    cursor = conn.cursor()

    execute_sql(cursor, "SELECT COUNT(*) AS count FROM users")
    result = cursor.fetchone()

    conn.close()
    return result["count"] or 0

def bind_line_user_to_account(user_id, line_user_id):
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        UPDATE users
        SET
            line_user_id = ?,
            line_bind_code = '',
            line_bind_code_expires_at = ''
        WHERE id = ?
    """

    execute_sql(cursor, sql, [
        line_user_id,
        user_id
    ])

    conn.commit()
    conn.close()


def unbind_line_user(line_user_id):
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        UPDATE users
        SET
            line_user_id = '',
            line_bind_code = '',
            line_bind_code_expires_at = ''
        WHERE line_user_id = ?
    """

    execute_sql(cursor, sql, [line_user_id])

    conn.commit()
    conn.close()


def get_first_user():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM users
        ORDER BY id ASC
        LIMIT 1
    """)

    user = cursor.fetchone()

    conn.close()
    return user


def assign_unowned_cards_to_user(user_id):
    """
    舊資料處理用：
    帳號系統上線前已存在的卡牌，user_id 會是 NULL。
    這個 function 可以把舊卡牌歸到指定使用者名下。
    """
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        UPDATE cards
        SET user_id = ?
        WHERE user_id IS NULL
    """

    execute_sql(cursor, sql, [user_id])

    conn.commit()
    conn.close()


# =========================
# Card Functions
# =========================

def add_card(card_data):
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
    INSERT INTO cards (
        user_id,

        card_name,
        card_display_name,
        card_number,
        series_name,
        rarity,
        grade,
        purchase_method,

        buy_price,
        shipping_fee,
        tax_fee,
        platform_fee,
        other_fee,

        total_cost,
        current_market_price,
        unrealized_profit,
        roi,

        status,
        buy_date,
        image_url,
        product_url,
        note
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    params = [
        card_data.get("user_id"),

        card_data["card_name"],
        card_data.get("card_display_name", ""),
        card_data.get("card_number", ""),
        card_data.get("series_name", ""),
        card_data.get("rarity", ""),
        card_data.get("grade", ""),
        card_data.get("purchase_method", ""),

        card_data.get("buy_price", 0),
        card_data.get("shipping_fee", 0),
        card_data.get("tax_fee", 0),
        card_data.get("platform_fee", 0),
        card_data.get("other_fee", 0),

        card_data.get("total_cost", 0),
        card_data.get("current_market_price", 0),
        card_data.get("unrealized_profit", 0),
        card_data.get("roi", 0),

        card_data.get("status", "holding"),
        card_data.get("buy_date", ""),
        card_data.get("image_url", ""),
        card_data.get("product_url", ""),
        card_data.get("note", "")
    ]

    execute_sql(cursor, sql, params)

    conn.commit()
    conn.close()


def get_all_cards(status=None, keyword=None, sort=None, user_id=None):
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        SELECT * FROM cards
        WHERE 1 = 1
    """

    params = []

    if user_id is not None:
        sql += " AND user_id = ?"
        params.append(user_id)

    if status:
        sql += " AND status = ?"
        params.append(status)

    if keyword:
        if is_postgres():
            sql += """
                AND (
                    card_name ILIKE ?
                    OR card_display_name ILIKE ?
                    OR card_number ILIKE ?
                    OR grade ILIKE ?
                    OR purchase_method ILIKE ?
                    OR product_url ILIKE ?
                    OR note ILIKE ?
                )
            """
        else:
            sql += """
                AND (
                    card_name LIKE ?
                    OR card_display_name LIKE ?
                    OR card_number LIKE ?
                    OR grade LIKE ?
                    OR purchase_method LIKE ?
                    OR product_url LIKE ?
                    OR note LIKE ?
                )
            """

        search_keyword = f"%{keyword}%"
        params.extend([
            search_keyword,
            search_keyword,
            search_keyword,
            search_keyword,
            search_keyword,
            search_keyword,
            search_keyword
        ])

    if sort == "date_desc":
        sql += " ORDER BY buy_date DESC, created_at DESC"
    elif sort == "date_asc":
        sql += " ORDER BY buy_date ASC, created_at DESC"
    elif sort == "cost_desc":
        sql += " ORDER BY total_cost DESC"
    elif sort == "cost_asc":
        sql += " ORDER BY total_cost ASC"
    elif sort == "profit_desc":
        sql += """
            ORDER BY
            CASE
                WHEN status = 'sold' THEN realized_profit
                ELSE unrealized_profit
            END DESC
        """
    elif sort == "profit_asc":
        sql += """
            ORDER BY
            CASE
                WHEN status = 'sold' THEN realized_profit
                ELSE unrealized_profit
            END ASC
        """
    elif sort == "roi_desc":
        sql += """
            ORDER BY
            CASE
                WHEN status = 'sold' THEN realized_roi
                ELSE roi
            END DESC
        """
    elif sort == "roi_asc":
        sql += """
            ORDER BY
            CASE
                WHEN status = 'sold' THEN realized_roi
                ELSE roi
            END ASC
        """
    else:
        sql += """
            ORDER BY
                CASE
                    WHEN status = 'holding' THEN 0
                    WHEN status = 'sold' THEN 1
                    ELSE 2
                END,
                created_at DESC
        """

    execute_sql(cursor, sql, params)
    cards = cursor.fetchall()

    conn.close()
    return cards


def get_card_by_id(card_id, user_id=None):
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        SELECT * FROM cards
        WHERE id = ?
    """

    params = [card_id]

    if user_id is not None:
        sql += " AND user_id = ?"
        params.append(user_id)

    execute_sql(cursor, sql, params)
    card = cursor.fetchone()

    conn.close()
    return card


def update_card(card_id, card_data, user_id=None):
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
    UPDATE cards
    SET
        card_name = ?,
        card_display_name = ?,
        card_number = ?,
        series_name = ?,
        rarity = ?,
        grade = ?,
        purchase_method = ?,

        buy_price = ?,
        shipping_fee = ?,
        tax_fee = ?,
        platform_fee = ?,
        other_fee = ?,

        total_cost = ?,
        current_market_price = ?,
        unrealized_profit = ?,
        roi = ?,

        buy_date = ?,
        image_url = ?,
        product_url = ?,
        note = ?
    WHERE id = ?
    """

    params = [
        card_data["card_name"],
        card_data.get("card_display_name", ""),
        card_data.get("card_number", ""),
        card_data.get("series_name", ""),
        card_data.get("rarity", ""),
        card_data.get("grade", ""),
        card_data.get("purchase_method", ""),

        card_data.get("buy_price", 0),
        card_data.get("shipping_fee", 0),
        card_data.get("tax_fee", 0),
        card_data.get("platform_fee", 0),
        card_data.get("other_fee", 0),

        card_data.get("total_cost", 0),
        card_data.get("current_market_price", 0),
        card_data.get("unrealized_profit", 0),
        card_data.get("roi", 0),

        card_data.get("buy_date", ""),
        card_data.get("image_url", ""),
        card_data.get("product_url", ""),
        card_data.get("note", ""),

        card_id
    ]

    if user_id is not None:
        sql += " AND user_id = ?"
        params.append(user_id)

    execute_sql(cursor, sql, params)

    conn.commit()
    conn.close()

def update_card_market_price(card_id, current_market_price, unrealized_profit, roi, price_updated_at, user_id=None):
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
    UPDATE cards
    SET
        current_market_price = ?,
        unrealized_profit = ?,
        roi = ?,
        price_updated_at = ?
    WHERE id = ?
    """

    params = [
        current_market_price,
        unrealized_profit,
        roi,
        price_updated_at,
        card_id
    ]

    if user_id is not None:
        sql += " AND user_id = ?"
        params.append(user_id)

    execute_sql(cursor, sql, params)

    conn.commit()
    conn.close()

def delete_card(card_id, user_id=None):
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        DELETE FROM cards
        WHERE id = ?
    """

    params = [card_id]

    if user_id is not None:
        sql += " AND user_id = ?"
        params.append(user_id)

    execute_sql(cursor, sql, params)

    conn.commit()
    conn.close()

def delete_user_account(user_id):
    conn = get_connection()
    cursor = conn.cursor()

    # 先刪除該使用者所有卡牌
    delete_cards_sql = """
        DELETE FROM cards
        WHERE user_id = ?
    """

    execute_sql(cursor, delete_cards_sql, [user_id])

    # 再刪除使用者帳號
    delete_user_sql = """
        DELETE FROM users
        WHERE id = ?
    """

    execute_sql(cursor, delete_user_sql, [user_id])

    conn.commit()
    conn.close()

def _admin_cards_search_clause(keyword):
    sql = """
        FROM cards c
        LEFT JOIN users u
            ON c.user_id = u.id
        WHERE 1 = 1
    """

    params = []

    if keyword:
        if is_postgres():
            sql += """
                AND (
                    c.card_name ILIKE ?
                    OR c.card_display_name ILIKE ?
                    OR c.card_number ILIKE ?
                    OR c.grade ILIKE ?
                    OR c.product_url ILIKE ?
                    OR u.user_code ILIKE ?
                    OR u.username ILIKE ?
                    OR u.display_name ILIKE ?
                )
            """
        else:
            sql += """
                AND (
                    c.card_name LIKE ?
                    OR c.card_display_name LIKE ?
                    OR c.card_number LIKE ?
                    OR c.grade LIKE ?
                    OR c.product_url LIKE ?
                    OR u.user_code LIKE ?
                    OR u.username LIKE ?
                    OR u.display_name LIKE ?
                )
            """

        search_keyword = f"%{keyword}%"
        params.extend([
            search_keyword,
            search_keyword,
            search_keyword,
            search_keyword,
            search_keyword,
            search_keyword,
            search_keyword,
            search_keyword
        ])

    return sql, params


def get_admin_cards(keyword=None, limit=None, offset=0):
    conn = get_connection()
    cursor = conn.cursor()

    from_sql, params = _admin_cards_search_clause(keyword)

    sql = """
        SELECT
            c.*,
            u.user_code,
            u.username,
            u.display_name AS owner_display_name
    """ + from_sql + " ORDER BY c.created_at DESC"

    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])

    execute_sql(cursor, sql, params)
    cards = cursor.fetchall()

    conn.close()
    return cards


def count_admin_cards(keyword=None):
    conn = get_connection()
    cursor = conn.cursor()

    from_sql, params = _admin_cards_search_clause(keyword)
    sql = "SELECT COUNT(*) AS count " + from_sql

    execute_sql(cursor, sql, params)
    result = cursor.fetchone()

    conn.close()
    return result["count"] or 0


# =========================
# LINE Log Functions
# =========================

def create_line_logs_table_if_not_exists():
    conn = get_connection()
    cursor = conn.cursor()

    if is_postgres():
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS line_logs (
            id SERIAL PRIMARY KEY,
            line_user_id TEXT,
            user_id INTEGER,
            action TEXT,
            result TEXT,
            message TEXT,
            raw_keyword TEXT,
            resolved_keyword TEXT,
            product_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
    else:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS line_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            line_user_id TEXT,
            user_id INTEGER,
            action TEXT,
            result TEXT,
            message TEXT,
            raw_keyword TEXT,
            resolved_keyword TEXT,
            product_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

    conn.commit()
    conn.close()


def add_line_log(
    line_user_id=None,
    user_id=None,
    action="",
    result="",
    message="",
    raw_keyword="",
    resolved_keyword="",
    product_count=None
):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        product_count_value = int(product_count) if product_count is not None else 0
    except:
        product_count_value = 0

    sql = """
        INSERT INTO line_logs (
            line_user_id,
            user_id,
            action,
            result,
            message,
            raw_keyword,
            resolved_keyword,
            product_count
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """

    execute_sql(cursor, sql, [
        line_user_id or "",
        user_id,
        action,
        result,
        message,
        raw_keyword or "",
        resolved_keyword or "",
        product_count_value
    ])

    conn.commit()
    conn.close()

def get_admin_line_logs(limit=200, offset=0):
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        SELECT
            l.id,
            l.action,
            l.result,
            l.message,
            l.raw_keyword,
            l.resolved_keyword,
            l.product_count,
            l.created_at,
            u.user_code,
            u.username,
            u.display_name
        FROM line_logs l
        LEFT JOIN users u
            ON l.user_id = u.id
        ORDER BY l.created_at DESC
        LIMIT ? OFFSET ?
    """

    execute_sql(cursor, sql, [limit, offset])
    logs = cursor.fetchall()

    conn.close()
    return logs


def count_admin_line_logs():
    conn = get_connection()
    cursor = conn.cursor()

    execute_sql(cursor, "SELECT COUNT(*) AS count FROM line_logs")
    result = cursor.fetchone()

    conn.close()
    return result["count"] or 0


def cleanup_old_line_logs(retention_days=90, max_rows=50000):
    """
    清理 LINE 使用紀錄，避免 line_logs 無限膨脹。

    規則：
    1. 刪除超過 retention_days 天的資料
    2. 若仍超過 max_rows 筆，只保留最新 max_rows 筆
    """
    try:
        retention_days = int(retention_days or 90)
    except:
        retention_days = 90

    try:
        max_rows = int(max_rows or 50000)
    except:
        max_rows = 50000

    if retention_days < 1:
        retention_days = 90

    if max_rows < 1000:
        max_rows = 1000

    cutoff_dt = datetime.now() - timedelta(days=retention_days)
    cutoff_text = cutoff_dt.strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()
    cursor = conn.cursor()

    execute_sql(cursor, "SELECT COUNT(*) AS count FROM line_logs")
    before_row = cursor.fetchone()
    before_count = before_row["count"] or 0

    # 先刪掉超過保留天數的紀錄。
    execute_sql(cursor, "DELETE FROM line_logs WHERE created_at < ?", [cutoff_text])
    deleted_by_age = cursor.rowcount if cursor.rowcount is not None and cursor.rowcount >= 0 else 0

    execute_sql(cursor, "SELECT COUNT(*) AS count FROM line_logs")
    middle_row = cursor.fetchone()
    middle_count = middle_row["count"] or 0

    deleted_by_limit = 0

    # 再用總筆數上限保護資料庫。
    if middle_count > max_rows:
        if is_postgres():
            sql = """
                DELETE FROM line_logs
                WHERE id NOT IN (
                    SELECT id
                    FROM line_logs
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                )
            """
        else:
            sql = """
                DELETE FROM line_logs
                WHERE id NOT IN (
                    SELECT id
                    FROM line_logs
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                )
            """

        execute_sql(cursor, sql, [max_rows])
        deleted_by_limit = cursor.rowcount if cursor.rowcount is not None and cursor.rowcount >= 0 else 0

    execute_sql(cursor, "SELECT COUNT(*) AS count FROM line_logs")
    after_row = cursor.fetchone()
    after_count = after_row["count"] or 0

    conn.commit()
    conn.close()

    return {
        "before_count": before_count,
        "after_count": after_count,
        "deleted_count": max(0, before_count - after_count),
        "deleted_by_age": deleted_by_age,
        "deleted_by_limit": deleted_by_limit,
        "retention_days": retention_days,
        "max_rows": max_rows
    }


def get_line_search_popular_keywords(limit=50):
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        SELECT
            raw_keyword,
            COUNT(*) AS search_count,
            SUM(CASE WHEN result = 'success' THEN 1 ELSE 0 END) AS success_count,
            SUM(CASE WHEN result = 'no_result' THEN 1 ELSE 0 END) AS no_result_count,
            MAX(created_at) AS latest_at
        FROM line_logs
        WHERE action = 'search'
        AND raw_keyword IS NOT NULL
        AND raw_keyword != ''
        GROUP BY raw_keyword
        ORDER BY search_count DESC, latest_at DESC
        LIMIT ?
    """

    execute_sql(cursor, sql, [limit])
    rows = cursor.fetchall()

    conn.close()
    return rows


def get_line_search_no_result_keywords(limit=50):
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        SELECT
            raw_keyword,
            COUNT(*) AS no_result_count,
            MAX(created_at) AS latest_at
        FROM line_logs
        WHERE action = 'search'
        AND result = 'no_result'
        AND raw_keyword IS NOT NULL
        AND raw_keyword != ''
        GROUP BY raw_keyword
        ORDER BY no_result_count DESC, latest_at DESC
        LIMIT ?
    """

    execute_sql(cursor, sql, [limit])
    rows = cursor.fetchall()

    conn.close()
    return rows


def get_recent_line_search_logs(limit=50, offset=0):
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        SELECT
            l.id,
            l.raw_keyword,
            l.resolved_keyword,
            l.product_count,
            l.result,
            l.message,
            l.created_at,
            u.user_code,
            u.username,
            u.display_name
        FROM line_logs l
        LEFT JOIN users u
            ON l.user_id = u.id
        WHERE l.action = 'search'
        AND l.raw_keyword IS NOT NULL
        AND l.raw_keyword != ''
        ORDER BY l.created_at DESC
        LIMIT ? OFFSET ?
    """

    execute_sql(cursor, sql, [limit, offset])
    rows = cursor.fetchall()

    conn.close()
    return rows


def count_recent_line_search_logs():
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        SELECT COUNT(*) AS count
        FROM line_logs
        WHERE action = 'search'
        AND raw_keyword IS NOT NULL
        AND raw_keyword != ''
    """

    execute_sql(cursor, sql)
    result = cursor.fetchone()

    conn.close()
    return result["count"] or 0


# =========================
# Search Alias Functions
# =========================

def create_search_aliases_table_if_not_exists():
    conn = get_connection()
    cursor = conn.cursor()

    if is_postgres():
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS search_aliases (
            id SERIAL PRIMARY KEY,
            alias_keyword TEXT UNIQUE NOT NULL,
            search_keyword TEXT NOT NULL,
            note TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
    else:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS search_aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alias_keyword TEXT UNIQUE NOT NULL,
            search_keyword TEXT NOT NULL,
            note TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

    conn.commit()
    conn.close()



def add_search_alias(alias_keyword, search_keyword, note="", is_active=1, tag_ids=None):
    alias_keyword = (alias_keyword or "").strip()
    search_keyword = (search_keyword or "").strip()
    note = (note or "").strip()

    if not alias_keyword or not search_keyword:
        return False

    conn = get_connection()
    cursor = conn.cursor()

    if is_postgres():
        sql = """
            INSERT INTO search_aliases (
                alias_keyword,
                search_keyword,
                note,
                is_active
            )
            VALUES (?, ?, ?, ?)
            RETURNING id
        """

        execute_sql(cursor, sql, [
            alias_keyword,
            search_keyword,
            note,
            1 if is_active else 0
        ])

        new_alias = cursor.fetchone()
        alias_id = new_alias["id"]
    else:
        sql = """
            INSERT INTO search_aliases (
                alias_keyword,
                search_keyword,
                note,
                is_active
            )
            VALUES (?, ?, ?, ?)
        """

        execute_sql(cursor, sql, [
            alias_keyword,
            search_keyword,
            note,
            1 if is_active else 0
        ])

        alias_id = cursor.lastrowid

    conn.commit()
    conn.close()

    if tag_ids is not None:
        set_search_alias_tags(alias_id, tag_ids)

    return alias_id



def get_all_search_aliases(keyword=None, limit=20, offset=0, tag_id=None):
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        SELECT DISTINCT sa.*
        FROM search_aliases sa
        WHERE 1 = 1
    """

    params = []

    if keyword:
        if is_postgres():
            sql += """
                AND (
                    sa.alias_keyword ILIKE ?
                    OR sa.search_keyword ILIKE ?
                    OR sa.note ILIKE ?
                    OR EXISTS (
                        SELECT 1
                        FROM search_alias_tags sat
                        JOIN search_tags st
                            ON sat.tag_id = st.id
                        WHERE sat.alias_id = sa.id
                        AND st.tag_name ILIKE ?
                    )
                )
            """
        else:
            sql += """
                AND (
                    sa.alias_keyword LIKE ?
                    OR sa.search_keyword LIKE ?
                    OR sa.note LIKE ?
                    OR EXISTS (
                        SELECT 1
                        FROM search_alias_tags sat
                        JOIN search_tags st
                            ON sat.tag_id = st.id
                        WHERE sat.alias_id = sa.id
                        AND st.tag_name LIKE ?
                    )
                )
            """

        search_keyword = f"%{keyword}%"
        params.extend([
            search_keyword,
            search_keyword,
            search_keyword,
            search_keyword
        ])

    if tag_id:
        sql += """
            AND EXISTS (
                SELECT 1
                FROM search_alias_tags sat_filter
                WHERE sat_filter.alias_id = sa.id
                AND sat_filter.tag_id = ?
            )
        """
        params.append(tag_id)

    sql += """
        ORDER BY sa.id DESC
        LIMIT ?
        OFFSET ?
    """

    params.extend([limit, offset])

    execute_sql(cursor, sql, params)
    aliases = cursor.fetchall()

    conn.close()

    return hydrate_search_aliases_with_tags(aliases)



def count_search_aliases(keyword=None, tag_id=None):
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        SELECT COUNT(DISTINCT sa.id) AS count
        FROM search_aliases sa
        WHERE 1 = 1
    """

    params = []

    if keyword:
        if is_postgres():
            sql += """
                AND (
                    sa.alias_keyword ILIKE ?
                    OR sa.search_keyword ILIKE ?
                    OR sa.note ILIKE ?
                    OR EXISTS (
                        SELECT 1
                        FROM search_alias_tags sat
                        JOIN search_tags st
                            ON sat.tag_id = st.id
                        WHERE sat.alias_id = sa.id
                        AND st.tag_name ILIKE ?
                    )
                )
            """
        else:
            sql += """
                AND (
                    sa.alias_keyword LIKE ?
                    OR sa.search_keyword LIKE ?
                    OR sa.note LIKE ?
                    OR EXISTS (
                        SELECT 1
                        FROM search_alias_tags sat
                        JOIN search_tags st
                            ON sat.tag_id = st.id
                        WHERE sat.alias_id = sa.id
                        AND st.tag_name LIKE ?
                    )
                )
            """

        search_keyword = f"%{keyword}%"
        params.extend([
            search_keyword,
            search_keyword,
            search_keyword,
            search_keyword
        ])

    if tag_id:
        sql += """
            AND EXISTS (
                SELECT 1
                FROM search_alias_tags sat_filter
                WHERE sat_filter.alias_id = sa.id
                AND sat_filter.tag_id = ?
            )
        """
        params.append(tag_id)

    execute_sql(cursor, sql, params)
    result = cursor.fetchone()

    conn.close()
    return result["count"] or 0



def get_search_alias_by_id(alias_id):
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        SELECT * FROM search_aliases
        WHERE id = ?
    """

    execute_sql(cursor, sql, [alias_id])
    alias = cursor.fetchone()

    conn.close()

    if not alias:
        return alias

    alias_dict = dict(alias)
    alias_dict["tags"] = get_tags_for_alias(alias_id)
    alias_dict["tag_ids"] = [tag["id"] for tag in alias_dict["tags"]]

    return alias_dict



def update_search_alias(alias_id, alias_keyword, search_keyword, note="", is_active=None, tag_ids=None):
    alias_keyword = (alias_keyword or "").strip()
    search_keyword = (search_keyword or "").strip()
    note = (note or "").strip()

    if not alias_keyword or not search_keyword:
        return False

    conn = get_connection()
    cursor = conn.cursor()

    if is_active is None:
        sql = """
            UPDATE search_aliases
            SET
                alias_keyword = ?,
                search_keyword = ?,
                note = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """

        params = [
            alias_keyword,
            search_keyword,
            note,
            alias_id
        ]
    else:
        sql = """
            UPDATE search_aliases
            SET
                alias_keyword = ?,
                search_keyword = ?,
                note = ?,
                is_active = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """

        params = [
            alias_keyword,
            search_keyword,
            note,
            1 if is_active else 0,
            alias_id
        ]

    execute_sql(cursor, sql, params)

    conn.commit()
    conn.close()

    if tag_ids is not None:
        set_search_alias_tags(alias_id, tag_ids)

    return True


def update_search_alias_active(alias_id, is_active):
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        UPDATE search_aliases
        SET
            is_active = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """

    execute_sql(cursor, sql, [
        1 if is_active else 0,
        alias_id
    ])

    conn.commit()
    conn.close()



def delete_search_alias(alias_id):
    conn = get_connection()
    cursor = conn.cursor()

    delete_links_sql = """
        DELETE FROM search_alias_tags
        WHERE alias_id = ?
    """

    execute_sql(cursor, delete_links_sql, [alias_id])

    delete_alias_sql = """
        DELETE FROM search_aliases
        WHERE id = ?
    """

    execute_sql(cursor, delete_alias_sql, [alias_id])

    conn.commit()
    conn.close()


def resolve_search_alias(raw_keyword):
    """
    LINE 查價用：
    先用使用者輸入的文字去查 search_aliases。
    找到啟用中的完全符合別名，就回傳 search_keyword。
    找不到就回傳原本輸入。
    """
    keyword = (raw_keyword or "").strip()

    if not keyword:
        return keyword

    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        SELECT search_keyword
        FROM search_aliases
        WHERE is_active = 1
        AND LOWER(alias_keyword) = LOWER(?)
        ORDER BY id DESC
        LIMIT 1
    """

    execute_sql(cursor, sql, [keyword])
    alias = cursor.fetchone()

    conn.close()

    if alias:
        return alias["search_keyword"]

    return keyword



# =========================
# Search Tag Functions
# =========================

def create_search_tags_tables_if_not_exists():
    conn = get_connection()
    cursor = conn.cursor()

    if is_postgres():
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS search_tags (
            id SERIAL PRIMARY KEY,
            tag_name TEXT UNIQUE NOT NULL,
            tag_color TEXT DEFAULT '#3b82f6',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS search_alias_tags (
            id SERIAL PRIMARY KEY,
            alias_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(alias_id, tag_id)
        )
        """)
    else:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS search_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tag_name TEXT UNIQUE NOT NULL,
            tag_color TEXT DEFAULT '#3b82f6',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS search_alias_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alias_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(alias_id, tag_id)
        )
        """)

    conn.commit()
    conn.close()


def normalize_tag_color(tag_color):
    tag_color = (tag_color or "#3b82f6").strip()

    if not tag_color.startswith("#"):
        tag_color = "#" + tag_color

    if len(tag_color) != 7:
        tag_color = "#3b82f6"

    return tag_color


def add_search_tag(tag_name, tag_color="#3b82f6"):
    tag_name = (tag_name or "").strip()
    tag_color = normalize_tag_color(tag_color)

    if not tag_name:
        return False

    conn = get_connection()
    cursor = conn.cursor()

    if is_postgres():
        sql = """
            INSERT INTO search_tags (
                tag_name,
                tag_color
            )
            VALUES (?, ?)
            RETURNING id
        """

        execute_sql(cursor, sql, [
            tag_name,
            tag_color
        ])

        new_tag = cursor.fetchone()
        tag_id = new_tag["id"]
    else:
        sql = """
            INSERT INTO search_tags (
                tag_name,
                tag_color
            )
            VALUES (?, ?)
        """

        execute_sql(cursor, sql, [
            tag_name,
            tag_color
        ])

        tag_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return tag_id


def get_all_search_tags(keyword=None):
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        SELECT *
        FROM search_tags
        WHERE 1 = 1
    """

    params = []

    if keyword:
        if is_postgres():
            sql += " AND tag_name ILIKE ?"
        else:
            sql += " AND tag_name LIKE ?"

        params.append(f"%{keyword}%")

    sql += """
        ORDER BY tag_name ASC, id ASC
    """

    execute_sql(cursor, sql, params)
    tags = cursor.fetchall()

    conn.close()
    return tags


def get_search_tag_by_id(tag_id):
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        SELECT *
        FROM search_tags
        WHERE id = ?
    """

    execute_sql(cursor, sql, [tag_id])
    tag = cursor.fetchone()

    conn.close()
    return tag


def update_search_tag(tag_id, tag_name, tag_color="#3b82f6"):
    tag_name = (tag_name or "").strip()
    tag_color = normalize_tag_color(tag_color)

    if not tag_name:
        return False

    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        UPDATE search_tags
        SET
            tag_name = ?,
            tag_color = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """

    execute_sql(cursor, sql, [
        tag_name,
        tag_color,
        tag_id
    ])

    conn.commit()
    conn.close()

    return True


def delete_search_tag(tag_id):
    conn = get_connection()
    cursor = conn.cursor()

    delete_links_sql = """
        DELETE FROM search_alias_tags
        WHERE tag_id = ?
    """

    execute_sql(cursor, delete_links_sql, [tag_id])

    delete_tag_sql = """
        DELETE FROM search_tags
        WHERE id = ?
    """

    execute_sql(cursor, delete_tag_sql, [tag_id])

    conn.commit()
    conn.close()


def clean_tag_ids(tag_ids, max_tags=8):
    cleaned = []

    for tag_id in tag_ids or []:
        try:
            tag_id_int = int(tag_id)
        except:
            continue

        if tag_id_int <= 0:
            continue

        if tag_id_int not in cleaned:
            cleaned.append(tag_id_int)

        if len(cleaned) >= max_tags:
            break

    return cleaned


def set_search_alias_tags(alias_id, tag_ids, max_tags=8):
    cleaned_tag_ids = clean_tag_ids(tag_ids, max_tags=max_tags)

    conn = get_connection()
    cursor = conn.cursor()

    delete_sql = """
        DELETE FROM search_alias_tags
        WHERE alias_id = ?
    """

    execute_sql(cursor, delete_sql, [alias_id])

    insert_sql = """
        INSERT INTO search_alias_tags (
            alias_id,
            tag_id
        )
        VALUES (?, ?)
    """

    for tag_id in cleaned_tag_ids:
        try:
            execute_sql(cursor, insert_sql, [
                alias_id,
                tag_id
            ])
        except Exception as e:
            print("搜尋別名標籤寫入失敗：", e)
            continue

    conn.commit()
    conn.close()

    return cleaned_tag_ids


def get_search_alias_tag_ids(alias_id):
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        SELECT tag_id
        FROM search_alias_tags
        WHERE alias_id = ?
        ORDER BY id ASC
    """

    execute_sql(cursor, sql, [alias_id])
    rows = cursor.fetchall()

    conn.close()

    return [row["tag_id"] for row in rows]


def get_tags_for_alias(alias_id):
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        SELECT
            st.id,
            st.tag_name,
            st.tag_color
        FROM search_alias_tags sat
        JOIN search_tags st
            ON sat.tag_id = st.id
        WHERE sat.alias_id = ?
        ORDER BY sat.id ASC
    """

    execute_sql(cursor, sql, [alias_id])
    tags = cursor.fetchall()

    conn.close()
    return [dict(tag) for tag in tags]


def get_tags_for_aliases(alias_ids):
    alias_ids = [
        int(alias_id)
        for alias_id in (alias_ids or [])
        if str(alias_id).isdigit()
    ]

    if not alias_ids:
        return {}

    placeholders = ", ".join(["?"] * len(alias_ids))

    conn = get_connection()
    cursor = conn.cursor()

    sql = f"""
        SELECT
            sat.alias_id,
            st.id,
            st.tag_name,
            st.tag_color
        FROM search_alias_tags sat
        JOIN search_tags st
            ON sat.tag_id = st.id
        WHERE sat.alias_id IN ({placeholders})
        ORDER BY sat.alias_id ASC, sat.id ASC
    """

    execute_sql(cursor, sql, alias_ids)
    rows = cursor.fetchall()

    conn.close()

    result = {}

    for row in rows:
        alias_id = row["alias_id"]

        if alias_id not in result:
            result[alias_id] = []

        result[alias_id].append({
            "id": row["id"],
            "tag_name": row["tag_name"],
            "tag_color": row["tag_color"]
        })

    return result


def hydrate_search_aliases_with_tags(aliases):
    alias_list = []

    for alias in aliases or []:
        alias_list.append(dict(alias))

    alias_ids = [alias["id"] for alias in alias_list]
    tags_map = get_tags_for_aliases(alias_ids)

    for alias in alias_list:
        tags = tags_map.get(alias["id"], [])
        alias["tags"] = tags
        alias["tag_ids"] = [tag["id"] for tag in tags]

    return alias_list


def get_search_tag_by_name(tag_name):
    tag_name = (tag_name or "").strip()

    if not tag_name:
        return None

    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        SELECT *
        FROM search_tags
        WHERE LOWER(tag_name) = LOWER(?)
        ORDER BY id ASC
        LIMIT 1
    """

    execute_sql(cursor, sql, [tag_name])
    tag = cursor.fetchone()

    conn.close()
    return tag


def get_or_create_search_tag(tag_name, tag_color="#3b82f6"):
    tag_name = (tag_name or "").strip()

    if not tag_name:
        return None

    existing_tag = get_search_tag_by_name(tag_name)

    if existing_tag:
        return existing_tag["id"]

    try:
        return add_search_tag(tag_name, tag_color=tag_color)
    except Exception:
        # 避免同時間新增或大小寫差異造成錯誤，再查一次。
        existing_tag = get_search_tag_by_name(tag_name)

        if existing_tag:
            return existing_tag["id"]

        raise


def get_search_alias_by_keyword(alias_keyword):
    alias_keyword = (alias_keyword or "").strip()

    if not alias_keyword:
        return None

    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        SELECT *
        FROM search_aliases
        WHERE LOWER(alias_keyword) = LOWER(?)
        ORDER BY id DESC
        LIMIT 1
    """

    execute_sql(cursor, sql, [alias_keyword])
    alias = cursor.fetchone()

    conn.close()
    return alias


def split_import_tag_names(tags_text, max_tags=8):
    tags_text = (tags_text or "").strip()

    if not tags_text:
        return []

    normalized = tags_text

    for separator in ["，", ",", "、", ";", "；", "／", "/"]:
        normalized = normalized.replace(separator, "|")

    tag_names = []

    for part in normalized.split("|"):
        tag_name = part.strip()

        if not tag_name:
            continue

        if tag_name not in tag_names:
            tag_names.append(tag_name)

        if len(tag_names) >= max_tags:
            break

    return tag_names


def upsert_search_alias(alias_keyword, search_keyword, note="", tag_names=None, is_active=1):
    alias_keyword = (alias_keyword or "").strip()
    search_keyword = (search_keyword or "").strip()
    note = (note or "").strip()

    if not alias_keyword or not search_keyword:
        return {
            "status": "skipped",
            "alias_id": None
        }

    tag_ids = []

    for tag_name in (tag_names or [])[:8]:
        tag_id = get_or_create_search_tag(tag_name)

        if tag_id and tag_id not in tag_ids:
            tag_ids.append(tag_id)

    existing_alias = get_search_alias_by_keyword(alias_keyword)

    if existing_alias:
        alias_id = existing_alias["id"]

        update_search_alias(
            alias_id=alias_id,
            alias_keyword=alias_keyword,
            search_keyword=search_keyword,
            note=note,
            is_active=is_active,
            tag_ids=tag_ids
        )

        return {
            "status": "updated",
            "alias_id": alias_id
        }

    alias_id = add_search_alias(
        alias_keyword=alias_keyword,
        search_keyword=search_keyword,
        note=note,
        is_active=is_active,
        tag_ids=tag_ids
    )

    return {
        "status": "created",
        "alias_id": alias_id
    }


def bulk_import_search_aliases(rows, max_tags=8):
    """
    rows 格式：
    [
        {
            "alias_keyword": "梵谷皮",
            "search_keyword": "085 svp",
            "note": "Van Gogh Pikachu",
            "tags": "寶可夢|皮卡丘|特典"
        }
    ]

    標籤名稱若已存在，會使用原本顏色；若不存在，會自動建立藍色標籤。
    """
    result = {
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "errors": 0,
        "total": 0
    }

    for row in rows or []:
        result["total"] += 1

        try:
            alias_keyword = (row.get("alias_keyword") or "").strip()
            search_keyword = (row.get("search_keyword") or "").strip()
            note = (row.get("note") or "").strip()
            tags_text = (row.get("tags") or "").strip()

            if not alias_keyword or not search_keyword:
                result["skipped"] += 1
                continue

            tag_names = split_import_tag_names(tags_text, max_tags=max_tags)

            upsert_result = upsert_search_alias(
                alias_keyword=alias_keyword,
                search_keyword=search_keyword,
                note=note,
                tag_names=tag_names,
                is_active=1
            )

            if upsert_result["status"] == "created":
                result["created"] += 1
            elif upsert_result["status"] == "updated":
                result["updated"] += 1
            else:
                result["skipped"] += 1

        except Exception as e:
            print("批量匯入搜尋別名失敗：", e)
            result["errors"] += 1

    return result


# =========================
# Price Update Job / Cache Functions
# =========================

def create_price_update_tables_if_not_exists():
    conn = get_connection()
    cursor = conn.cursor()

    if is_postgres():
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS market_price_cache (
            id SERIAL PRIMARY KEY,
            product_id TEXT NOT NULL,
            grade TEXT NOT NULL,
            market_price_twd REAL DEFAULT 0,
            average_jpy REAL DEFAULT 0,
            jpy_rate REAL DEFAULT 0,
            source TEXT DEFAULT 'SNKRDUNK',
            updated_at TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(product_id, grade)
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS jpy_rate_cache (
            id SERIAL PRIMARY KEY,
            cache_key TEXT UNIQUE NOT NULL,
            rate REAL DEFAULT 0,
            updated_at TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS price_update_jobs (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            job_type TEXT DEFAULT 'all',
            card_id INTEGER,
            status TEXT DEFAULT 'pending',
            total_count INTEGER DEFAULT 0,
            updated_count INTEGER DEFAULT 0,
            skipped_count INTEGER DEFAULT 0,
            failed_count INTEGER DEFAULT 0,
            message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            started_at TEXT,
            finished_at TEXT
        )
        """)
    else:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS market_price_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL,
            grade TEXT NOT NULL,
            market_price_twd REAL DEFAULT 0,
            average_jpy REAL DEFAULT 0,
            jpy_rate REAL DEFAULT 0,
            source TEXT DEFAULT 'SNKRDUNK',
            updated_at TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(product_id, grade)
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS jpy_rate_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cache_key TEXT UNIQUE NOT NULL,
            rate REAL DEFAULT 0,
            updated_at TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS price_update_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            job_type TEXT DEFAULT 'all',
            card_id INTEGER,
            status TEXT DEFAULT 'pending',
            total_count INTEGER DEFAULT 0,
            updated_count INTEGER DEFAULT 0,
            skipped_count INTEGER DEFAULT 0,
            failed_count INTEGER DEFAULT 0,
            message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            started_at TEXT,
            finished_at TEXT
        )
        """)

    conn.commit()
    conn.close()


def get_jpy_rate_cache(cache_key="jpy_spot_sell"):
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        SELECT *
        FROM jpy_rate_cache
        WHERE cache_key = ?
        LIMIT 1
    """

    execute_sql(cursor, sql, [cache_key])
    row = cursor.fetchone()

    conn.close()
    return row


def upsert_jpy_rate_cache(rate, updated_at, cache_key="jpy_spot_sell"):
    conn = get_connection()
    cursor = conn.cursor()

    if is_postgres():
        sql = """
            INSERT INTO jpy_rate_cache (
                cache_key,
                rate,
                updated_at
            )
            VALUES (?, ?, ?)
            ON CONFLICT (cache_key)
            DO UPDATE SET
                rate = EXCLUDED.rate,
                updated_at = EXCLUDED.updated_at
        """
    else:
        sql = """
            INSERT INTO jpy_rate_cache (
                cache_key,
                rate,
                updated_at
            )
            VALUES (?, ?, ?)
            ON CONFLICT(cache_key)
            DO UPDATE SET
                rate = excluded.rate,
                updated_at = excluded.updated_at
        """

    execute_sql(cursor, sql, [
        cache_key,
        rate,
        updated_at
    ])

    conn.commit()
    conn.close()


def get_market_price_cache(product_id, grade):
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        SELECT *
        FROM market_price_cache
        WHERE product_id = ?
        AND grade = ?
        LIMIT 1
    """

    execute_sql(cursor, sql, [
        str(product_id or ""),
        str(grade or "")
    ])

    row = cursor.fetchone()
    conn.close()
    return row


def upsert_market_price_cache(product_id, grade, market_price_twd, average_jpy, jpy_rate, updated_at, source="SNKRDUNK"):
    conn = get_connection()
    cursor = conn.cursor()

    if is_postgres():
        sql = """
            INSERT INTO market_price_cache (
                product_id,
                grade,
                market_price_twd,
                average_jpy,
                jpy_rate,
                source,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (product_id, grade)
            DO UPDATE SET
                market_price_twd = EXCLUDED.market_price_twd,
                average_jpy = EXCLUDED.average_jpy,
                jpy_rate = EXCLUDED.jpy_rate,
                source = EXCLUDED.source,
                updated_at = EXCLUDED.updated_at
        """
    else:
        sql = """
            INSERT INTO market_price_cache (
                product_id,
                grade,
                market_price_twd,
                average_jpy,
                jpy_rate,
                source,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(product_id, grade)
            DO UPDATE SET
                market_price_twd = excluded.market_price_twd,
                average_jpy = excluded.average_jpy,
                jpy_rate = excluded.jpy_rate,
                source = excluded.source,
                updated_at = excluded.updated_at
        """

    execute_sql(cursor, sql, [
        str(product_id or ""),
        str(grade or ""),
        market_price_twd or 0,
        average_jpy or 0,
        jpy_rate or 0,
        source or "SNKRDUNK",
        updated_at or ""
    ])

    conn.commit()
    conn.close()


def create_price_update_job(user_id, job_type="all", card_id=None, message=""):
    conn = get_connection()
    cursor = conn.cursor()

    if is_postgres():
        sql = """
            INSERT INTO price_update_jobs (
                user_id,
                job_type,
                card_id,
                status,
                message
            )
            VALUES (?, ?, ?, 'pending', ?)
            RETURNING id
        """

        execute_sql(cursor, sql, [
            user_id,
            job_type or "all",
            card_id,
            message or ""
        ])

        row = cursor.fetchone()
        job_id = row["id"]
    else:
        sql = """
            INSERT INTO price_update_jobs (
                user_id,
                job_type,
                card_id,
                status,
                message
            )
            VALUES (?, ?, ?, 'pending', ?)
        """

        execute_sql(cursor, sql, [
            user_id,
            job_type or "all",
            card_id,
            message or ""
        ])

        job_id = cursor.lastrowid

    conn.commit()
    conn.close()
    return job_id


def get_price_update_job(job_id):
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        SELECT *
        FROM price_update_jobs
        WHERE id = ?
        LIMIT 1
    """

    execute_sql(cursor, sql, [job_id])
    job = cursor.fetchone()

    conn.close()
    return job


def get_latest_price_update_job_for_user(user_id):
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        SELECT *
        FROM price_update_jobs
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 1
    """

    execute_sql(cursor, sql, [user_id])
    job = cursor.fetchone()

    conn.close()
    return job


def has_recent_price_update_job(user_id, job_type="all", within_minutes=10):
    """
    檢查使用者是否在指定分鐘內建立過同類型更新任務。
    用字串時間做資料庫比較，避免 SQLite/PostgreSQL 日期函式差異。
    """
    import datetime

    cutoff = datetime.datetime.now() - datetime.timedelta(minutes=within_minutes)
    cutoff_text = cutoff.strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        SELECT COUNT(*) AS count
        FROM price_update_jobs
        WHERE user_id = ?
        AND job_type = ?
        AND created_at >= ?
        AND status IN ('pending', 'running', 'done')
    """

    execute_sql(cursor, sql, [
        user_id,
        job_type or "all",
        cutoff_text
    ])

    result = cursor.fetchone()
    conn.close()

    return (result["count"] or 0) > 0


def has_active_price_update_job(user_id, card_id=None, job_type=None):
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        SELECT COUNT(*) AS count
        FROM price_update_jobs
        WHERE user_id = ?
        AND status IN ('pending', 'running')
    """

    params = [user_id]

    if card_id is not None:
        sql += " AND card_id = ?"
        params.append(card_id)

    if job_type is not None:
        sql += " AND job_type = ?"
        params.append(job_type)

    execute_sql(cursor, sql, params)
    result = cursor.fetchone()

    conn.close()
    return (result["count"] or 0) > 0


def get_pending_price_update_job():
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        SELECT *
        FROM price_update_jobs
        WHERE status = 'pending'
        ORDER BY id ASC
        LIMIT 1
    """

    execute_sql(cursor, sql)
    job = cursor.fetchone()

    conn.close()
    return job


def mark_price_update_job_running(job_id, started_at):
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        UPDATE price_update_jobs
        SET
            status = 'running',
            started_at = ?,
            message = ?
        WHERE id = ?
        AND status = 'pending'
    """

    execute_sql(cursor, sql, [
        started_at,
        "更新中",
        job_id
    ])

    changed = cursor.rowcount
    conn.commit()
    conn.close()

    return changed > 0


def update_price_update_job_progress(job_id, total_count=None, updated_count=None, skipped_count=None, failed_count=None, message=None):
    fields = []
    params = []

    if total_count is not None:
        fields.append("total_count = ?")
        params.append(total_count)

    if updated_count is not None:
        fields.append("updated_count = ?")
        params.append(updated_count)

    if skipped_count is not None:
        fields.append("skipped_count = ?")
        params.append(skipped_count)

    if failed_count is not None:
        fields.append("failed_count = ?")
        params.append(failed_count)

    if message is not None:
        fields.append("message = ?")
        params.append(message)

    if not fields:
        return

    params.append(job_id)

    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        UPDATE price_update_jobs
        SET
    """ + ",\n            ".join(fields) + "\n        WHERE id = ?"

    execute_sql(cursor, sql, params)
    conn.commit()
    conn.close()


def finish_price_update_job(job_id, status, message, finished_at, updated_count=None, skipped_count=None, failed_count=None, total_count=None):
    fields = [
        "status = ?",
        "message = ?",
        "finished_at = ?"
    ]

    params = [
        status,
        message or "",
        finished_at
    ]

    if updated_count is not None:
        fields.append("updated_count = ?")
        params.append(updated_count)

    if skipped_count is not None:
        fields.append("skipped_count = ?")
        params.append(skipped_count)

    if failed_count is not None:
        fields.append("failed_count = ?")
        params.append(failed_count)

    if total_count is not None:
        fields.append("total_count = ?")
        params.append(total_count)

    params.append(job_id)

    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        UPDATE price_update_jobs
        SET
    """ + ",\n            ".join(fields) + "\n        WHERE id = ?"

    execute_sql(cursor, sql, params)
    conn.commit()
    conn.close()



def fail_stale_price_update_jobs(user_id=None, stale_minutes=30):
    """
    Web-only 分批更新用：
    如果使用者關掉頁面或網路中斷，running/pending 任務可能不會被正常完成。
    這個 helper 會把太久沒有結束的任務標成 failed，避免永遠卡住更新鎖。
    """
    import datetime

    cutoff = datetime.datetime.now() - datetime.timedelta(minutes=stale_minutes)
    cutoff_text = cutoff.strftime("%Y-%m-%d %H:%M:%S")
    finished_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        UPDATE price_update_jobs
        SET
            status = 'failed',
            message = '更新逾時或頁面中斷，已自動結束。請重新按更新市價。',
            finished_at = ?
        WHERE status IN ('pending', 'running')
        AND created_at < ?
    """

    params = [finished_at, cutoff_text]

    if user_id is not None:
        sql += " AND user_id = ?"
        params.append(user_id)

    execute_sql(cursor, sql, params)
    changed = cursor.rowcount

    conn.commit()
    conn.close()

    return changed

# =========================
# Migration Helpers
# =========================

def add_column_if_not_exists(column_name, column_definition):
    conn = get_connection()
    cursor = conn.cursor()

    if is_postgres():
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'cards'
        """)

        columns = cursor.fetchall()
        existing_columns = [col["column_name"] for col in columns]

        if column_name not in existing_columns:
            cursor.execute(
                f"ALTER TABLE cards ADD COLUMN {column_name} {column_definition}"
            )
            conn.commit()

    else:
        cursor.execute("PRAGMA table_info(cards)")
        columns = cursor.fetchall()
        existing_columns = [col["name"] for col in columns]

        if column_name not in existing_columns:
            cursor.execute(
                f"ALTER TABLE cards ADD COLUMN {column_name} {column_definition}"
            )
            conn.commit()

    conn.close()


def add_user_column_if_not_exists(column_name, column_definition):
    conn = get_connection()
    cursor = conn.cursor()

    if is_postgres():
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'users'
        """)

        columns = cursor.fetchall()
        existing_columns = [col["column_name"] for col in columns]

        if column_name not in existing_columns:
            cursor.execute(
                f"ALTER TABLE users ADD COLUMN {column_name} {column_definition}"
            )
            conn.commit()

    else:
        cursor.execute("PRAGMA table_info(users)")
        columns = cursor.fetchall()
        existing_columns = [col["name"] for col in columns]

        if column_name not in existing_columns:
            cursor.execute(
                f"ALTER TABLE users ADD COLUMN {column_name} {column_definition}"
            )
            conn.commit()

    conn.close()

def add_line_log_column_if_not_exists(column_name, column_definition):
    conn = get_connection()
    cursor = conn.cursor()

    if is_postgres():
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'line_logs'
        """)

        columns = cursor.fetchall()
        existing_columns = [col["column_name"] for col in columns]

        if column_name not in existing_columns:
            cursor.execute(
                f"ALTER TABLE line_logs ADD COLUMN {column_name} {column_definition}"
            )
            conn.commit()

    else:
        cursor.execute("PRAGMA table_info(line_logs)")
        columns = cursor.fetchall()
        existing_columns = [col["name"] for col in columns]

        if column_name not in existing_columns:
            cursor.execute(
                f"ALTER TABLE line_logs ADD COLUMN {column_name} {column_definition}"
            )
            conn.commit()

    conn.close()


def backfill_user_codes():
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        SELECT id, user_code
        FROM users
        ORDER BY id ASC
    """

    cursor.execute(sql)
    users = cursor.fetchall()

    for user in users:
        user_id = user["id"] if is_postgres() else user["id"]
        user_code = user["user_code"] if is_postgres() else user["user_code"]

        if user_code:
            continue

        new_user_code = generate_user_code(user_id)

        update_sql = """
            UPDATE users
            SET user_code = ?
            WHERE id = ?
        """

        execute_sql(cursor, update_sql, [
            new_user_code,
            user_id
        ])

    conn.commit()
    conn.close()

def migrate_db():
    """
    舊資料庫升級用。
    PostgreSQL 和 SQLite 都會檢查欄位是否存在。
    """
    add_user_column_if_not_exists("user_code", "TEXT")
    add_user_column_if_not_exists("display_name", "TEXT")
    add_user_column_if_not_exists("is_admin", "INTEGER DEFAULT 0")
    add_user_column_if_not_exists("membership_level", "TEXT DEFAULT 'free'")
    add_user_column_if_not_exists("line_user_id", "TEXT")
    add_user_column_if_not_exists("line_bind_code", "TEXT")
    add_user_column_if_not_exists("line_bind_code_expires_at", "TEXT")
    add_user_column_if_not_exists("terms_accepted_at", "TEXT")
    add_user_column_if_not_exists("privacy_accepted_at", "TEXT")

    backfill_user_codes()

    add_column_if_not_exists("user_id", "INTEGER")

    add_column_if_not_exists("card_display_name", "TEXT")
    add_column_if_not_exists("purchase_method", "TEXT")
    add_column_if_not_exists("product_url", "TEXT")
    add_column_if_not_exists("price_updated_at", "TEXT")

    add_column_if_not_exists("sell_fee", "REAL DEFAULT 0")
    add_column_if_not_exists("sell_shipping_fee", "REAL DEFAULT 0")
    add_column_if_not_exists("sell_other_fee", "REAL DEFAULT 0")
    add_column_if_not_exists("net_revenue", "REAL DEFAULT 0")
    add_column_if_not_exists("realized_roi", "REAL DEFAULT 0")

    create_price_update_tables_if_not_exists()

    create_line_logs_table_if_not_exists()
    add_line_log_column_if_not_exists("raw_keyword", "TEXT")
    add_line_log_column_if_not_exists("resolved_keyword", "TEXT")
    add_line_log_column_if_not_exists("product_count", "INTEGER DEFAULT 0")
    create_search_aliases_table_if_not_exists()
    create_search_tags_tables_if_not_exists()


# =========================
# Sell / Holding Functions
# =========================

def mark_card_as_sold(card_id, sell_data, user_id=None):
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
    UPDATE cards
    SET
        status = 'sold',
        sell_price = ?,
        sell_fee = ?,
        sell_shipping_fee = ?,
        sell_other_fee = ?,
        net_revenue = ?,
        realized_profit = ?,
        realized_roi = ?,
        sell_date = ?
    WHERE id = ?
    """

    params = [
        sell_data.get("sell_price", 0),
        sell_data.get("sell_fee", 0),
        sell_data.get("sell_shipping_fee", 0),
        sell_data.get("sell_other_fee", 0),
        sell_data.get("net_revenue", 0),
        sell_data.get("realized_profit", 0),
        sell_data.get("realized_roi", 0),
        sell_data.get("sell_date", ""),
        card_id
    ]

    if user_id is not None:
        sql += " AND user_id = ?"
        params.append(user_id)

    execute_sql(cursor, sql, params)

    conn.commit()
    conn.close()


def mark_card_as_holding(card_id, user_id=None):
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
    UPDATE cards
    SET
        status = 'holding',
        sell_price = 0,
        sell_fee = 0,
        sell_shipping_fee = 0,
        sell_other_fee = 0,
        net_revenue = 0,
        realized_profit = 0,
        realized_roi = 0,
        sell_date = ''
    WHERE id = ?
    """

    params = [card_id]

    if user_id is not None:
        sql += " AND user_id = ?"
        params.append(user_id)

    execute_sql(cursor, sql, params)

    conn.commit()
    conn.close()


# =========================
# Dashboard Summary
# =========================

def get_dashboard_full_summary(user_id=None):
    conn = get_connection()
    cursor = conn.cursor()

    holding_sql = """
        SELECT
            COUNT(*) AS total_cards,
            SUM(total_cost) AS total_cost,
            SUM(current_market_price) AS total_market_value,
            SUM(unrealized_profit) AS total_unrealized_profit
        FROM cards
        WHERE status = 'holding'
    """

    holding_params = []

    if user_id is not None:
        holding_sql += " AND user_id = ?"
        holding_params.append(user_id)

    execute_sql(cursor, holding_sql, holding_params)
    holding = cursor.fetchone()

    sold_sql = """
        SELECT
            COUNT(*) AS total_cards,
            SUM(total_cost) AS total_cost,
            SUM(net_revenue) AS total_net_revenue,
            SUM(realized_profit) AS total_realized_profit
        FROM cards
        WHERE status = 'sold'
    """

    sold_params = []

    if user_id is not None:
        sold_sql += " AND user_id = ?"
        sold_params.append(user_id)

    execute_sql(cursor, sold_sql, sold_params)
    sold = cursor.fetchone()

    conn.close()

    return holding, sold

def get_admin_overview_stats():
    conn = get_connection()
    cursor = conn.cursor()

    execute_sql(cursor, "SELECT COUNT(*) AS count FROM users")
    total_users = cursor.fetchone()["count"] or 0

    execute_sql(
        cursor,
        """
        SELECT COUNT(*) AS count
        FROM users
        WHERE line_user_id IS NOT NULL
        AND line_user_id != ''
        """
    )
    bound_users = cursor.fetchone()["count"] or 0

    unbound_users = total_users - bound_users

    execute_sql(cursor, "SELECT COUNT(*) AS count FROM cards")
    total_cards = cursor.fetchone()["count"] or 0

    execute_sql(
        cursor,
        "SELECT COUNT(*) AS count FROM cards WHERE status = 'holding'"
    )
    holding_cards = cursor.fetchone()["count"] or 0

    execute_sql(
        cursor,
        "SELECT COUNT(*) AS count FROM cards WHERE status = 'sold'"
    )
    sold_cards = cursor.fetchone()["count"] or 0

    execute_sql(
        cursor,
        """
        SELECT COUNT(*) AS count
        FROM cards
        WHERE DATE(created_at) = CURRENT_DATE
        """
        if is_postgres()
        else
        """
        SELECT COUNT(*) AS count
        FROM cards
        WHERE DATE(created_at) = DATE('now')
        """
    )
    today_new_cards = cursor.fetchone()["count"] or 0

    conn.close()

    return {
        "total_users": total_users,
        "bound_users": bound_users,
        "unbound_users": unbound_users,
        "total_cards": total_cards,
        "holding_cards": holding_cards,
        "sold_cards": sold_cards,
        "today_new_cards": today_new_cards
    }

# =========================
# Fast Bulk Import Override
# =========================

def _import_safe_text(value):
    if value is None:
        return ""

    try:
        # openpyxl 讀到數字時，避免變成 85.0 這種格式。
        if isinstance(value, float) and value.is_integer():
            return str(int(value)).strip()
    except:
        pass

    return str(value).strip()


def bulk_import_search_aliases(rows, max_tags=8):
    """
    快速批量匯入搜尋別名。

    重點：
    1. 只開一次資料庫連線。
    2. 先把現有標籤、現有別名讀進記憶體。
    3. 匯入過程不再每一筆都重新 get_connection()。
    4. Excel tags 欄位填「寶可夢」會套用既有寶可夢標籤顏色。
    5. 不存在的標籤會自動建立為預設藍色。
    """
    result = {
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "errors": 0,
        "total": 0
    }

    rows = rows or []

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # 先載入所有現有標籤，key 用 lower，方便不分大小寫比對。
        execute_sql(cursor, "SELECT id, tag_name, tag_color FROM search_tags")
        existing_tags = cursor.fetchall()

        tag_map = {}

        for tag in existing_tags:
            tag_name = tag["tag_name"]
            tag_map[_import_safe_text(tag_name).lower()] = tag["id"]

        # 先載入所有現有別名，避免每一筆查一次。
        execute_sql(cursor, "SELECT id, alias_keyword FROM search_aliases")
        existing_aliases = cursor.fetchall()

        alias_map = {}

        for alias in existing_aliases:
            alias_keyword = alias["alias_keyword"]
            alias_map[_import_safe_text(alias_keyword).lower()] = alias["id"]

        for row in rows:
            result["total"] += 1

            try:
                alias_keyword = _import_safe_text(row.get("alias_keyword"))
                search_keyword = _import_safe_text(row.get("search_keyword"))
                note = _import_safe_text(row.get("note"))
                tags_text = _import_safe_text(row.get("tags"))

                if not alias_keyword or not search_keyword:
                    result["skipped"] += 1
                    continue

                tag_names = split_import_tag_names(tags_text, max_tags=max_tags)
                tag_ids = []

                for tag_name in tag_names:
                    tag_name = _import_safe_text(tag_name)

                    if not tag_name:
                        continue

                    tag_key = tag_name.lower()
                    tag_id = tag_map.get(tag_key)

                    if not tag_id:
                        tag_color = "#3b82f6"

                        if is_postgres():
                            insert_tag_sql = """
                                INSERT INTO search_tags (
                                    tag_name,
                                    tag_color
                                )
                                VALUES (?, ?)
                                RETURNING id
                            """

                            execute_sql(cursor, insert_tag_sql, [
                                tag_name,
                                tag_color
                            ])

                            new_tag = cursor.fetchone()
                            tag_id = new_tag["id"]
                        else:
                            insert_tag_sql = """
                                INSERT INTO search_tags (
                                    tag_name,
                                    tag_color
                                )
                                VALUES (?, ?)
                            """

                            execute_sql(cursor, insert_tag_sql, [
                                tag_name,
                                tag_color
                            ])

                            tag_id = cursor.lastrowid

                        tag_map[tag_key] = tag_id

                    if tag_id and tag_id not in tag_ids:
                        tag_ids.append(tag_id)

                    if len(tag_ids) >= max_tags:
                        break

                alias_key = alias_keyword.lower()
                alias_id = alias_map.get(alias_key)

                if alias_id:
                    update_alias_sql = """
                        UPDATE search_aliases
                        SET
                            alias_keyword = ?,
                            search_keyword = ?,
                            note = ?,
                            is_active = 1,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """

                    execute_sql(cursor, update_alias_sql, [
                        alias_keyword,
                        search_keyword,
                        note,
                        alias_id
                    ])

                    result["updated"] += 1
                else:
                    if is_postgres():
                        insert_alias_sql = """
                            INSERT INTO search_aliases (
                                alias_keyword,
                                search_keyword,
                                note,
                                is_active
                            )
                            VALUES (?, ?, ?, 1)
                            RETURNING id
                        """

                        execute_sql(cursor, insert_alias_sql, [
                            alias_keyword,
                            search_keyword,
                            note
                        ])

                        new_alias = cursor.fetchone()
                        alias_id = new_alias["id"]
                    else:
                        insert_alias_sql = """
                            INSERT INTO search_aliases (
                                alias_keyword,
                                search_keyword,
                                note,
                                is_active
                            )
                            VALUES (?, ?, ?, 1)
                        """

                        execute_sql(cursor, insert_alias_sql, [
                            alias_keyword,
                            search_keyword,
                            note
                        ])

                        alias_id = cursor.lastrowid

                    alias_map[alias_key] = alias_id
                    result["created"] += 1

                # 重新設定此別名的標籤。
                delete_link_sql = """
                    DELETE FROM search_alias_tags
                    WHERE alias_id = ?
                """

                execute_sql(cursor, delete_link_sql, [alias_id])

                insert_link_sql = """
                    INSERT INTO search_alias_tags (
                        alias_id,
                        tag_id
                    )
                    VALUES (?, ?)
                """

                for tag_id in tag_ids[:max_tags]:
                    try:
                        execute_sql(cursor, insert_link_sql, [
                            alias_id,
                            tag_id
                        ])
                    except Exception as e:
                        print("批量匯入標籤關聯失敗：", e)
                        continue

                # 每 200 筆 commit 一次，避免交易太大。
                if result["total"] % 200 == 0:
                    conn.commit()

            except Exception as e:
                print("批量匯入搜尋別名單筆失敗：", e)
                result["errors"] += 1
                continue

        conn.commit()

    except Exception as e:
        conn.rollback()
        print("批量匯入搜尋別名整批失敗：", e)
        raise

    finally:
        conn.close()

    return result
