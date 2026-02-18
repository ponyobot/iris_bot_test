from iris import ChatContext, Bot
from iris.bot.models import ErrorContext
from bots.gemini import get_gemini
from bots.pyeval import python_eval, real_eval
from bots.stock import create_stock_image
from bots.imagen import get_imagen
from bots.lyrics import get_lyrics, find_lyrics
from bots.replyphoto import reply_photo
from bots.text2image import draw_text
from bots.coin import get_coin_info

from iris.decorators import *
from helper.BanControl import ban_user, unban_user
from iris.kakaolink import IrisLink

from bots.detect_nickname_change import detect_nickname_change
import sys, threading
import base64
import requests
import os
import subprocess
import tempfile

from bots.mentions import mention_user, mention_room_master, mention_user_in_thread
from bots.notification import share_notice_command, share_current_notice, set_notice_command, delete_notice_command, change_notice_command, get_notices_command, get_notice_detail_command
from bots.kakao_reaction import react_command
from bots.em import emoticon_command
from bots.user_posts import get_user_posts_command, get_posts_by_link_id_command
from bots.kick_list import kick_list_command
from bots.vote import vote_command
from bots.room_info import room_search_command

iris_url = sys.argv[1]
bot = Bot(iris_url)


def normalize_iris_endpoint(endpoint: str) -> str:
    normalized = endpoint.strip()
    if not normalized.startswith("http://") and not normalized.startswith("https://"):
        normalized = f"http://{normalized}"
    return normalized.rstrip("/")

def transcode_to_aac_320k(input_path: str) -> str:
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        ffmpeg = get_ffmpeg_exe()
    except Exception:
        ffmpeg = None
    if not ffmpeg:
        raise RuntimeError("missing python package: pip install imageio-ffmpeg")

    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"file not found: {input_path}")

    fd, output_path = tempfile.mkstemp(prefix="iris_aac_", suffix=".m4a")
    os.close(fd)

    cmd = [
        ffmpeg,
        "-y",
        "-i",
        input_path,
        "-vn",
        "-c:a",
        "aac",
        "-b:a",
        "320k",
        output_path,
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        try:
            os.remove(output_path)
        except Exception:
            pass
        stderr = (result.stderr or "").strip().splitlines()
        msg = stderr[-1] if stderr else "unknown ffmpeg error"
        raise RuntimeError(f"ffmpeg transcode failed: {msg}")

    return output_path


def send_audio_multiple_http(iris_endpoint: str, room_id: int, mp3_paths: list[str]):
    base64_audio_data = []

    for mp3_path in mp3_paths:
        with open(mp3_path, "rb") as f:
            base64_audio_data.append(base64.b64encode(f.read()).decode("utf-8"))

    endpoint = normalize_iris_endpoint(iris_endpoint)

    response = requests.post(
        f"{endpoint}/reply",
        json={
            "type": "audio_multiple",
            "room": str(room_id),
            "data": base64_audio_data,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()

@bot.on_event("message")
@is_not_banned
def on_message(chat: ChatContext):
    try:
        match chat.message.command:

            case "!tt" | "!ttt" | "!프사" | "!프사링":
                reply_photo(chat, kl)

            case "!멘션":
                mention_user(chat)
            
            case "!멘션1":  # 스레드용 멘션
                mention_user_in_thread(chat)
            
            case "!방장":
                mention_room_master(chat)
            
            case "!공지":
                share_notice_command(chat)
            
            case "!현재공지":
                share_current_notice(chat)
            
            case "!공지등록":
                set_notice_command(chat)
            
            case "!공지삭제":
                delete_notice_command(chat)
            
            case "!공지수정":
                change_notice_command(chat)

            case "!공지목록":
                get_notices_command(chat)

            case "!공지확인":
                get_notice_detail_command(chat)

            case "!임티":
                emoticon_command(chat)

            case "!react":
                react_command(chat)

            case "!유저포스트":
                get_user_posts_command(chat)

            case "!포스트":
                get_posts_by_link_id_command(chat)

            case "!강퇴목록":
                kick_list_command(chat)
            
            case "!투표":
                vote_command(chat)

            case "!방검색":
                room_search_command(chat)
                
    except Exception as e :
        print(e)


@bot.on_event("message")
@is_not_banned
def on_audio_test(chat: ChatContext):
    if chat.message.command != "!mp3test":
        return

    try:
        if not chat.message.param:
            chat.reply("usage: !mp3test C:\\\\a.mp3|C:\\\\b.mp3")
            return

        mp3_paths = [path.strip().strip('"') for path in chat.message.param.split("|") if path.strip()]
        if not mp3_paths:
            chat.reply("mp3 path required")
            return

        transcoded_files = []
        try:
            for path in mp3_paths:
                transcoded_files.append(transcode_to_aac_320k(path))

            chat.reply_audio(transcoded_files)
            chat.reply(f"sent {len(transcoded_files)} audio file(s) as aac 320kbps")
        finally:
            for temp_file in transcoded_files:
                try:
                    os.remove(temp_file)
                except Exception:
                    pass
    except Exception as e:
        chat.reply(f"mp3 send failed: {e}")
        print(e)

@bot.on_event("message")
@is_not_banned
def on_message(chat: ChatContext):
    try:
        match chat.message.command:
            
            case "!py":
                python_eval(chat)
            
            case "!ev":
                real_eval(chat, kl)
            
    except Exception as e :
        print(e)

@bot.on_event("error")
def on_error(err: ErrorContext):
    print(err.event, "이벤트에서 오류가 발생했습니다", err.exception)
    #sys.stdout.flush()

if __name__ == "__main__":
    #닉네임감지를 사용하지 않는 경우 주석처리
    nickname_detect_thread = threading.Thread(target=detect_nickname_change, args=(bot.iris_url,))
    nickname_detect_thread.start()
    #카카오링크를 사용하지 않는 경우 주석처리
    kl = IrisLink(bot.iris_url)
    bot.run()
