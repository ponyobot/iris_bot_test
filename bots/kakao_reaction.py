"""
카카오톡 리액션(공감) 기능 모듈
"""
import requests
import time


class KakaoReaction:
    """카카오톡 공감(리액션) 기능"""
    
    # 리액션 타입
    CANCEL = 0
    HEART = 1
    LIKE = 2
    CHECK = 3
    LAUGH = 4
    SURPRISE = 5
    SAD = 6
    
    def __init__(self, iris_url):
        """
        Args:
            iris_url: Iris 서버 URL (예: http://100.94.231.4:3000)
        """
        self.iris_url = iris_url
        self.base_url = "https://talk-pilsner.kakao.com"
        self._authorization = None
    
    def _get_auth_info(self):
        """Iris API에서 AOT 정보 가져오기"""
        if self._authorization:
            return self._authorization
            
        try:
            response = requests.get(f"{self.iris_url}/aot")
            data = response.json()
            
            if data.get("success"):
                aot = data.get("aot", {})
                access_token = aot.get("access_token")
                device_uuid = aot.get("d_id")
                self._authorization = f"{access_token}-{device_uuid}"
                return self._authorization
        except Exception as e:
            print(f"[KakaoReaction] Failed to get auth info: {e}")
        
        return None
    
    def _get_headers(self):
        """API 요청 헤더 생성"""
        auth = self._get_auth_info()
        if not auth:
            return None
            
        return {
            'Authorization': auth,
            'talk-agent': 'android/11.0.0',
            'talk-language': 'ko',
            'Content-Type': 'application/json; charset=UTF-8',
            'User-Agent': 'okhttp/4.10.0'
        }
    
    def react(self, channel_id, log_id, reaction_type, link_id=None):
        """
        메시지에 리액션 추가
        
        Args:
            channel_id: 채팅방 ID
            log_id: 메시지 ID (chat.message.id)
            reaction_type: 리액션 타입 (HEART, LIKE, CHECK 등)
            link_id: 오픈채팅 링크 ID (오픈채팅인 경우 필수)
            
        Returns:
            bool: 성공 여부
        """
        try:
            headers = self._get_headers()
            if not headers:
                print("[KakaoReaction] Headers is None")
                return False
            
            url = f"{self.base_url}/messaging/chats/{channel_id}/bubble/reactions"
            
            # reqId 생성 (현재 시간을 밀리초로)
            req_id = int(time.time() * 1000)
            
            # Payload 생성 (모든 값은 숫자로)
            payload = {
                "logId": int(log_id),
                "reqId": req_id,
                "type": reaction_type
            }
            
            if link_id:
                payload["linkId"] = int(link_id)
            
            print(f"[KakaoReaction] Payload: {payload}")
            
            response = requests.post(url, json=payload, headers=headers)
            
            if response.status_code == 200:
                print(f"[KakaoReaction] Success!")
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


def get_link_id(iris_url, chat_id):
    """
    오픈채팅 링크 ID 가져오기
    
    Args:
        iris_url: Iris 서버 URL
        chat_id: 채팅방 ID
        
    Returns:
        str or None: 링크 ID
    """
    try:
        # chat_rooms 테이블에서 직접 link_id 조회
        query = "SELECT id, link_id, type FROM chat_rooms WHERE id = ?"
        result = requests.post(
            f"{iris_url}/query",
            json={"query": query, "bind": [str(chat_id)]}
        ).json()
        
        if result.get("data") and len(result["data"]) > 0:
            link_id = result["data"][0].get("link_id")
            if link_id:
                print(f"[KakaoReaction] Found link_id: {link_id}")
                return link_id
        
        print(f"[KakaoReaction] No link_id found - not an open chat")
        return None
    except Exception as e:
        print(f"[KakaoReaction] Could not get link_id: {e}")
        import traceback
        traceback.print_exc()
        return None


def add_reaction_to_message(chat, reaction_type, reactor, iris_url):
    """
    메시지에 리액션을 추가하는 헬퍼 함수
    
    Args:
        chat: ChatContext 객체
        reaction_type: 리액션 타입 (0~6)
        reactor: KakaoReaction 인스턴스
        iris_url: Iris 서버 URL
        
    Returns:
        bool: 성공 여부
    """
    try:
        log_id = chat.message.id
        channel_id = chat.room.id
        
        # 오픈채팅 링크 ID 가져오기 (user_id 파라미터 제거)
        link_id = get_link_id(iris_url, channel_id)
        
        # 리액션 추가
        success = reactor.react(
            channel_id=channel_id,
            log_id=log_id,
            reaction_type=reaction_type,
            link_id=link_id
        )
        
        return success
        
    except Exception as e:
        import traceback
        print(f"[KakaoReaction] add_reaction error: {e}")
        traceback.print_exc()
        return False