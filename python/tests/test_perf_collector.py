from perf_collector import normalize_sample


def test_normalize_sample_marks_unsupported() -> None:
    sample = normalize_sample(
        {
            "cpu_pct": 30.5,
            "memory_mb": 128.0,
            "launch_ms": 900,
        },
        requested_metrics=["cpu_pct", "memory_mb", "fps"],
    )

    assert sample["metric_flags"]["fps"] == "unsupported"
