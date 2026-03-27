# frontend/pages/1_上传解析.py
import streamlit as st
from frontend.api_client import upload_report

if "token" not in st.session_state:
    st.error("请先登录")
    st.stop()

st.title("上传解析")
st.markdown("支持格式：**PDF（原生/扫描）、JPG、PNG**")

uploaded_file = st.file_uploader(
    "上传征信报告",
    type=["pdf", "jpg", "jpeg", "png"],
    label_visibility="visible",
)

if uploaded_file is not None:
    with st.spinner("解析中，请稍候..."):
        try:
            result = upload_report(
                file_bytes=uploaded_file.getvalue(),
                filename=uploaded_file.name,
            )
            st.success(f"解析完成！报告ID：{result['report_id']}")
            st.session_state["last_report_id"] = result["report_id"]
        except Exception as e:
            st.error(f"解析失败：{e}")

if st.session_state.get("last_report_id"):
    st.info(f"最近解析的报告 ID：{st.session_state['last_report_id']}，可在「报告列表」页查看详情")
