"""Split project time without losing seconds at regular/overtime boundaries."""
from datetime import datetime, timedelta


def split_work_time(start, end, regular_start, regular_end):
    if end <= start:
        raise ValueError("Checkout must be after check-in.")
    if regular_start == regular_end:
        raise ValueError("Regular start and end times must differ.")
    boundaries = {start, end}
    windows = []
    day = start.date() - timedelta(days=1)
    while day <= end.date():
        window_start = datetime.combine(day, regular_start)
        window_end = datetime.combine(day, regular_end)
        if regular_end < regular_start:
            window_end += timedelta(days=1)
        windows.append((window_start, window_end))
        for boundary in (window_start, window_end):
            if start < boundary < end:
                boundaries.add(boundary)
        day += timedelta(days=1)
    points = sorted(boundaries)
    result = []
    for left, right in zip(points, points[1:]):
        regular = any(a <= left < b for a, b in windows)
        if result and result[-1][2] == regular:
            result[-1] = (result[-1][0], right, regular)
        else:
            result.append((left, right, regular))
    return result
