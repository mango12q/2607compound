"""
detect_events.py — 共享的热浪事件检测核心逻辑
被 detect_mhw.py 和 detect_thw.py 共用。
"""
from typing import List, Tuple


def detect_events_from_exceed(
    exceed, min_duration: int, max_gap: int
) -> List[Tuple[int, int]]:
    events = []
    in_event = False
    start_idx = 0
    gap_count = 0
    last_true_idx = -1

    for i in range(len(exceed)):
        if exceed[i]:
            if not in_event:
                in_event = True
                start_idx = i
                gap_count = 0
            else:
                gap_count = 0
            last_true_idx = i
        else:
            if in_event:
                gap_count += 1
                if gap_count > max_gap:
                    end_idx = i - gap_count + 1
                    if end_idx - start_idx >= min_duration:
                        events.append((start_idx, end_idx))
                    in_event = False

    if in_event:
        end_idx = last_true_idx + 1
        if end_idx - start_idx >= min_duration:
            events.append((start_idx, end_idx))

    return events
