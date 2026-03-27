# frontend/pages/2_报告列表.py
import streamlit as st
import pandas as pd
from frontend.api_client import list_reports, delete_report

if "token" not in st.session_state:
    st.error("请先登录")
    st.stop()

st.title("报告列表")

try:
    reports = list_reports()
except Exception as e:
    st.error(f"获取报告列表失败：{e}")
    st.stop()

if not reports:
    st.info("暂无报告，请前往「上传解析」页上传")
    st.stop()

TYPE_MAP = {"enterprise": "企业版", "personal_detail": "个人详版", "personal_simple": "个人简版"}
STATUS_MAP = {"success": "✅ 成功", "failed": "❌ 失败", "pending": "⏳ 处理中"}

df = pd.DataFrame([
    {
        "ID": r["id"],
        "主体名称": r["subject_name"] or "-",
        "类型": TYPE_MAP.get(r["report_type"], r["report_type"]),
        "报告日期": r["report_date"] or "-",
        "解析状态": STATUS_MAP.get(r["parse_status"], r["parse_status"]),
        "防篡改": "✅ 通过" if r["is_valid"] else ("❌ 未通过" if r["is_valid"] is False else "-"),
        "上传时间": r["created_at"][:19] if r["created_at"] else "-",
    }
    for r in reports
])

# 筛选
search = st.text_input("按主体名称筛选")
if search:
    df = df[df["主体名称"].str.contains(search, na=False)]

st.dataframe(df, use_container_width=True)

# 查看/删除
col1, col2 = st.columns(2)
with col1:
    view_id = st.number_input("输入报告ID查看详情", min_value=1, step=1, value=None)
    if view_id and st.button("查看详情"):
        st.session_state["view_report_id"] = int(view_id)
        st.switch_page("pages/3_报告详情.py")

with col2:
    del_id = st.number_input("输入报告ID删除", min_value=1, step=1, value=None, key="del_id")
    if del_id and st.button("删除报告", type="primary"):
        try:
            delete_report(int(del_id))
            st.success("删除成功")
            st.rerun()
        except Exception as e:
            st.error(f"删除失败：{e}")
