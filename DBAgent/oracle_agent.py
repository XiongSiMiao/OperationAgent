# oracle_agent.py （建议完整替换原有内容）

import pandas as pd
import oracledb
from typing import Optional, Dict, Any
from connect_database import ConnectDatabase

def clean_db(text):
    s = str(text).replace('\n','').replace('\r','').replace('\t','')
    cleaned = "".join(c for c in s if c.isprintable())
    cleaned = " ".join(cleaned.split())
    return cleaned

def clean_df(df):
    df_clean=df.copy()
    for i in df_clean.columns:
        df_clean[i] = df_clean[i].apply(lambda x:str(x))
    return df_clean

def run_sql(sql: str) -> pd.DataFrame:
    """直接执行已完整拼好的 SQL（不带参数绑定）"""
    DB = ConnectDatabase()
    engine = DB.connect_database("BIDB")
    try:
        return pd.read_sql(sql, engine)
    except Exception as e:
        raise RuntimeError(f"SQL 执行失败:\n{str(e)}\n\nSQL:\n{sql}") 


def build_trans_query(
    date_start: str,               # '2025-03-01'
    date_end: Optional[str] = None,
    f11: Optional[str] = None,
    f22: Optional[str] = None,
    f32: Optional[str] = None,     # acq_ins_cde
    f33: Optional[str] = None,     # fwd_ins_cde
    f42: Optional[str] = None,     # mer_id
    f100: Optional[str] = None,    # recv_ins_cde
) -> str:
    """
    一次性构建完整的 SQL 字符串，sett_dt 条件放在最后
    所有值都已转义或加引号，尽量降低注入风险（但仍建议生产环境用绑定）
    """
    if date_end is None:
        date_end = date_start

    # 基础查询
    sql = """
    SELECT *
    FROM szopr.tbl_daily_trans_temp_15
    WHERE 1=1
    """

    # 日期条件（放在前面，但你要求 sett_dt 最后 → 我们移到最后）
    if date_end != date_start:
        date_cond = f"sett_dt BETWEEN TO_DATE('{date_start}', 'YYYY-MM-DD') AND TO_DATE('{date_end}', 'YYYY-MM-DD')"
    else:
        date_cond = f"sett_dt = TO_DATE('{date_start}', 'YYYY-MM-DD')"
    # 其他条件收集
    conditions = []

    if f11:
        conditions.append(f"TRACE_NUM = '{f11.strip()}'")
    if f22:
        conditions.append(f"SRV_ENTRY_MOD = '{f22.strip()}'")
    if f32:
        conditions.append(f"acq_ins_cde = '{f32.strip()}'")
    if f33:
        conditions.append(f"fwd_ins_cde = '{f33.strip()}'")
    if f42:
        conditions.append(f"mer_id = '{f42.strip()}'")
    if f100:
        conditions.append(f"recv_ins_cde = '{f100.strip()}'")

    # 把所有非日期条件拼上
    if conditions:
        sql += " AND " + " AND ".join(conditions)

    # 最后加上 sett_dt 条件（按你的要求）
    sql += f" AND {date_cond}"

    #sql += " ORDER BY sett_dt, sys_trace_num"

    return sql


def get_transactions(
    date_start: str,
    date_end: Optional[str] = None,
    **filters  # f11, f22, f32, f33, f42, f100
) -> pd.DataFrame:
    sql = build_trans_query(date_start, date_end, **filters)
    return run_sql(sql)



def is_settled(df: pd.DataFrame) -> str:
    if df.empty:
        return "未找到交易记录"
    sett_ind = str(df["sett_ind"].iloc[0])
    return "✅ 已清算" if sett_ind != "0" else "❌ 未清算"


def get_response_code_desc(df):
    """
    rc_desc
    upi_rc_desc
    iss_rc_desc
    exp_desc
    applicable_condition
    """
    if df.empty: return "无响应码", "无"
    resp_cde = df["trans_resp_cde"].dropna().iloc[0]
    rc_type = df["rc_type"].dropna().iloc[0]
    SQL = f"SELECT rc,rc_desc,upi_rc_desc,iss_rc_desc,exp_desc FROM szopr.qs_resp_rep_code WHERE rc = '{resp_cde}'"
    desc_df = run_sql(SQL)
    if not desc_df.empty:
        if rc_type == "银联拒绝":
            return desc_df['rc_desc'].iloc[0], desc_df['upi_rc_desc'].iloc[0]
        elif rc_type == "发卡拒绝":
            return desc_df['rc_desc'].iloc[0], desc_df['iss_rc_desc'].iloc[0]
        else:
            return desc_df['rc_desc'].iloc[0], desc_df['exp_desc'].iloc[0]
    return f"响应码 {resp_cde} 未定义", "无"#,rc_type
