import requests
import json
import uuid
from datetime import datetime, timedelta
from iris import ChatContext
from iris.decorators import *

def format_time_kst(utc_time_str: str) -> str:
    """UTC 시간을 KST로 변환하고 간단한 형식으로 반환합니다."""
    try:
        # ISO 8601 형식 파싱 (예: 2026-01-18T16:26:04.000Z)
        utc_time = datetime.fromisoformat(utc_time_str.replace('Z', '+00:00'))
        # KST = UTC + 9시간
        kst_time = utc_time + timedelta(hours=9)
        # YYYY-MM-DD HH:MM 형식으로 반환
        return kst_time.strftime('%Y-%m-%d %H:%M')
    except Exception as e:
        print(f"[DEBUG] Error formatting time: {e}")
        return utc_time_str

def get_notice_type_label(object_type: str) -> str:
    """공지 타입을 아이콘과 한글로 변환합니다."""
    type_map = {
        "TEXT": "📝 텍스트",
        "SCHEDULE": "📅 일정",
        "POLL": "📊 투표",
        "QUIZ": "❓ 퀴즈"
    }
    return type_map.get(object_type, f"❔ {object_type}")

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

def get_notices(chat: ChatContext):
    """현재 방의 공지 목록을 가져옵니다."""
    try:
        session_info = get_auth_from_iris(chat.api.iris_endpoint)
        if not session_info:
            return None, "인증 정보를 가져올 수 없습니다."

        link_id = get_link_id_from_room(chat)

        if link_id:
            url = f"https://open.kakao.com/moim/chats/{chat.room.id}/posts?link_id={link_id}"
        else:
            url = f"https://talkmoim-api.kakao.com/chats/{chat.room.id}/posts"

        headers = {
            "Authorization": session_info,
            "accept-language": "ko",
            "content-type": "application/x-www-form-urlencoded",
            "A": "android/25.8.2/ko"
        }

        print(f"[DEBUG] get_notices URL: {url}")

        response = requests.get(url, headers=headers)

        print(f"[DEBUG] get_notices status: {response.status_code}")
        print(f"[DEBUG] get_notices body: {response.text}")

        if response.status_code == 200:
            return response.json(), "성공"
        else:
            return None, f"HTTP 오류: {response.status_code}"

    except Exception as e:
        import traceback
        print(f"[ERROR] Error in get_notices: {e}")
        traceback.print_exc()
        return None, str(e)

def get_notices_command(chat: ChatContext):
    """!공지목록 명령어 - 현재 방의 공지 목록을 요약 출력합니다."""
    try:
        print(f"[DEBUG] get_notices_command called")

        notices, message = get_notices(chat)
        if notices is None:
            chat.reply(f"공지 목록을 가져올 수 없습니다.\n사유: {message}")
            return

        if isinstance(notices, dict):
            notices = notices.get("posts", [])

        if not notices:
            chat.reply("현재 방에 공지가 없습니다.")
            return

        # open_chat_member 테이블에서 닉네임 맵 생성
        member_names = {}
        try:
            query = "SELECT * FROM open_chat_member"
            result = chat.api.query(query=query)
            print(f"[DEBUG] open_chat_member query result count: {len(result) if result else 0}")
            for row in result:
                user_id = row.get("user_id")
                nickname = row.get("nickname")
                if user_id and nickname:
                    member_names[user_id] = nickname
            print(f"[DEBUG] member_names map size: {len(member_names)}")
        except Exception as e:
            print(f"[DEBUG] Error getting nicknames from open_chat_member: {e}")

        result_lines = ["📌 공지 목록"]
        for i, notice in enumerate(notices):
            post_id = notice.get("id", "unknown")
            owner_id = str(notice.get("owner_id"))
            print(f"[DEBUG] Notice {i+1} - owner_id from API: {owner_id} (type: {type(notice.get('owner_id'))})")
            author = member_names.get(owner_id, owner_id)
            print(f"[DEBUG] Notice {i+1} - author found: {author}")
            created_at = format_time_kst(notice.get("created_at", ""))
            
            # 타입과 고정 여부
            object_type = notice.get("object_type", "UNKNOWN")
            type_label = get_notice_type_label(object_type)
            is_notice = notice.get("notice", False)
            notice_badge = "📌 공지" if is_notice else "📄 일반"
            
            result_lines.append(f"\n{i + 1}. {author}\n📄 {post_id}\n🏷️ {type_label} | {notice_badge}\n🕐 {created_at}")

        chat.reply("\n".join(result_lines))

    except Exception as e:
        import traceback
        print(f"[ERROR] Exception in get_notices_command: {e}")
        traceback.print_exc()
        chat.reply("공지 목록 조회 중 오류가 발생했습니다.")

@has_param
def get_notice_detail_command(chat: ChatContext):
    """!공지확인 명령어 - 특정 공지의 내용을 확인합니다."""
    try:
        print(f"[DEBUG] get_notice_detail_command called")

        post_id = chat.message.param.strip()

        notices, message = get_notices(chat)
        if notices is None:
            chat.reply(f"공지를 가져올 수 없습니다.\n사유: {message}")
            return

        if isinstance(notices, dict):
            notices = notices.get("posts", [])

        # 해당 post_id 공지 찾기
        target = None
        for notice in notices:
            if notice.get("id") == post_id:
                target = notice
                break

        if not target:
            chat.reply(f"'{post_id}' 공지를 찾을 수 없습니다.")
            return

        # open_chat_member 테이블에서 닉네임 가져오기
        owner_id = str(target.get("owner_id"))
        print(f"[DEBUG] owner_id from API: {owner_id}")
        author = owner_id
        
        try:
            query = "SELECT * FROM open_chat_member WHERE user_id = ?"
            result = chat.api.query(query=query, bind=[owner_id])
            print(f"[DEBUG] open_chat_member query result: {result}")
            
            if result and len(result) > 0 and result[0].get("nickname"):
                author = result[0].get("nickname")
                print(f"[DEBUG] Found nickname: {author}")
            else:
                print(f"[DEBUG] No nickname found for user_id={owner_id}")
        except Exception as e:
            print(f"[DEBUG] Error getting nickname from open_chat_member: {e}")
            import traceback
            traceback.print_exc()
        
        created_at = format_time_kst(target.get("created_at", ""))

        # 타입별 content 파싱
        object_type = target.get("object_type", "TEXT")
        type_label = get_notice_type_label(object_type)
        content = ""
        
        try:
            if object_type == "TEXT":
                # 텍스트 공지
                content_list = json.loads(target.get("content", "[]"))
                content = content_list[0].get("text", "")
                
            elif object_type == "SCHEDULE":
                # 일정
                schedule = target.get("schedule", {})
                subject = schedule.get("subject", "")
                start_at = format_time_kst(schedule.get("start_at", ""))
                end_at = format_time_kst(schedule.get("end_at", ""))
                all_day = schedule.get("all_day", False)
                
                content = f"📅 일정: {subject}\n"
                if all_day:
                    content += f"⏰ 종일"
                else:
                    content += f"⏰ {start_at} ~ {end_at}"
                    
            elif object_type == "POLL":
                # 투표
                poll = target.get("poll", {})
                poll_details = poll.get("poll_details", [])
                if poll_details:
                    detail = poll_details[0]
                    subject = detail.get("subject", "")
                    items = detail.get("items", [])
                    closed = poll.get("closed", False)
                    closed_at = format_time_kst(poll.get("closed_at", ""))
                    
                    content = f"📊 투표: {subject}\n"
                    content += f"상태: {'종료' if closed else '진행중'}\n"
                    if not closed:
                        content += f"마감: {closed_at}\n"
                    content += "\n선택지:\n"
                    for idx, item in enumerate(items, 1):
                        title = item.get("title", "")
                        user_count = item.get("user_count", 0)
                        content += f"{idx}. {title} ({user_count}표)\n"
                        
            elif object_type == "QUIZ":
                # 퀴즈
                quiz = target.get("quiz", {})
                quiz_details = quiz.get("quiz_details", [])
                if quiz_details:
                    detail = quiz_details[0]
                    subject = detail.get("subject", "")
                    items = detail.get("items", [])
                    closed = quiz.get("closed", False)
                    time_limit = quiz.get("time_limit", 0)
                    
                    content = f"❓ 퀴즈: {subject}\n"
                    content += f"상태: {'종료' if closed else '진행중'}\n"
                    content += f"제한시간: {time_limit}초\n"
                    content += "\n선택지:\n"
                    for idx, item in enumerate(items, 1):
                        title = item.get("title", "")
                        user_count = item.get("user_count", 0)
                        content += f"{idx}. {title} ({user_count}명)\n"
        except Exception as e:
            print(f"[DEBUG] Error parsing content: {e}")
            import traceback
            traceback.print_exc()
            content = "(내용을 불러올 수 없습니다)"

        ALLSEE = '\u200b' * 500
        chat.reply(f"{ALLSEE}📌 공지\n🏷️ {type_label}\n✍️ {author}\n🕐 {created_at}\n\n{content}")

    except Exception as e:
        import traceback
        print(f"[ERROR] Exception in get_notice_detail_command: {e}")
        traceback.print_exc()
        chat.reply("공지 확인 중 오류가 발생했습니다.")

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
        
        if response.status_code != 200:
            print(f"[ERROR] HTTP error: {response.status_code}")
            return False, f"HTTP 오류: {response.status_code}"
        
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
        
        post_id = chat.message.param.strip()
        
        if not post_id:
            chat.reply("사용법: !공지 <post_id>")
            return
        
        print(f"[DEBUG] Post ID from param: {post_id}")
        
        session_info = get_auth_from_iris(chat.api.iris_endpoint)
        
        if not session_info:
            chat.reply("인증 정보를 가져올 수 없습니다.")
            return
        
        link_id = get_link_id_from_room(chat)
        
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
        
        post_id = get_post_id_from_room(chat)
        
        if not post_id:
            chat.reply("현재 방에 공지가 없거나 post_id를 찾을 수 없습니다.")
            return
        
        print(f"[DEBUG] Current room post_id: {post_id}")
        
        session_info = get_auth_from_iris(chat.api.iris_endpoint)
        
        if not session_info:
            chat.reply("인증 정보를 가져올 수 없습니다.")
            return
        
        link_id = get_link_id_from_room(chat)
        
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
        
        content = json.dumps([{"text": text, "type": "text"}], ensure_ascii=False)
        
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
        
        session_info = get_auth_from_iris(chat.api.iris_endpoint)
        
        if not session_info:
            chat.reply("인증 정보를 가져올 수 없습니다.")
            return
        
        link_id = get_link_id_from_room(chat)
        
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
        
        session_info = get_auth_from_iris(chat.api.iris_endpoint)
        
        if not session_info:
            chat.reply("인증 정보를 가져올 수 없습니다.")
            return
        
        link_id = get_link_id_from_room(chat)
        
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
        
        content = json.dumps([{"text": text, "type": "text"}], ensure_ascii=False)
        
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
        
        session_info = get_auth_from_iris(chat.api.iris_endpoint)
        
        if not session_info:
            chat.reply("인증 정보를 가져올 수 없습니다.")
            return
        
        link_id = get_link_id_from_room(chat)
        
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