"""任務看板的 Streamlit 多頁面入口。

正式程式統一維護在專案根目錄的 ``task_board.py``，避免兩套同名頁面
產生功能不一致。無論部署指定根目錄入口或由 pages 目錄進入，都會執行
同一份任務看板程式。
"""

from pathlib import Path


TASK_BOARD_FILE = Path(__file__).resolve().parents[1] / "task_board.py"

if not TASK_BOARD_FILE.exists():
    raise FileNotFoundError("找不到正式任務看板：task_board.py")

exec(compile(TASK_BOARD_FILE.read_text(encoding="utf-8"), str(TASK_BOARD_FILE), "exec"), globals())
