"""
카카오톡 리액션(공감) 기능 모듈
"""
import requests
import time
from iris import ChatContext

# 리액션 타입 상수
CANCEL = 0
HEART = 1
LIKE = 2
CHECK = 3
LAUGH = 4
SURPRISE = 5
SAD = 6

BASE_URL = "https://talk-pilsner.kakao.com"


def _get_auth(iris_endpoint: str):
    """Iris에서 AOT 토큰 정보를 가져옵니다."""
    try:
        response = requests.get(f"{iris_endpoint}/aot")
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                aot = data.get("aot", {})
                access_token = aot.get("access_token")
                device_uuid = aot.get("d_id")
                if access_token and device_uuid:
                    return f"{access_token}-{device_uuid}"
        return None
    except Exception as e:
        print(f"[KakaoReaction] Failed to get auth: {e}")
        return None


def _get_link_id(chat: ChatContext):
    """오픈채팅 링크 ID 가져오기"""
    try:
        query = "SELECT id, link_id, type FROM chat_rooms WHERE id = ?"
        result = chat.api.query(query=query, bind=[str(chat.room.id)])

        if result and len(result) > 0:
            link_id = result[0].get("link_id")
            if link_id:
                print(f"[KakaoReaction] Found link_id: {link_id}")
                return link_id

        print(f"[KakaoReaction] No link_id found")
        return None
    except Exception as e:
        print(f"[KakaoReaction] Could not get link_id: {e}")
        return None


def react_command(chat: ChatContext):
    """!react 명령어 — 리액션을 추가합니다."""
    try:
        param = chat.message.param.strip() if chat.message.has_param else ""

        if not param:
            chat.reply("사용법: !react [숫자]\n0:취소, 1:하트, 2:좋아요, 3:체크, 4:웃음, 5:놀람, 6:슬픔")
            return

        try:
            reaction_type = int(param)
        except ValueError:
            chat.reply("숫자를 입력하세요!\n사용법: !react [숫자]\n0:취소, 1:하트, 2:좋아요, 3:체크, 4:웃음, 5:놀람, 6:슬픔")
            return

        add_reaction(chat, reaction_type)

    except Exception as e:
        print(f"[KakaoReaction] react_command error: {e}")
        chat.reply("리액션 추가 중 오류가 발생했습니다.")


def add_reaction(chat: ChatContext, reaction_type: int):
    """
    메시지에 리액션을 추가합니다.

    Args:
        chat: ChatContext 객체
        reaction_type: 리액션 타입
            0: 취소, 1: 하트, 2: 좋아요, 3: 체크, 4: 웃음, 5: 놀람, 6: 슬픔

    Returns:
        bool: 성공 여부
    """
    try:
        auth = _get_auth(chat.api.iris_endpoint)
        if not auth:
            print("[KakaoReaction] Failed to get auth")
            return False

        link_id = _get_link_id(chat)

        headers = {
            'Authorization': auth,
            'talk-agent': 'android/11.0.0',
            'talk-language': 'ko',
            'Content-Type': 'application/json; charset=UTF-8',
            'User-Agent': 'okhttp/4.10.0'
        }

        payload = {
            "logId": int(chat.message.id),
            "reqId": int(time.time() * 1000),
            "type": reaction_type
        }
        if link_id:
            payload["linkId"] = int(link_id)

        url = f"{BASE_URL}/messaging/chats/{chat.room.id}/bubble/reactions"

        print(f"[KakaoReaction] Payload: {payload}")
        response = requests.post(url, json=payload, headers=headers)

        if response.status_code == 200:
            print("[KakaoReaction] Success!")
            return True
        else:
            print(f"[KakaoReaction] Failed - Status: {response.status_code}")
            print(f"[KakaoReaction] Response: {response.text}")
            return False

    except Exception as e:
        import traceback
        print(f"[KakaoReaction] Exception: {e}")
        traceback.print_exc()
        return False