import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

st.set_page_config(layout="wide") # 讓網頁變寬，更適合看月班表
st.title("🍔 隔壁早餐店 - 月班表系統")

# --- 1. 建立連線並讀取資料 ---
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df = conn.read(worksheet="工作表1", ttl=0)
    df = df.dropna(how="all")
    
    # 填補空值為 False，這樣 Streamlit 才會全部以勾選框顯示
    df = df.fillna(False) 
    
    # 【關鍵設定】：將第一欄（夥伴名稱）設為 Index
    # 這樣在畫面上往右滑動看月底的班時，名字才會固定凍結在左邊！
    df.set_index(df.columns[0], inplace=True)

except Exception as e:
    st.error(f"讀取試算表失敗，請檢查連線：{e}")
    st.stop()

st.write("👉 請直接點擊格子進行排班（打勾代表上班），完成後點擊最下方按鈕儲存。")

# --- 2. 顯示互動式月班表 ---
# 針對所有日期欄位設定為 CheckboxColumn
column_configs = {
    str(col): st.column_config.CheckboxColumn(str(col)) 
    for col in df.columns
}

# 渲染表格
edited_df = st.data_editor(
    df,
    column_config=column_configs,
    use_container_width=True,
    height=500 # 設定一個適合的高度
)

# --- 3. 儲存按鈕 ---
if st.button("💾 同步儲存班表至雲端", type="primary"):
    # 存回 Google Sheets 前，要把 Index (夥伴名稱) 變回一般的欄位
    save_df = edited_df.reset_index()
    conn.update(worksheet="工作表1", data=save_df)
    st.success("班表已成功同步更新！")
