# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify
import pandas as pd
from datetime import datetime, timedelta
import math

# --- 基础数据定义 (保持不变) ---
TIAN_GAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
DI_ZHI = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
JIAZI_CYCLE = [TIAN_GAN[i % 10] + DI_ZHI[i % 12] for i in range(60)]
JIE_QI = ['立春', '惊蛰', '清明', '立夏', '芒种', '小暑', '立秋', '白露', '寒露', '立冬', '大雪', '小寒']

# --- 核心计算函数 (保持不变) ---
def get_bazi_details(birth_time_str, gender):
    try:
        birth_dt = datetime.strptime(birth_time_str, '%Y-%m-%d %H:%M')
    except ValueError:
        raise ValueError("日期时间格式错误，请使用 'YYYY-MM-DD HH:MM' 格式。")

    try:
        df = pd.read_csv('data.csv', encoding='gbk')
    except FileNotFoundError:
        raise FileNotFoundError("错误：找不到 data.csv 文件。请确保它与脚本在同一个文件夹中。")
    except Exception as e:
        raise Exception(f"读取CSV文件时出错: {e}")

    DATE_COLUMN, SOLAR_TERM_COLUMN, GAN_ZHI_COLUMN = '日期', '节气', '干支'
    df[DATE_COLUMN] = pd.to_datetime(df[DATE_COLUMN])

    lichun_this_year = df[(df[DATE_COLUMN].dt.year == birth_dt.year) & (df[SOLAR_TERM_COLUMN] == '立春')]
    year_for_bazi = birth_dt.year
    if not lichun_this_year.empty and birth_dt < lichun_this_year.iloc[0][DATE_COLUMN]:
        year_for_bazi = birth_dt.year - 1
    year_gan_zhi = JIAZI_CYCLE[(year_for_bazi - 1984) % 60]

    jie_qi_df = df[df[SOLAR_TERM_COLUMN].isin(JIE_QI)].sort_values(DATE_COLUMN).reset_index()
    last_jie_qi = jie_qi_df[jie_qi_df[DATE_COLUMN] <= birth_dt].iloc[-1]
    
    year_gan_index = TIAN_GAN.index(year_gan_zhi[0])
    month_start_gan_index = (year_gan_index % 5) * 2
    month_index = JIE_QI.index(last_jie_qi[SOLAR_TERM_COLUMN])
    month_gan_index = (month_start_gan_index + month_index) % 10
    month_di_zhi_index = (month_index + 2) % 12
    month_gan_zhi = TIAN_GAN[month_gan_index] + DI_ZHI[month_di_zhi_index]

    day_row = df[df[DATE_COLUMN].dt.date == birth_dt.date()]
    if day_row.empty:
        raise ValueError(f"数据表中找不到日期: {birth_dt.date()}。")
    day_gan_zhi = day_row.iloc[0][GAN_ZHI_COLUMN]
    
    hour = birth_dt.hour
    hour_map = {
        (23, 0): '子（23-1）', (1, 2): '丑(1-3)', (3, 4): '寅(3-5)', (5, 6): '卯(5-7)',
        (7, 8): '辰(7-9)', (9, 10): '巳(9-11)', (11, 12): '午(11-13)', (13, 14): '未(13-15)',
        (15, 16): '申(15-17)', (17, 18): '酉(17-19)', (19, 20): '戌(19-21)', (21, 22): '亥(21-23)'
    }
    hour_gan_zhi = None
    for hours, col_name in hour_map.items():
        if hour in hours:
            hour_gan_zhi = day_row.iloc[0][col_name]
            break
    
    if pd.isna(hour_gan_zhi):
        raise ValueError(f"无法为 {birth_dt.hour} 点找到对应的时柱。")

    year_gan = year_gan_zhi[0]
    is_yang_year = year_gan in ['甲', '丙', '戊', '庚', '壬']
    is_male = gender == '男'
    is_forward = (is_yang_year and is_male) or (not is_yang_year and not is_male)

    if is_forward:
        next_jie_qi = jie_qi_df[jie_qi_df[DATE_COLUMN] > birth_dt].iloc[0]
        time_diff = next_jie_qi[DATE_COLUMN] - birth_dt
    else:
        time_diff = birth_dt - last_jie_qi[DATE_COLUMN]
        
    days_diff = time_diff.total_seconds() / (24 * 3600)
    start_luck_years = int(days_diff / 3)
    start_luck_months = int((days_diff % 3) * 12 / 3)
    start_luck_days = math.ceil((((days_diff % 3) * 12) % 3) * 10)

    luck_pillars = []
    month_pillar_index = JIAZI_CYCLE.index(month_gan_zhi)
    for i in range(1, 10):
        pillar_index = (month_pillar_index + i) % 60 if is_forward else (month_pillar_index - i + 60) % 60
        luck_pillars.append(JIAZI_CYCLE[pillar_index])

    return {
        "基本信息": {"公历生日": birth_dt.strftime('%Y-%m-%d %H:%M'), "性别": gender},
        "八字命盘": {"年柱": year_gan_zhi, "月柱": month_gan_zhi, "日柱": day_gan_zhi, "时柱": hour_gan_zhi},
        "起运信息": {"方向": "顺行" if is_forward else "逆行", "起运岁数": f"{start_luck_years}岁 {start_luck_months}个月 {start_luck_days}天后"},
        "大运（前九步）": {f"{start_luck_years + i*10}岁": pillar for i, pillar in enumerate(luck_pillars)}
    }

# --- Flask Web 应用封装 (保持不变) ---
app = Flask(__name__)
@app.route('/bazi', methods=['POST'])
def bazi_handler():
    data = request.get_json()
    if not data or 'birth_time' not in data or 'gender' not in data:
        return jsonify({"error": "请求体必须是JSON，且包含 'birth_time' 和 'gender' 字段。"}), 400
    try:
        bazi_info = get_bazi_details(data['birth_time'], data['gender'])
        return jsonify(bazi_info)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- 本地测试运行 (保持不变) ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
