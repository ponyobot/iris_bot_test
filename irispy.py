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

from bots.mentions import mention_user, mention_new_member, mention_self_and_bot, mention_room_master
from bots.notification import share_notice_command, share_current_notice, set_notice_command, delete_notice_command, change_notice_command, get_notices_command, get_notice_detail_command
from bots.kakao_reaction import react_command
from bots.em import emoticon_command

iris_url = sys.argv[1]
bot = Bot(iris_url)

@bot.on_event("message")
@is_not_banned
def on_message(chat: ChatContext):
    try:
        match chat.message.command:

            case "!멘션":
                mention_user(chat)
            
            #case "!멘션1":
            #    mention_self_and_bot(chat)
            
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

    except Exception as e :
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

# 입장 멘션을 보낼 방 리스트
WELCOME_ROOMS = [18472312239224835,18469145050793422]

#입장감지
@bot.on_event("new_member")
def on_newmem(chat: ChatContext):
    if chat.room.id in WELCOME_ROOMS:
        mention_new_member(chat)
    #chat.reply(f"Hello {chat.sender.name}")

#퇴장감지
@bot.on_event("del_member")
def on_delmem(chat: ChatContext):
    if chat.room.id in WELCOME_ROOMS:
        mention_new_member(chat)
    #chat.reply(f"Bye {chat.sender.name}")


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
