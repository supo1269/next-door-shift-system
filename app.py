import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import datetime
from dateutil.relativedelta import relativedelta
import random

st.set_page_config(layout="wide")
st.title("🍔 隔壁早餐店 - 智慧排班管理系統")

conn = st.connection("gsheets", type=GSheetsConnection)

# 定義員工與班別
full_time = ["權 (正)", "Popo(正)", "Ting(正)"]
part_time = ["柏吟(兼)", "Ping(兼)", "雅妍(兼)", "胖弟(兼)"]
all_employees = full_time + part_time
all_shifts = ["休", "6:30", "8:00", "10:30", "7:00", "9:30", "10:00"]
weekday_shifts = ["6:30", "8:00", "10:30"] 
weekend_shifts = ["7:00", "8:00", "8:00", "9:30", "10:00"]
weekday_mapping = ["一", "二", "三", "四", "五", "六", "日"]

# 限制不上最早班的人員名單
early_shift_restricted_staff = ["Ping(兼)", "雅妍(兼)"]

tab1, tab2 = st.tabs(["📝 夥伴畫休登記", "🤖 排班與歷史紀錄管理"])

# --- 頁籤 1: 畫休登記 ---
with tab1:
    st.subheader("📝 所有人畫休調整")
    next_month_date = datetime.date.today() + relativedelta(months=1)
    target_year = st.number_input("年份", value=next_month_date.year)
    target_month = st.selectbox("欲登記月份", list(range(1, 13)), index=next_month_date.month - 1)
    
    # 產生月份天數
    if target_month == 12: num_days = 31
    else: num_days = (datetime.date(target_year, target_month + 1, 1) - datetime.date(target_year, target_month, 1)).days
        
    date_options = [f"{datetime.date(target_year, target_month, d).strftime('%Y-%m-%d')} ({weekday_mapping[datetime.date(target_year, target_month, d).weekday()]})" for d in range(1, num_days + 1)]
    date_to_option_map = {d.strftime('%Y-%m-%d'): f"{d.strftime('%Y-%m-%d')} ({weekday_mapping[d.weekday()]})" for d in [datetime.date(target_year, target_month, d) for d in range(1, num_days+1)]}

    try:
        leave_df = conn.read(worksheet="休假紀錄", ttl=0).dropna(how="all")
        leave_df["休假日期"] = leave_df["休假日期"].astype(str)
    except: leave_df = pd.DataFrame(columns=["員工姓名", "休假日期"])

    current_selections = {}
    for emp in all_employees:
        emp_saved = leave_df[leave_df["員工姓名"] == emp]["休假日期"].tolist()
        default = [date_to_option_map[d] for d in emp_saved if d in date_to_option_map]
        selected = st.multiselect(f"👤 {emp} 的不克上班日期", options=date_options, default=default)
        current_selections[emp] = [s.split(" ")[0] for s in selected]

    if st.button("💾 統一儲存所有人畫休", type="primary"):
        prefix = f"{target_year}-{target_month:02d}-"
        updated_df = pd.concat([leave_df[~leave_df["休假日期"].str.startswith(prefix)], 
                               pd.DataFrame([{"員工姓名": e, "休假日期": d} for e, dates in current_selections.items() for d in dates], columns=["員工姓名", "休假日期"])], ignore_index=True)
        conn.update(worksheet="休假紀錄", data=updated_df)
        st.success("✅ 畫休紀錄已儲存！")
        st.rerun()

# --- 頁籤 2: 排班與查詢 ---
with tab2:
    st.subheader("📅 排班操作與歷史查詢")
    
    # 排班大腦
    if st.button("🤖 產生並儲存該月班表", type="primary"):
        sheet_name = f"{target_year}-{target_month:02d}"
        schedule_result = {emp: ["休"] * num_days for emp in all_employees}
        consecutive_days = {emp: 0 for emp in all_employees}
        this_month_leaves = leave_df[leave_df["休假日期"].str.startswith(f"{target_year}-{target_month:02d}-")]
        
        for d_idx in range(num_days):
            d_obj = datetime.date(target_year, target_month, d_idx + 1)
            date_str = d_obj.strftime("%Y-%m-%d")
            is_wknd = d_obj.weekday() >= 5
            
            unavail = this_month_leaves[this_month_leaves["休假日期"] == date_str]["員工姓名"].tolist()
            if not is_wknd and "雅妍(兼)" not in unavail: unavail.append("雅妍(兼)")
            for e in all_employees:
                if consecutive_days[e] >= 6 and e not in unavail: unavail.append(e)
            
            avail_ft = [e for e in full_time if e not in unavail]
            avail_pt = [e for e in part_time if e not in unavail]
            random.shuffle(avail_ft); random.shuffle(avail_pt)
            
            # 決定今日出勤名單與當日原始班別
            assigned = (avail_ft[:2] + avail_pt[:1]) if not is_wknd else (avail_ft + avail_pt)[:5]
            shifts = weekday_shifts.copy() if not is_wknd else weekend_shifts.copy()
            random.shuffle(shifts)
            shifts = shifts[:len(assigned)] # 確保人數不足時班別與人數一致
            
            # --- 【核心升級】：防呆指派（Ping、雅妍不上最早班） ---
            earliest_shift = "6:30" if not is_wknd else "7:00"
            assigned_shifts = {}
            
            # 分流：今日出勤人員中，誰「能上最早班」，誰「不能上最早班」
            unrestricted_pool = [e for e in assigned if e not in early_shift_restricted_staff]
            restricted_pool = [e for e in assigned if e in early_shift_restricted_staff]
            
            remaining_shifts = shifts.copy()
            early_shift_count = remaining_shifts.count(earliest_shift)
            
            # 優先把最早班塞給 unrestricted_pool (正職或其他兼職)
            for _ in range(early_shift_count):
                if unrestricted_pool and earliest_shift in remaining_shifts:
                    person = unrestricted_pool.pop(0)
                    assigned_shifts[person] = earliest_shift
                    remaining_shifts.remove(earliest_shift)
            
            # 剩下來的班別（非最早班）再與剩下的人（包含Ping、雅妍）混合隨機抽籤
            remaining_people = unrestricted_pool + restricted_pool
            random.shuffle(remaining_shifts)
            
            for person in remaining_people:
                assigned_shifts[person] = remaining_shifts.pop(0)
            
            # 將最終安全的排班結果寫入總表，並累計連續上班天數
            for e in assigned:
                schedule_result[e][d_idx] = assigned_shifts[e]
                consecutive_days[e] += 1
                
            for e in all_employees:
                if e not in assigned: consecutive_days[e] = 0
                
            # 人手不足警告提示
            if not is_wknd and (len(avail_ft) < 2 or len(avail_pt) < 1):
                st.warning(f"⚠️ {date_str} 平日人手不足！已盡力排班。")
            elif is_wknd and len(avail_ft) + len(avail_pt) < 5:
                st.warning(f"⚠️ {date_str} 假日人手不足！已盡力排班。")
        
        final_df = pd.DataFrame(schedule_result).T
        final_df.columns = [str(i) for i in range(1, num_days + 1)]
        final_df.insert(0, "夥伴 \ 日期", final_df.index)
        conn.update(worksheet=sheet_name, data=final_df)
        st.success(f"🎉 {sheet_name} 班表已成功存檔！")
        st.rerun()

    st.divider()
    v_year = st.number_input("查詢年份", value=target_year)
    v_month = st.selectbox("查詢月份", list(range(1, 13)), index=target_month - 1)
    view_sheet = f"{v_year}-{v_month:02d}"
    
    try:
        df = conn.read(worksheet=view_sheet, ttl=0).dropna(how="all").set_index("夥伴 \ 日期")
        
        def style_cells(val):
            colors = {"休": "#FFD2D2; color:#D60000; font-weight:bold;", "6:30": "#D2E9FF; color:#005EA6", 
                      "8:00": "#E1F5FE; color:#0288D1", "10:30": "#FFF3CD; color:#856404", 
                      "7:00": "#E8D2FF; color:#6F00D2", "9:30": "#FFE4CA; color:#A65100", 
                      "10:00": "#E2F0D9; color:#385623"}
            return f"background-color: {colors.get(val, '')}"

        if not st.checkbox("✍️ 開啟微調模式"):
            disp = df.copy()
            disp.columns = [f"{c} ({weekday_mapping[datetime.date(v_year, v_month, int(c)).weekday()]})" for c in disp.columns]
            st.subheader("📋 本月班表總表（彩色預覽）")
            st.dataframe(disp.style.map(style_cells), use_container_width=True, height=350)
        else:
            st.subheader("🛠️ 班表微調中...")
            cfg = {str(c): st.column_config.SelectboxColumn(f"{c} ({weekday_mapping[datetime.date(v_year, v_month, int(c)).weekday()]})", options=all_shifts) for c in df.columns}
            ed = st.data_editor(df, column_config=cfg, use_container_width=True)
            if st.button("💾 儲存微調結果", type="primary"):
                conn.update(worksheet=view_sheet, data=ed.reset_index())
                st.success("更新成功！")
                st.rerun()
    except: st.info(f"尚未建立 {view_sheet} 的班表。")
