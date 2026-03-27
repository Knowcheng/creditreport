# frontend/pages/4_用户管理.py
import streamlit as st
import pandas as pd
from frontend.api_client import list_users, register_user

if "token" not in st.session_state:
    st.error("请先登录")
    st.stop()

if st.session_state.get("role") != "admin":
    st.error("需要管理员权限")
    st.stop()

st.title("用户管理")

# 用户列表
try:
    users = list_users()
    df = pd.DataFrame(users)
    st.subheader("当前用户")
    st.dataframe(df, use_container_width=True)
except Exception as e:
    st.error(f"获取用户列表失败：{e}")

st.divider()

# 新增用户
st.subheader("新增用户")
with st.form("add_user_form"):
    new_username = st.text_input("用户名")
    new_password = st.text_input("密码", type="password")
    submitted = st.form_submit_button("创建用户")
    if submitted:
        if not new_username or not new_password:
            st.error("用户名和密码不能为空")
        else:
            try:
                register_user(new_username, new_password)
                st.success(f"用户 {new_username} 创建成功")
                st.rerun()
            except Exception as e:
                st.error(f"创建失败：{e}")
