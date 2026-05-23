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

# 定義所有夥伴與班別 (加上顏色標籤)
full_time = ["權 (正)", "Popo(正)", "Ting(正)"]
part_time = ["柏吟(兼)", "Ping(兼)", "雅妍(兼)", "胖弟(兼)"]
all_employees = full_time + part_time

# 給每個班別一個專屬顏色！
all_shifts = ["🔴 休", "🔵 6:30", "🟢 8:00", "🟡 10:30", "🟣 7:00", "🟠 9:30", "🟤 10:00"]

# 定義每日需求與班別
weekday_shifts = ["🔵 6:30", "🟢 8:00", "🟡 10:30"] # 平日需 3 人 
weekend_shifts = ["🟣 7:00", "🟢 8:00", "🟢 8:00", "🟠 9:30", "🟤 10:00"] # 假日需 5 人

tab1, tab2 = st.tabs(["🗓️ 第一步：夥伴畫休登記", "🤖 第二步：一鍵自動排班與微調"])

# ==========================================
# 頁籤一：畫休登記 (與先前相同，省略部分重複註解)
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
        current_month_df = pd.DataFrame(new_rows)
        
        updated_df = pd.concat([other_months_df, current_month_df], ignore_index=True)
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
# 頁籤二：核心大腦 - 自動排班與微調
# ==========================================
with tab2:
    st.subheader("✨ 智慧自動排班系統")
    st.write(f"系統將針對 **{target_year} 年 {target_month} 月** 進行自動排班運算。")
    
    if st.button("🤖 開始依規則自動排班", type="primary"):
        with st.spinner("排班大腦運算中..."):
            
            # --- 建立空的排班總表字典 ---
            schedule_result = {emp: ["🔴 休"] * num_days for emp in all_employees}
            
            # 追蹤每個人連續上班的天數
            consecutive_days = {emp: 0 for emp in all_employees}

            # 抓取本月畫休名單
            prefix = f"{target_year}-{target_month:02d}-"
            this_month_leaves = leave_df[leave_df["休假日期"].str.startswith(prefix)]
            
            # 每天逐一排班
            for day_idx in range(num_days):
                current_date = datetime.date(target_year, target_month, day_idx + 1)
                date_str = current_date.strftime("%Y-%m-%d")
                is_weekend = current_date.weekday() >= 5
                
                # 1. 找出今天不能上班的人 (包含畫休，以及連上6天的人)
                unavailable = this_month_leaves[this_month_leaves["休假日期"] == date_str]["員工姓名"].tolist()
                
                # 規則：雅妍只有六日要上班 (平日強制設為不可上班)
                if not is_weekend and "雅妍(兼)" not in unavailable:
                    unavailable.append("雅妍(兼)")
                
                # 規則：不能連上超過 6 天 (若前一天上滿 6 天，今天強制休假)
                for emp in all_employees:
                    if consecutive_days[emp] >= 6 and emp not in unavailable:
                        unavailable.append(emp)

                # 2. 篩選出今天「可以上班」的正職與兼職
                available_ft = [e for e in full_time if e not in unavailable]
                available_pt = [e for e in part_time if e not in unavailable]
                
                # 隨機打亂順序，避免每次都排到同一個人
                random.shuffle(available_ft)
                random.shuffle(available_pt)
                
                # 準備發派的班別
                shifts_to_assign = []
                assigned_today = []
                
                # 3. 依照平假日規則發派班別
                if not is_weekend:
                    # 平日需求：2 正職 + 1 兼職
                    if len(available_ft) >= 2 and len(available_pt) >= 1:
                        assigned_today = available_ft[:2] + available_pt[:1]
                        shifts_to_assign = weekday_shifts.copy()
                    else:
                        st.warning(f"⚠️ {date_str} 平日人手不足！(需要 2正1兼，目前只有 {len(available_ft)}正 {len(available_pt)}兼)")
                else:
                    # 假日需求：5 人 (不限正兼，先抓正職再抓兼職)
                    all_available = available_ft + available_pt
                    if len(all_available) >= 5:
                        assigned_today = all_available[:5]
                        shifts_to_assign = weekend_shifts.copy()
                    else:
                        st.warning(f"⚠️ {date_str} 假日人手不足！(需要 5 人，目前只有 {len(all_available)} 人)")

                # 4. 把班別填入結果，並更新連續上班天數
                random.shuffle(shifts_to_assign) # 隨機分配班別時間
                for i, emp in enumerate(assigned_today):
                    schedule_result[emp][day_idx] = shifts_to_assign[i]
                    consecutive_days[emp] += 1
                
                # 沒被排到班的人，連續上班天數歸零
                for emp in all_employees:
                    if emp not in assigned_today:
                        consecutive_days[emp] = 0

            # --- 整理運算結果並存回雲端 ---
            final_df = pd.DataFrame(schedule_result).T
            # 將欄位名稱設為 1, 2, 3...
            final_df.columns = [str(i) for i in range(1, num_days + 1)]
            # 加入夥伴姓名作為第一欄
            final_df.insert(0, "夥伴 \ 日期", final_df.index)
            
            # 更新雲端
            conn.update(worksheet="最終班表", data=final_df)
            st.success("🎉 排班運算完成！結果已存入下方總表。")
            st.rerun()

    st.divider()
    st.subheader("📋 本月最終班表總表 (可手動微調)")
    
    try:
        schedule_df = conn.read(worksheet="最終班表", ttl=0)
        schedule_df = schedule_df.dropna(how="all").fillna("🔴 休")
        schedule_df.set_index(schedule_df.columns[0], inplace=True)
        
        schedule_configs = {
            str(col): st.column_config.SelectboxColumn(str(col), options=all_shifts) 
            for col in schedule_df.columns
        }
        
        edited_schedule_df = st.data_editor(
            schedule_df,
            column_config=schedule_configs,
            use_container_width=True,
            key="schedule_editor",
            height=300
        )
        
        if st.button("💾 儲存微調後的最終班表"):
            save_schedule_df = edited_schedule_df.reset_index()
            conn.update(worksheet="最終班表", data=save_schedule_df)
            st.success("✅ 最終班表已成功儲存！")
    except Exception as e:
        st.info("目前還沒有排班資料，請點擊上方按鈕開始自動排班。")
