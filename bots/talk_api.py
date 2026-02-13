import json
import time
import requests

TALK_WRITE_URL = "https://talk-external.kakao.com/talk/write"


def _java_string_hashcode(s: str) -> int:
    h = 0
    for c in s:
        h = (31 * h + ord(c)) & 0xFFFFFFFF
    if h >= 0x80000000:
        h -= 0x100000000
    return h


def _generate_message_id(device_uuid: str, timestamp: int = None) -> int:
    if timestamp is None:
        timestamp = int(time.time() * 1000)
    counter = _java_string_hashcode(device_uuid)
    mod_value = 2147483547
    rounded_time = ((timestamp % mod_value) // 100) * 100
    return rounded_time + counter


def get_auth(iris_endpoint: str):
    try:
        response = requests.get(f"{iris_endpoint}/aot")
        if response.status_code != 200:
            return None, None

        data = response.json()
        if not data.get("success"):
            return None, None

        aot = data.get("aot", {})
        access_token = aot.get("access_token")
        device_uuid = aot.get("d_id")
        if access_token and device_uuid:
            return access_token, device_uuid
    except Exception as e:
        print(f"[TalkApi] Failed to get auth: {e}")
    return None, None


def talk_write(
    iris_endpoint: str,
    chat_id,
    msg: str,
    attach: dict = None,
    msg_type: int = 1,
    thread_id: int | str = None,
) -> dict:
    if attach is None:
        attach = {}
    if msg is None or not chat_id:
        return {"result": False}

    auth_token, device_uuid = get_auth(iris_endpoint)
    if not auth_token or not device_uuid:
        return {"result": False}

    msg_id = _generate_message_id(device_uuid)

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

    if thread_id is not None:
        thread_id_str = str(thread_id).strip()
        if thread_id_str and thread_id_str != "0":
            thread_id_value = int(thread_id_str) if thread_id_str.isdigit() else thread_id_str
            data["threadId"] = thread_id_value
            data["scope"] = 3
            data["supplement"] = json.dumps(
                {"scope": 3, "threadId": thread_id_value},
                ensure_ascii=False,
                separators=(",", ":"),
            )

    try:
        response = requests.post(
            TALK_WRITE_URL,
            data=json.dumps(data, ensure_ascii=False).encode("utf-8"),
            headers=headers,
        )
        if response.status_code == 200:
            return response.json()
        return {"result": False, "status": response.status_code}
    except Exception as e:
        print(f"[TalkApi] Exception: {e}")
        return {"result": False}
