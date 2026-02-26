# 역량 점수 및 계층 매핑
ROLE_SCORES = {
    "발주": 4,
    "메인": 3,
    "면말이": 2,
    "서브": 1
}

class KitchenMember:
    def __init__(self, name, top_role, can_dishwash=False):
        self.name = name
        self.top_role = top_role
        self.score = ROLE_SCORES[top_role]
        self.can_dishwash = can_dishwash 

    def can_do(self, required_role):
        return self.score >= ROLE_SCORES[required_role]
    
    def to_dict(self):
        return {
            "이름": self.name,
            "최고 역량": self.top_role,
            "설거지 가능여부": "O" if self.can_dishwash else "X",
            "역량 점수": self.score
        }

    @classmethod
    def from_dict(cls, data):
        """구글 시트에서 불러온 데이터를 객체로 변환합니다."""
        can_dishwash = True if data.get("설거지 가능여부") == "O" else False
        return cls(data["이름"], data["최고 역량"], can_dishwash)