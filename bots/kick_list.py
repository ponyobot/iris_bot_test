import requests
from iris import ChatContext
from bots.talk_api import get_auth


def get_link_id(chat: ChatContext):
    """DB에서 현재 채팅방의 link_id를 가져옵니다."""
    try:
        result = chat.api.query(
            query="SELECT id, link_id, type FROM chat_rooms WHERE id = ?",
            bind=[str(chat.room.id)]
        )
        if result and len(result) > 0:
            return result[0].get("link_id")
        return None
    except Exception as e:
        print(f"[KickList] Failed to get link_id: {e}")
        return None


def get_kicked_members(link_id: str, auth: str, offset: int = 0):
    """강퇴된 멤버 목록을 가져옵니다."""
    url = f"https://open.kakao.com/c/link/kickedMembers?linkId={link_id}&offset={offset}"
    headers = {
        "Authorization": auth,
        "A": "android/26.1.3/ko",
        "User-Agent": "KT/26.1.3 An/14 ko",
        "Accept-Language": "ko",
        "Accept-Encoding": "gzip, deflate, br",
    }
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("status", 0) < 0:
                return None, f"API 오류 (status: {data.get('status')})"
            return data.get("kickedMembers", []), "성공"
        return None, f"HTTP 오류: {response.status_code}"
    except Exception as e:
        print(f"[KickList] Exception: {e}")
        return None, str(e)


def kick_list_command(chat: ChatContext):
    """!강퇴목록 명령어 - 현재 오픈채팅방의 강퇴 멤버 목록을 출력합니다."""
    try:
        link_id = get_link_id(chat)
        if not link_id:
            chat.reply("오픈채팅방의 link_id를 찾을 수 없습니다.\n오픈채팅방에서만 사용 가능합니다.")
            return

        access_token, device_uuid = get_auth(chat.api.iris_endpoint)
        if not access_token or not device_uuid:
            chat.reply("인증 정보를 가져올 수 없습니다.")
            return

        auth = f"{access_token}-{device_uuid}"

        # 전체 목록 수집 (페이지네이션)
        all_members = []
        offset = 0
        while True:
            members, message = get_kicked_members(link_id, auth, offset)
            if members is None:
                chat.reply(f"강퇴 목록을 가져올 수 없습니다.\n사유: {message}")
                return
            if not members:
                break
            all_members.extend(members)
            if len(members) < 100:
                break
            offset += len(members)

        if not all_members:
            chat.reply("강퇴된 멤버가 없습니다.")
            return

        ALLSEE = '\u200b' * 500
        lines = [f"🚫 강퇴 목록 ({len(all_members)}명){ALLSEE}"]

        for i, member in enumerate(all_members, 1):
            nickname = member.get("nickname", "(알 수 없음)")
            user_id = member.get("userId", "")
            profile_url = member.get("profileImageUrl", "")
            lines.append(f"\n{i}. {nickname}\nID: {user_id}\n프로필: {profile_url}")

        chat.reply("\n".join(lines))

    except Exception as e:
        import traceback
        traceback.print_exc()
        chat.reply("강퇴 목록 조회 중 오류가 발생했습니다.")
