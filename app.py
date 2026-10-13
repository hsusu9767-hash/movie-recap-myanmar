
import asyncio
import re
import subprocess
import tempfile
from pathlib import Path

import streamlit as st
from youtube_transcript_api import YouTubeTranscriptApi

st.set_page_config(
    page_title="Movie Recap Myanmar",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 Movie Recap Myanmar")
st.write("YouTube Transcript • Recap • AI Voice • Subtitles • MP4")

st.info(
    "Free version: no paid AI API key required. "
    "YouTube video ကို Preview ကြည့်နိုင်ပြီး Transcript ရနိုင်လျှင် "
    "Recap Script ပြင်ဆင်နိုင်ပါတယ်။ Video ထုတ်လုပ်ရန် ကိုယ်ပိုင် "
    "သို့မဟုတ် အသုံးပြုခွင့်ရှိတဲ့ Video ဖိုင်ကို တင်ပါ။"
)

# -------------------------------
# Helper functions
# -------------------------------

def get_video_id(url):
    patterns = [
        r"(?:youtube\.com/watch\?.*?v=)([A-Za-z0-9_-]{11})",
        r"(?:youtu\.be/)([A-Za-z0-9_-]{11})",
        r"(?:youtube\.com/shorts/)([A-Za-z0-9_-]{11})",
        r"(?:youtube\.com/embed/)([A-Za-z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def get_transcript(video_id, language_code):
    transcript = YouTubeTranscriptApi().fetch(
        video_id,
        languages=[language_code, "en"]
    )
    return " ".join(
        item.text for item in transcript
    )


def make_recap(text, max_words=650):
    """Create an extractive draft without a paid AI API."""
    text = re.sub(r"\s+", " ", text).strip()
    sentences = re.split(r"(?<=[.!?။])\s+", text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return text[:max_words * 8]

    if len(text.split()) <= max_words:
        return "\n\n".join(sentences)

    # Select sentences from across the transcript.
    selected = []
    total_words = 0
    step = max(1, len(sentences) // 80)

    for i in range(0, len(sentences), step):
        sentence = sentences[i]
        count = len(sentence.split())
        if total_words + count <= max_words:
            selected.append(sentence)
            total_words += count

    return "\n\n".join(selected)


def parse_seconds(value):
    value = str(value).strip()
    if not value:
        return None

    if re.fullmatch(r"\d+(\.\d+)?", value):
        return float(value)

    parts = value.split(":")
    try:
        numbers = [float(p) for p in parts]
        if len(numbers) == 2:
            return numbers[0] * 60 + numbers[1]
        if len(numbers) == 3:
            return (
                numbers[0] * 3600
                + numbers[1] * 60
                + numbers[2]
            )
    except ValueError:
        pass

    raise ValueError(
        "Time ကို seconds, MM:SS သို့မဟုတ် HH:MM:SS ပုံစံနဲ့ ထည့်ပါ။"
    )


def timestamp(seconds):
    ms = max(0, int(seconds * 1000))
    hours, ms = divmod(ms, 3600000)
    minutes, ms = divmod(ms, 60000)
    seconds, ms = divmod(ms, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{ms:03}"


def create_srt(text, duration):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""

    interval = max(1, duration / len(lines))
    result = []

    for i, line in enumerate(lines):
        start = i * interval
        end = min(duration, (i + 1) * interval)
        if end <= start:
            end = start + 1

        result.append(
            f"{i + 1}\n"
            f"{timestamp(start)} --> {timestamp(end)}\n"
            f"{line}"
        )

    return "\n\n".join(result) + "\n"


async def generate_tts(text, voice, output_path):
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(output_path))


def run_ffmpeg(args):
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
        + args,
        capture_output=True,
        text=True,
        timeout=900
    )

    if result.returncode != 0:
        raise RuntimeError(
            (result.stderr or "FFmpeg export failed")[-2500:]
        )


def get_duration(video_path):
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path)
        ],
        capture_output=True,
        text=True,
        timeout=30
    )
    if result.returncode != 0:
        return None

    try:
        return float(result.stdout.strip())
    except ValueError:
        return None



# -------------------------------
# 1. YouTube link and transcript
# -------------------------------

st.header("1. YouTube Video")

youtube_url = st.text_input(
    "YouTube Link Paste လုပ်ပါ",
    placeholder="https://www.youtube.com/watch?v=..."
)

col_a, col_b = st.columns(2)

with col_a:
    if st.button("▶️ Preview YouTube", use_container_width=True):
        video_id = get_video_id(youtube_url.strip())

        if video_id:
            st.session_state["youtube_id"] = video_id
        else:
            st.error("YouTube Link မှန်ကန်စွာ ထည့်ပါ။")

with col_b:
    if st.button(
        "🌍 ဗီဒီယိုဘာသာစကားအားလုံး ရှာပါ",
        use_container_width=True
    ):
        video_id = get_video_id(youtube_url.strip())

        if not video_id:
            st.error("YouTube Link မှန်ကန်စွာ ထည့်ပါ။")
        else:
            try:
                with st.spinner("ဘာသာစကားစာရင်း ရှာနေပါတယ်..."):
                    transcripts = list(
                        YouTubeTranscriptApi().list(video_id)
                    )

                    options = []
                    seen_codes = set()

                    # Original transcript languages
                    for item in transcripts:
                        code = item.language_code

                        if code not in seen_codes:
                            generated = (
                                " (Auto-generated)"
                                if item.is_generated else ""
                            )

                            options.append({
                                "label": (
                                    f"{item.language} [{code}]"
                                    f"{generated}"
                                ),
                                "code": code,
                                "source_code": code,
                                "translated": False
                            })

                            seen_codes.add(code)

                    # YouTube-supported translated languages
                    for item in transcripts:
                        if not item.is_translatable:
                            continue

                        for target in item.translation_languages:
                            code = target["language_code"]

                            if code not in seen_codes:
                                options.append({
                                    "label": (
                                        f"{target['language']} [{code}]"
                                        f" — Auto-translated"
                                    ),
                                    "code": code,
                                    "source_code": item.language_code,
                                    "translated": True
                                })

                                seen_codes.add(code)

                    st.session_state["transcript_languages"] = options
                    st.session_state["language_video_id"] = video_id

                if options:
                    st.success(
                        f"ဘာသာစကား {len(options)} မျိုး ရရှိပါတယ်။"
                    )
                else:
                    st.warning(
                        "ဒီဗီဒီယိုမှာ ရနိုင်တဲ့ Transcript "
                        "ဘာသာစကား မတွေ့ပါ။"
                    )

            except Exception as error:
                st.error(
                    "ဘာသာစကားစာရင်း ရယူမရပါ။ "
                    "ဒီဗီဒီယိုမှာ Transcript မရှိနိုင်ပါ။"
                )
                st.caption(str(error)[:500])

if "youtube_id" in st.session_state:
    st.video(
        "https://www.youtube.com/watch?v="
        + st.session_state["youtube_id"]
    )

# Select a language from available captions/translations
language_options = st.session_state.get(
    "transcript_languages", []
)

if language_options:
    st.subheader("🌐 Video Transcript Language")

    selected_language = st.selectbox(
        "ဗီဒီယိုရဲ့ ဘာသာစကား ရွေးပါ",
        options=language_options,
        format_func=lambda item: item["label"]
    )

    if st.button("📝 Get Transcript", use_container_width=True):
        video_id = st.session_state.get("language_video_id")

        try:
            with st.spinner("Transcript ရယူနေပါတယ်..."):
                text = get_transcript(
                    video_id,
                    selected_language
                )

            st.session_state["transcript"] = text
            st.success("Transcript ရရှိပါပြီ။")

        except Exception as error:
            st.error(
                "ဒီဘာသာစကားနဲ့ Transcript ရယူမရပါ။ "
                "အခြားဘာသာစကားကို ရွေးပြီး ထပ်စမ်းပါ။"
            )
            st.caption(str(error)[:500])
    
voice_options = {
    "မြန်မာ - Nilar (Female)": "my-MM-NilarNeural",
    "မြန်မာ - Thiha (Male)": "my-MM-ThihaNeural",
    "English - Aria (Female)": "en-US-AriaNeural",
    "English - Guy (Male)": "en-US-GuyNeural",
    "English - Jenny (Female)": "en-US-JennyNeural",
}

voice_name = st.selectbox(
    "အသံရွေးပါ",
    list(voice_options.keys())
)

st.caption(
    "Edge TTS သည် အင်တာနက်လိုအပ်ပါတယ်။ ရွေးထားတဲ့အသံ "
    "မရနိုင်ပါက အခြားအသံကို စမ်းပါ။"
)

st.header("4. Subtitles")

subtitle_language = st.selectbox(
    "Subtitle Language",
    ["မြန်မာ", "English", "အခြားဘာသာစကား"]
)

subtitle_text = st.text_area(
    "Subtitle စာသား (တစ်ကြောင်းစီရေးပါ)",
    placeholder="ပထမစာကြောင်း\nဒုတိယစာကြောင်း\nတတိယစာကြောင်း",
    height=140
)

# -------------------------------
# 5. Export settings
# -------------------------------

st.header("5. Video Export")

video_file = st.file_uploader(
    "ကိုယ်ပိုင် သို့မဟုတ် ခွင့်ပြုချက်ရှိတဲ့ Video ဖိုင်တင်ပါ",
    type=["mp4", "mov", "mkv", "webm"]
)

audio_file = st.file_uploader(
    "ရှိပြီးသား Narration အသံဖိုင် (optional)",
    type=["mp3", "wav", "m4a", "aac", "ogg"]
)

start_text = st.text_input(
    "Clip Start (seconds or MM:SS)",
    value="0"
)

end_text = st.text_input(
    "Clip End (seconds or MM:SS)",
    value="300"
)

keep_original_audio = st.checkbox(
    "Narration မထည့်လျှင် မူရင်းအသံကို ထားမယ်",
    value=True
)

embed_subtitles = st.checkbox(
    "SRT ကို MP4 ထဲမှာ selectable subtitle track အဖြစ် ထည့်မယ်",
    value=True
)

st.caption(
    "YouTube URL ကို Preview/Transcript အတွက် အသုံးပြုနိုင်ပါတယ်။ "
    "ဒီ App က URL တစ်ခုတည်းကနေ YouTube ဗီဒီယိုကို "
    "Download မလုပ်ပါ။ Export အတွက် အပေါ်မှာ Video ဖိုင်တင်ပါ။"
)

if st.button("🎬 Generate Narration + MP4 + SRT", type="primary"):
    if not video_file:
        st.error("Export လုပ်ဖို့ Video ဖိုင်တင်ပါ။")
        st.stop()

    if not recap_script.strip() and not audio_file:
        st.error("Recap Script ရေးပါ၊ သို့မဟုတ် Narration Audio တင်ပါ။")
        st.stop()

    try:
        start_seconds = parse_seconds(start_text)
        end_seconds = parse_seconds(end_text)

        if start_seconds is None or start_seconds < 0:
            raise ValueError("Clip Start ကို မှန်ကန်စွာ ထည့်ပါ။")

        if end_seconds is not None and end_seconds <= start_seconds:
            raise ValueError("Clip End သည် Clip Start ထက် ကြီးရပါမယ်။")

        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            video_path = work / ("source" + Path(video_file.name).suffix.lower())
            video_path.write_bytes(video_file.getvalue())

            source_duration = get_duration(video_path)

            if end_seconds is None:
                if source_duration is None:
                    raise ValueError("Video ကြာချိန်ကို မသိနိုင်ပါ။ Clip End ထည့်ပါ။")
                end_seconds = source_duration

            if source_duration and end_seconds > source_duration:
                end_seconds = source_duration

            clip_duration = end_seconds - start_seconds
            if clip_duration <= 0:
                raise ValueError("Video Clip ကြာချိန် မမှန်ပါ။")

            audio_path = None

            if audio_file:
                audio_path = work / (
                    "narration" + Path(audio_file.name).suffix.lower()
                )
                audio_path.write_bytes(audio_file.getvalue())
            elif recap_script.strip():
                audio_path = work / "narration.mp3"
                with st.spinner("Narration အသံထုတ်နေပါတယ်..."):
                    asyncio.run(
                        generate_tts(
                            recap_script.strip(),
                            voice_options[voice_name],
                            audio_path
                        )
                    )

            srt_content = create_srt(
                subtitle_text,
                clip_duration
            )

            srt_path = work / "subtitles.srt"
            if srt_content:
                srt_path.write_text(
                    srt_content,
                    encoding="utf-8-sig"
                )

            output_path = work / "movie_recap.mp4"

            ffmpeg_args = [
                "-ss", str(start_seconds),
                "-i", str(video_path)
            ]

            if audio_path:
                ffmpeg_args += ["-i", str(audio_path)]

            subtitle_input_index = None
            if srt_content and embed_subtitles:
                subtitle_input_index = 2 if audio_path else 1
                ffmpeg_args += ["-i", str(srt_path)]

            ffmpeg_args += ["-t", str(clip_duration), "-map", "0:v:0"]

            if audio_path:
                ffmpeg_args += ["-map", "1:a:0"]
            elif keep_original_audio:
                ffmpeg_args += ["-map", "0:a?"]
            else:
                ffmpeg_args += ["-an"]

            if subtitle_input_index is not None:
                ffmpeg_args += [
                    "-map", f"{subtitle_input_index}:s:0"
                ]

            ffmpeg_args += [
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", "26"
            ]

            if audio_path or keep_original_audio:
                ffmpeg_args += [
                    "-c:a", "aac",
                    "-b:a", "128k",
                    "-shortest"
                ]

            if subtitle_input_index is not None:
                ffmpeg_args += [
                    "-c:s", "mov_text"
                ]

            ffmpeg_args += [
                "-movflags", "+faststart",
                str(output_path)
            ]

            with st.spinner("MP4 ဖန်တီးနေပါတယ်..."):
                run_ffmpeg(ffmpeg_args)

            st.success("Video ဖန်တီးပြီးပါပြီ။")

            st.subheader("🎞️ Recap Preview")
            st.video(output_path.read_bytes())

            st.download_button(
                "⬇️ Download MP4",
                data=output_path.read_bytes(),
                file_name="movie_recap.mp4",
                mime="video/mp4",
                use_container_width=True
            )

            if srt_content:
                st.download_button(
                    "⬇️ Download SRT",
                    data=srt_content.encode("utf-8-sig"),
                    file_name="subtitles.srt",
                    mime="application/x-subrip",
                    use_container_width=True
                )

            if audio_path:
                st.download_button(
                    "⬇️ Download Narration Audio",
                    data=audio_path.read_bytes(),
                    file_name="narration" + audio_path.suffix,
                    mime="application/octet-stream",
                    use_container_width=True
                )

    except Exception as error:
        st.error("Video ထုတ်လုပ်ရာမှာ အမှားဖြစ်နေပါတယ်။")
        st.code(str(error)[:2500])
        st.info(
            "Video ဖိုင်အရွယ်အစား လျှော့ကြည့်ပါ။ "
            "FFmpeg တပ်ဆင်ထားခြင်းနဲ့ TTS အင်တာနက်ချိတ်ဆက်မှုကို စစ်ပါ။"
        )
