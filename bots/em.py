from iris import ChatContext
from iris.decorators import *
from bots.talk_api import talk_write


def send_emoticon(chat: ChatContext, emoticon_number: int) -> bool:
    """
    이모티콘을 전송합니다.

    Args:
        chat: ChatContext 객체
        emoticon_number: 이모티콘 번호 (1~88)

    Returns:
        bool: 성공 여부
    """
    if emoticon_number < 1 or emoticon_number > 88:
        chat.reply("이모티콘 번호는 1~88 사이여야 합니다.")
        return False

    emot_filename = f"2212560.emot_{emoticon_number:03d}.png"
    print(f"[em] Sending emoticon: {emot_filename}")

    attachment = {
        "type": "sticker/digital-item",
        "path": emot_filename,
        "name": "(이모티콘)",
        "sound": "",
        "width": "360",
        "height": "360",
        "msg": "",
        "alt": "하트뿅뿅 어피치이모티콘",
        "welcome": False,
    }

    result = talk_write(
        iris_endpoint=chat.api.iris_endpoint,
        chat_id=chat.room.id,
        msg=" ",
        attach=attachment,
        msg_type=12,  # 이모티콘 타입
    )

    if result.get("result") is False:
        print(f"[em] Failed to send emoticon: {result}")
        chat.reply("이모티콘 전송에 실패했습니다.")
        return False

    print("[em] Emoticon sent successfully")
    return True


@has_param
def emoticon_command(chat: ChatContext):
    """!임티 명령어 - 이모티콘을 전송합니다."""
    try:
        param = chat.message.param.strip()
        if not param:
            chat.reply("사용법: !임티 [1~88]")
            return

        try:
            emoticon_number = int(param)
        except ValueError:
            chat.reply("숫자를 입력하세요!\n사용법: !임티 [1~88]")
            return

        send_emoticon(chat, emoticon_number)

    except Exception as e:
        import traceback
        print(f"[em] Exception: {e}")
        traceback.print_exc()
        chat.reply("명령어 처리 중 오류가 발생했습니다.")