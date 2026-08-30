from executive_health_ai.ui.localization.zh_cn import (
    barrier, device_class, observation, priority, program_phase, program_type,
    provider, risk_level, status,
)

def test_core_display_mappings_are_chinese():
    assert status("PARTIAL_SUCCESS") == "部分成功"
    assert priority("HIGH") == "高"
    assert observation("systolic_bp") == "收缩压"
    assert provider("apple_health") == "苹果健康"
    assert barrier("TRAVEL") == "出差"
    assert status("UNMATCHED") == "未匹配成员"
    assert program_type("NINETY_DAY") == "90天健康管理"
    assert program_phase("EXECUTION") == "执行与调整"
    assert risk_level("GREEN") == "低风险"
    assert risk_level("YELLOW") == "中风险"
    assert risk_level("RED") == "高风险"
    assert risk_level("UNKNOWN") == "暂无正式风险评估"
    assert device_class("MEDICAL_MONITOR") == "医疗监测设备"
