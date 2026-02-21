import json
import time
import requests
from threading import Lock
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

TALK_WRITE_URL = "https://talk-external.kakao.com/talk/write"

# 인증 정보 캐싱
_auth_cache = {}
_auth_cache_lock = Lock()
_AUTH_CACHE_TTL = 300  # 5분

# HTTP 세션 풀링 (연결 재사용)
_http_session = None
_session_lock = Lock()

# 백그라운드 작업용 ThreadPool
_executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="TalkAPI")


def _get_session():
    """HTTP 세션을 싱글톤으로 관리"""
    global _http_session
    with _session_lock:
        if _http_session is None:
            _http_session = requests.Session()
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=10,
                pool_maxsize=20,
                max_retries=1
            )
            _http_session.mount('http://', adapter)
            _http_session.mount('https://', adapter)
        return _http_session


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


def get_auth(iris_endpoint: str, force_refresh: bool = False):
    """인증 정보를 캐싱하여 반환합니다."""
    current_time = time.time()
    
    with _auth_cache_lock:
        # 캐시 확인
        if not force_refresh and iris_endpoint in _auth_cache:
            cached_data = _auth_cache[iris_endpoint]
            if current_time - cached_data["timestamp"] < _AUTH_CACHE_TTL:
                return cached_data["access_token"], cached_data["device_uuid"]
    
    # 캐시 미스 또는 만료 - API 호출
    try:
        session = _get_session()
        response = session.get(f"{iris_endpoint}/aot", timeout=3)
        
        if response.status_code != 200:
            return None, None

        data = response.json()
        if not data.get("success"):
            return None, None

        aot = data.get("aot", {})
        access_token = aot.get("access_token")
        device_uuid = aot.get("d_id")
        
        if access_token and device_uuid:
            # 캐싱
            with _auth_cache_lock:
                _auth_cache[iris_endpoint] = {
                    "access_token": access_token,
                    "device_uuid": device_uuid,
                    "timestamp": current_time
                }
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
    """동기 방식으로 메시지를 전송합니다."""
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
        session = _get_session()
        response = session.post(
            TALK_WRITE_URL,
            data=json.dumps(data, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            timeout=5
        )
        
        if response.status_code == 200:
            return response.json()
        return {"result": False, "status": response.status_code}
    except Exception as e:
        print(f"[TalkApi] Exception: {e}")
        return {"result": False}


def _talk_write_worker(
    iris_endpoint: str,
    chat_id,
    msg: str,
    attach: dict,
    msg_type: int,
    thread_id,
    callback: Optional[Callable] = None
):
    """백그라운드에서 실행될 실제 전송 함수"""
    try:
        result = talk_write(iris_endpoint, chat_id, msg, attach, msg_type, thread_id)
        
        if result.get("result") is False:
            print(f"[TalkApi] Send failed: {result}")
        
        if callback:
            callback(result)
            
    except Exception as e:
        print(f"[TalkApi] Exception in worker: {e}")
        import traceback
        traceback.print_exc()


def talk_write_async(
    iris_endpoint: str,
    chat_id,
    msg: str,
    attach: dict = None,
    msg_type: int = 1,
    thread_id: int | str = None,
    callback: Optional[Callable] = None
) -> bool:
    """
    비동기 방식으로 메시지를 전송합니다. (즉시 반환)
    
    Args:
        iris_endpoint: Iris 엔드포인트
        chat_id: 채팅방 ID
        msg: 메시지 내용
        attach: 첨부 데이터
        msg_type: 메시지 타입
        thread_id: 스레드 ID (선택)
        callback: 전송 완료 후 호출할 콜백 함수 (선택)
    
    Returns:
        bool: 백그라운드 작업 제출 성공 여부
    """
    if attach is None:
        attach = {}
    if msg is None or not chat_id:
        return False
    
    try:
        _executor.submit(
            _talk_write_worker,
            iris_endpoint,
            chat_id,
            msg,
            attach,
            msg_type,
            thread_id,
            callback
        )
        return True
    except Exception as e:
        print(f"[TalkApi] Failed to submit: {e}")
        return False