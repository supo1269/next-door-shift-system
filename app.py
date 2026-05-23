import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import datetime

st.set_page_config(layout="wide")
st.title("🍔 隔壁早餐店 - 自動排班系統")

# --- 建立資料庫連線 ---
conn = st.connection("gsheets", type=GSheetsConnection)

# 定義員工名單 (區分正職與兼職)
full_time = ["權 (正)", "Popo(正)", "Ting(正)"]
part_time = ["柏吟(兼)", "Ping(兼)", "雅妍(兼)", "胖弟(兼)"]
all_employees = full_time + part_time

# --- 建立網頁頁籤 ---
tab1, tab2 = st.tabs(["🗓️ 第一步：畫休登記", "✨ 第二步：自動排班與總表"])

# ==========================================
# 頁籤一：畫休登記介面
# ==========================================
with tab1:
    st.subheader("📝 新增休假")
    
    # 建立輸入表單
    with st.form("leave_form"):
        col1, col2 = st.columns(2)
        with col1:
            selected_emp = st.selectbox("選擇員工", all_employees)
        with col2:
            # 讓員工選擇要休哪一天
            selected_date = st.date_input("選擇休假日期")
            
        submitted = st.form_submit_button("送出休假")
        
        if submitted:
            # 讀取原本的休假紀錄
            try:
                leave_df = conn.read(worksheet="休假紀錄", ttl=0)
                leave_df = leave_df.dropna(how="all")
            except:
                leave_df = pd.DataFrame(columns=["員工姓名", "休假日期"])

            # 檢查是否已經重複登記
            date_str = selected_date.strftime("%Y-%m-%d")
            is_duplicate = ((leave_df["員工姓名"] == selected_emp) & (leave_df["休假日期"] == date_str)).any()
            
            if is_duplicate:
                st.warning(f"⚠️ {selected_emp} 在 {date_str} 已經劃過休囉！")
            else:
                # 將新資料加進去並存回 Google Sheets
                new_data = pd.DataFrame([{"員工姓名": selected_emp, "休假日期": date_str}])
                updated_df = pd.concat([leave_df, new_data], ignore_index=True)
                conn.update(worksheet="休假紀錄", data=updated_df)
                st.success(f"✅ 已成功登記：{selected_emp} 於 {date_str} 休假！")

    st.divider()
    st.subheader("📋 目前已登記的休假清單")
    # 顯示目前的休假表，方便老闆核對
    try:
        current_leaves = conn.read(worksheet="休假紀錄", ttl=0).dropna(how="all")
        st.dataframe(current_leaves, use_container_width=True, hide_index=True)
    except:
        st.info("目前還沒有人劃休。")

# ==========================================
# 頁籤二：預留給未來的排班演算法
# ==========================================
with tab2:
    st.subheader("🤖 系統自動排班 (開發中...)")
    st.write("未來只要按下按鈕，系統就會自動扣除【頁籤一】的休假名單，並依照平日/假日的人力規則生成班表。")
