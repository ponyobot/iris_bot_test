import json
from iris import ChatContext
from bots.talk_api import talk_write, talk_write_async


def get_room_master_from_db(chat: ChatContext):
    """DB에서 방장 정보를 가져옵니다."""
    try:
        rows = chat.api.query(
            "SELECT active_member_ids FROM chat_rooms WHERE id = ?",
            [chat.room.id],
        )
        if not rows:
            return None

        members_data = rows[0].get("active_member_ids")
        if not members_data:
            return None

        try:
            member_ids = json.loads(members_data)
            if not isinstance(member_ids, list):
                member_ids = [member_ids]
        except Exception:
            member_ids = [m.strip() for m in str(members_data).split(",") if m.strip()]

        for member_id in member_ids:
            result = chat.api.query(
                "SELECT user_id, nickname, link_member_type FROM open_chat_member WHERE user_id = ?",
                [member_id],
            )
            if not result:
                continue

            row = result[0]
            if str(row.get("link_member_type")) == "1":
                return {"id": int(row.get("user_id")), "name": row.get("nickname")}
    except Exception as e:
        print(f"[mentions] get_room_master_from_db error: {e}")

    return None


def get_room_master_from_members(chat: ChatContext):
    """room.members에서 방장 정보를 가져옵니다."""
    try:
        members = getattr(chat.room, "members", None)
        if not members:
            return None

        for member in members:
            if getattr(member, "type", None) == "HOST":
                return {"id": member.id, "name": member.name}
    except Exception as e:
        print(f"[mentions] get_room_master_from_members error: {e}")

    return None


def _get_message_text(chat: ChatContext) -> str:
    """파라미터에서 메시지 텍스트를 추출합니다."""
    if getattr(chat.message, "has_param", False) and chat.message.param:
        return chat.message.param.strip()
    return ""


def _extract_thread_id(chat: ChatContext) -> str | None:
    """스레드 ID를 추출합니다."""
    raw_obj = chat.raw if isinstance(chat.raw, dict) else {}
    attachment = chat.message.attachment if isinstance(chat.message.attachment, dict) else {}

    candidates = [
        raw_obj.get("thread_id"),
        attachment.get("thread_id"),
        attachment.get("src_logId"),
        attachment.get("src_log_id"),
    ]

    for value in candidates:
        if value and str(value) != "0":
            return str(value)

    try:
        src_chat = chat.get_source()
        if src_chat and src_chat.message and src_chat.message.id:
            return str(src_chat.message.id)
    except Exception:
        pass

    return None


def send_mention_message(
    chat: ChatContext,
    user_id: int,
    user_name: str,
    message_text: str = "",
    use_brackets: bool = False,
    thread_id: int | str = None,
    async_mode: bool = True
):
    """
    멘션 메시지를 전송합니다.
    
    Args:
        chat: ChatContext 객체
        user_id: 멘션할 사용자 ID
        user_name: 멘션할 사용자 이름
        message_text: 추가 메시지
        use_brackets: 대괄호 사용 여부
        thread_id: 스레드 ID (선택)
        async_mode: 비동기 전송 여부 (기본: True)
    
    Returns:
        bool: 성공 여부
    """
    try:
        if not user_name:
            return False

        if use_brackets:
            suffix = f" {message_text}" if message_text else ""
            full_message = f"[ @{user_name} ]{suffix}"
            at_position = 3
        else:
            suffix = f" {message_text}" if message_text else ""
            full_message = f"@{user_name}{suffix}"
            at_position = 1

        attachment_obj = {
            "mentions": [
                {
                    "user_id": user_id,
                    "at": [at_position],
                    "len": len(user_name),
                }
            ]
        }

        # 비동기/동기 선택
        if async_mode:
            result = talk_write_async(
                iris_endpoint=chat.api.iris_endpoint,
                chat_id=chat.room.id,
                msg=full_message,
                attach=attachment_obj,
                msg_type=1,
                thread_id=thread_id,
            )
        else:
            result = talk_write(
                iris_endpoint=chat.api.iris_endpoint,
                chat_id=chat.room.id,
                msg=full_message,
                attach=attachment_obj,
                msg_type=1,
                thread_id=thread_id,
            )
            
            if result.get("result") is False or result.get("status", 0) < 0:
                return False

            if thread_id is not None:
                chat_log = result.get("chatLog") if isinstance(result, dict) else None
                returned_thread_id = chat_log.get("threadId") if isinstance(chat_log, dict) else None
                returned_scope = chat_log.get("scope") if isinstance(chat_log, dict) else None
                if returned_thread_id is None or str(returned_scope) != "3":
                    return False

        return result
    except Exception as e:
        print(f"[mentions] send_mention_message error: {e}")
        return False


def mention_user(chat: ChatContext):
    """자신을 멘션합니다."""
    try:
        user_id = chat.sender.id
        user_name = chat.sender.name
        if not user_name:
            chat.reply("사용자 이름을 가져올 수 없습니다.")
            return

        message_text = _get_message_text(chat)
        send_mention_message(chat, user_id, user_name, message_text, async_mode=True)
    except Exception as e:
        print(f"[mentions] mention_user error: {e}")
        chat.reply("멘션 중 오류가 발생했습니다.")


def mention_user_in_thread(chat: ChatContext):
    """스레드에서 자신을 멘션합니다."""
    try:
        user_id = chat.sender.id
        user_name = chat.sender.name
        if not user_name:
            chat.reply("사용자 이름을 가져올 수 없습니다.")
            return

        thread_id = _extract_thread_id(chat)
        if not thread_id:
            chat.reply("스레드 ID를 찾을 수 없습니다.")
            return

        message_text = _get_message_text(chat)
        success = send_mention_message(
            chat, user_id, user_name, message_text, 
            thread_id=thread_id, async_mode=False  # 스레드는 동기로 처리
        )
        if not success:
            chat.reply("현재 환경에서는 스레드 멘션 전송이 지원되지 않습니다.")
    except Exception as e:
        print(f"[mentions] mention_user_in_thread error: {e}")
        chat.reply("멘션 중 오류가 발생했습니다.")


def mention_room_master(chat: ChatContext):
    """방장을 멘션합니다."""
    try:
        master_info = get_room_master_from_db(chat) or get_room_master_from_members(chat)
        if not master_info:
            chat.reply("방장 정보를 찾을 수 없습니다.")
            return

        master_id = master_info["id"]
        master_name = master_info["name"]
        if not master_name:
            chat.reply("방장 이름을 가져올 수 없습니다.")
            return

        message_text = _get_message_text(chat) or "방장을 호출합니다."
        send_mention_message(chat, master_id, master_name, message_text, async_mode=True)
    except Exception as e:
        print(f"[mentions] mention_room_master error: {e}")
        chat.reply("방장 호출 중 오류가 발생했습니다.")