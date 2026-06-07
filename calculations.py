def calculate_total_cost(
    buy_price,
    shipping_fee=0,
    tax_fee=0,
    platform_fee=0,
    other_fee=0
):
    return buy_price + shipping_fee + tax_fee + platform_fee + other_fee


def calculate_unrealized_profit(current_market_price, total_cost):
    return current_market_price - total_cost


def calculate_roi(profit, total_cost):
    if total_cost == 0:
        return 0

    return (profit / total_cost) * 100

def calculate_net_revenue(
    sell_price,
    sell_fee=0,
    sell_shipping_fee=0,
    sell_other_fee=0
):
    return sell_price - sell_fee - sell_shipping_fee - sell_other_fee


def calculate_realized_profit(net_revenue, total_cost):
    return net_revenue - total_cost


def calculate_realized_roi(realized_profit, total_cost):
    if total_cost == 0:
        return 0

    return (realized_profit / total_cost) * 100