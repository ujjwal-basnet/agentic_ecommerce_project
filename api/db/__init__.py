"""Database package public API."""

from api.db.row import Row
from api.db.pool import PostgresConnection, QueryResult, close_pool, get_conn
from api.db.schema import init_db, startup
from api.db.users import (
    bind_session_user,
    clear_history,
    ensure_session,
    get_user_by_session,
    load_history,
    save_message,
    unbind_session_user,
    upsert_user,
)
from api.db.cart import (
    cart_count,
    cart_total,
    cart_totals,
    db_add_to_cart,
    db_clear_cart,
    db_get_cart,
    db_remove_from_cart,
    db_update_cart_quantity,
)
from api.db.orders import (
    get_order_stats_by_session,
    get_orders_by_session,
    place_order,
    update_order_status,
)
from api.db.products import (
    add_to_wishlist,
    delete_product_row,
    get_all_products,
    get_product_by_id,
    get_product_by_name,
    get_products_by_ids,
    get_wishlist,
    insert_product,
    save_product_image,
    save_user_image,
    search_products,
    update_product,
)
from api.db.analytics import (
    get_customer_count,
    get_daily_signals,
    get_logistics_rows,
    get_product_signals,
    get_recent_orders,
    get_revenue_by_category,
    get_revenue_by_day,
    get_revenue_for_day,
    get_stock_levels,
    get_summary_stats,
    get_top_products,
    log_product_view,
)
from api.db.knowledge import search_knowledge_base

__all__ = [name for name in globals() if not name.startswith("_")]
