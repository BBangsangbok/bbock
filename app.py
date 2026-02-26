import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from models.member import KitchenMember
from logic.scheduler import generate_best_schedules, DAYS
st.write("시크릿 파일 로드 확인:", st.secrets.has_key("connections"))
worksheet="시트1"
st.set_page_config(page_title="주방 일정 조합기", layout="wide")

# ==========================================
# 구글 시트 연동 및 데이터 불러오기
# ==========================================
# 구글 시트 연결 객체 생성
conn = st.connection("gsheets", type=GSheetsConnection)

# 시트에서 데이터 읽어오기 (캐시를 쓰지 않고 항상 최신 데이터를 가져옴)
try:
    existing_data = conn.read(worksheet=worksheet, ttl=0) 
    # 빈 행(빈 이름) 제거
    existing_data = existing_data.dropna(subset=['이름']) 
except Exception as e:
    # 최초 실행이거나 시트가 비어있을 경우 대비
    existing_data = pd.DataFrame(columns=["이름", "최고 역량", "설거지 가능여부", "역량 점수"])

# 시트 데이터를 객체 리스트로 변환하여 세션 상태에 저장
st.session_state.members = [KitchenMember.from_dict(row) for _, row in existing_data.iterrows()]

def update_google_sheet():
    """현재 session_state의 멤버 목록을 구글 시트에 덮어씁니다."""
    if st.session_state.members:
        df_to_save = pd.DataFrame([m.to_dict() for m in st.session_state.members])
    else:
        # 멤버가 한 명도 없을 때를 대비한 빈 뼈대
        df_to_save = pd.DataFrame(columns=["이름", "최고 역량", "설거지 가능여부", "역량 점수"])
    conn.update(worksheet=worksheet, data=df_to_save) # 시트 이름 일치 주의


st.subheader("🍳 주방 일정 조합 생성 서비스")

tab1, tab2 = st.tabs(["👥 주방 멤버 관리", "📅 일정 산출 창"])

# ==========================================
# 탭 1: 멤버 관리
# ==========================================
with tab1:
    st.header("주방 멤버 역량 관리")
    
    with st.form("add_member_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            name_input = st.text_input("멤버 이름")
        with col2:
            role_input = st.selectbox("최고 역량", ["서브", "면말이", "메인", "발주"])
        with col3:
            dishwash_input = st.checkbox("설거지 역량 보유 여부 (독립 역량)")
            
        submit_btn = st.form_submit_button("멤버 추가")
        
        if submit_btn and name_input:
            if any(m.name == name_input for m in st.session_state.members):
                st.error("이미 존재하는 이름입니다.")
            else:
                new_member = KitchenMember(name_input, role_input, dishwash_input)
                st.session_state.members.append(new_member)
                
                # 구글 시트에 업데이트 반영
                update_google_sheet()
                
                st.success(f"'{name_input}' 멤버가 추가되었습니다. (구글 시트 저장 완료)")
                st.rerun()

    st.subheader("현재 등록된 멤버 (Google Sheets 연동 중)")
    if st.session_state.members:
        df = pd.DataFrame([m.to_dict() for m in st.session_state.members])
        st.dataframe(df, use_container_width=True)
        
        delete_name = st.selectbox("삭제할 멤버 선택", [m.name for m in st.session_state.members])
        if st.button("해당 멤버 삭제", type="primary"):
            st.session_state.members = [m for m in st.session_state.members if m.name != delete_name]
            
            # 구글 시트에 업데이트 반영 (삭제된 상태로 덮어쓰기)
            update_google_sheet()
            
            st.success("멤버가 삭제되었습니다.")
            st.rerun()
    else:
        st.info("등록된 멤버가 없습니다.")

# ==========================================
# 탭 2: 일정 산출 (기존과 동일하므로 핵심 구조만 유지)
# ==========================================
with tab2:
    st.header("주간 일정 산출 조건 설정")
    
    if len(st.session_state.members) < 4:
        st.warning("일정을 산출하려면 최소 4명 이상의 멤버가 필요합니다.")
    else:
        col_left, col_right = st.columns([1, 1])
        
        with col_left:
            st.subheader("멤버별 희망 휴일 지정")
            off_days_dict = {}
            for member in st.session_state.members:
                selected_days = st.multiselect(
                    f"{member.name} 님의 휴일", 
                    options=range(7), 
                    format_func=lambda x: f"{DAYS[x]}요일",
                    key=f"off_{member.name}",
                    placeholder="상관없음"
                )
                off_days_dict[member.name] = selected_days
                
        with col_right:
            st.subheader("특별 일정 지정")
            
            # ✨ 새로 추가된 공휴일 기능
            st.write("이번 주 평일 중 공휴일이 있나요?")
            st.caption("공휴일은 주말과 동일하게 기본 4명이 투입됩니다.")
            public_holidays = st.multiselect(
                "공휴일 선택 (평일)", 
                options=range(5), # 0(월) ~ 4(금)까지만 선택 가능하게 제한
                format_func=lambda x: f"{DAYS[x]}요일",
                placeholder="없음"
            )
            
            st.write("") # 약간의 여백
            
            st.write("설거지 이모 부재일 지정")
            st.caption("체크된 요일은 주방 멤버가 1명 더 투입됩니다.")
            no_dishwasher_days = st.multiselect(
                "설거지 이모가 못 오시는 날", 
                options=range(7), 
                format_func=lambda x: f"{DAYS[x]}요일",
                placeholder="없음"
            )
            
        st.divider()
        
        if st.button("🚀 일정 추천 5개 산출하기", type="primary", use_container_width=True):
            with st.spinner('멤버별 목표 근무 횟수를 맞춘 최적의 일정을 탐색 중입니다...'):
                # ✨ public_holidays 파라미터가 추가되었습니다!
                success, message, schedules = generate_best_schedules(
                    st.session_state.members, 
                    off_days_dict, 
                    no_dishwasher_days,
                    public_holidays, 
                    top_n=5
                )
                
                if not success:
                    st.error(message) 
                else:
                    st.success(f"🎉 산출 완료! (월차 자동 반영, 역량 분산 최소화 상위 {len(schedules)}개)")
                    if message != "성공":
                        st.info(f"💡 {message}")
                    
                    tabs = st.tabs([f"추천 {i+1}" for i in range(len(schedules))])
                    
                    for i, (tab, schedule) in enumerate(zip(tabs, schedules)):
                        with tab:
                            # 1. 스케줄 표
                            schedule_data = []
                            for j, team in enumerate(schedule):
                                team_names = ", ".join([m.name for m in team])
                                schedule_data.append({"요일": f"{DAYS[j]}요일", "투입 멤버": team_names, "투입 인원": f"{len(team)}명"})
                                
                            result_df = pd.DataFrame(schedule_data)
                            st.table(result_df)
                            # 1. 한눈에 보기 쉬운 멤버-요일별 스케줄 표 (Grid 형식)
                            grid_data = {}
                            for member in st.session_state.members:
                                row_data = []
                                for j in range(7):
                                    # 해당 멤버가 j번째 요일에 투입되는지 확인
                                    is_working = any(m.name == member.name for m in schedule[j])
                                    row_data.append("⭕" if is_working else "")
                                grid_data[member.name] = row_data
                            
                            # 빨간날(주말/공휴일) 인덱스 모음
                            red_days = set([5, 6] + public_holidays)
                            
                            # 열 이름 생성 (빨간날은 앞에 🔴 이모지 추가)
                            col_names = [f"🔴 {DAYS[i]}" if i in red_days else f"{DAYS[i]}" for i in range(7)]
                            
                            grid_df = pd.DataFrame.from_dict(grid_data, orient='index', columns=col_names)
                            
                            # 데이터프레임 스타일링 (빨간날 열의 ⭕ 기호를 빨간색으로, 평일은 기본색으로)
                            def highlight_red_days(col):
                                if "🔴" in col.name:
                                    return ['color: #ff4b4b; font-weight: bold' if v == '⭕' else '' for v in col]
                                return ['font-weight: bold' if v == '⭕' else '' for v in col]
                                
                            styled_grid = grid_df.style.apply(highlight_red_days, axis=0)
                            
                            st.markdown("##### 📅 주간 투입 현황표")
                            st.dataframe(styled_grid, use_container_width=True)
                            
                            st.write("") # 여백