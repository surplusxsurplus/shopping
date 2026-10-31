import html
import json
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="쇼핑 리스트", page_icon="🛒", layout="centered")

# 최소한의 CSS: 테마 변수/투명도만 사용해 라이트/다크 모두에서 읽히도록 함
CSS = """
<style>
.block-container { max-width: 640px; padding-top: 2.5rem; }
/* 모바일에서도 한 줄 유지 */
div[data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: 0.4rem; }
div[data-testid="stColumn"] { min-width: 0 !important; }
/* 입력창의 "Press Enter to submit form" 안내가 placeholder와 겹치는 문제 */
[data-testid="InputInstructions"] { display: none; }
/* 아이템 이름 */
.item-name { font-size: 1.05rem; line-height: 2.2rem; word-break: break-word; }
.item-done { text-decoration: line-through; opacity: 0.45; }
/* 목록 행 사이 여백 */
div[data-testid="stCheckbox"] { padding: 0; }
/* 보조 버튼(수정/삭제)은 테두리 없이 담백하게 */
div[data-testid="stButton"] button[kind="tertiary"] { padding: 0.2rem 0.4rem; opacity: 0.6; }
div[data-testid="stButton"] button[kind="tertiary"]:hover { opacity: 1; }
</style>
"""

DATA_FILE = Path(__file__).parent / "items.json"


# ---- 저장 / 불러오기 (F7) ----
def load_items():
    """items.json을 읽는다. 파일이 없거나 손상되었으면 빈 리스트를 반환."""
    if not DATA_FILE.exists():
        return []
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, list):
        return []
    items = []
    for it in data:
        if (
            isinstance(it, dict)
            and isinstance(it.get("id"), int)
            and isinstance(it.get("name"), str)
        ):
            items.append(
                {"id": it["id"], "name": it["name"], "checked": bool(it.get("checked"))}
            )
    return items


def save_items():
    try:
        DATA_FILE.write_text(
            json.dumps(st.session_state.shopping_items, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        st.session_state.save_error = True


# ---- 상태 초기화 ----
def init_state():
    if "shopping_items" not in st.session_state:
        # 데이터 모델: {"id": int, "name": str, "checked": bool}
        st.session_state.shopping_items = load_items()
    if "editing" not in st.session_state:
        st.session_state.editing = None
    if "next_id" not in st.session_state:
        # 삭제 후에도 id가 재사용되지 않도록 카운터를 따로 관리
        st.session_state.next_id = (
            max((i["id"] for i in st.session_state.shopping_items), default=0) + 1
        )


def find_item(item_id):
    for it in st.session_state.shopping_items:
        if it["id"] == item_id:
            return it
    return None


# ---- 기능 콜백 ----
def add_item():  # F1
    name = st.session_state.new_item.strip()
    if name:
        st.session_state.shopping_items.append(
            {"id": st.session_state.next_id, "name": name, "checked": False}
        )
        st.session_state.next_id += 1
        save_items()
    st.session_state.new_item = ""


def start_edit(item_id):  # F2
    st.session_state.editing = item_id


def cancel_edit():  # F2
    st.session_state.editing = None


def save_edit(item_id):  # F2
    item = find_item(item_id)
    # 이미 삭제되었거나 수정 모드가 아니면 무시 (Enter/버튼 중복 호출 방지)
    if item is None or st.session_state.editing != item_id:
        return
    name = st.session_state.get(f"edit_{item_id}", "").strip()
    if name:  # 빈 값이면 기존 이름 유지
        item["name"] = name
        save_items()
    st.session_state.editing = None


def delete_item(item_id):  # F3
    st.session_state.shopping_items = [i for i in st.session_state.shopping_items if i["id"] != item_id]
    if st.session_state.editing == item_id:
        st.session_state.editing = None
    save_items()


def toggle_item(item_id):  # F4
    item = find_item(item_id)
    if item is not None:
        item["checked"] = st.session_state[f"chk_{item_id}"]
        save_items()


def clear_checked():  # F6
    st.session_state.shopping_items = [i for i in st.session_state.shopping_items if not i["checked"]]
    if find_item(st.session_state.editing) is None:
        st.session_state.editing = None
    save_items()


# ---- 화면 영역 ----
def render_header():
    st.markdown(CSS, unsafe_allow_html=True)
    st.title("🛒 쇼핑 리스트")
    items = st.session_state.shopping_items
    if items:  # F5
        done = sum(1 for i in items if i["checked"])
        st.progress(done / len(items), text=f"{done} / {len(items)} 완료")
    if st.session_state.pop("save_error", False):
        st.warning("items.json에 저장하지 못했습니다. 파일 권한을 확인하세요.")


def render_input():
    with st.form("add_form", border=False):
        c1, c2 = st.columns([5, 2], vertical_alignment="center")
        c1.text_input(
            "아이템",
            key="new_item",
            placeholder="사야 할 물건을 입력하세요",
            label_visibility="collapsed",
        )
        c2.form_submit_button(
            "➕ 추가", on_click=add_item, type="primary", use_container_width=True
        )


def render_edit_row(item):
    """수정 모드 행. 폼으로 감싸서 값이 💾/Enter 제출 때만 반영되게 한다.
    (취소를 눌러도 입력값이 저장되지 않도록 on_change 콜백은 쓰지 않는다.)"""
    iid = item["id"]
    with st.form(f"edit_form_{iid}", border=False):
        c_pad, c_name, c_a, c_b = st.columns(
            [1, 8, 1.3, 1.3], vertical_alignment="center"
        )
        c_pad.write("✏️")
        c_name.text_input(
            "이름 수정",
            value=item["name"],
            key=f"edit_{iid}",
            label_visibility="collapsed",
        )
        # Enter는 폼의 첫 번째 제출 버튼(저장)을 실행한다
        c_a.form_submit_button(
            "💾", help="저장", on_click=save_edit, args=(iid,), type="primary"
        )
        c_b.form_submit_button("✖", help="취소", on_click=cancel_edit)


def render_row(item):
    iid = item["id"]
    if st.session_state.editing == iid:
        render_edit_row(item)
        return
    c_chk, c_name, c_a, c_b = st.columns(
        [1, 8, 1.3, 1.3], vertical_alignment="center"
    )

    c_chk.checkbox(
        "완료",
        value=item["checked"],
        key=f"chk_{iid}",
        on_change=toggle_item,
        args=(iid,),
        label_visibility="collapsed",
    )

    # st.html은 마크다운을 해석하지 않으므로 URL 자동 링크 등이 생기지 않는다
    cls = "item-name item-done" if item["checked"] else "item-name"
    with c_name:
        st.html(f'<span class="{cls}">{html.escape(item["name"])}</span>')
    c_a.button(
        "✏️", key=f"editbtn_{iid}", help="수정", on_click=start_edit,
        args=(iid,), type="tertiary",
    )
    c_b.button(
        "🗑️", key=f"del_{iid}", help="삭제", on_click=delete_item,
        args=(iid,), type="tertiary",
    )


def render_list():
    items = st.session_state.shopping_items
    if not items:
        st.info("목록이 비어 있습니다. 아이템을 추가해 보세요.", icon="📝")
        return
    st.divider()
    for item in items:
        render_row(item)


def render_footer():
    if any(i["checked"] for i in st.session_state.shopping_items):  # F6
        st.divider()
        st.button(
            "🧹 완료 항목 모두 삭제", on_click=clear_checked, use_container_width=True
        )


def main():
    init_state()
    render_header()
    render_input()
    render_list()
    render_footer()


main()
