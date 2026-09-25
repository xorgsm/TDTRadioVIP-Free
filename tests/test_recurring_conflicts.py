from core.recurring_recordings import RecurringRule, find_rule_conflicts


def _rule(days, start, duration, enabled=True):
    return RecurringRule(
        id="rule",
        channel_name="Canal",
        channel_url="https://stream.test",
        days=days,
        start_time=start,
        duration_minutes=duration,
        enabled=enabled,
    )


def test_recurring_conflict_on_same_day():
    existing = _rule([0], "20:00", 60)
    assert find_rule_conflicts([0], "20:30", 30, [existing]) == [existing]


def test_touching_recurring_rules_do_not_conflict():
    existing = _rule([0], "20:00", 60)
    assert find_rule_conflicts([0], "21:00", 30, [existing]) == []


def test_recurring_conflict_across_midnight_and_week_boundary():
    sunday = _rule([6], "23:30", 90)
    assert find_rule_conflicts([0], "00:30", 30, [sunday]) == [sunday]


def test_disabled_recurring_rule_does_not_conflict():
    disabled = _rule([0], "20:00", 60, enabled=False)
    assert find_rule_conflicts([0], "20:30", 30, [disabled]) == []
