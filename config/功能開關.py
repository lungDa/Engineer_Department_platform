"""開發工程部平台集中式功能開關。

此檔只保存功能清單與初始值；實際狀態由開發者在平台後台管理，
並持久保存到 Google Sheet 的 FeatureFlags 工作表。
"""

from __future__ import annotations


功能分類 = {
    "一、主要頁面": {
        "首頁": "ON",
        "任務看板": "ON",
        "艾森豪矩陣": "ON",
        "行事曆": "ON",
        "專案甘特圖": "ON",
        "效率統計分析": "ON",
        "會議系統": "ON",
        "簽核中心": "ON",
        "人員名單": "ON",
        "證照資料整合": "ON",
    },
    "二、首頁與管理功能": {
        "布告欄": "ON",
        "公告發布": "ON",
        "開發者功能": "ON",
        "系統診斷": "ON",
        "Microsoft 365人員同步": "ON",
    },
    "三、任務管理功能": {
        "任務子項目": "ON",
        "任務留言與操作歷程": "ON",
        "任務附件": "ON",
    },
    "四、通知與外部整合": {
        "Teams通知": "ON",
        "Outlook通知": "ON",
        "LINE通知": "ON",
        "LINE智慧助理": "ON",
        "會議自動提醒": "ON",
    },
    "五、資料工具": {
        "行事曆匯出": "ON",
    },
}

# 防止關閉後無法再次進入後台恢復。
必要功能 = {"首頁", "開發者功能"}


_頁面路徑 = {
    "任務看板": "1_任務看板",
    "艾森豪矩陣": "2_艾森豪矩陣",
    "行事曆": "3_行事曆",
    "專案甘特圖": "4_專案甘特圖",
    "效率統計分析": "5_效率統計分析",
    "會議系統": "6_會議系統",
    "簽核中心": "7_簽核中心",
    "人員名單": "8_人員名單",
    "證照資料整合": "9_證照資料整合",
}


def _檢查設定() -> None:
    錯誤 = [
        f"{類別}／{名稱}"
        for 類別, 功能清單 in 功能分類.items()
        for 名稱, 狀態 in 功能清單.items()
        if 狀態 not in {"ON", "OFF"}
    ]
    if 錯誤:
        raise ValueError(
            "功能開關只接受大寫 ON 或 OFF；請修正：" + "、".join(錯誤)
        )


def 功能已開啟(功能名稱: str) -> bool:
    """回傳指定功能是否開啟；不存在的名稱視為程式設定錯誤。"""
    _檢查設定()
    try:
        from services.feature_flag_service import FeatureFlagService
        current = FeatureFlagService.load(功能分類)
    except Exception:
        current = 功能分類
    for 功能清單 in current.values():
        if 功能名稱 in 功能清單:
            return 功能清單[功能名稱] == "ON"
    raise KeyError(f"找不到功能開關：{功能名稱}")


def 要求功能開啟(功能名稱: str) -> None:
    """供 Streamlit 頁面使用；OFF 時顯示訊息並停止執行。"""
    if 功能已開啟(功能名稱):
        return
    import streamlit as st

    st.warning(f"🔒「{功能名稱}」目前已由系統管理員關閉。")
    st.info("如需重新開啟，請由開發者進入首頁的「功能開關管理」。")
    st.stop()


def 隱藏已關閉頁面() -> None:
    """隱藏 Streamlit 原生側邊欄中已關閉的頁面入口。"""
    import streamlit as st

    選擇器 = []
    for 名稱, 路徑 in _頁面路徑.items():
        if not 功能已開啟(名稱):
            選擇器.append(f'a[href*="{路徑}"]')
    if 選擇器:
        st.markdown(
            "<style>" + ",".join(選擇器) + "{display:none !important;}</style>",
            unsafe_allow_html=True,
        )


def 功能狀態一覽() -> list[dict[str, str]]:
    """提供管理畫面或測試使用的繁體中文功能清單。"""
    _檢查設定()
    try:
        from services.feature_flag_service import FeatureFlagService
        current = FeatureFlagService.load(功能分類)
    except Exception:
        current = 功能分類
    return [
        {"功能類別": 類別, "功能名稱": 名稱, "狀態": 狀態}
        for 類別, 功能清單 in current.items()
        for 名稱, 狀態 in 功能清單.items()
    ]
