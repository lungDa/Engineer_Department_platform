"""LINE commands for querying current certificate status."""

from __future__ import annotations

from datetime import date

from services.certificate_service import CertificateService
from services.core import UserService


def _bound_user(line_user_id: str | None) -> dict | None:
    target = str(line_user_id or "").strip()
    return next(
        (
            user
            for user in UserService.get_active_users()
            if str(user.get("line_user_id") or "").strip() == target
        ),
        None,
    )


def _status(record: dict, today: date) -> tuple[int, str]:
    expiry = CertificateService.parse_date(record.get("expiry_date"))
    if not expiry:
        return 3, "⚪ 未設定到期日"
    days = (expiry - today).days
    reminder_days = CertificateService.to_int(record.get("reminder_days"), 30)
    if days < 0:
        return 0, f"🔴 已逾期 {-days} 天"
    if days == 0:
        return 1, "🟠 今天到期"
    if days <= reminder_days:
        return 1, f"🟠 即將到期（剩 {days} 天）"
    return 2, f"🟢 有效（剩 {days} 天）"


def _matches(record: dict, keyword: str) -> bool:
    key = keyword.casefold()
    return any(
        key in str(record.get(field) or "").casefold()
        for field in ("account", "name", "certificate_name", "certificate_number", "issuer")
    )


def certificate_status_text(
    text: str,
    user_id: str | None = None,
    *,
    today: date | None = None,
    limit: int = 20,
) -> str | None:
    """Return a certificate query reply, or None when text is not this command."""
    raw = str(text or "").strip()
    compact = raw.replace("＃", "#")
    is_mine = compact in {"我的證照", "#我的證照"}
    is_query = compact in {"證照", "#證照"} or compact.startswith(("證照 ", "#證照 "))
    if not is_mine and not is_query:
        return None

    records = CertificateService.load_all()
    query_label = "全部"
    if is_mine:
        actor = _bound_user(user_id)
        if not actor:
            return "❌ 尚未綁定平台帳號，無法查詢本人證照。\n\n請先輸入：綁定 工號 密碼"
        account = str(actor.get("account") or "").strip().casefold()
        records = [
            row for row in records
            if str(row.get("account") or "").strip().casefold() == account
        ]
        query_label = str(actor.get("name") or actor.get("account") or "本人")
    else:
        keyword = compact.lstrip("#")[len("證照"):].strip()
        if keyword:
            records = [row for row in records if _matches(row, keyword)]
            query_label = keyword

    if not records:
        return f"🪪 證照狀態｜{query_label}\n\n目前沒有查到符合的證照資料。"

    check_date = today or date.today()
    prepared = [(_status(row, check_date), row) for row in records]
    prepared.sort(
        key=lambda item: (
            item[0][0],
            str(item[1].get("expiry_date") or "9999-12-31"),
            str(item[1].get("name") or ""),
            str(item[1].get("certificate_name") or ""),
        )
    )
    counts = {0: 0, 1: 0, 2: 0, 3: 0}
    for status, _ in prepared:
        counts[status[0]] += 1

    lines = [
        f"🪪 證照狀態｜{query_label}",
        f"查詢日期：{check_date.isoformat()}",
        f"共 {len(prepared)} 筆｜逾期 {counts[0]}｜即將到期 {counts[1]}｜有效 {counts[2]}｜未設定 {counts[3]}",
        "",
    ]
    for index, (status, row) in enumerate(prepared[:limit], start=1):
        lines.extend(
            [
                f"{index}. {row.get('name') or row.get('account') or '未指定人員'}｜{row.get('certificate_name') or '未命名證照'}",
                f"   {status[1]}",
                f"   到期：{row.get('expiry_date') or '未設定'}",
            ]
        )
        if row.get("certificate_number"):
            lines.append(f"   證書字號：{row.get('certificate_number')}")
        lines.append("")

    if len(prepared) > limit:
        lines.append(f"尚有 {len(prepared) - limit} 筆未列出，請輸入「證照 關鍵字」縮小範圍。")
    return "\n".join(lines).strip()
