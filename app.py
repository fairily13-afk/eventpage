import base64
import os

import markdown
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

st.set_page_config(page_title="AI 맞춤 여행 코스 제작", page_icon="🧳", layout="centered")

BG_COLOR = "#FFF6F0"
ACCENT = "#FF6F61"
ACCENT_SOFT = "#FFB74D"

st.markdown(
    f"""
    <style>
    .stApp {{
        background-color: {BG_COLOR};
    }}
    .stButton > button {{
        background-color: {ACCENT};
        color: white;
        border: none;
        font-weight: 600;
    }}
    .stButton > button:hover {{
        background-color: {ACCENT_SOFT};
        color: white;
    }}
    .ai-course-body h1, .ai-course-body h2, .ai-course-body h3 {{
        color: {ACCENT};
        font-size: 16px;
        margin: 18px 0 6px;
    }}
    .ai-course-body h1:first-child, .ai-course-body h2:first-child, .ai-course-body h3:first-child {{
        margin-top: 0;
    }}
    .ai-course-body strong {{
        color: #1a1a1a;
    }}
    .ai-course-body ul, .ai-course-body ol {{
        margin: 4px 0 12px;
        padding-left: 20px;
    }}
    .ai-course-body li {{
        margin-bottom: 4px;
    }}
    .ai-course-body p {{
        margin: 0 0 10px;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🧳 AI 맞춤 여행 코스 제작")
st.caption("몇 가지만 선택하면 나만의 여행 코스를 만들어드려요")

st.divider()

destination = st.text_input("여행지", placeholder="예: 제주도, 오사카, 파리")

date_range = st.date_input("일정", value=[])

companion = st.radio(
    "동행자",
    ["혼자", "커플", "친구", "가족"],
    horizontal=True,
)

budget = st.selectbox(
    "예산",
    ["10만원 이하", "10~30만원", "30~50만원", "50만원 이상"],
)

travel_style = st.multiselect(
    "여행 스타일",
    ["힐링", "액티비티", "맛집 탐방", "감성 사진", "쇼핑", "문화·역사"],
)

transportation = st.multiselect(
    "이동수단",
    ["도보", "대중교통", "렌터카", "택시"],
)

st.divider()

TONE_KEYWORDS = ["감성적", "친근한", "청량한", "설레는", "직관적인", "개인 맞춤형"]


def build_prompt():
    start, end = (list(date_range) + [None, None])[:2]
    period = f"{start} ~ {end}" if start and end else "미정"

    return f"""
아래 조건에 맞는 맞춤 여행 코스를 만들어줘.

- 여행지: {destination or "미정"}
- 일정: {period}
- 동행자: {companion}
- 예산: {budget}
- 여행 스타일: {", ".join(travel_style) if travel_style else "미정"}
- 이동수단: {", ".join(transportation) if transportation else "미정"}

톤앤매너: {", ".join(TONE_KEYWORDS)}
위 톤앤매너 키워드를 반영해서, 여행을 준비하는 순간부터 설렘을 느낄 수 있도록
친근하고 이해하기 쉬운 말투로 작성해줘.
""".strip()


def build_image_prompt():
    return f"""
{destination or "여행지"}로 떠나는 {companion} 여행을 표현하는 이미지.
여행 스타일: {", ".join(travel_style) if travel_style else "미정"}
이동수단: {", ".join(transportation) if transportation else "미정"}
분위기: {", ".join(TONE_KEYWORDS)}
""".strip()


def generate_result(prompt):
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.responses.create(
        model="gpt-4o-mini",
        input=prompt,
    )
    return response.output_text


def generate_image(prompt):
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        size="1024x1024",
    )
    return base64.b64decode(response.data[0].b64_json)


def render_result_card(result_text, image_bytes):
    if image_bytes:
        image_b64 = base64.b64encode(image_bytes).decode()
        image_html = f'<img src="data:image/png;base64,{image_b64}" style="width:100%; border-radius:14px; margin-bottom:16px;" />'
    else:
        image_html = """
            <div style="
                width:100%; height:200px; border-radius:14px; margin-bottom:16px;
                background:#FFF6F0; display:flex; align-items:center; justify-content:center;
                color:#aaa; font-size:13px;
            ">🖼️ 이미지를 불러오지 못했어요</div>
        """
    text_html = markdown.markdown(result_text, extensions=["nl2br"])
    hashtags = " ".join(
        f"#{tag}" for tag in [destination, companion, "설레는여행", "AI맞춤코스"] if tag
    )
    place = destination or "그곳"
    subtitle = f"✨ {place}(으)로 떠나는 {companion} 여행, 설레는 나만의 이야기"

    st.markdown(
        f"""
        <div style="
            border: 1px solid rgba(0,0,0,0.08);
            border-radius: 20px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.10);
            padding: 24px;
            margin-top: 20px;
            background: #ffffff;
        ">
            <div style="display:flex; align-items:center; gap:10px; margin-bottom:16px;">
                <span style="font-size:26px;">🧳</span>
                <div>
                    <div style="font-weight:700; font-size:16px; color:#1a1a1a;">AI 맞춤 여행 코스</div>
                    <div style="font-size:13px; color:#888;">{subtitle}</div>
                </div>
            </div>
            {image_html}
            <div class="ai-course-body" style="font-size:14px; line-height:1.7; color:#333;">{text_html}</div>
            <div style="margin-top:18px; padding-top:14px; border-top:1px dashed rgba(0,0,0,0.12); font-size:13px; color:{ACCENT};">
                🗺️ {hashtags}
            </div>
            <div style="margin-top:16px; display:flex; gap:10px;">
                <button style="flex:1; padding:10px; border-radius:10px; border:none; background:{ACCENT}; color:white; font-weight:600;">💾 저장</button>
                <button style="flex:1; padding:10px; border-radius:10px; border:1px solid {ACCENT_SOFT}; background:white; color:{ACCENT};">📤 공유</button>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


if "generating" not in st.session_state:
    st.session_state.generating = False


def _trigger_generate():
    st.session_state.generating = True


st.button("결과 보기", use_container_width=True, on_click=_trigger_generate)

if st.session_state.generating:
    prompt = build_prompt()

    with st.spinner("여행 코스를 만들고 있어요..."):
        result_text = generate_result(prompt)

    image_prompt = build_image_prompt()

    with st.spinner("이미지를 만들고 있어요..."):
        try:
            image_bytes = generate_image(image_prompt)
        except Exception:
            image_bytes = None

    render_result_card(result_text, image_bytes)

    st.button("다시 생성", use_container_width=True, on_click=_trigger_generate)
