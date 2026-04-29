"""Order receipt emails — fire-and-forget via SMTP.

Sends a simple HTML receipt after checkout. Does nothing if SMTP is not configured.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from api import config

logger = logging.getLogger(__name__)


def _configured() -> bool:
    return bool(
        config.SMTP_HOST
        and config.SMTP_USER
        and config.SMTP_PASSWORD
        and config.SMTP_FROM
    )


def _build_receipt_html(user_name: str, order_items: list[dict], total: float) -> str:
    rows = ""
    for item in order_items:
        name = item.get("product_name", "Item")
        qty = item.get("quantity", 1)
        price = item.get("price", 0)
        rows += (
            f"<tr>"
            f"<td style='padding:8px;border-bottom:1px solid #eee'>{name}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;text-align:center'>{qty}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;text-align:right'>Rs. {price * qty:,.2f}</td>"
            f"</tr>"
        )

    return f"""
    <div style="font-family:sans-serif;max-width:500px;margin:auto">
        <h2 style="color:#333">🛍️ Order Confirmation</h2>
        <p>Hi {user_name},</p>
        <p>Thank you for your order! Here's your receipt:</p>
        <table style="width:100%;border-collapse:collapse;margin:16px 0">
            <thead>
                <tr style="background:#f8f8f8">
                    <th style="padding:8px;text-align:left">Product</th>
                    <th style="padding:8px;text-align:center">Qty</th>
                    <th style="padding:8px;text-align:right">Subtotal</th>
                </tr>
            </thead>
            <tbody>{rows}</tbody>
            <tfoot>
                <tr>
                    <td colspan="2" style="padding:10px;font-weight:bold">Total</td>
                    <td style="padding:10px;text-align:right;font-weight:bold">Rs. {total:,.2f}</td>
                </tr>
            </tfoot>
        </table>
        <p style="color:#888;font-size:13px">
            If you have questions about your order, reply to this email or
            contact support@smartshop.com.np.
        </p>
        <p style="color:#888;font-size:12px">— SmartShop</p>
    </div>
    """


def _send_blocking(
    to_email: str, user_name: str, order_items: list[dict], total: float
):
    """Blocking SMTP send — run in a thread."""
    if not _configured():
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "SmartShop — Your Order Confirmation"
        msg["From"] = config.SMTP_FROM
        msg["To"] = to_email

        html = _build_receipt_html(user_name, order_items, total)
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as smtp:
            smtp.starttls()
            smtp.login(config.SMTP_USER, config.SMTP_PASSWORD)
            smtp.sendmail(config.SMTP_FROM, [to_email], msg.as_string())

        logger.info("Receipt email sent to %s", to_email)
    except Exception:
        logger.exception("Failed to send receipt email to %s", to_email)


async def send_receipt(
    to_email: str, user_name: str, order_items: list[dict], total: float
):
    """Fire-and-forget: send email receipt in background thread."""
    if not _configured() or not to_email:
        return
    asyncio.get_running_loop().run_in_executor(
        None, _send_blocking, to_email, user_name, order_items, total
    )
