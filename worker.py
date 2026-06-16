"""
Cadouka price update worker.

Run this process separately from the Flask web process:

    python worker.py

It reads pending jobs from price_update_jobs, uses market_price_cache and
jpy_rate_cache, then updates card market prices in the background.
"""

import os
import time
import traceback
from datetime import datetime, timedelta, timezone

from exchange import get_jpy_spot_sell
from snkrdunk import get_product_id, build_sales_history_url, getprice
from models import (
    init_db,
    migrate_db,
    get_all_cards,
    get_card_by_id,
    update_card_market_price,
    get_pending_price_update_job,
    mark_price_update_job_running,
    update_price_update_job_progress,
    finish_price_update_job,
    get_jpy_rate_cache,
    upsert_jpy_rate_cache,
    get_market_price_cache,
    upsert_market_price_cache,
)

CACHE_HOURS = int(os.getenv("PRICE_CACHE_HOURS", "6"))
CARD_COOLDOWN_HOURS = int(os.getenv("CARD_PRICE_COOLDOWN_HOURS", "6"))
WORKER_SLEEP_SECONDS = int(os.getenv("PRICE_WORKER_SLEEP_SECONDS", "5"))
JOB_SLEEP_SECONDS = float(os.getenv("PRICE_WORKER_JOB_SLEEP_SECONDS", "0.4"))
DEFAULT_GRADE = "PSA10"
VALID_GRADES = {"PSA10", "PSA9", "PSA8以下", "A", "B"}


def taiwan_now():
    return datetime.now(timezone(timedelta(hours=8))).replace(tzinfo=None)


def taiwan_now_text():
    return taiwan_now().strftime("%Y-%m-%d %H:%M:%S")


def parse_time_text(value):
    if not value:
        return None

    text = str(value).split(".")[0].strip()

    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"]:
        try:
            return datetime.strptime(text, fmt)
        except:
            continue

    return None


def is_fresh(updated_at, hours):
    dt = parse_time_text(updated_at)

    if not dt:
        return False

    return taiwan_now() - dt < timedelta(hours=hours)


def should_skip_card(card, cooldown_hours=CARD_COOLDOWN_HOURS):
    return is_fresh(card.get("price_updated_at"), cooldown_hours)


def parse_jpy_price(price):
    try:
        return int(float(str(price).replace(",", "").replace("¥", "").strip()))
    except:
        return None


def calculate_average_jpy(prices):
    valid_prices = []

    for item in prices or []:
        price = parse_jpy_price(item.get("price"))

        if price is not None:
            valid_prices.append(price)

    if not valid_prices:
        return 0

    return round(sum(valid_prices) / len(valid_prices))


def calculate_unrealized_by_buy_price(current_market_price, buy_price):
    buy_price = buy_price or 0
    unrealized_profit = current_market_price - buy_price

    if buy_price == 0:
        roi = 0
    else:
        roi = (unrealized_profit / buy_price) * 100

    return unrealized_profit, roi


def normalize_grade(value):
    grade = str(value or "").strip()

    if grade in VALID_GRADES:
        return grade

    return DEFAULT_GRADE


def get_cached_jpy_rate():
    cached = get_jpy_rate_cache()

    if cached:
        try:
            cached_rate = float(cached["rate"] or 0)
        except:
            cached_rate = 0

        if cached_rate > 0 and is_fresh(cached["updated_at"], CACHE_HOURS):
            return cached_rate

    try:
        rate = float(get_jpy_spot_sell() or 0)
    except Exception as e:
        print("日圓匯率更新失敗：", e)
        rate = 0

    if rate > 0:
        upsert_jpy_rate_cache(rate, taiwan_now_text())
        return rate

    # 外部匯率失敗時，允許使用舊快取，避免整批任務全掛。
    if cached:
        try:
            fallback_rate = float(cached["rate"] or 0)
        except:
            fallback_rate = 0

        if fallback_rate > 0:
            return fallback_rate

    return 0


def get_market_price_with_cache(product_url, grade):
    product_id = get_product_id(product_url)

    if not product_id:
        return 0

    grade = normalize_grade(grade)
    cached = get_market_price_cache(product_id, grade)

    if cached:
        try:
            cached_price = float(cached["market_price_twd"] or 0)
        except:
            cached_price = 0

        if cached_price > 0 and is_fresh(cached["updated_at"], CACHE_HOURS):
            return round(cached_price)

    jpy_rate = get_cached_jpy_rate()

    if jpy_rate <= 0:
        return 0

    price_url = build_sales_history_url(
        product_id,
        condition=grade,
        page=1,
        per_page=20
    )

    prices = getprice(price_url)
    average_jpy = calculate_average_jpy(prices)

    if average_jpy <= 0:
        return 0

    market_price_twd = round(average_jpy * jpy_rate)

    upsert_market_price_cache(
        product_id=product_id,
        grade=grade,
        market_price_twd=market_price_twd,
        average_jpy=average_jpy,
        jpy_rate=jpy_rate,
        updated_at=taiwan_now_text(),
        source="SNKRDUNK"
    )

    return market_price_twd


def get_job_cards(job):
    job_type = job.get("job_type") or "all"
    user_id = job["user_id"]

    if job_type == "single":
        card_id = job.get("card_id")
        card = get_card_by_id(card_id, user_id=user_id)
        return [dict(card)] if card else []

    cards = get_all_cards(
        status="holding",
        keyword=None,
        sort=None,
        user_id=user_id
    )

    return [dict(card) for card in cards]


def process_job(job):
    job_id = job["id"]

    if not mark_price_update_job_running(job_id, taiwan_now_text()):
        return

    updated_count = 0
    skipped_count = 0
    failed_count = 0

    try:
        cards = get_job_cards(job)
        total_count = len(cards)

        update_price_update_job_progress(
            job_id,
            total_count=total_count,
            updated_count=0,
            skipped_count=0,
            failed_count=0,
            message="更新中"
        )

        if total_count == 0:
            finish_price_update_job(
                job_id,
                status="done",
                message="沒有可更新的卡牌",
                finished_at=taiwan_now_text(),
                updated_count=0,
                skipped_count=0,
                failed_count=0,
                total_count=0
            )
            return

        for card in cards:
            try:
                if card.get("status") != "holding":
                    skipped_count += 1
                    continue

                product_url = card.get("product_url") or ""

                if not product_url:
                    skipped_count += 1
                    continue

                if should_skip_card(card):
                    skipped_count += 1
                    continue

                market_price = get_market_price_with_cache(
                    product_url=product_url,
                    grade=card.get("grade")
                )

                if market_price <= 0:
                    failed_count += 1
                    continue

                buy_price = card.get("buy_price") or 0
                unrealized_profit, roi = calculate_unrealized_by_buy_price(
                    market_price,
                    buy_price
                )

                update_card_market_price(
                    card["id"],
                    market_price,
                    unrealized_profit,
                    roi,
                    taiwan_now_text(),
                    user_id=job["user_id"]
                )

                updated_count += 1

                update_price_update_job_progress(
                    job_id,
                    total_count=total_count,
                    updated_count=updated_count,
                    skipped_count=skipped_count,
                    failed_count=failed_count,
                    message="更新中"
                )

                if JOB_SLEEP_SECONDS > 0:
                    time.sleep(JOB_SLEEP_SECONDS)

            except Exception as e:
                print(f"卡牌市價更新失敗 card_id={card.get('id')}：", e)
                traceback.print_exc()
                failed_count += 1
                update_price_update_job_progress(
                    job_id,
                    total_count=total_count,
                    updated_count=updated_count,
                    skipped_count=skipped_count,
                    failed_count=failed_count,
                    message="更新中，部分卡牌失敗"
                )
                continue

        if failed_count == 0:
            message = f"更新完成：成功 {updated_count} 張，略過 {skipped_count} 張"
        else:
            message = f"更新完成：成功 {updated_count} 張，略過 {skipped_count} 張，失敗 {failed_count} 張"

        finish_price_update_job(
            job_id,
            status="done",
            message=message,
            finished_at=taiwan_now_text(),
            updated_count=updated_count,
            skipped_count=skipped_count,
            failed_count=failed_count,
            total_count=total_count
        )

    except Exception as e:
        print(f"更新任務失敗 job_id={job_id}：", e)
        traceback.print_exc()

        finish_price_update_job(
            job_id,
            status="failed",
            message="更新任務發生錯誤，請稍後再試",
            finished_at=taiwan_now_text(),
            updated_count=updated_count,
            skipped_count=skipped_count,
            failed_count=failed_count
        )


def run_forever():
    init_db()
    migrate_db()

    print("Cadouka price worker started")

    while True:
        job = get_pending_price_update_job()

        if job:
            try:
                process_job(dict(job))
            except Exception as e:
                print("worker 處理任務時發生未預期錯誤：", e)
                traceback.print_exc()
        else:
            time.sleep(WORKER_SLEEP_SECONDS)


if __name__ == "__main__":
    run_forever()
