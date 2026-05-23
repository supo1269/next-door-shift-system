import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import datetime
from dateutil.relativedelta import relativedelta

st.set_page_config(layout="wide")
st.title("🍔 隔壁早餐店 - 自動排班系統")

# --- 1. 建立資料庫連線 ---
conn = st.connection("gsheets", type=GSheetsConnection)

# 固定 7 位夥伴名單
full_time = ["權 (正)", "Popo(正)", "Ting(正)"]
part_time = ["柏吟(兼)", "Ping(兼)", "雅妍(兼)", "胖弟(兼)"]
all_employees = full_time + part_time
all_shifts = ["休", "6:30", "8:00", "10:30", "7:00", "9:30", "10:00"]

# --- 2. 建立網頁頁籤 ---
tab1, tab2 = st.tabs(["🗓️ 第一步：夥伴畫休登記", "🤖 第二步：一鍵自動排班與微調"])

# ==========================================
# 頁籤一：所有人同時畫休登記
# ==========================================
with tab1:
    st.subheader("📝 所有人畫休調整")
    st.write("👉 **操作說明：** 點擊框框可新增日期；點擊已選日期旁的 **✕** 即可刪除。調整完畢後請務必點擊最下方的【統一儲存】按鈕。")

    # --- 自動產生月份日期選項 ---
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
        
    # 產生日期選單選項，同時建立對應字典
    weekday_mapping = ["一", "二", "三", "四", "五", "六", "日"]
    date_options = []
    date_to_option_map = {} 
    for day in range(1, num_days + 1):
        d = datetime.date(target_year, target_month, day)
        w = weekday_mapping[d.weekday()]
        opt_str = f"{d.strftime('%Y-%m-%d')} ({w})"
        date_options.append(opt_str)
        date_to_option_map[d.strftime('%Y-%m-%d')] = opt_str

    # --- 讀取現有休假紀錄 ---
    try:
        leave_df = conn.read(worksheet="休假紀錄", ttl=0).dropna(how="all")
        leave_df["休假日期"] = leave_df["休假日期"].astype(str)
    except:
        leave_df = pd.DataFrame(columns=["員工姓名", "休假日期"])

    # --- 渲染 7 位夥伴的獨立下拉選單 ---
    st.write("---")
    current_selections = {}
    
    # 這裡會直接把 7 個人排成一個清單列表
    for emp in all_employees:
        # 找出該員工在資料庫中，屬於「目前選擇月份」的既有休假日期
        emp_saved_leaves = leave_df[leave_df["員工姓名"] == emp]["休假日期"].tolist()
        
        # 將資料庫的 YYYY-MM-DD 轉回選單認識的 "YYYY-MM-DD (星期)" 格式，當作預設值 (Default)
        default_vals = [date_to_option_map[d] for d in emp_saved_leaves if d in date_to_option_map]
        
        # 產生多選欄位
        selected = st.multiselect(
            f"👤 {emp} 的不克上班日期", 
            options=date_options, 
            default=default_vals, 
            key=f"leave_{emp}"
        )
        # 收集拿掉星期備註後的純日期字串
        current_selections[emp] = [s.split(" ")[0] for s in selected]

    # --- 統一儲存按鈕 ---
    st.write("---")
    if st.button("💾 統一儲存所有人畫休", type="primary"):
        # 為了避免動到「其他月份」的請假紀錄，先保留非本月設定的資料
        prefix = f"{target_year}-{target_month:02d}-"
        other_months_df = leave_df[~leave_df["休假日期"].str.startswith(prefix)]
        
        # 組合本月新調整的資料
        new_rows = []
        for emp, dates in current_selections.items():
            for d_str in dates:
                new_rows.append({"員工姓名": emp, "休假日期": d_str})
        current_month_df = pd.DataFrame(new_rows)
        
        # 合併並覆寫回雲端
        updated_df = pd.concat([other_months_df, current_month_df], ignore_index=True)
        conn.update(worksheet="休假紀錄", data=updated_df)
        st.success("✅ 所有人畫休紀錄已成功同步至雲端！")
        st.rerun() # 重新整理網頁，更新下方的總清單

    # ==========================================
    # 精簡版：已登記的休假總清單 (一人一行)
    # ==========================================
    st.divider()
    st.subheader("📋 本月已登記畫休總表")
    
    try:
        # 過濾出當前月份的資料
        prefix = f"{target_year}-{target_month:02d}-"
        display_df = leave_df[leave_df["休假日期"].str.startswith(prefix)].copy()
        
        if not display_df.empty:
            # 將 YYYY-MM-DD 轉換成 MM-DD 格式
            display_df["MM-DD"] = display_df["休假日期"].apply(lambda x: x.split("-")[1] + "-" + x.split("-")[2])
            
            # 關鍵：依員工姓名分組，並將日期用 " / " 串接起來
            summary_df = display_df.groupby("員工姓名")["MM-DD"].apply(lambda x: " / ".join(sorted(x))).reset_index()
            summary_df.columns = ["夥伴姓名", "不克上班日期 (月-日)"]
            
            # 顯示漂亮的一行行表格
            st.dataframe(summary_df, use_container_width=True, hide_index=True)
        else:
            st.info("本月份目前沒有任何人畫休。")
    except Exception as e:
        st.info("目前沒有任何人畫休。")

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
