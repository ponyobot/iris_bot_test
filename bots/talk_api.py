"""
KakaoTalk TalkApi 유틸리티
utils.js의 TalkApi 함수를 Python으로 포팅
"""
import json
import time
import requests

TALK_WRITE_URL = "https://talk-external.kakao.com/talk/write"


def _java_string_hashcode(s: str) -> int:
    """Java의 String.hashCode()를 Python으로 구현"""
    h = 0
    for c in s:
        h = (31 * h + ord(c)) & 0xFFFFFFFF
    # unsigned → signed 32bit
    if h >= 0x80000000:
        h -= 0x100000000
    return h


def _generate_message_id(device_uuid: str, timestamp: int = None) -> int:
    """utils.js의 generate_message_id 로직"""
    if timestamp is None:
        timestamp = int(time.time() * 1000)
    counter = _java_string_hashcode(device_uuid)
    mod_value = 2147483547
    rounded_time = ((timestamp % mod_value) // 100) * 100
    return rounded_time + counter


def get_auth(iris_endpoint: str):
    """
    Iris에서 AOT 토큰 정보를 가져옵니다.
    Returns: (auth_token, device_uuid) 또는 (None, None)
    """
    try:
        response = requests.get(f"{iris_endpoint}/aot")
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                aot = data.get("aot", {})
                access_token = aot.get("access_token")
                device_uuid = aot.get("d_id")
                if access_token and device_uuid:
                    return access_token, device_uuid
        return None, None
    except Exception as e:
        print(f"[TalkApi] Failed to get auth: {e}")
        return None, None


def talk_write(iris_endpoint: str, chat_id, msg: str, attach: dict = None, msg_type: int = 1) -> dict:
    """
    https://talk-external.kakao.com/talk/write 로 메시지를 전송합니다.
    utils.js의 TalkApi 함수와 동일한 로직.

    Args:
        iris_endpoint: Iris 봇 엔드포인트
        chat_id: 채팅방 ID
        msg: 전송할 메시지
        attach: attachment 딕셔너리 (기본값 {})
        msg_type: 메시지 타입 (기본값 1, 이모티콘 12)

    Returns:
        dict: 응답 JSON 또는 {"result": False}
    """
    if attach is None:
        attach = {}
    if msg is None or not chat_id:
        return {"result": False}

    auth_token, device_uuid = get_auth(iris_endpoint)
    if not auth_token or not device_uuid:
        print("[TalkApi] Failed to get auth")
        return {"result": False}

    timestamp = int(time.time() * 1000)
    msg_id = _generate_message_id(device_uuid, timestamp)

    headers = {
        "Authorization": auth_token,
        "Duuid": device_uuid,
        "Content-Type": "application/json; charset=utf-8",
        "Accept-Encoding": "gzip, deflate, br",
        "User-Agent": "okhttp/4.12.0",
        "Connection": "keep-alive",
    }

    data = {
        "chatId": chat_id,
        "type": msg_type,
        "message": msg,
        "attachment": json.dumps(attach, ensure_ascii=False),
        "msgId": msg_id,
    }

    try:
        response = requests.post(
            TALK_WRITE_URL,
            data=json.dumps(data, ensure_ascii=False).encode("utf-8"),
            headers=headers,
        )
        print(f"[TalkApi] Status: {response.status_code}")
        print(f"[TalkApi] Body: {response.text}")

        if response.status_code == 200:
            return response.json()
        else:
            return {"result": False, "status": response.status_code}
    except Exception as e:
        import traceback
        print(f"[TalkApi] Exception: {e}")
        traceback.print_exc()
        return {"result": False}
