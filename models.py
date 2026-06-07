import sqlite3


DB_NAME = "cards.db"


def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,

        card_name TEXT NOT NULL,
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
        note TEXT,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()


def add_card(card_data):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO cards (
        card_name,
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
        note
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        card_data["card_name"],
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
        card_data.get("note", "")
    ))

    conn.commit()
    conn.close()


def get_all_cards(status=None, keyword=None, sort=None):
    conn = get_connection()

    sql = """
        SELECT * FROM cards
        WHERE 1 = 1
    """

    params = []

    if status:
        sql += " AND status = ?"
        params.append(status)

    if keyword:
        sql += """
            AND (
                card_name LIKE ?
                OR card_number LIKE ?
                OR grade LIKE ?
                OR purchase_method LIKE ?
                OR note LIKE ?
            )
        """

        search_keyword = f"%{keyword}%"
        params.extend([
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
        sql += " ORDER BY created_at DESC"

    cards = conn.execute(sql, params).fetchall()

    conn.close()
    return cards


def get_card_by_id(card_id):
    conn = get_connection()

    card = conn.execute("""
        SELECT * FROM cards
        WHERE id = ?
    """, (card_id,)).fetchone()

    conn.close()
    return card


def update_card(card_id, card_data):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE cards
    SET
        card_name = ?,
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
        note = ?
    WHERE id = ?
    """, (
        card_data["card_name"],
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
        card_data.get("note", ""),

        card_id
    ))

    conn.commit()
    conn.close()


def delete_card(card_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM cards
        WHERE id = ?
    """, (card_id,))

    conn.commit()
    conn.close()


def add_column_if_not_exists(column_name, column_definition):
    conn = get_connection()
    cursor = conn.cursor()

    columns = cursor.execute("PRAGMA table_info(cards)").fetchall()
    existing_columns = [col["name"] for col in columns]

    if column_name not in existing_columns:
        cursor.execute(
            f"ALTER TABLE cards ADD COLUMN {column_name} {column_definition}"
        )
        conn.commit()

    conn.close()


def migrate_db():
    """
    舊資料庫升級用。
    如果 cards.db 已經存在，init_db() 不會重建表格，
    所以要用 migrate_db() 補上後來新增的欄位。
    """
    add_column_if_not_exists("purchase_method", "TEXT")

    add_column_if_not_exists("sell_fee", "REAL DEFAULT 0")
    add_column_if_not_exists("sell_shipping_fee", "REAL DEFAULT 0")
    add_column_if_not_exists("sell_other_fee", "REAL DEFAULT 0")
    add_column_if_not_exists("net_revenue", "REAL DEFAULT 0")
    add_column_if_not_exists("realized_roi", "REAL DEFAULT 0")


def mark_card_as_sold(card_id, sell_data):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
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
    """, (
        sell_data.get("sell_price", 0),
        sell_data.get("sell_fee", 0),
        sell_data.get("sell_shipping_fee", 0),
        sell_data.get("sell_other_fee", 0),
        sell_data.get("net_revenue", 0),
        sell_data.get("realized_profit", 0),
        sell_data.get("realized_roi", 0),
        sell_data.get("sell_date", ""),
        card_id
    ))

    conn.commit()
    conn.close()


def get_dashboard_full_summary():
    conn = get_connection()

    holding = conn.execute("""
        SELECT
            COUNT(*) AS total_cards,
            SUM(total_cost) AS total_cost,
            SUM(current_market_price) AS total_market_value,
            SUM(unrealized_profit) AS total_unrealized_profit
        FROM cards
        WHERE status = 'holding'
    """).fetchone()

    sold = conn.execute("""
        SELECT
            COUNT(*) AS total_cards,
            SUM(total_cost) AS total_cost,
            SUM(net_revenue) AS total_net_revenue,
            SUM(realized_profit) AS total_realized_profit
        FROM cards
        WHERE status = 'sold'
    """).fetchone()

    conn.close()

    return holding, sold