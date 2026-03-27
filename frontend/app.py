# frontend/app.py
import streamlit as st
from frontend.api_client import login

st.set_page_config(page_title="征信报告审核系统", layout="wide")

def show_login():
    st.title("征信报告审核系统")
    st.subheader("登录")
    username = st.text_input("用户名")
    password = st.text_input("密码", type="password")
    if st.button("登录"):
        try:
            data = login(username, password)
            st.session_state["token"] = data["token"]
            st.session_state["username"] = data["username"]
            st.session_state["role"] = data["role"]
            st.success("登录成功")
            st.rerun()
        except Exception:
            st.error("用户名或密码错误")

def require_login():
    if "token" not in st.session_state:
        show_login()
        st.stop()

require_login()

st.sidebar.success(f"已登录：{st.session_state.get('username')}")
if st.sidebar.button("退出登录"):
    st.session_state.clear()
    st.rerun()

st.title("欢迎使用征信报告审核系统")
st.info("请从左侧导航选择功能")
