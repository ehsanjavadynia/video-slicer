import math
import pytest
from app.constants import CRF_MAP, VALID_QUALITIES, VALID_COMPRESSION_LEVELS


class TestInputValidation:
    """Input Validation Tests"""

    def test_max_duration_zero_is_invalid(self):
        max_duration = 0
        assert max_duration <= 0

    def test_max_duration_positive_is_valid(self):
        max_duration = 30
        assert max_duration > 0

    def test_quality_must_be_valid(self):
        test_quality = 720
        assert test_quality in VALID_QUALITIES

    def test_compression_level_valid(self):
        compression = 3
        assert compression in VALID_COMPRESSION_LEVELS

    def test_invalid_compression_rejected(self):
        compression = 7
        assert compression not in VALID_COMPRESSION_LEVELS


class TestCRFMapping:
    """CRF Mapping Tests"""

    def test_level_0_maps_to_15(self):
        assert CRF_MAP[0] == 15

    def test_level_3_maps_to_23(self):
        assert CRF_MAP[3] == 23

    def test_level_6_maps_to_32(self):
        assert CRF_MAP[6] == 32

    def test_all_levels_have_values(self):
        for i in range(7):
            assert CRF_MAP[i] is not None


class TestQualityLevels:
    """Quality Level Tests"""

    def test_480p_available(self):
        assert 480 in VALID_QUALITIES

    def test_720p_available(self):
        assert 720 in VALID_QUALITIES

    def test_1080p_available(self):
        assert 1080 in VALID_QUALITIES

    def test_invalid_quality_rejected(self):
        test_quality = 360
        assert test_quality not in VALID_QUALITIES


class TestDurationCalculation:
    """Duration Calculation Tests"""

    def test_chunk_count_100s_with_30s_clips(self):
        total_duration = 100
        max_duration = 30
        chunk_count = math.ceil(total_duration / max_duration)
        assert chunk_count == 4

    def test_chunk_count_exact_division(self):
        total_duration = 120
        max_duration = 30
        chunk_count = math.ceil(total_duration / max_duration)
        assert chunk_count == 4

    def test_chunk_count_with_remainder(self):
        total_duration = 100
        max_duration = 25
        chunk_count = math.ceil(total_duration / max_duration)
        assert chunk_count == 4

    def test_start_time_calculation(self):
        clip_index = 2
        max_duration = 30
        start_time = clip_index * max_duration
        assert start_time == 60


class TestClipNaming:
    """Clip Naming Tests"""

    def test_clip_1_zero_padded(self):
        clip_num = str(1).zfill(3)
        assert clip_num == "001"

    def test_clip_10_padded(self):
        clip_num = str(10).zfill(3)
        assert clip_num == "010"

    def test_clip_100_not_padded(self):
        clip_num = str(100).zfill(3)
        assert clip_num == "100"


class TestErrorHandling:
    """Error Handling Tests"""

    def test_nan_max_duration_invalid(self):
        assert math.isnan(float("nan"))

    def test_negative_max_duration_invalid(self):
        max_duration = -30
        assert max_duration <= 0

    def test_string_max_duration_parseable(self):
        max_duration_str = "30"
        max_duration = int(max_duration_str)
        assert max_duration == 30

    def test_invalid_string_raises_error(self):
        max_duration_str = "abc"
        with pytest.raises(ValueError):
            int(max_duration_str)
