# coding: utf8
import requests
import json
import os
from iris import ChatContext
from iris.decorators import *

TALK_API_URL = os.getenv("TALK_API_URL") or "https://talk-api.naijun.dev/api/v1/send"

def get_auth_from_iris(iris_endpoint: str):
    """Iris에서 AOT 토큰 정보를 가져옵니다."""
    try:
        print(f"[DEBUG] Iris endpoint: {iris_endpoint}")
        aot_url = f"{iris_endpoint}/aot"
        print(f"[DEBUG] Requesting AOT from: {aot_url}")
        
        response = requests.get(aot_url)
        print(f"[DEBUG] AOT response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"[DEBUG] AOT data received: {data}")
            
            if data.get("success"):
                aot_data = data.get("aot", {})
                access_token = aot_data.get("access_token")
                device_uuid = aot_data.get("d_id")
                
                if not access_token or not device_uuid:
                    print(f"[ERROR] Missing access_token or d_id")
                    return None
                
                auth = f"{access_token}-{device_uuid}"
                print(f"[DEBUG] Auth header created: {auth[:30]}...{auth[-20:]}")
                return auth
        return None
    except Exception as e:
        print(f"[ERROR] Error getting auth from Iris: {e}")
        import traceback
        traceback.print_exc()
        return None

def send_emoticon(chat: ChatContext, emoticon_number: int):
    """
    이모티콘을 전송합니다.
    
    Args:
        chat: ChatContext 객체
        emoticon_number: 이모티콘 번호 (1~88)
    
    Returns:
        bool: 성공 여부
    """
    try:
        # 번호 검증
        if emoticon_number < 1 or emoticon_number > 88:
            chat.reply("이모티콘 번호는 1~88 사이여야 합니다.")
            return False
        
        # 이모티콘 파일명 생성 (001, 002, ... 형식)
        emot_filename = f"2212560.emot_{emoticon_number:03d}.png"
        
        print(f"[DEBUG] Sending emoticon: {emot_filename}")
        
        # attachment 객체 생성
        attachment_obj = {
            "type": "sticker/digital-item",
            "path": emot_filename,
            "name": "(이모티콘)",
            "sound": "",
            "width": "360",
            "height": "360",
            "msg": "",
            "alt": "하트뿅뿅 어피치이모티콘",
            "welcome": False
        }
        
        print(f"[DEBUG] Attachment object: {attachment_obj}")
        
        # Iris에서 인증 정보 가져오기
        auth_header = get_auth_from_iris(chat.api.iris_endpoint)
        
        if not auth_header:
            print("[ERROR] Failed to get auth header")
            chat.reply("인증 정보를 가져올 수 없습니다.")
            return False
        
        # TalkApi로 메시지 전송
        payload = {
            "chatId": chat.room.id,
            "type": 12,  # 이모티콘 타입
            "message": " ",
            "attachment": attachment_obj
        }
        
        headers = {
            "Authorization": auth_header,
            "Content-Type": "application/json"
        }
        
        print(f"[DEBUG] Payload: {json.dumps(payload, ensure_ascii=False)}")
        
        response = requests.post(TALK_API_URL, json=payload, headers=headers)
        
        print(f"[DEBUG] Response status: {response.status_code}")
        print(f"[DEBUG] Response body: {response.text}")
        
        if response.status_code == 200:
            print("[SUCCESS] Emoticon sent successfully")
            return True
        else:
            print(f"[ERROR] Failed to send emoticon: {response.status_code}")
            chat.reply(f"이모티콘 전송 실패: {response.status_code}")
            return False
            
    except Exception as e:
        import traceback
        print(f"[ERROR] Exception in send_emoticon: {e}")
        traceback.print_exc()
        chat.reply("이모티콘 전송 중 오류가 발생했습니다.")
        return False

@has_param
def emoticon_command(chat: ChatContext):
    """!임티 명령어 - 이모티콘을 전송합니다."""
    try:
        print(f"[DEBUG] emoticon_command called")
        
        # 파라미터에서 번호 추출
        param = chat.message.param.strip()
        
        if not param:
            chat.reply("사용법: !임티 [1~88]")
            return
        
        try:
            emoticon_number = int(param)
        except ValueError:
            chat.reply("숫자를 입력하세요!\n사용법: !임티 [1~88]")
            return
        
        # 이모티콘 전송
        send_emoticon(chat, emoticon_number)
        
    except Exception as e:
        import traceback
        print(f"[ERROR] Exception in emoticon_command: {e}")
        traceback.print_exc()
        chat.reply("명령어 처리 중 오류가 발생했습니다.")