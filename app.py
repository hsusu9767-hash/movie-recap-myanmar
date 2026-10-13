import streamlit as st
import re
import os
import shutil
import tempfile
import subprocess
import asyncio
from pathlib import Path
import edge_tts
from youtube_transcript_api import YouTubeTranscriptApi

st.set_page_config(
    page_title="Movie Recap Myanmar",
    page_icon="🎬"
)

st.title("🎬 Movie Recap Myanmar")
st.write("အခမဲ့ Movie Recap ဖန်တီးရေး App")

st.warning(
    "YouTube Link မှ Video ကို download မလုပ်ပါ။ "
    "Transcript ရရှိလျှင် Recap Script ဖန်တီးပေးနိုင်ပါတယ်။ "
    "MP4 ဖန်တီးရန် ကိုယ်ပိုင် သို့မဟုတ် တည်းဖြတ်ခွင့်ရှိသော Video ကို Upload လုပ်ပါ။"
)

def get_video_id(url):
    patterns = [
        r"(?:youtube\.com/watch\?v=)([A-Za-z0-9_-]{11})",
        r"(?:youtu\.be/)([A-Za-z0-9_-]{11})",
        r"(?:youtube\.com/shorts/)([A-Za-z0-9_-]{11})",
        r"(?:youtube\.com/embed/)([A-Za-z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def get_transcript(url):
    video_id = get_video_id(url)
    if not video_id:
        raise ValueError("YouTube Link မှန်ကန်မှုကို စစ်ဆေးပါ။")

    api = YouTubeTranscriptApi()
    transcript_list = api.list(video_id)

    for language in ["my", "en"]:
        try:
            transcript = transcript_list.find_transcript([language])
            return " ".join(
                item.text for item in transcript.fetch()
            )
        except Exception:
            continue

    transcript = next(iter(transcript_list))
    return " ".join(
        item.text for item in transcript.fetch()
    )

def make_recap(text, minutes):
    text = re.sub(r"\s+", " ", text).strip()
    sentences = re.split(r"(?<=[.!?။])\s+", text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]

    if not sentences:
        return " ".join(text.split()[:minutes * 125])

    target_words = minutes * 125
    average = max(
        1,
        sum(len(s.split()) for s in sentences) // len(sentences)
    )
    count = max(1, min(len(sentences), target_words // average))

    if count == 1:
        return sentences[0]

    indexes = sorted(set(
        round(i * (len(sentences) - 1) / (count - 1))
        for i in range(count)
    ))

    selected = [sentences[i] for i in indexes]
    result = []
    words = 0

    for sentence in selected:
        length = len(sentence.split())
        if words + length > target_words and result:
            break
        result.append(sentence)
        words += length

    return " ".join(result)

def run_command(args):
    result = subprocess.run(
        args,
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        raise RuntimeError(
            (result.stderr or "Video processing failed")[-2000:]
        )

def video_duration(path):
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path)
        ],
        capture_output=True,
        text=True,
        check=True
    )
    return float(result.stdout.strip())

def timestamp(seconds):
    milliseconds = int(seconds * 1000)
    hours, milliseconds = divmod(milliseconds, 3600000)
    minutes, milliseconds = divmod(milliseconds, 60000)
    seconds, milliseconds = divmod(milliseconds, 1000)
    return (
        f"{hours:02}:{minutes:02}:"
        f"{seconds:02},{milliseconds:03}"
    )

def create_srt(text, duration, path):
    sentences = [
        s.strip()
        for s in re.split(r"(?<=[.!?။])\s+", text)
        if s.strip()
    ]

    if not sentences:
        sentences = [text.strip()] if text.strip() else []

    total_words = sum(
        max(1, len(sentence.split()))
        for sentence in sentences
    ) or 1

    current_time = 0
    output = []

    for index, sentence in enumerate(sentences, start=1):
        sentence_words = max(1, len(sentence.split()))
        start = current_time
        end = min(
            duration,
            start + duration * sentence_words / total_words
        )
        current_time = end

        if end <= start:
            continue

        output.append(
            f"{index}\n"
            f"{timestamp(start)} --> {timestamp(end)}\n"
            f"{sentence}\n"
        )

    Path(path).write_text(
        "\n".join(output),
        encoding="utf-8"
    )

def make_video(source, script, voice, minutes, folder):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError(
            "FFmpeg မရှိပါ။ packages.txt ကို စစ်ဆေးပါ။"
        )

    duration = video_duration(source)
    target = minutes * 60

    if duration < 5:
        raise RuntimeError("Video က အလွန်တိုနေပါတယ်။")

    clip_count = max(1, min(10, minutes))
    clip_duration = target / clip_count
    max_start = max(0, duration - clip_duration)
    clips = []

    for i in range(clip_count):
        start = (
            max_start * i / max(1, clip_count - 1)
            if clip_count > 1 else 0
        )

        clip = folder / f"clip_{i}.mp4"

        run_command([
            "ffmpeg", "-y",
            "-ss", str(start),
            "-i", str(source),
            "-t", str(clip_duration),
            "-an",
            "-vf",
            "scale=1280:720:force_original_aspect_ratio=decrease,"
            "pad=1280:720:(ow-iw)/2:(oh-ih)/2",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "29",
            "-pix_fmt", "yuv420p",
            str(clip)
        ])

        clips.append(clip)

    concat_file = folder / "concat.txt"
    concat_file.write_text(
        "".join(
            f"file '{clip.as_posix()}'\n"
            for clip in clips
        ),
        encoding="utf-8"
    )

    silent_video = folder / "silent.mp4"

    run_command([
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),
        "-c", "copy",
        str(silent_video)
    ])

    audio = folder / "narration.mp3"

    async def create_audio():
        await edge_tts.Communicate(
            script,
            voice
        ).save(str(audio))

    asyncio.run(create_audio())

    audio_length = video_duration(audio)
    subtitle = folder / "subtitles.srt"

    create_srt(
        script,
        min(audio_length, target),
        subtitle
    )

    output = folder / "movie_recap_myanmar.mp4"

    subtitle_filter_path = str(subtitle).replace(
        "\\", "\\\\"
    ).replace(":", r"\:")

    run_command([
        "ffmpeg", "-y",
        "-i", str(silent_video),
        "-i", str(audio),
        "-vf",
        f"subtitles='{subtitle_filter_path}'",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-af", "apad",
        "-t", str(target),
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "29",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        str(output)
    ])

    return output

st.header("1. YouTube Link")

youtube_url = st.text_input(
    "YouTube URL",
    placeholder="https://www.youtube.com/watch?v=..."
)

if st.button("YouTube Transcript ရယူမယ်"):
    if not youtube_url.strip():
        st.error("YouTube Link ထည့်ပါ။")
    else:
        try:
            with st.spinner("Transcript ရှာနေပါတယ်..."):
                transcript = get_transcript(youtube_url.strip())
                st.session_state["transcript"] = transcript
            st.success("Transcript ရရှိပါပြီ။")
        except Exception as error:
            st.error(f"Transcript မရပါ: {error}")

st.header("2. Video Upload")

uploaded_video = st.file_uploader(
    "ကိုယ်ပိုင် သို့မဟုတ် ခွင့်ပြုချက်ရှိသော Video",
    type=["mp4", "mov", "m4v"]
)

if uploaded_video:
    st.video(uploaded_video)

st.header("3. Recap Script")

default_text = st.session_state.get("transcript", "")

script = st.text_area(
    "Recap အတွက် စာသား",
    value=default_text,
    height=220,
    key="recap_text"
)

minutes = st.selectbox(
    "Recap အချိန်",
    [1, 2, 3, 4, 5],
    index=2
)

voice_options = {
    "မြန်မာ အမျိုးသမီး": "my-MM-NilarNeural",
    "မြန်မာ အမျိုးသား": "my-MM-ThihaNeural",
    "English အမျိုးသမီး": "en-US-JennyNeural",
    "English အမျိုးသား": "en-US-GuyNeural"
}

voice_label = st.selectbox(
    "Narration အသံ",
    list(voice_options.keys())
)

if st.button("Recap Script ဖန်တီးမယ်"):
    if not script.strip():
        st.error("Transcript သို့မဟုတ် စာသား ထည့်ပါ။")
    else:
        recap = make_recap(script, minutes)
        st.session_state["final_script"] = recap
        st.success("Recap Script အသင့်ဖြစ်ပါပြီ။")

if "final_script" in st.session_state:
    st.subheader("Recap Script Preview")
    st.text_area(
        "လိုအပ်သလို ပြင်ဆင်ပါ",
        key="final_script_edit",
        value=st.session_state["final_script"],
        height=220
    )

st.header("4. Recap Video ထုတ်လုပ်မယ်")

if st.button("🎬 MP4 ဖန်တီးမယ်"):
    final_script = st.session_state.get(
        "final_script_edit",
        st.session_state.get("final_script", script)
    )

    if uploaded_video is None:
        st.error(
            "MP4 ထုတ်လုပ်ရန် ကိုယ်ပိုင် Video ကို Upload လုပ်ပါ။"
        )
    elif not final_script.strip():
        st.error("Recap Script ထည့်ပါ။")
    else:
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                folder = Path(temp_dir)
                source = folder / "input.mp4"
                source.write_bytes(uploaded_video.getvalue())

                with st.spinner(
                    "Video ဖန်တီးနေပါတယ်။ ခဏစောင့်ပါ..."
                ):
                    output = make_video(
                        source,
                        final_script,
                        voice_options[voice_label],
                        minutes,
                        folder
                    )

                    video_bytes = output.read_bytes()

                st.success("Recap Video ပြီးပါပြီ။")
                st.video(video_bytes)

                st.download_button(
                    "⬇️ MP4 Download",
                    data=video_bytes,
                    file_name="movie_recap_myanmar.mp4",
                    mime="video/mp4"
                )

        except Exception as error:
            st.error(f"Video ဖန်တီးရာတွင် အမှား: {error}")

st.caption(
    "အခမဲ့ဗားရှင်းသည် Transcript မှ စာကြောင်းရွေးချယ်ခြင်းကို "
    "အသုံးပြုသည်။ Scene များကို ဇာတ်လမ်းအဓိပ္ပာယ်အရ "
    "AI ဖြင့်ရွေးချယ်ခြင်း မဟုတ်ပါ။"
)
