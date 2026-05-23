import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import datetime
from dateutil.relativedelta import relativedelta
import random

st.set_page_config(layout="wide")
st.title("🍔 隔壁早餐店 - 自動排班系統")

# --- 1. 建立資料庫連線 ---
conn = st.connection("gsheets", type=GSheetsConnection)

# 固定 7 位夥伴名單
full_time = ["權 (正)", "Popo(正)", "Ting(正)"]
part_time = ["柏吟(兼)", "Ping(兼)", "雅妍(兼)", "胖弟(兼)"]
all_employees = full_time + part_time

# 恢復乾淨的純文字班別
all_shifts = ["休", "6:30", "8:00", "10:30", "7:00", "9:30", "10:00"]
weekday_shifts = ["6:30", "8:00", "10:30"] 
weekend_shifts = ["7:00", "8:00", "8:00", "9:30", "10:00"]

# --- 2. 建立網頁頁籤 ---
tab1, tab2 = st.tabs(["🗓️ 第一步：夥伴畫休登記", "🤖 第二步：一鍵自動排班與微調"])

# ==========================================
# 頁籤一：夥伴畫休登記 (保持不變)
# ==========================================
with tab1:
    st.subheader("📝 所有人畫休調整")
    next_month_date = datetime.date.today() + relativedelta(months=1)
    
    col_y, col_m = st.columns(2)
    with col_y:
        target_year = st.number_input("年份", min_value=2026, max_value=2030, value=next_month_date.year)
    with col_m:
        target_month = st.selectbox("欲排班月份", list(range(1, 13)), index=next_month_date.month - 1)
    
    num_days = 31 if target_month == 12 else (datetime.date(target_year, target_month + 1, 1) - datetime.date(target_year, target_month, 1)).days
        
    weekday_mapping = ["一", "二", "三", "四", "五", "六", "日"]
    date_options = []
    date_to_option_map = {} 
    for day in range(1, num_days + 1):
        d = datetime.date(target_year, target_month, day)
        w = weekday_mapping[d.weekday()]
        opt_str = f"{d.strftime('%Y-%m-%d')} ({w})"
        date_options.append(opt_str)
        date_to_option_map[d.strftime('%Y-%m-%d')] = opt_str

    try:
        leave_df = conn.read(worksheet="休假紀錄", ttl=0).dropna(how="all")
        leave_df["休假日期"] = leave_df["休假日期"].astype(str)
    except:
        leave_df = pd.DataFrame(columns=["員工姓名", "休假日期"])

    st.write("---")
    current_selections = {}
    for emp in all_employees:
        emp_saved_leaves = leave_df[leave_df["員工姓名"] == emp]["休假日期"].tolist()
        default_vals = [date_to_option_map[d] for d in emp_saved_leaves if d in date_to_option_map]
        selected = st.multiselect(f"👤 {emp} 的不克上班日期", options=date_options, default=default_vals, key=f"leave_{emp}")
        current_selections[emp] = [s.split(" ")[0] for s in selected]

    st.write("---")
    if st.button("💾 統一儲存所有人畫休", type="primary"):
        prefix = f"{target_year}-{target_month:02d}-"
        other_months_df = leave_df[~leave_df["休假日期"].str.startswith(prefix)]
        
        new_rows = []
        for emp, dates in current_selections.items():
            for d_str in dates:
                new_rows.append({"員工姓名": emp, "休假日期": d_str})
        current_month_df = pd.DataFrame(new_rows, columns=["員工姓名", "休假日期"])
        
        updated_df = pd.concat([other_months_df, current_month_df], ignore_index=True)
        if updated_df.empty:
            updated_df = pd.DataFrame(columns=["員工姓名", "休假日期"])
        conn.update(worksheet="休假紀錄", data=updated_df)
        st.success("✅ 所有人畫休紀錄已成功同步至雲端！")
        st.rerun()

    st.divider()
    st.subheader("📋 本月已登記畫休總表")
    try:
        prefix = f"{target_year}-{target_month:02d}-"
        display_df = leave_df[leave_df["休假日期"].str.startswith(prefix)].copy()
        if not display_df.empty:
            display_df["MM-DD"] = display_df["休假日期"].apply(lambda x: x.split("-")[1] + "-" + x.split("-")[2])
            summary_df = display_df.groupby("員工姓名")["MM-DD"].apply(lambda x: " / ".join(sorted(x))).reset_index()
            summary_df.columns = ["夥伴姓名", "不克上班日期 (月-日)"]
            st.dataframe(summary_df, use_container_width=True, hide_index=True)
        else:
            st.info("本月份目前沒有任何人畫休。")
    except:
        st.info("目前沒有任何人畫休。")


# ==========================================
# 頁籤二：核心大腦 - 自動排班與精美色彩表
# ==========================================
with tab2:
    st.subheader("✨ 智慧自動排班系統")
    st.write(f"系統將針對 **{target_year} 年 {target_month} 月** 進行自動排班。")
    
    if st.button("🤖 開始依規則自動排班", type="primary"):
        with st.spinner("排班大腦運算中..."):
            schedule_result = {emp: ["休"] * num_days for emp in all_employees}
            consecutive_days = {emp: 0 for emp in all_employees}
            prefix = f"{target_year}-{target_month:02d}-"
            this_month_leaves = leave_df[leave_df["休假日期"].str.startswith(prefix)]
            
            for day_idx in range(num_days):
                current_date = datetime.date(target_year, target_month, day_idx + 1)
                date_str = current_date.strftime("%Y-%m-%d")
                is_weekend = current_date.weekday() >= 5
                
                unavailable = this_month_leaves[this_month_leaves["休假日期"] == date_str]["員工姓名"].tolist()
                
                if not is_weekend and "雅妍(兼)" not in unavailable:
                    unavailable.append("雅妍(兼)")
                
                for emp in all_employees:
                    if consecutive_days[emp] >= 6 and emp not in unavailable:
                        unavailable.append(emp)

                available_ft = [e for e in full_time if e not in unavailable]
                available_pt = [e for e in part_time if e not in unavailable]
                
                random.shuffle(available_ft)
                random.shuffle(available_pt)
                
                shifts_to_assign = []
                assigned_today = []
                
                if not is_weekend:
                    assigned_today = available_ft[:2] + available_pt[:1]
                    shifts_to_assign = weekday_shifts.copy()
                    if len(available_ft) < 2 or len(available_pt) < 1:
                        st.warning(f"⚠️ {date_str} 平日人手不足！")
                else:
                    all_available = available_ft + available_pt
                    assigned_today = all_available[:5]
                    shifts_to_assign = weekend_shifts.copy()
                    if len(all_available) < 5:
                        st.warning(f"⚠️ {date_str} 假日人手不足！")

                random.shuffle(shifts_to_assign)
                for i, emp in enumerate(assigned_today):
                    schedule_result[emp][day_idx] = shifts_to_assign[i]
                    consecutive_days[emp] += 1
                
                for emp in all_employees:
                    if emp not in assigned_today:
                        consecutive_days[emp] = 0

            final_df = pd.DataFrame(schedule_result).T
            final_df.columns = [str(i) for i in range(1, num_days + 1)]
            final_df.insert(0, "夥伴 \ 日期", final_df.index)
            
            conn.update(worksheet="最終班表", data=final_df)
            st.success("🎉 排班運算完成！")
            st.rerun()

    st.divider()
    
    # --- 關鍵：彩色顯示與微調介面 ---
    try:
        schedule_df = conn.read(worksheet="最終班表", ttl=0)
        schedule_df = schedule_df.dropna(how="all").fillna("休")
        schedule_df.set_index(schedule_df.columns[0], inplace=True)
        
        # 1. 定義顏色函數
        def style_cells(val):
            if val == "休":
                return "background-color: #FFD2D2; color: #D60000; font-weight: bold;"
            elif val == "6:30":
                return "background-color: #D2E9FF; color: #005EA6;"
            elif val == "8:00":
                return "background-color: #E1F5FE; color: #0288D1;"
            elif val == "10:30":
                return "background-color: #FFF3CD; color: #856404;"
            elif val == "7:00":
                return "background-color: #E8D2FF; color: #6F00D2;"
            elif val == "9:30":
                return "background-color: #FFE4CA; color: #A65100;"
            elif val == "10:00":
                return "background-color: #E2F0D9; color: #385623;"
            return ""

        is_edit_mode = st.checkbox("✍️ 開啟【手動微調模式】（會暫時拔除顏色，允許下拉修改）")

        if not is_edit_mode:
            # 【預覽模式】：動態加上星期幾
            display_df = schedule_df.copy()
            new_columns = []
            for col in display_df.columns:
                if str(col).isdigit(): # 確認是數字日期
                    day_int = int(col)
                    # 防呆：確保日期沒有超過該月總天數 (例如 6月沒有 31號)
                    if day_int <= num_days:
                        d = datetime.date(target_year, target_month, day_int)
                        w = weekday_mapping[d.weekday()]
                        new_columns.append(f"{col} ({w})")
                    else:
                        new_columns.append(str(col)) # 超出的天數保持原樣
                else:
                    new_columns.append(str(col))
            display_df.columns = new_columns # 套用新標題
            
            st.subheader("📋 本月班表總表（彩色預覽）")
            styled_df = display_df.style.map(style_cells)
            st.dataframe(styled_df, use_container_width=True, height=350)
            
        else:
            # 【編輯模式】：利用 column_config 的 label 屬性，只改顯示名稱不改底層資料
            st.subheader("🛠️ 班表微調中...")
            schedule_configs = {}
            for col in schedule_df.columns:
                if str(col).isdigit():
                    day_int = int(col)
                    if day_int <= num_days:
                        d = datetime.date(target_year, target_month, day_int)
                        w = weekday_mapping[d.weekday()]
                        display_label = f"{col} ({w})" # 顯示為 1 (一)
                    else:
                        display_label = str(col)
                    # 設定下拉選單，並套用新的顯示名稱
                    schedule_configs[str(col)] = st.column_config.SelectboxColumn(
                        label=display_label, 
                        options=all_shifts
                    )
            
            edited_schedule_df = st.data_editor(
                schedule_df,
                column_config=schedule_configs,
                use_container_width=True,
                key="schedule_editor",
                height=300
            )
            
            if st.button("💾 儲存微調後的最終班表", type="primary"):
                save_schedule_df = edited_schedule_df.reset_index()
                # 存檔時，底層依然是乾淨的 1, 2, 3，不會把星期幾寫進資料庫！
                conn.update(worksheet="最終班表", data=save_schedule_df)
                st.success("✅ 最終班表已成功儲存！")
                st.rerun()
                
    except Exception as e:
        st.info("目前還沒有排班資料，請點擊上方按鈕開始自動排班。")
