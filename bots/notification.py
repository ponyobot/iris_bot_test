import requests
import json
import uuid
from iris import ChatContext
from iris.decorators import *

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
                
                session_info = f"{access_token}-{device_uuid}"
                print(f"[DEBUG] Session info created: {session_info[:30]}...{session_info[-20:]}")
                return session_info
        return None
    except Exception as e:
        print(f"[ERROR] Error getting auth from Iris: {e}")
        import traceback
        traceback.print_exc()
        return None

def get_link_id_from_room(chat: ChatContext):
    """채팅방의 link_id를 가져옵니다 (오픈채팅방용)."""
    try:
        chat_id = str(chat.room.id)
        
        print(f"[DEBUG] Getting link_id for chat_id: {chat_id}")
        
        # chat_rooms 테이블에서 직접 link_id 조회
        query = "SELECT id, link_id, type FROM chat_rooms WHERE id = ?"
        result = chat.api.query(
            query=query,
            bind=[chat_id]
        )
        
        print(f"[DEBUG] chat_rooms query result: {result}")
        
        if result and len(result) > 0 and result[0].get("link_id"):
            link_id = result[0].get("link_id")
            print(f"[DEBUG] Found link_id: {link_id}")
            return link_id
        
        print(f"[DEBUG] No link_id found - this might not be an open chat")
        return None
    except Exception as e:
        print(f"[ERROR] Error getting link_id: {e}")
        import traceback
        traceback.print_exc()
        return None

def get_post_id_from_room(chat: ChatContext):
    """채팅방의 moim_meta에서 post_id를 가져옵니다."""
    try:
        result = chat.api.query(
            query="SELECT moim_meta FROM chat_rooms WHERE id = ?",
            bind=[str(chat.room.id)]
        )

        if result and result[0].get("moim_meta"):
            raw_meta = result[0].get("moim_meta")
            moim_meta = json.loads(raw_meta)

            if isinstance(moim_meta, list) and moim_meta:
                ct_raw = moim_meta[0].get("ct")
                if ct_raw:
                    ct_data = json.loads(ct_raw)
                    post_id = ct_data.get("id")
                    print(f"[DEBUG] Found post_id: {post_id}")
                    return post_id
        
        print(f"[DEBUG] No post_id found in moim_meta")
        return None
    except Exception as e:
        print(f"[ERROR] Error getting post_id from room: {e}")
        import traceback
        traceback.print_exc()
        return None

def share_notice(chat: ChatContext, post_id: str, session_info: str, link_id: str = None):
    """공지를 공유합니다."""
    try:
        # 오픈채팅 여부에 따라 URL 변경
        if link_id:
            url = f"https://open.kakao.com/moim/posts/{post_id}/share?link_id={link_id}"
            print(f"[DEBUG] Using open chat URL with link_id: {link_id}")
        else:
            url = f"https://talkmoim-api.kakao.com/posts/{post_id}/share"
            print(f"[DEBUG] Using regular chat URL")
        
        # 더 완전한 헤더 설정
        headers = {
            "content-length": "0",
            "accept-encoding": "gzip",
            "a": "android/11.0.0/ko",
            "c": str(uuid.uuid4()),
            "accept-language": "ko",
            "user-agent": "KT/11.0.0 An/9 ko",
            "authorization": session_info
        }
        
        print(f"[DEBUG] Sharing notice - URL: {url}")
        
        response = requests.post(url, headers=headers)
        
        print(f"[DEBUG] Share response status: {response.status_code}")
        print(f"[DEBUG] Share response body: {response.text}")
        
        # HTTP 상태 코드 체크
        if response.status_code != 200:
            print(f"[ERROR] HTTP error: {response.status_code}")
            return False, f"HTTP 오류: {response.status_code}"
        
        # 응답 본문의 status 필드 체크
        try:
            result = response.json()
            status = result.get("status")
            
            if status is not None and status < 0:
                error_messages = {
                    -4046: "공지 공유 권한이 없거나 이미 공유된 공지입니다",
                    -401: "인증 오류",
                    -403: "권한 없음",
                    -404: "공지를 찾을 수 없음"
                }
                error_msg = error_messages.get(status, f"알 수 없는 오류 (status: {status})")
                print(f"[ERROR] API error: {error_msg}")
                return False, error_msg
            
            print("[SUCCESS] Notice shared successfully")
            return True, "성공"
            
        except json.JSONDecodeError:
            # JSON 파싱 실패 시에도 HTTP 200이면 성공으로 간주
            print("[SUCCESS] Notice shared (non-JSON response)")
            return True, "성공"
            
    except Exception as e:
        print(f"[ERROR] Exception in share_notice: {e}")
        import traceback
        traceback.print_exc()
        return False, f"예외 발생: {str(e)}"

@has_param
def share_notice_command(chat: ChatContext):
    """!공지 명령어 - post_id를 받아 공지를 공유합니다."""
    try:
        print(f"[DEBUG] share_notice_command called")
        
        # 파라미터로 post_id 받기
        post_id = chat.message.param.strip()
        
        if not post_id:
            chat.reply("사용법: !공지 <post_id>")
            return
        
        print(f"[DEBUG] Post ID from param: {post_id}")
        
        # Iris에서 인증 정보 가져오기
        session_info = get_auth_from_iris(chat.api.iris_endpoint)
        
        if not session_info:
            chat.reply("인증 정보를 가져올 수 없습니다.")
            return
        
        # 오픈채팅방이면 link_id 가져오기
        link_id = get_link_id_from_room(chat)
        
        # 공지 공유
        success, message = share_notice(chat, post_id, session_info, link_id)
        
        if success:
            chat.reply(f"✅ 공지 공유 완료\npost_id: {post_id}")
        else:
            chat.reply(f"❌ 공지 공유 실패\n사유: {message}")
            
    except Exception as e:
        import traceback
        print(f"[ERROR] Exception in share_notice_command: {e}")
        traceback.print_exc()
        chat.reply("공지 공유 중 오류가 발생했습니다.")

def share_current_notice(chat: ChatContext):
    """!현재공지 명령어 - 현재 방의 공지를 공유합니다."""
    try:
        print(f"[DEBUG] share_current_notice called")
        
        # moim_meta에서 post_id 가져오기
        post_id = get_post_id_from_room(chat)
        
        if not post_id:
            chat.reply("현재 방에 공지가 없거나 post_id를 찾을 수 없습니다.")
            return
        
        print(f"[DEBUG] Current room post_id: {post_id}")
        
        # Iris에서 인증 정보 가져오기
        session_info = get_auth_from_iris(chat.api.iris_endpoint)
        
        if not session_info:
            chat.reply("인증 정보를 가져올 수 없습니다.")
            return
        
        # 오픈채팅방이면 link_id 가져오기
        link_id = get_link_id_from_room(chat)
        
        # 공지 공유
        success, message = share_notice(chat, post_id, session_info, link_id)
        
        if success:
            chat.reply(f"✅ 현재 방의 공지를 공유했습니다\npost_id: {post_id}")
        else:
            chat.reply(f"❌ 공지 공유 실패\n사유: {message}\npost_id: {post_id}")
            
    except Exception as e:
        import traceback
        print(f"[ERROR] Exception in share_current_notice: {e}")
        traceback.print_exc()
        chat.reply("공지 공유 중 오류가 발생했습니다.")

def set_notice(chat: ChatContext, text: str, session_info: str, link_id: str = None):
    """공지를 등록합니다."""
    try:
        import urllib.parse
        
        # content JSON 구성
        content = json.dumps([{"text": text, "type": "text"}], ensure_ascii=False)
        
        # 오픈채팅 여부에 따라 URL과 body 변경
        if link_id:
            url = f"https://open.kakao.com/moim/chats/{chat.room.id}/posts?link_id={link_id}"
            body = f"content={urllib.parse.quote(content)}&object_type=TEXT&notice=true&link_id={link_id}"
            print(f"[DEBUG] Using open chat URL with link_id: {link_id}")
        else:
            url = f"https://talkmoim-api.kakao.com/chats/{chat.room.id}/posts"
            body = f"content={urllib.parse.quote(content)}&object_type=TEXT&notice=true"
            print(f"[DEBUG] Using regular chat URL")
        
        headers = {
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "A": "android/11.0.0/ko",
            "Authorization": session_info
        }
        
        print(f"[DEBUG] Setting notice - URL: {url}")
        print(f"[DEBUG] Body: {body}")
        
        response = requests.post(url, data=body, headers=headers)
        
        print(f"[DEBUG] Set notice response status: {response.status_code}")
        print(f"[DEBUG] Set notice response body: {response.text}")
        
        if response.status_code == 200:
            try:
                result = response.json()
                status = result.get("status")
                
                # status 필드가 음수면 에러
                if status is not None and status < 0:
                    error_messages = {
                        -4046: "등록 권한이 없거나 이미 처리된 요청입니다",
                        -401: "인증 오류",
                        -403: "권한 없음",
                        -805: "방장이나 관리자만 공지를 등록할 수 있습니다"
                    }
                    error_msg = error_messages.get(status, result.get("error_message", f"알 수 없는 오류 (status: {status})"))
                    print(f"[ERROR] API error: {error_msg}")
                    return False, error_msg
                
                post_id = result.get("id")
                print(f"[SUCCESS] Notice created with post_id: {post_id}")
                return True, post_id
            except json.JSONDecodeError:
                return True, None
        else:
            return False, f"HTTP 오류: {response.status_code}"
            
    except Exception as e:
        print(f"[ERROR] Exception in set_notice: {e}")
        import traceback
        traceback.print_exc()
        return False, str(e)

@has_param
def set_notice_command(chat: ChatContext):
    """!공지등록 명령어 - 새로운 공지를 등록합니다."""
    try:
        print(f"[DEBUG] set_notice_command called")
        
        text = chat.message.param.strip()
        
        if not text:
            chat.reply("사용법: !공지등록 <내용>")
            return
        
        # Iris에서 인증 정보 가져오기
        session_info = get_auth_from_iris(chat.api.iris_endpoint)
        
        if not session_info:
            chat.reply("인증 정보를 가져올 수 없습니다.")
            return
        
        # 오픈채팅방이면 link_id 가져오기
        link_id = get_link_id_from_room(chat)
        
        # 공지 등록
        success, result = set_notice(chat, text, session_info, link_id)
        
        if success:
            if result:
                chat.reply(f"✅ 공지 등록 완료\npost_id: {result}")
            else:
                chat.reply(f"✅ 공지 등록 완료")
        else:
            chat.reply(f"❌ 공지 등록 실패\n사유: {result}")
            
    except Exception as e:
        import traceback
        print(f"[ERROR] Exception in set_notice_command: {e}")
        traceback.print_exc()
        chat.reply("공지 등록 중 오류가 발생했습니다.")

def delete_notice(post_id: str, session_info: str, link_id: str = None):
    """공지를 삭제합니다."""
    try:
        # 오픈채팅 여부에 따라 URL 변경
        if link_id:
            url = f"https://open.kakao.com/moim/posts/{post_id}?link_id={link_id}"
            print(f"[DEBUG] Using open chat URL with link_id: {link_id}")
        else:
            url = f"https://talkmoim-api.kakao.com/posts/{post_id}"
            print(f"[DEBUG] Using regular chat URL")
        
        headers = {
            "A": "android/11.0.0/ko",
            "Authorization": session_info
        }
        
        print(f"[DEBUG] Deleting notice - URL: {url}")
        
        response = requests.delete(url, headers=headers)
        
        print(f"[DEBUG] Delete notice response status: {response.status_code}")
        print(f"[DEBUG] Delete notice response body: {response.text}")
        
        if response.status_code == 200:
            try:
                result = response.json()
                status = result.get("status")
                
                # status 필드가 음수면 에러
                if status is not None and status < 0:
                    error_messages = {
                        -4046: "삭제 권한이 없거나 이미 삭제된 공지입니다",
                        -401: "인증 오류",
                        -403: "권한 없음",
                        -404: "공지를 찾을 수 없음",
                        -805: "방장이나 관리자만 삭제할 수 있습니다"
                    }
                    error_msg = error_messages.get(status, result.get("error_message", f"알 수 없는 오류 (status: {status})"))
                    print(f"[ERROR] API error: {error_msg}")
                    return False, error_msg
                
                print(f"[SUCCESS] Notice deleted")
                return True, "성공"
            except json.JSONDecodeError:
                return True, "성공"
        else:
            return False, f"HTTP 오류: {response.status_code}"
            
    except Exception as e:
        print(f"[ERROR] Exception in delete_notice: {e}")
        import traceback
        traceback.print_exc()
        return False, str(e)

@has_param
def delete_notice_command(chat: ChatContext):
    """!공지삭제 명령어 - 공지를 삭제합니다."""
    try:
        print(f"[DEBUG] delete_notice_command called")
        
        post_id = chat.message.param.strip()
        
        if not post_id:
            chat.reply("사용법: !공지삭제 <post_id>")
            return
        
        # Iris에서 인증 정보 가져오기
        session_info = get_auth_from_iris(chat.api.iris_endpoint)
        
        if not session_info:
            chat.reply("인증 정보를 가져올 수 없습니다.")
            return
        
        # 오픈채팅방이면 link_id 가져오기
        link_id = get_link_id_from_room(chat)
        
        # 공지 삭제
        success, message = delete_notice(post_id, session_info, link_id)
        
        if success:
            chat.reply(f"✅ 공지 삭제 완료\npost_id: {post_id}")
        else:
            chat.reply(f"❌ 공지 삭제 실패\n사유: {message}")
            
    except Exception as e:
        import traceback
        print(f"[ERROR] Exception in delete_notice_command: {e}")
        traceback.print_exc()
        chat.reply("공지 삭제 중 오류가 발생했습니다.")

def change_notice(post_id: str, text: str, session_info: str, link_id: str = None):
    """공지를 수정합니다."""
    try:
        import urllib.parse
        
        # content JSON 구성
        content = json.dumps([{"text": text, "type": "text"}], ensure_ascii=False)
        
        # 오픈채팅 여부에 따라 URL과 body 변경
        if link_id:
            url = f"https://open.kakao.com/moim/posts/{post_id}?link_id={link_id}"
            body = f"content={urllib.parse.quote(content)}&object_type=TEXT&notice=true&link_id={link_id}"
            print(f"[DEBUG] Using open chat URL with link_id: {link_id}")
        else:
            url = f"https://talkmoim-api.kakao.com/posts/{post_id}"
            body = f"content={urllib.parse.quote(content)}&object_type=TEXT&notice=true"
            print(f"[DEBUG] Using regular chat URL")
        
        headers = {
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "A": "android/11.0.0/ko",
            "Authorization": session_info
        }
        
        print(f"[DEBUG] Changing notice - URL: {url}")
        print(f"[DEBUG] Body: {body}")
        
        response = requests.put(url, data=body, headers=headers)
        
        print(f"[DEBUG] Change notice response status: {response.status_code}")
        print(f"[DEBUG] Change notice response body: {response.text}")
        
        if response.status_code == 200:
            try:
                result = response.json()
                status = result.get("status")
                
                # status 필드가 음수면 에러
                if status is not None and status < 0:
                    error_messages = {
                        -4046: "수정 권한이 없거나 이미 처리된 요청입니다",
                        -401: "인증 오류",
                        -403: "권한 없음",
                        -404: "공지를 찾을 수 없음",
                        -805: "방장이나 관리자만 공지를 수정할 수 있습니다"
                    }
                    error_msg = error_messages.get(status, result.get("error_message", f"알 수 없는 오류 (status: {status})"))
                    print(f"[ERROR] API error: {error_msg}")
                    return False, error_msg
                
                print(f"[SUCCESS] Notice changed")
                return True, "성공"
            except json.JSONDecodeError:
                return True, "성공"
        else:
            return False, f"HTTP 오류: {response.status_code}"
            
    except Exception as e:
        print(f"[ERROR] Exception in change_notice: {e}")
        import traceback
        traceback.print_exc()
        return False, str(e)

@has_param
def change_notice_command(chat: ChatContext):
    """!공지수정 명령어 - 공지를 수정합니다."""
    try:
        print(f"[DEBUG] change_notice_command called")
        
        params = chat.message.param.split(" ", 1)
        
        if len(params) < 2:
            chat.reply("사용법: !공지수정 <post_id> <내용>")
            return
        
        post_id = params[0].strip()
        text = params[1].strip()
        
        # Iris에서 인증 정보 가져오기
        session_info = get_auth_from_iris(chat.api.iris_endpoint)
        
        if not session_info:
            chat.reply("인증 정보를 가져올 수 없습니다.")
            return
        
        # 오픈채팅방이면 link_id 가져오기
        link_id = get_link_id_from_room(chat)
        
        # 공지 수정
        success, message = change_notice(post_id, text, session_info, link_id)
        
        if success:
            chat.reply(f"✅ 공지 수정 완료\npost_id: {post_id}")
        else:
            chat.reply(f"❌ 공지 수정 실패\n사유: {message}")
            
    except Exception as e:
        import traceback
        print(f"[ERROR] Exception in change_notice_command: {e}")
        traceback.print_exc()
        chat.reply("공지 수정 중 오류가 발생했습니다.")