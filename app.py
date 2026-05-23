import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import datetime
from dateutil.relativedelta import relativedelta

st.set_page_config(layout="wide")
st.title("🍔 隔壁早餐店 - 自動排班系統")

# --- 建立資料庫連線 ---
conn = st.connection("gsheets", type=GSheetsConnection)

# 定義所有夥伴與班別
full_time = ["權 (正)", "Popo(正)", "Ting(正)"]
part_time = ["柏吟(兼)", "Ping(兼)", "雅妍(兼)", "胖弟(兼)"]
all_employees = full_time + part_time
all_shifts = ["休", "6:30", "8:00", "10:30", "7:00", "9:30", "10:00"]

# --- 建立網頁頁籤 ---
tab1, tab2 = st.tabs(["🗓️ 第一步：夥伴畫休登記 (下拉多選)", "🤖 第二步：一鍵自動排班與微調"])

# ==========================================
# 頁籤一：畫休登記 (st.multiselect)
# ==========================================
with tab1:
    st.subheader("📝 夥伴不克上班多選登記")
    
    # --- 自動產生月份日期選項 ---
    # 預設顯示下個月
    next_month_date = datetime.date.today() + relativedelta(months=1)
    
    col_y, col_m = st.columns(2)
    with col_y:
        target_year = st.number_input("年份", min_value=2026, max_value=2030, value=next_month_date.year)
    with col_m:
        target_month = st.selectbox("欲排班月份", list(range(1, 13)), index=next_month_date.month - 1)
    
    # 計算該月天數
    if target_month == 12:
        num_days = 31
    else:
        num_days = (datetime.date(target_year, target_month + 1, 1) - datetime.date(target_year, target_month, 1)).days
        
    # 產生日期選單字串 (例如 "2026-06-01 (一)")
    weekday_mapping = ["一", "二", "三", "四", "五", "六", "日"]
    date_options = []
    for day in range(1, num_days + 1):
        d = datetime.date(target_year, target_month, day)
        w = weekday_mapping[d.weekday()]
        date_options.append(f"{d.strftime('%Y-%m-%d')} ({w})")

    # --- 畫休輸入表單 ---
    with st.form("multiselect_leave_form"):
        selected_emp = st.selectbox("選擇你的名字", all_employees)
        selected_dates = st.multiselect("選擇你【不克上班】的日期 (可多選)", date_options)
        
        submitted = st.form_submit_button("確認送出登記")
        
        if submitted:
            if not selected_dates:
                st.warning("⚠️ 請至少選擇一個日期再送出！")
            else:
                # 讀取現有的休假紀錄
                try:
                    leave_df = conn.read(worksheet="休假紀錄", ttl=0).dropna(how="all")
                except:
                    leave_df = pd.DataFrame(columns=["員工姓名", "休假日期"])
                
                # 提取出純日期字串 (去除後面的星期幾備註)
                cleaned_dates = [d.split(" ")[0] for d in selected_dates]
                
                # 準備要寫入的新資料，並自動過濾掉重複登記的日期
                new_rows = []
                for d_str in cleaned_dates:
                    is_duplicate = ((leave_df["員工姓名"] == selected_emp) & (leave_df["休假日期"] == d_str)).any()
                    if not is_duplicate:
                        new_rows.append({"員工姓名": selected_emp, "休假日期": d_str})
                
                if new_rows:
                    new_df = pd.DataFrame(new_rows)
                    updated_df = pd.concat([leave_df, new_df], ignore_index=True)
                    conn.update(worksheet="休假紀錄", data=updated_df)
                    st.success(f"✅ 成功！已幫 【{selected_emp}】 新增 {len(new_rows)} 筆不克上班紀錄。")
                else:
                    st.info(" 選擇的日期先前都已經登記過了，未重複新增。")

    st.divider()
    st.subheader("📋 目前雲端已登記的休假總清單")
    try:
        current_leaves = conn.read(worksheet="休假紀錄", ttl=0).dropna(how="all")
        if not current_leaves.empty:
            # 排序讓表格更美觀
            current_leaves = current_leaves.sort_values(by=["員工姓名", "休假日期"])
        st.dataframe(current_leaves, use_container_width=True, hide_index=True)
    except:
        st.info("目前還沒有任何人登記劃休。")

# ==========================================
# 頁籤二：最終班表微調 (保持不變)
# ==========================================
with tab2:
    st.subheader("✨ 智慧自動排班系統")
    st.write("系統將會根據【頁籤一】的休假紀錄，自動分配平日與假日的人力需求。")
    
    if st.button("🤖 開始依規則自動排班"):
        st.info("排班大腦準備就緒，等待下一步邏輯注入...")
        
    st.divider()
    st.subheader("📋 本月最終班表總表 (老闆微調專用)")
    
    try:
        schedule_df = conn.read(worksheet="最終班表", ttl=0)
        schedule_df = schedule_df.dropna(how="all").fillna("")
        schedule_df.set_index(schedule_df.columns[0], inplace=True)
        
        schedule_configs = {
            str(col): st.column_config.SelectboxColumn(str(col), options=all_shifts) 
            for col in schedule_df.columns
        }
        
        edited_schedule_df = st.data_editor(
            schedule_df,
            column_config=schedule_configs,
            use_container_width=True,
            key="schedule_editor"
        )
        
        if st.button("💾 儲存微調後的最終班表"):
            save_schedule_df = edited_schedule_df.reset_index()
            conn.update(worksheet="最終班表", data=save_schedule_df)
            st.success("✅ 最終班表已成功儲存！")
    except Exception as e:
        st.error(f"讀取『最終班表』失敗：{e}")
