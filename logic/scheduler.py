import itertools
import numpy as np

DAYS = ["월", "화", "수", "목", "금", "토", "일"]

# ✨ 1. 파라미터에 no_dishwasher_days 추가
def get_valid_daily_teams(members, day_idx, off_days_dict, allowed_sizes, no_dishwasher_days):
    available_members = [m for m in members if day_idx not in off_days_dict.get(m.name, [])]
    
    valid_teams = []
    for req_count in allowed_sizes:
        if len(available_members) < req_count:
            continue 
            
        for team in itertools.combinations(available_members, req_count):
            main_capable_count = sum(1 for m in team if m.can_do("메인"))
            ordering_capable_count = sum(1 for m in team if m.can_do("발주"))
            
            # ✨ 2. 설거지 이모 부재일 역량 검증 로직 추가
            if day_idx in no_dishwasher_days:
                dishwash_capable_count = sum(1 for m in team if m.can_dishwash)
                # 설거지 가능한 멤버가 1명도 없다면 이 조합은 탈락!
                if dishwash_capable_count == 0:
                    continue 
            
            if main_capable_count >= 2 and ordering_capable_count >= 1:
                valid_teams.append(team)
                
    return valid_teams

def generate_best_schedules(members, off_days_dict, no_dishwasher_days, public_holidays, top_n=5):
    target_shifts = {}
    for m in members:
        off_count = len(off_days_dict.get(m.name, []))
        target_shifts[m.name] = 4 if off_count >= 3 else 5
    total_supply = sum(target_shifts.values())

    base_reqs = []
    for i in range(7):
        is_weekend_or_holiday = (i >= 5) or (i in public_holidays)
        req = 4 if is_weekend_or_holiday else 3
        
        if i in no_dishwasher_days:
            req += 1
        base_reqs.append(req)
    total_base_demand = sum(base_reqs)

    if total_supply < total_base_demand:
        return False, f"⚠️ **인력 부족**: 최소 필요 근무 자리({total_base_demand}자리)보다 멤버들의 총 투입 가능 횟수({total_supply}회)가 적어 산출이 불가능합니다.", []

    extra_shifts = total_supply - total_base_demand
    max_daily_extra = (extra_shifts + 6) // 7 if extra_shifts > 0 else 0
    max_reqs = [req + max_daily_extra for req in base_reqs]

    daily_candidates = []
    for i in range(7):
        allowed_sizes = range(base_reqs[i], max_reqs[i] + 1)
        # ✨ 3. 함수 호출 시 no_dishwasher_days를 전달하도록 수정
        teams = get_valid_daily_teams(members, i, off_days_dict, allowed_sizes, no_dishwasher_days)
        if not teams:
            return False, f"⚠️ 지정된 휴일 또는 조건(설거지 역량 부족 등) 때문에 **{DAYS[i]}요일**의 일정 산출이 불가합니다.", []
        daily_candidates.append(teams)

    # ... (이하 백트래킹 및 분산 정렬 코드는 기존과 동일하게 유지합니다) ...
    valid_week_schedules = []
    
    def solve(day_idx, current_counts, current_schedule):
        if len(valid_week_schedules) >= 1000:
            return
            
        if any(current_counts[m.name] > target_shifts[m.name] for m in members):
            return
            
        remaining_days = 7 - day_idx
        for m in members:
            if current_counts[m.name] + remaining_days < target_shifts[m.name]:
                return

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
        return False, "⚠️ 조건을 동시에 만족하는 스케줄이 없습니다. 특정 요일에 휴일자나 특정 역량 부족자가 몰렸을 수 있습니다.", []

    unique_schedules = {}
    red_days = set([5, 6] + public_holidays)

    for week_schedule in valid_week_schedules:
        red_day_work_counts = {m.name: 0 for m in members}
        daily_avg_scores = [] 
        
        for day_idx, day_team in enumerate(week_schedule):
            day_total_score = sum(member.score for member in day_team)
            day_avg_score = day_total_score / len(day_team)
            daily_avg_scores.append(day_avg_score)
            
            if day_idx in red_days:
                for member in day_team:
                    red_day_work_counts[member.name] += 1
                
        team_strength_variance = np.var(daily_avg_scores)
        red_day_array = list(red_day_work_counts.values())
        red_day_variance = np.var(red_day_array)
        
        schedule_key = tuple(tuple(sorted([m.name for m in team])) for team in week_schedule)
        if schedule_key not in unique_schedules:
            unique_schedules[schedule_key] = (red_day_variance, team_strength_variance, week_schedule)
            
    sorted_schedules = sorted(unique_schedules.values(), key=lambda x: (x[0], x[1]))
    top_schedules = [sched for r_var, s_var, sched in sorted_schedules[:top_n]]
    
    msg = "성공"
    if extra_shifts > 0:
        msg = f"근무 가능 인력이 필요 인원보다 많아, 남는 **{extra_shifts}명**의 자리가 일부 요일에 유동적으로 추가 배치되었습니다."
    
    return True, msg, top_schedules