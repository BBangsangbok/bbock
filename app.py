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
                            
                            # 2. 투입 횟수 검증 요약
                            st.caption("✅ 멤버별 주간 투입 횟수 검증")
                            
                            verification_data = {"멤버명": [], "목표 근무 횟수": [], "실제 배정 횟수": [], "비고": []}
                            for m in st.session_state.members:
                                off_count = len(off_days_dict.get(m.name, []))
                                target_count = 4 if off_count >= 3 else 5
                                actual_count = sum(1 for team in schedule if m in team)
                                
                                verification_data["멤버명"].append(m.name)
                                verification_data["목표 근무 횟수"].append(f"{target_count}회")
                                verification_data["실제 배정 횟수"].append(f"{actual_count}회")
                                verification_data["비고"].append("월차 적용 (휴일 3일 이상)" if target_count == 4 else "-")
                                    
                            count_df = pd.DataFrame(verification_data)
                            st.dataframe(count_df, hide_index=True, use_container_width=True)