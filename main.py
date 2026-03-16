# main.py （推荐写法 - 2025/2026 风格，满足你的最新输入要求）

import streamlit as st
from datetime import date, timedelta
import pandas as pd
import json

# 假设已有的导入（根据你项目实际情况保留/调整）
from oracle_agent import (
    get_transactions, is_settled, get_response_code_desc, clean_db, clean_df,
    build_trans_query, run_sql   # 如果有的话
)
from marketing_agent import get_discount_transaction,compare, load_json
from log_agent import real_query, analyze_with_ai

st.set_page_config(page_title="生产运营数字人", layout="wide")
st.title("🛠 生产运营数字人")

# ── 侧边栏 ───────────────────────────────────────────────
with st.sidebar:
    st.header("查询设置")
    st.caption("仅支持近15天数据查询")

    mode = st.radio(
        "功能模式",
        ["交易问题定位", "清算状态排查", "立减客诉排查"],
        index=0
    )

    today = date.today()
    min_date = today - timedelta(days=14)

    if mode == "清算状态排查":
        date_range = st.date_input(
            "交易日期范围",
            value=(today, today),
            min_value=min_date,
            max_value=today,
            help="可选择单日或一段日期"
        )
    else:
        selected_date = st.date_input(
            "交易日期",
            value=today,
            min_value=min_date,
            max_value=today,
            help="仅支持单日查询"
        )

    with st.form(key="query_form", clear_on_submit=False):
        if mode in ["交易问题定位", "清算状态排查"]:
            col1, col2 = st.columns(2)
            f11 = col1.text_input("F11 跟踪号", key="f11", help="必填")
            f33 = col2.text_input("F33 前置机构", key="f33")

            if mode == "清算状态排查":
                st.caption("以下至少填写一项（F33/F22/F32/F42/F100）")
                col1, col2, col3 = st.columns(3)
                f22  = col1.text_input("F22 服务点输入方式", key="f22")
                f32  = col2.text_input("F32 收单机构", key="f32")
                f42  = col3.text_input("F42 商户号", key="f42")
                f100 = st.text_input("F100 接收机构", key="f100")

        elif mode == "立减客诉排查":
            col1, col2, col3 = st.columns(3)
            trans_amt = col1.text_input("交易金额（分）", key="trans_amt", help="必填，例如 10000 表示100.00元")
            pri_num   = col2.text_input("主账号（卡号）", key="pri_num", help="必填，明文卡号")
            act_num   = col3.text_input("立减活动编号", key="act_num", help="必填，活动编号")

        submitted = st.form_submit_button("🚀 开始查询", type="primary", use_container_width=True)

# ── 主内容区 ─────────────────────────────────────────────
if submitted:
    # ── 日期处理 ────────────────────────────────────────
    if mode == "清算状态排查":
        if len(date_range) == 1:
            start_date = end_date = date_range[0]
        else:
            start_date, end_date = date_range
    else:
        start_date = end_date = selected_date

    start_str = start_date.strftime("%Y-%m-%d")
    end_str   = end_date.strftime("%Y-%m-%d")
    sett_dt_yyyymmdd = start_date.strftime("%Y%m%d")   # 立减用

    # ── 校验 ────────────────────────────────────────────
    error = None
    if mode == "交易问题定位":
        if not f11 or not f33:
            error = "【交易问题定位】必须填写 F11 和 F33"
    elif mode == "清算状态排查":
        has_identifier = any([f11, f33, f22, f32, f42, f100])
        if not f11 or not has_identifier:
            error = "【清算状态排查】必须填写 F11 + 至少一个机构/商户标识（F33/F22/F32/F42/F100）"
    elif mode == "立减客诉排查":
        if not trans_amt or not pri_num:
            error = "【立减客诉排查】必须填写 交易金额、卡号和活动编号"

    if error:
        st.error(error)
        st.stop()

    # ── 根据模式执行不同查询 ───────────────────────────────
    if mode in ["交易问题定位", "清算状态排查"]:
        with st.spinner("正在查询交易明细..."):
            df = get_transactions(
                date_start=start_str,
                date_end=end_str,
                f11=f11.strip() if f11 else None,
                f33=f33.strip() if f33 else None,
                f22=f22.strip() if 'f22' in locals() and f22 else None,
                f32=f32.strip() if 'f32' in locals() and f32 else None,
                f42=f42.strip() if 'f42' in locals() and f42 else None,
                f100=f100.strip() if 'f100' in locals() and f100 else None,
            )

        if df.empty:
            st.warning("未找到符合条件的交易记录")
        else:
            st.subheader(f"交易明细（{len(df)} 条）")
            df1=clean_df(df)
            display = json.dumps(
                df1.to_dict(orient="records"),
                indent=1,
                ensure_ascii=False
            )
            st.json(display,expanded=False)
            #st.json(df.head(100))  # 或用 st.json() / aggrid 等更好看的组件

            if mode == "清算状态排查":
                status = is_settled(df)
                st.metric("清算状态", status)
                if "已清算" in status:
                    st.success("该交易已完成清算")
                else:
                    st.warning("交易尚未清算，请检查后续流程，若还有疑问可进入交易问题定位模块")

            elif mode == "交易问题定位":
                desc_raw, exp_raw = get_response_code_desc(df)
                rc_type = df["rc_type"].iloc[0]
                desc=clean_db(desc_raw)
                exp=clean_db(exp_raw)
                st.info(f"**交易拒绝方**：{rc_type}")
                col1, col2 = st.columns(2)
                col1.info(f"**响应码解释**：{desc}")
                col2.warning(f"**历史经验建议**：{exp}")
                if rc_type != "发卡拒绝":
                    # 查询 LDM 日志
                    with st.spinner("正在检索 LDM 日志并进行 AI 分析..."):
                        if len(f11)<6:
                            f11 = f11.zfill(6)
                        end = (start_date + timedelta(days=1)).strftime("%Y-%m-%d")
                        st.write("--- 日志查询调试信息 ---")
                        st.write("日期范围:", start_str, "~", end)
                        st.write("F11:", repr(f11))   # repr 会显示引号和不可见字符
                        st.write("F33:", repr(f33))
                        
                        core_logs, full_msgs = real_query(start_str, end, f11, f33)
                        
                        if core_logs in ["ERROR", "NO_LOGS"]:
                            st.error(f"日志检索失败: {full_msgs}")
                        else:
                            with st.expander("📄 查看完整原始日志"):
                                st.text_area("", full_msgs, height=300)
                            
                            analysis = analyze_with_ai(core_logs, full_msgs,desc,exp)
                            st.subheader("🤖 AI 智能分析结论")
                            st.markdown(f"> {analysis}")
                            
                            with st.expander("📑 核心日志片段",expanded=True):
                                st.code(core_logs)

    elif mode == "立减客诉排查":
        with st.spinner("查询立减交易明细..."):
            # 还需要检查是否真的参与交易
            trans_json = get_discount_transaction(
                trans_amt=trans_amt.strip(),
                pri_acct_num=pri_num.strip(),
                sett_date=sett_dt_yyyymmdd
            )

        if trans_json is None:
            st.info("未找到匹配的交易记录")
        else:
            st.subheader("交易明细")
            st.json(trans_json,expanded=False)
            st.subheader(f"活动**{act_num}**明细")
            params = load_json(f"/home/tma/jupyterlab/RPAtoTMA/discountActivity/{act_num}.json")
            st.json(params,expanded=False)
            with st.spinner(f"正在查看活动{act_num}的配置信息，并进行 AI 分析..."):
                analyze,audit=compare(trans_json,act_num)
                st.subheader("🤖 AI 智能分析结论")
                st.markdown(f"> {analyze}")
                st.subheader("🤖 AI 智能审计结论")
                st.markdown(f"> {audit}")

st.divider()
st.caption(f"当前模式：{mode}")