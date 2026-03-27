# frontend/pages/3_报告详情.py
import streamlit as st
import pandas as pd
from frontend.api_client import get_report

if "token" not in st.session_state:
    st.error("请先登录")
    st.stop()

report_id = st.session_state.get("view_report_id")
if not report_id:
    report_id = st.number_input("输入报告ID", min_value=1, step=1)
    if not st.button("加载"):
        st.stop()

try:
    report = get_report(int(report_id))
except Exception as e:
    st.error(f"获取报告失败：{e}")
    st.stop()

TYPE_MAP = {"enterprise": "企业版", "personal_detail": "个人详版", "personal_simple": "个人简版"}
st.title(f"报告详情 — {report.get('subject_name', '未知')}")

col1, col2, col3 = st.columns(3)
col1.metric("报告类型", TYPE_MAP.get(report["report_type"], report["report_type"]))
col2.metric("报告日期", report.get("report_date") or "-")
col3.metric("防篡改校验", "✅ 通过" if report["is_valid"] else ("❌ 未通过" if report["is_valid"] is False else "-"))

tab1, tab2, tab3 = st.tabs(["基本信息", "信贷账户", "查询记录"])

with tab1:
    detail = report.get("detail")
    if detail:
        if "report_info" in detail:
            st.subheader("报告信息")
            st.json(detail["report_info"])
        if "com_base" in detail:
            st.subheader("企业基本信息")
            st.json(detail["com_base"])
        if "base_info" in detail:
            st.subheader("个人基本信息")
            st.json(detail["base_info"])
        if "summary" in detail and detail["summary"]:
            st.subheader("信息概要")
            st.json(detail["summary"])
    else:
        st.info("暂无详情数据")

with tab2:
    accounts = report.get("credit_accounts", [])
    if accounts:
        st.dataframe(pd.DataFrame(accounts), use_container_width=True)
    else:
        st.info("暂无信贷账户数据")

with tab3:
    queries = report.get("query_records", [])
    if queries:
        st.dataframe(pd.DataFrame(queries), use_container_width=True)
    else:
        st.info("暂无查询记录")
