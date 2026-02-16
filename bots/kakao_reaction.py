"""
카카오톡 리액션(공감) 기능 모듈 (최적화 + 답장 지원)
"""
import requests
import time
import json
from iris import ChatContext
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from bots.talk_api import get_auth

# 리액션 타입 상수
CANCEL = 0
HEART = 1
LIKE = 2
CHECK = 3
LAUGH = 4
SURPRISE = 5
SAD = 6

BASE_URL = "https://talk-pilsner.kakao.com"

# 백그라운드 작업용 ThreadPool
_reaction_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="Reaction")

# HTTP 세션 풀링 (연결 재사용)
_reaction_session = None
_reaction_session_lock = Lock()

# link_id 캐싱
_link_id_cache = {}
_link_id_cache_lock = Lock()
_LINK_ID_CACHE_TTL = 600  # 10분


def _get_reaction_session():
    """HTTP 세션을 싱글톤으로 관리"""
    global _reaction_session
    with _reaction_session_lock:
        if _reaction_session is None:
            _reaction_session = requests.Session()
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=5,
                pool_maxsize=10,
                max_retries=1
            )
            _reaction_session.mount('http://', adapter)
            _reaction_session.mount('https://', adapter)
        return _reaction_session


def _get_link_id(chat: ChatContext):
    """오픈채팅 링크 ID 가져오기 (캐싱)"""
    room_id = str(chat.room.id)
    current_time = time.time()
    
    # 캐시 확인
    with _link_id_cache_lock:
        if room_id in _link_id_cache:
            cached_data = _link_id_cache[room_id]
            if current_time - cached_data["timestamp"] < _LINK_ID_CACHE_TTL:
                return cached_data["link_id"]
    
    # 캐시 미스 - DB 조회
    try:
        query = "SELECT id, link_id, type FROM chat_rooms WHERE id = ?"
        result = chat.api.query(query=query, bind=[room_id])

        if result and len(result) > 0:
            link_id = result[0].get("link_id")
            
            # 캐싱
            with _link_id_cache_lock:
                _link_id_cache[room_id] = {
                    "link_id": link_id,
                    "timestamp": current_time
                }
            
            return link_id

        return None
    except Exception as e:
        print(f"[Reaction] Could not get link_id: {e}")
        return None


def _extract_reply_message_id(chat: ChatContext):
    """답장한 메시지 ID를 추출합니다 (get_source 사용 안 함)."""
    try:
        # attachment에서 직접 src_logId 추출
        if not hasattr(chat.message, 'attachment') or not chat.message.attachment:
            return None
        
        attachment = chat.message.attachment
        
        # attachment가 문자열이면 JSON 파싱
        if isinstance(attachment, str):
            try:
                attachment = json.loads(attachment)
            except:
                return None
        
        # attachment가 dict가 아니면 None
        if not isinstance(attachment, dict):
            return None
        
        # src_logId 추출 시도
        src_log_id = attachment.get('src_logId') or attachment.get('src_log_id')
        
        if src_log_id and str(src_log_id) != "0":
            return int(src_log_id)
        
        return None
    except Exception as e:
        print(f"[Reaction] Failed to extract reply message ID: {e}")
        return None


def _add_reaction_worker(chat: ChatContext, reaction_type: int, target_message_id: int):
    """백그라운드에서 리액션을 추가합니다."""
    try:
        # 1. 인증 정보 가져오기 (캐싱됨)
        access_token, device_uuid = get_auth(chat.api.iris_endpoint)
        if not access_token or not device_uuid:
            print("[Reaction] Failed to get auth")
            return False
        
        auth = f"{access_token}-{device_uuid}"

        # 2. link_id 가져오기 (캐싱됨)
        link_id = _get_link_id(chat)

        # 3. 요청 준비
        headers = {
            'Authorization': auth,
            'talk-agent': 'android/11.0.0',
            'talk-language': 'ko',
            'Content-Type': 'application/json; charset=UTF-8',
            'User-Agent': 'okhttp/4.10.0'
        }

        payload = {
            "logId": int(target_message_id),
            "reqId": int(time.time() * 1000),
            "type": reaction_type
        }
        if link_id:
            payload["linkId"] = int(link_id)

        url = f"{BASE_URL}/messaging/chats/{chat.room.id}/bubble/reactions"

        # 4. POST 요청 (세션 재사용)
        session = _get_reaction_session()
        response = session.post(url, json=payload, headers=headers, timeout=5)

        if response.status_code == 200:
            return True
        else:
            print(f"[Reaction] Failed - Status: {response.status_code}")
            return False

    except Exception as e:
        print(f"[Reaction] Exception: {e}")
        return False


def add_reaction(chat: ChatContext, reaction_type: int, target_message_id: int = None):
    """
    메시지에 리액션을 추가합니다 (비동기).

    Args:
        chat: ChatContext 객체
        reaction_type: 리액션 타입
            0: 취소, 1: 하트, 2: 좋아요, 3: 체크, 4: 웃음, 5: 놀람, 6: 슬픔
        target_message_id: 리액션을 추가할 메시지 ID (None이면 현재 메시지)

    Returns:
        bool: 제출 성공 여부
    """
    try:
        if target_message_id is None:
            target_message_id = chat.message.id
            
        _reaction_executor.submit(_add_reaction_worker, chat, reaction_type, target_message_id)
        return True
    except Exception as e:
        print(f"[Reaction] Failed to submit: {e}")
        return False


def react_command(chat: ChatContext):
    """!react 명령어 — 리액션을 추가합니다."""
    try:
        param = chat.message.param.strip() if chat.message.has_param else ""

        if not param:
            chat.reply("사용법: !react [숫자]\n0:취소, 1:하트, 2:좋아요, 3:체크, 4:웃음, 5:놀람, 6:슬픔\n\n답장하면서 사용하면 답장한 메시지에 리액션이 추가됩니다.")
            return

        try:
            reaction_type = int(param)
        except ValueError:
            chat.reply("숫자를 입력하세요!\n사용법: !react [숫자]\n0:취소, 1:하트, 2:좋아요, 3:체크, 4:웃음, 5:놀람, 6:슬픔")
            return

        # 답장한 메시지 ID 추출 (get_source 사용 안 함)
        target_message_id = _extract_reply_message_id(chat)
        
        # 답장이 아니면 현재 메시지
        if target_message_id is None:
            target_message_id = chat.message.id

        add_reaction(chat, reaction_type, target_message_id)

    except Exception as e:
        print(f"[Reaction] react_command error: {e}")
        import traceback
        traceback.print_exc()
        chat.reply("리액션 추가 중 오류가 발생했습니다.")