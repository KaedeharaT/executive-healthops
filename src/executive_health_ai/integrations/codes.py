"""Small, extensible canonical observation-code registry."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ObservationCode:
    canonical_code: str
    aliases: tuple[str, ...]
    default_unit: str
    category: str
    minimum: float | None = None
    maximum: float | None = None


REGISTRY = {
    item.canonical_code: item for item in (
        ObservationCode("systolic_bp", ("sys", "sbp", "systolic", "收缩压", "高压", "bloodpressurehigh"), "mmHg", "blood_pressure", 50, 300),
        ObservationCode("diastolic_bp", ("dia", "dbp", "diastolic", "舒张压", "低压", "bloodpressurelow"), "mmHg", "blood_pressure", 30, 200),
        ObservationCode("heart_rate", ("pulse", "hr", "心率"), "bpm", "vital", 20, 250),
        ObservationCode("glucose", ("blood_glucose", "cgm_glucose", "血糖"), "mg/dL", "metabolic", 20, 800),
        ObservationCode("weight", ("body_weight", "体重"), "kg", "body", 20, 400),
        ObservationCode("height", ("身高",), "cm", "body", 50, 260),
        ObservationCode("sleep_duration", ("total_sleep_duration", "sleep_minutes", "睡眠时长"), "minutes", "sleep", 0, 1440),
        ObservationCode("deep_sleep_duration", ("deep_sleep", "deep_sleep_minutes", "深度睡眠"), "minutes", "sleep", 0, 1440),
        ObservationCode("light_sleep_duration", ("light_sleep", "light_sleep_minutes", "浅睡"), "minutes", "sleep", 0, 1440),
        ObservationCode("rem_sleep_duration", ("rem_sleep", "rem_sleep_minutes"), "minutes", "sleep", 0, 1440),
        ObservationCode("awake_duration", ("awake_minutes", "清醒时间"), "minutes", "sleep", 0, 1440),
        ObservationCode("sleep_score", ("score", "sleepscore"), "score", "sleep", 0, 100),
        ObservationCode("resting_heart_rate", ("rhr",), "bpm", "sleep", 20, 250),
        ObservationCode("steps", ("step_count",), "count", "activity", 0, 100000),
        ObservationCode("exercise_minutes", ("appleexercisetime",), "minutes", "activity", 0, 1440),
        ObservationCode("active_calories", ("activeenergyburned",), "kcal", "activity", 0, 20000),
        ObservationCode("spo2", ("oxygensaturation",), "%", "vital", 50, 100),
        ObservationCode("hba1c", ("a1c", "糖化血红蛋白", "糖化血红蛋白a1c"), "%", "metabolic", 2, 20),
        ObservationCode("fasting_glucose", ("空腹血糖", "fbg"), "mmol/L", "metabolic", 1, 60),
        ObservationCode("bmi", ("体质指数",), "kg/m²", "body", 5, 100),
        ObservationCode("waist_circumference", ("腰围",), "cm", "body", 20, 300),
        ObservationCode("body_fat_percentage", ("体脂率",), "%", "body", 1, 100),
        ObservationCode("skeletal_muscle_mass", ("骨骼肌量",), "kg", "body", 1, 200),
        ObservationCode("basal_metabolic_rate", ("基础代谢", "基础代谢率"), "kcal", "body", 100, 10000),
        ObservationCode("triglycerides", ("甘油三酯", "tg"), "mmol/L", "lipid", 0, 100),
        ObservationCode("total_cholesterol", ("总胆固醇", "tc"), "mmol/L", "lipid", 0, 100),
        ObservationCode("ldl_c", ("低密度脂蛋白", "低密度脂蛋白胆固醇", "ldl", "ldl-c"), "mmol/L", "lipid", 0, 100),
        ObservationCode("hdl_c", ("高密度脂蛋白", "高密度脂蛋白胆固醇", "hdl", "hdl-c"), "mmol/L", "lipid", 0, 100),
        ObservationCode("alt", ("谷丙转氨酶",), "U/L", "liver", 0, 2000),
        ObservationCode("ast", ("谷草转氨酶",), "U/L", "liver", 0, 2000),
        ObservationCode("ggt", ("γ-谷氨酰转肽酶", "谷氨酰转肽酶"), "U/L", "liver", 0, 2000),
        ObservationCode("alkaline_phosphatase", ("碱性磷酸酶", "alp"), "U/L", "liver", 0, 2000),
        ObservationCode("creatinine", ("肌酐", "scr"), "μmol/L", "renal", 0, 5000),
        ObservationCode("egfr", ("估算肾小球滤过率",), "mL/min/1.73m²", "renal", 0, 300),
        ObservationCode("uric_acid", ("尿酸",), "μmol/L", "renal", 0, 5000),
        ObservationCode("urea", ("尿素", "尿素氮"), "mmol/L", "renal", 0, 100),
        ObservationCode("tsh", ("促甲状腺激素",), "mIU/L", "thyroid", 0, 1000),
        ObservationCode("ft3", ("游离三碘甲状腺原氨酸",), "pmol/L", "thyroid", 0, 100),
        ObservationCode("ft4", ("游离甲状腺素",), "pmol/L", "thyroid", 0, 1000),
        ObservationCode("psa", ("前列腺特异抗原",), "ng/mL", "tumor_marker", 0, 10000),
        ObservationCode("free_psa", ("游离前列腺特异抗原",), "ng/mL", "tumor_marker", 0, 10000),
        ObservationCode("cea", ("癌胚抗原",), "ng/mL", "tumor_marker", 0, 10000),
        ObservationCode("afp", ("甲胎蛋白",), "ng/mL", "tumor_marker", 0, 10000),
    )
}


def canonical_code(value: str) -> ObservationCode | None:
    normalized = value.strip().lower().replace(" ", "").replace("_", "")
    for item in REGISTRY.values():
        names = (item.canonical_code, *item.aliases)
        if normalized in {name.lower().replace("_", "") for name in names}:
            return item
    return None
