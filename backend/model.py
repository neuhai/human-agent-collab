class Session:
    - session_id: str
    - experiment_type: str
    - status: 'waiting' | 'running' | 'paused' | 'ended'
    - config: dict  
    - params: dict  
    - interaction: dict 
    - created_at: datetime
    - started_at: datetime | None
    - duration_minutes: int
    - remaining_seconds: int

class Participant:
    - participant_id: str
    - session_id: str
    - participant_type: 'human' | 'ai'
    - participant_name: str 
    - online: bool
    - data: dict  # 实验特定数据（money, inventory等）
    