from datetime import datetime, timedelta, timezone
import jwt
import streamlit as st
import utils
from streamlit_feedback import streamlit_feedback

UTC = timezone.utc

utils.retrieve_config_from_agent()
st.set_page_config(page_title="DAB Consults ChatBot", page_icon=":robot_face:", layout="wide")

# Custom CSS to enhance the UI design
st.markdown(
    """
    <style>
    .main {
        background-color: #e0f7fa;
    }
    .stButton button {
        background-color: #00796b;
        color: white;
        border-radius: 12px;
        padding: 10px 24px;
        font-size: 16px;
        border: none;
    }
    .title {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 20px;
        margin-bottom: 30px;
    }
    .title img {
        height: 60px;
    }
    .title h1 {
        font-size: 2.5em;
        color: #004d40;
        margin: 0;
    }
    .chat-box {
        background-color: #ffffff;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0px 0px 10px rgba(0,0,0,0.1);
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Load the base64 logo
with open("logo_base64.txt", "r") as file:
    logo_base64 = file.read()

st.markdown(
    f"""
    <div class="title">
        <img src="data:image/png;base64,{logo_base64}" alt="Logo">
        <h1>DAB Consults ChatBot</h1>
    </div>
    """,
    unsafe_allow_html=True
)

def clear_chat_history():
    st.session_state.messages = [{"role": "assistant", "content": "How may I assist you today?"}]
    st.session_state.questions = []
    st.session_state.answers = []
    st.session_state.input = ""
    st.session_state["chat_history"] = []
    st.session_state["conversationId"] = ""
    st.session_state["parentMessageId"] = ""

oauth2 = utils.configure_oauth_component()

if "token" not in st.session_state:
    redirect_uri = f"https://{utils.OAUTH_CONFIG['ExternalDns']}/component/streamlit_oauth.authorize_button/index.html"
    result = oauth2.authorize_button("Connect with Cognito", scope="openid", pkce="S256", redirect_uri=redirect_uri)
    if result and "token" in result:
        st.session_state.token = result.get("token")
        st.session_state["idc_jwt_token"] = utils.get_iam_oidc_token(st.session_state.token["id_token"])
        st.session_state["idc_jwt_token"]["expires_at"] = datetime.now(tz=UTC) + timedelta(seconds=st.session_state["idc_jwt_token"]["expiresIn"])
        st.rerun()
else:
    token = st.session_state["token"]
    refresh_token = token["refresh_token"]
    user_email = jwt.decode(token["id_token"], options={"verify_signature": False})["email"]
    if st.button("Refresh Cognito Token"):
        token = oauth2.refresh_token(token, force=True)
        token["refresh_token"] = refresh_token
        st.session_state.token = token
        st.rerun()

    if "idc_jwt_token" not in st.session_state:
        st.session_state["idc_jwt_token"] = utils.get_iam_oidc_token(token["id_token"])
        st.session_state["idc_jwt_token"]["expires_at"] = datetime.now(UTC) + timedelta(seconds=st.session_state["idc_jwt_token"]["expiresIn"])
    elif st.session_state["idc_jwt_token"]["expires_at"] < datetime.now(UTC):
        try:
            st.session_state["idc_jwt_token"] = utils.refresh_iam_oidc_token(st.session_state["idc_jwt_token"]["refreshToken"])
            st.session_state["idc_jwt_token"]["expires_at"] = datetime.now(UTC) + timedelta(seconds=st.session_state["idc_jwt_token"]["expiresIn"])
        except Exception as e:
            st.error(f"Error refreshing Identity Center token: {e}. Please reload the page.")

col1, col2 = st.columns([1, 1])

with col1:
    st.write("Welcome: ", user_email)
with col2:
    st.button("Clear Chat History", on_click=clear_chat_history)

if "messages" not in st.session_state:
    st.session_state["messages"] = [{"role": "assistant", "content": "How can I help you?"}]
if "conversationId" not in st.session_state:
    st.session_state["conversationId"] = ""
if "parentMessageId" not in st.session_state:
    st.session_state["parentMessageId"] = ""
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []
if "questions" not in st.session_state:
    st.session_state.questions = []
if "answers" not in st.session_state:
    st.session_state.answers = []
if "input" not in st.session_state:
    st.session_state.input = ""

st.markdown('<div class="chat-box">', unsafe_allow_html=True)

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

st.markdown('</div>', unsafe_allow_html=True)

if prompt := st.chat_input():
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

if st.session_state.messages[-1]["role"] != "assistant":
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            placeholder = st.empty()
            response = utils.get_queue_chain(prompt, st.session_state["conversationId"], st.session_state["parentMessageId"], st.session_state["idc_jwt_token"]["idToken"])
            if "references" in response:
                full_response = f"""{response["answer"]}\n\n---\n{response["references"]}"""
            else:
                full_response = f"""{response["answer"]}\n\n---\nNo sources"""
            placeholder.markdown(full_response)
            st.session_state["conversationId"] = response["conversationId"]
            st.session_state["parentMessageId"] = response["parentMessageId"]

    st.session_state.messages.append({"role": "assistant", "content": full_response})
    feedback = streamlit_feedback(
        feedback_type="thumbs",
        optional_text_label="[Optional] Please provide an explanation",
    )
