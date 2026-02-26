import itertools
import numpy as np

DAYS = ["월", "화", "수", "목", "금", "토", "일"]

def get_valid_daily_teams(members, day_idx, off_days_dict, allowed_sizes):
    """지정된 여러 허용 인원수(allowed_sizes)에 맞춰 가능한 팀 조합을 모두 찾습니다."""
    available_members = [m for m in members if day_idx not in off_days_dict.get(m.name, [])]
    
    valid_teams = []
    for req_count in allowed_sizes:
        if len(available_members) < req_count:
            continue  # 가용 인원이 필요 인원보다 적으면 패스
            
        for team in itertools.combinations(available_members, req_count):
            main_capable_count = sum(1 for m in team if m.can_do("메인"))
            ordering_capable_count = sum(1 for m in team if m.can_do("발주"))
            
            if main_capable_count >= 2 and ordering_capable_count >= 1:
                valid_teams.append(team)
                
    return valid_teams

def generate_best_schedules(members, off_days_dict, no_dishwasher_days, top_n=5):
    """멤버별 목표 횟수를 기반으로, 자리가 남으면 인원을 추가 투입하여 일정을 산출합니다."""
    
    # 1. 멤버들의 총 목표 근무 횟수(공급) 계산
    target_shifts = {}
    for m in members:
        off_count = len(off_days_dict.get(m.name, []))
        target_shifts[m.name] = 4 if off_count >= 3 else 5
    total_supply = sum(target_shifts.values())

    # 2. 요일별 기본 필요 인원수(수요) 세팅
    base_reqs = []
    for i in range(7):
        is_weekend = i >= 5
        req = 4 if is_weekend else 3
        if i in no_dishwasher_days:
            req += 1
        base_reqs.append(req)
    total_base_demand = sum(base_reqs)

    # 3. 공급과 수요 비교 및 추가 인원 계산
    if total_supply < total_base_demand:
        return False, f"⚠️ **인력 부족**: 최소 필요 근무 자리({total_base_demand}자리)보다 멤버들의 총 투입 가능 횟수({total_supply}회)가 적어 산출이 불가능합니다. 휴일을 줄여주세요.", []

    extra_shifts = total_supply - total_base_demand
    
    # 남는 자리를 7일에 골고루 분배하기 위해 하루 최대 추가 가능 인원 계산 (기본 +1명)
    max_daily_extra = (extra_shifts + 6) // 7 if extra_shifts > 0 else 0
    max_reqs = [req + max_daily_extra for req in base_reqs]

    # 4. 요일별로 유동적인 사이즈의 조합 생성
    daily_candidates = []
    for i in range(7):
        # 기본 인원 ~ 최대 추가 인원까지의 범위를 허용
        allowed_sizes = range(base_reqs[i], max_reqs[i] + 1)
        teams = get_valid_daily_teams(members, i, off_days_dict, allowed_sizes)
        if not teams:
            return False, f"⚠️ 지정된 휴일 또는 조건 때문에 **{DAYS[i]}요일**의 일정 산출이 불가합니다.", []
        daily_candidates.append(teams)

    # 5. 백트래킹(DFS) 최적화 탐색
    valid_week_schedules = []
    
    def solve(day_idx, current_counts, current_schedule):
        if len(valid_week_schedules) >= 1000:
            return
            
        # 가지치기 1: 본인 목표 초과
        if any(current_counts[m.name] > target_shifts[m.name] for m in members):
            return
            
        # 가지치기 2: 남은 요일 매일 투입해도 목표 미달
        remaining_days = 7 - day_idx
        for m in members:
            if current_counts[m.name] + remaining_days < target_shifts[m.name]:
                return

        # 가지치기 3: 전체 남은 자리가 넘치거나 모자랄 때 조기 차단 (성능 극대화)
        current_total = sum(current_counts.values())
        min_future = sum(base_reqs[day_idx:])
        max_future = sum(max_reqs[day_idx:])
        
        if current_total + min_future > total_supply: return
        if current_total + max_future < total_supply: return

        if day_idx == 7:
            if all(current_counts[m.name] == target_shifts[m.name] for m in members):
                valid_week_schedules.append(current_schedule)
            return

        for team in daily_candidates[day_idx]:
            new_counts = current_counts.copy()
            for m in team:
                new_counts[m.name] += 1
            solve(day_idx + 1, new_counts, current_schedule + [team])

    initial_counts = {m.name: 0 for m in members}
    solve(0, initial_counts, [])

    if not valid_week_schedules:
        return False, "⚠️ '목표 근무 횟수 달성'과 '필수 역량' 조건을 동시에 만족하는 스케줄이 없습니다. 특정 요일에 휴일자가 너무 많이 몰렸을 수 있습니다.", []

    # 6. 분산 최소화 정렬 및 반환
    unique_schedules = {}
    for week_schedule in valid_week_schedules:
        member_scores = {m.name: 0 for m in members}
        for day_team in week_schedule:
            for member in day_team:
                member_scores[member.name] += member.score
                
        scores_array = list(member_scores.values())
        variance = np.var(scores_array)
        
        schedule_key = tuple(tuple(sorted([m.name for m in team])) for team in week_schedule)
        if schedule_key not in unique_schedules:
            unique_schedules[schedule_key] = (variance, week_schedule)
            
    sorted_schedules = sorted(unique_schedules.values(), key=lambda x: x[0])
    top_schedules = [sched for variance, sched in sorted_schedules[:top_n]]
    
    # 추가 배치 여부 안내 메시지 작성
    msg = "성공"
    if extra_shifts > 0:
        msg = f"근무 가능 인력이 기본 필요 인원보다 많아, 남는 **{extra_shifts}명**의 자리가 일부 요일에 1명씩 유동적으로 추가 배치되었습니다."
    
    return True, msg, top_schedules