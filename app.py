import base64
import io
import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

import markdown
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
from openai import OpenAI
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.pdfmetrics import registerFont
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

load_dotenv()

PDF_FONT = "HYGothic-Medium"
registerFont(UnicodeCIDFont(PDF_FONT))

DB_PATH = Path(__file__).parent / "shared_results.db"


def _get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS shared_results (
            id TEXT PRIMARY KEY,
            destination TEXT,
            companion TEXT,
            result_text TEXT NOT NULL,
            image_png BLOB,
            created_at TEXT NOT NULL
        )
        """
    )
    return conn


def save_shared_result(destination, companion, result_text, image_bytes):
    share_id = uuid.uuid4().hex[:10]
    conn = _get_db_connection()
    with conn:
        conn.execute(
            "INSERT INTO shared_results (id, destination, companion, result_text, image_png, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (share_id, destination, companion, result_text, image_bytes, datetime.now(timezone.utc).isoformat()),
        )
    conn.close()
    return share_id


def load_shared_result(share_id):
    conn = _get_db_connection()
    row = conn.execute(
        "SELECT destination, companion, result_text, image_png FROM shared_results WHERE id = ?",
        (share_id,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    destination, companion, result_text, image_png = row
    return {
        "destination": destination,
        "companion": companion,
        "result_text": result_text,
        "image_bytes": image_png,
    }


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


def _inline_markdown_to_pdf_markup(text):
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
    return text


def build_pdf(result_text, image_bytes, destination, companion, hashtags):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "KTitle", parent=styles["Title"], fontName=PDF_FONT, fontSize=20,
        textColor=colors.HexColor(ACCENT), alignment=TA_CENTER,
    )
    subtitle_style = ParagraphStyle(
        "KSubtitle", parent=styles["Normal"], fontName=PDF_FONT, fontSize=11,
        textColor=colors.HexColor("#888888"), alignment=TA_CENTER, spaceAfter=14,
    )
    heading_style = ParagraphStyle(
        "KHeading", parent=styles["Heading2"], fontName=PDF_FONT, fontSize=14,
        textColor=colors.HexColor(ACCENT), spaceBefore=12, spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "KBody", parent=styles["Normal"], fontName=PDF_FONT, fontSize=10.5,
        leading=16, spaceAfter=6,
    )
    bullet_style = ParagraphStyle("KBullet", parent=body_style, leftIndent=12)
    hashtag_style = ParagraphStyle(
        "KHashtag", parent=styles["Normal"], fontName=PDF_FONT, fontSize=9.5,
        textColor=colors.HexColor(ACCENT), spaceBefore=14,
    )

    place = destination or "그곳"
    story = [
        Paragraph("AI 맞춤 여행 코스", title_style),
        Paragraph(f"{place}(으)로 떠나는 {companion} 여행, 설레는 나만의 이야기", subtitle_style),
    ]

    if image_bytes:
        story.append(RLImage(io.BytesIO(image_bytes), width=150 * mm, height=150 * mm))
        story.append(Spacer(1, 10 * mm))

    for raw_line in result_text.splitlines():
        line = raw_line.strip()
        if not line:
            story.append(Spacer(1, 4 * mm))
        elif line.startswith("#"):
            story.append(Paragraph(_inline_markdown_to_pdf_markup(line.lstrip("#").strip()), heading_style))
        elif line.startswith(("-", "*", "•")):
            item_text = line.lstrip("-*• ").strip()
            story.append(Paragraph(f"• {_inline_markdown_to_pdf_markup(item_text)}", bullet_style))
        else:
            story.append(Paragraph(_inline_markdown_to_pdf_markup(line), body_style))

    if hashtags:
        story.append(Paragraph(_inline_markdown_to_pdf_markup(hashtags), hashtag_style))

    doc.build(story)
    return buffer.getvalue()


def render_share_button(subtitle, hashtags, image_bytes, share_url):
    share_text = f"{subtitle}\n\n{hashtags}"
    share_text_js = json.dumps(share_text)
    image_b64_js = json.dumps(base64.b64encode(image_bytes).decode()) if image_bytes else "null"
    share_url_js = json.dumps(share_url) if share_url else "null"

    html = f"""
    <div style="width:100%; font-family: 'Source Sans Pro', sans-serif;">
      <button id="share-btn" style="
          width:100%; padding:10px; border-radius:10px; border:1px solid {ACCENT_SOFT};
          background:white; color:{ACCENT}; font-weight:600;
          font-size:14px; cursor:pointer;
      ">📤 공유</button>
      <div id="share-msg" style="margin-top:6px; font-size:12px; color:#888; text-align:center;"></div>
    </div>
    <script>
      const shareText = {share_text_js};
      const imageB64 = {image_b64_js};
      const shareUrl = {share_url_js};
      const btn = document.getElementById('share-btn');
      const msg = document.getElementById('share-msg');

      function b64ToBlob(b64) {{
        const byteChars = atob(b64);
        const byteNumbers = new Array(byteChars.length);
        for (let i = 0; i < byteChars.length; i++) {{
          byteNumbers[i] = byteChars.charCodeAt(i);
        }}
        return new Blob([new Uint8Array(byteNumbers)], {{ type: 'image/png' }});
      }}

      btn.addEventListener('click', async () => {{
        msg.textContent = '';
        const shareData = {{ title: 'AI 맞춤 여행 코스', text: shareText }};
        if (shareUrl) {{
          shareData.url = shareUrl;
        }}
        const fallbackText = shareUrl ? (shareText + '\\n' + shareUrl) : shareText;
        try {{
          if (imageB64 && navigator.canShare) {{
            const file = new File([b64ToBlob(imageB64)], 'travel-course.png', {{ type: 'image/png' }});
            if (navigator.canShare({{ files: [file] }})) {{
              shareData.files = [file];
            }}
          }}
          if (navigator.share) {{
            await navigator.share(shareData);
            msg.textContent = '공유되었습니다.';
          }} else {{
            throw new Error('no-share-api');
          }}
        }} catch (err) {{
          if (err && err.name === 'AbortError') {{
            // 사용자가 공유를 취소함
          }} else {{
            try {{
              await navigator.clipboard.writeText(fallbackText);
              msg.textContent = '이 브라우저는 공유를 지원하지 않아 텍스트를 클립보드에 복사했어요.';
            }} catch (clipErr) {{
              msg.textContent = '공유에 실패했어요. 다시 시도해주세요.';
            }}
          }}
        }}
      }});
    </script>
    """
    components.html(html, height=70)


def render_result_card(result_text, image_bytes, destination, companion, share_id):
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
        </div>
        """,
        unsafe_allow_html=True,
    )

    pdf_bytes = build_pdf(result_text, image_bytes, destination, companion, hashtags)
    base_url = st.context.url or ""
    share_url = f"{base_url}?share_id={share_id}" if base_url and share_id else None

    save_col, share_col = st.columns(2)
    with save_col:
        st.download_button(
            "💾 저장 (PDF)",
            data=pdf_bytes,
            file_name=f"{destination or '여행코스'}_AI맞춤여행코스.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    with share_col:
        render_share_button(subtitle, hashtags, image_bytes, share_url)

    if share_url:
        st.caption("🔗 아래 링크를 복사해서 친구에게 공유해보세요")
        st.code(share_url, language=None)


st.title("🧳 AI 맞춤 여행 코스 제작")
st.caption("몇 가지만 선택하면 나만의 여행 코스를 만들어드려요")

st.divider()

shared_id_param = st.query_params.get("share_id")
if shared_id_param:
    shared = load_shared_result(shared_id_param)
    base_url = st.context.url or ""
    if shared:
        st.info("📎 친구가 공유한 여행 코스예요")
        render_result_card(
            shared["result_text"],
            shared["image_bytes"],
            shared["destination"],
            shared["companion"],
            shared_id_param,
        )
        if base_url:
            st.link_button("✨ 나도 만들기", url=base_url, use_container_width=True)
    else:
        st.warning("공유 링크를 찾을 수 없거나 삭제됐어요.")
        if base_url:
            st.link_button("🏠 홈으로", url=base_url, use_container_width=True)
    st.stop()

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

if "generating" not in st.session_state:
    st.session_state.generating = False
if "result" not in st.session_state:
    st.session_state.result = None


def _trigger_generate():
    st.session_state.generating = True
    st.session_state.result = None


st.button("결과 보기", use_container_width=True, on_click=_trigger_generate)

if st.session_state.generating and st.session_state.result is None:
    prompt = build_prompt()

    with st.spinner("여행 코스를 만들고 있어요..."):
        result_text = generate_result(prompt)

    image_prompt = build_image_prompt()

    with st.spinner("이미지를 만들고 있어요..."):
        try:
            image_bytes = generate_image(image_prompt)
        except Exception:
            image_bytes = None

    share_id = save_shared_result(destination, companion, result_text, image_bytes)
    st.session_state.result = {
        "text": result_text,
        "image": image_bytes,
        "destination": destination,
        "companion": companion,
        "share_id": share_id,
    }

if st.session_state.result:
    r = st.session_state.result
    render_result_card(r["text"], r["image"], r["destination"], r["companion"], r["share_id"])

    st.button("다시 생성", use_container_width=True, on_click=_trigger_generate)
