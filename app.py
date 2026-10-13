import streamlit as st
import re

st.set_page_config(
    page_title="Movie Recap Myanmar",
    page_icon="🎬",
    layout="centered"
)

st.title("🎬 Movie Recap Myanmar")
st.write("အခမဲ့ Movie Recap App")

st.info(
    "YouTube Link ထည့်နိုင်သလို "
    "ကိုယ်ပိုင် Video ကိုလည်း Upload လုပ်နိုင်ပါတယ်။"
)

st.header("1. YouTube Link")

youtube_url = st.text_input(
    "YouTube Video Link ထည့်ပါ",
    placeholder="https://www.youtube.com/watch?v=..."
)

if youtube_url:
    if "youtube.com" in youtube_url or "youtu.be" in youtube_url:
        st.success("YouTube Link ထည့်ပြီးပါပြီ။")
    else:
        st.error("YouTube Link မှန်ကန်မှုကို စစ်ဆေးပါ။")

st.header("2. Video Upload")

video_file = st.file_uploader(
    "ကိုယ်ပိုင် Video ရွေးပါ",
    type=["mp4", "mov", "m4v"]
)

if video_file:
    st.success("Video Upload လုပ်ပြီးပါပြီ။")
    st.video(video_file)

st.header("3. Recap အချိန်")

recap_minutes = st.selectbox(
    "Recap Video အချိန်ရွေးပါ",
    [1, 2, 3, 4, 5]
)

st.write(f"ရွေးချယ်ထားသော အချိန် — {recap_minutes} မိနစ်")

st.header("4. Recap Script")

script = st.text_area(
    "Recap ပြောမည့် စာသား",
    placeholder="ဒီနေရာမှာ Recap စာသား ထည့်ပါ...",
    height=200
)

voice = st.selectbox(
    "Narration ဘာသာစကား",
    ["မြန်မာ", "English"]
)

subtitle = st.selectbox(
    "Subtitle ဘာသာစကား",
    ["မြန်မာ", "English"]
)

if st.button("Recap အချက်အလက် စစ်ဆေးမယ်"):
    if not youtube_url and not video_file:
        st.error("YouTube Link သို့မဟုတ် Video တစ်ခု ထည့်ပါ။")
    elif not script.strip():
        st.warning(
            "Recap Script မထည့်ရသေးပါ။ "
            "ပထမဆုံး စာသားထည့်ပြီး ဆက်လုပ်ပါ။"
        )
    else:
        st.success("အချက်အလက်များ အသင့်ဖြစ်ပါပြီ။")
        st.write("Recap အချိန်:", recap_minutes, "မိနစ်")
        st.write("Narration:", voice)
        st.write("Subtitle:", subtitle)
        st.subheader("Recap Script Preview")
        st.write(script)

st.caption(
    "ဒီဗားရှင်းက အခြေခံ UI ဖြစ်ပါတယ်။ "
    "Video Recap ထုတ်လုပ်ခြင်း၊ အသံထည့်ခြင်းနှင့် "
    "Subtitle ဖန်တီးခြင်းတို့ကို နောက်အဆင့်များတွင် ထည့်သွင်းရပါမယ်။"
)
