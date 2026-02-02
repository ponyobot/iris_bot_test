# bots/user_posts.py
import requests
import json
from datetime import datetime
from iris import ChatContext
from iris.decorators import *

def get_auth_from_iris(iris_endpoint: str):
    """Iris에서 AOT 토큰 정보를 가져옵니다."""
    try:
        aot_url = f"{iris_endpoint}/aot"
        response = requests.get(aot_url)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                aot_data = data.get("aot", {})
                access_token = aot_data.get("access_token")
                device_uuid = aot_data.get("d_id")
                
                if access_token and device_uuid:
                    return f"{access_token}-{device_uuid}"
        return None
    except Exception as e:
        print(f"[ERROR] Error getting auth: {e}")
        return None

def get_user_profile_link_id_from_db(chat: ChatContext, user_id: str):
    """데이터베이스에서 유저의 모든 정보를 가져와 profile_link_id를 반환합니다."""
    try:
        # 모든 컬럼을 조회하도록 쿼리 수정
        query = "SELECT * FROM open_chat_member WHERE user_id = ?"
        result = chat.api.query(query=query, bind=[user_id])
        
        print(f"[DEBUG] Full query result: {result}")
        
        if result and len(result) > 0:
            # 전체 결과(dict 형태)에서 필요한 필드 추출
            user_data = result[0]
            profile_link_id = user_data.get("profile_link_id")
            
            print(f"[DEBUG] Found profile_link_id: {profile_link_id}")
            return profile_link_id
        
        return None
    except Exception as e:
        print(f"[ERROR] Error getting user info: {e}")
        import traceback
        traceback.print_exc()
        return None

def format_timestamp(timestamp: int) -> str:
    """타임스탬프를 읽기 쉬운 날짜로 변환합니다."""
    try:
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime('%Y-%m-%d %H:%M')
    except:
        return str(timestamp)

def get_user_posts_by_profile_link_id(profile_link_id: str, last_post_id: int = 0, count: int = 20, session_info: str = None):
    """profile_link_id로 유저 포스트를 가져옵니다."""
    try:
        url = f"https://open.kakao.com/profile/{profile_link_id}/posts/all?lastPostId={last_post_id}&count={count}"
        
        headers = {
            "Authorization": session_info,
            "accept-language": "ko",
            "content-type": "application/json",
            "A": "android/25.8.2/ko",
            "User-Agent": "KT/11.0.0 An/9 ko"
        }
        
        print(f"[DEBUG] Getting user posts - URL: {url}")
        
        response = requests.get(url, headers=headers)
        
        print(f"[DEBUG] Response status: {response.status_code}")
        print(f"[DEBUG] Response body: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            # status가 음수면 에러
            if data.get("status", 0) < 0:
                return None, f"API 오류 (status: {data.get('status')})"
            # count가 0이면 포스트 없음
            if data.get("count", 0) == 0:
                return None, "포스트가 없습니다"
            return data, "성공"
        else:
            return None, f"HTTP 오류: {response.status_code}"
            
    except Exception as e:
        print(f"[ERROR] Exception in get_user_posts_by_profile_link_id: {e}")
        import traceback
        traceback.print_exc()
        return None, str(e)

@has_param
def get_user_posts_command(chat: ChatContext):
    """!유저포스트 명령어 - 특정 유저의 포스트 목록을 가져옵니다."""
    try:
        print(f"[DEBUG] get_user_posts_command called")
        
        # 파라미터로 user_id 또는 profile_link_id 받기
        param = chat.message.param.strip()
        
        if not param:
            chat.reply("사용법: !유저포스트 <user_id 또는 profile_link_id>")
            return
        
        # Iris에서 인증 정보 가져오기
        session_info = get_auth_from_iris(chat.api.iris_endpoint)
        
        if not session_info:
            chat.reply("인증 정보를 가져올 수 없습니다.")
            return
        
        # 숫자가 매우 크면 user_id, 작으면 profile_link_id
        if len(param) > 10:  # user_id는 매우 긴 숫자
            user_id = param
            profile_link_id = get_user_profile_link_id_from_db(chat, user_id)
            
            if not profile_link_id:
                chat.reply(f"유저 {user_id}의 profile_link_id를 찾을 수 없습니다.")
                return
        else:  # profile_link_id를 직접 입력
            profile_link_id = param
        
        print(f"[DEBUG] Using profile_link_id: {profile_link_id}")
        
        # 포스트 가져오기
        posts, message = get_user_posts_by_profile_link_id(profile_link_id, session_info=session_info)
        
        if posts is None:
            chat.reply(f"포스트를 가져올 수 없습니다.\n사유: {message}")
            return
        
        # 포스트 목록 정리
        post_list = posts.get("posts", [])
        
        if not post_list:
            chat.reply("포스트가 없습니다.")
            return
        
        # 결과 출력
        result_lines = [f"📝 유저 포스트 ({len(post_list)}개)\n"]
        
        for i, post in enumerate(post_list[:10]):  # 최대 10개만 표시
            post_id = post.get("id", "unknown")
            
            # postDescription에서 내용 추출
            post_desc = post.get("postDescription", {})
            content_text = post_desc.get("text", "")
            
            # 스크랩 데이터가 있으면 추가
            scrap_data = post.get("scrapData", {})
            scrap_title = scrap_data.get("title", "")
            scrap_url = scrap_data.get("url", "")
            
            # 날짜 변환
            timestamp = post.get("date", 0)
            created_at = format_timestamp(timestamp)
            
            # 포스트 URL
            post_url = post.get("postUrl", "")
            
            result_lines.append(
                f"{i + 1}. 📄 ID: {post_id}\n"
                f"📅 {created_at}\n"
                f"💬 {content_text[:50]}{'...' if len(content_text) > 50 else ''}"
            )
            
            if scrap_title:
                result_lines.append(f"🔗 {scrap_title}")
            
            if post_url:
                result_lines.append(f"🌐 {post_url}")
            
            result_lines.append("")  # 빈 줄
        
        chat.reply("\n".join(result_lines))
        
    except Exception as e:
        import traceback
        print(f"[ERROR] Exception in get_user_posts_command: {e}")
        traceback.print_exc()
        chat.reply("유저 포스트 조회 중 오류가 발생했습니다.")

@is_reply
def get_replied_user_posts_command(chat: ChatContext):
    """!포스트목록 명령어 - 답장한 유저의 포스트 목록을 가져옵니다."""
    try:
        print(f"[DEBUG] get_replied_user_posts_command called")
        
        # 답장한 메시지의 발신자 ID 가져오기
        src_chat = chat.get_source()
        user_id = str(src_chat.sender.id)
        user_name = src_chat.sender.name
        
        print(f"[DEBUG] User ID: {user_id}, Name: {user_name}")
        
        # Iris에서 인증 정보 가져오기
        session_info = get_auth_from_iris(chat.api.iris_endpoint)
        
        if not session_info:
            chat.reply("인증 정보를 가져올 수 없습니다.")
            return
        
        # DB에서 profile_link_id 가져오기
        profile_link_id = get_user_profile_link_id_from_db(chat, user_id)
        
        if not profile_link_id:
            chat.reply(f"{user_name}님의 profile_link_id를 찾을 수 없습니다.")
            return
        
        print(f"[DEBUG] Using profile_link_id: {profile_link_id}")
        
        # 포스트 가져오기
        posts, message = get_user_posts_by_profile_link_id(profile_link_id, session_info=session_info)
        
        if posts is None:
            chat.reply(f"{user_name}님의 포스트를 가져올 수 없습니다.\n사유: {message}")
            return
        
        # 포스트 목록 정리
        post_list = posts.get("posts", [])
        
        if not post_list:
            chat.reply(f"{user_name}님의 포스트가 없습니다.")
            return
        
        # 결과 출력
        ALLSEE = '\u200b' * 500
        result_lines = [f"📝 {user_name}님의 포스트 ({len(post_list)}개){ALLSEE}\n"]
        
        for i, post in enumerate(post_list[:10]):  # 최대 10개만 표시
            post_id = post.get("id", "unknown")
            
            # postDescription에서 내용 추출
            post_desc = post.get("postDescription", {})
            content_text = post_desc.get("text", "")
            
            # 스크랩 데이터가 있으면 추가
            scrap_data = post.get("scrapData", {})
            scrap_title = scrap_data.get("title", "")
            scrap_url = scrap_data.get("url", "")
            
            # 날짜 변환
            timestamp = post.get("date", 0)
            created_at = format_timestamp(timestamp)
            
            # 포스트 URL
            post_url = post.get("postUrl", "")
            
            result_lines.append(
                f"{i + 1}. 📄 ID: {post_id}\n"
                f"📅 {created_at}\n"
                f"💬 {content_text[:50]}{'...' if len(content_text) > 50 else ''}"
            )
            
            if scrap_title:
                result_lines.append(f"🔗 {scrap_title}")
            
            if post_url:
                result_lines.append(f"🌐 {post_url}")
            
            result_lines.append("")  # 빈 줄
        
        chat.reply("\n".join(result_lines))
        
    except Exception as e:
        import traceback
        print(f"[ERROR] Exception in get_replied_user_posts_command: {e}")
        traceback.print_exc()
        chat.reply("유저 포스트 조회 중 오류가 발생했습니다.")

@is_reply
def debug_user_info(chat: ChatContext):
    """!유저정보 - 답장한 유저의 DB 정보를 출력합니다."""
    try:
        src_chat = chat.get_source()
        user_id = str(src_chat.sender.id)
        
        # DB에서 유저 정보 조회
        query = "SELECT * FROM open_chat_member WHERE user_id = ?"
        result = chat.api.query(query=query, bind=[user_id])
        
        if result and len(result) > 0:
            user_info = result[0]
            info_lines = ["📋 유저 DB 정보"]
            for key, value in user_info.items():
                info_lines.append(f"{key}: {value}")
            
            chat.reply("\n".join(info_lines))
        else:
            chat.reply("유저 정보를 찾을 수 없습니다.")
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        chat.reply(f"오류: {e}")