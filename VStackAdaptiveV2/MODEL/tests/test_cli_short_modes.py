from vnext.cli import short_mode_policy


def test_release_adaptive_mode_is_full_strength_and_f3_only():
    assert short_mode_policy("short_v2_adaptive") == (1.0, True)


def test_global_diagnostic_is_not_f3_only():
    assert short_mode_policy("short_v2_adaptive_global50") == (0.5, False)


def test_frozen_short_v2_has_zero_adaptation():
    assert short_mode_policy("short_v2") == (0.0, False)
