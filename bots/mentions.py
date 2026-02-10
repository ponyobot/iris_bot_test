import json
from iris import ChatContext
from iris.decorators import *
from bots.talk_api import talk_write

ALLSEE = '\u200b' * 500


def get_room_master_from_db(chat: ChatContext):
    """데이터베이스에서 방장 ID를 조회합니다 (link_member_type = 1)."""
    try:
        room_id = chat.room.id
        print(f"[DEBUG] Getting room master from DB for room_id: {room_id}")
        
        # 1. chat_rooms에서 active_member_ids 컬럼 가져오기
        query = "SELECT active_member_ids FROM chat_rooms WHERE id = ?"
        results = chat.api.query(query, [room_id])
        
        print(f"[DEBUG] chat_rooms query results: {results}")
        
        if not results or len(results) == 0:
            print(f"[DEBUG] Room not found in chat_rooms")
            return None
        
        members_data = results[0].get("active_member_ids")
        print(f"[DEBUG] active_member_ids data: {members_data}")
        
        if not members_data:
            print(f"[DEBUG] No active_member_ids data found")
            return None
        
        # 2. active_member_ids 데이터 파싱 (JSON 배열 형식)
        try:
            member_ids = json.loads(members_data)
            print(f"[DEBUG] Parsed member IDs: {member_ids}")
        except:
            # JSON이 아니면 쉼표로 구분된 문자열일 수도 있음
            member_ids = [m.strip() for m in members_data.split(",")]
            print(f"[DEBUG] Parsed member IDs (as CSV): {member_ids}")
        
        # 3. 각 멤버를 open_chat_member에서 조회하여 link_member_type = 1인 사람 찾기
        for member_id in member_ids:
            try:
                print(f"[DEBUG] Checking member: {member_id}")
                
                member_query = "SELECT user_id, nickname, enc, link_member_type FROM open_chat_member WHERE user_id = ?"
                member_results = chat.api.query(member_query, [member_id])
                
                print(f"[DEBUG] Member query result for {member_id}: {member_results}")
                
                if member_results and len(member_results) > 0:
                    member_type = member_results[0].get("link_member_type")
                    print(f"[DEBUG] User {member_id} has link_member_type: {member_type}")
                    
                    # link_member_type이 1 또는 "1"이면 방장
                    if str(member_type) == "1":
                        master_id = member_results[0].get("user_id")
                        master_name = member_results[0].get("nickname")
                        print(f"[DEBUG] Room master found in DB: {master_name} ({master_id})")
                        return {"id": int(master_id), "name": master_name}
            
            except Exception as e:
                print(f"[DEBUG] Error checking member {member_id}: {e}")
                continue
        
        print(f"[DEBUG] No HOST found in active_member_ids")
        return None
            
    except Exception as e:
        print(f"[ERROR] Error getting room master from DB: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_room_master_from_members(chat: ChatContext):
    """채팅방 멤버 리스트에서 방장을 찾습니다."""
    try:
        print(f"[DEBUG] Getting room master from members list")
        
        # chat.room.members에서 type이 "HOST"인 사용자 찾기
        if hasattr(chat.room, 'members') and chat.room.members:
            for member in chat.room.members:
                if hasattr(member, 'type'):
                    member_type = member.type
                    print(f"[DEBUG] Checking member: {member.name} (type: {member_type})")
                    
                    if member_type == "HOST":
                        master_id = member.id
                        master_name = member.name
                        print(f"[DEBUG] Room master found in members: {master_name} ({master_id})")
                        return {"id": master_id, "name": master_name}
        
        print(f"[DEBUG] Room master not found in members list")
        return None
        
    except Exception as e:
        print(f"[ERROR] Error getting room master from members: {e}")
        import traceback
        traceback.print_exc()
        return None


def send_mention_message(chat: ChatContext, user_id: int, user_name: str, message_text: str = "", use_brackets: bool = False):
    """
    멘션 메시지를 전송하는 헬퍼 함수
    
    Args:
        use_brackets: True면 [ @유저 ] 형식, False면 @유저 형식
    """
    try:
        print(f"[DEBUG] send_mention_message called")
        print(f"[DEBUG] User ID: {user_id}, Name: {user_name}, Message: {message_text}, Brackets: {use_brackets}")
        
        if not user_name:
            print("[ERROR] user_name is None")
            return False
        
        # 메시지 구성
        if use_brackets:
            # 입장/퇴장/강퇴: [ @유저 ] 형식 (공백 포함)
            full_message = f"[ @{user_name} ]{message_text}".strip()
            at_position = 2  # [ + 공백 + @ 위치
        else:
            # 명령어: @유저 형식
            full_message = f"@{user_name} {message_text}".strip()
            at_position = 0  # 맨 앞에 @ 위치
        
        print(f"[DEBUG] Full message with mention: {full_message}")
        
        # 멘션 정보 구성
        attachment_obj = {
            "mentions": [{
                "user_id": user_id,
                "at": [at_position],
                "len": len(user_name)
            }]
        }
        print(f"[DEBUG] Attachment object: {attachment_obj}")

        result = talk_write(
            iris_endpoint=chat.api.iris_endpoint,
            chat_id=chat.room.id,
            msg=full_message,
            attach=attachment_obj,
            msg_type=1,
        )

        if result.get("result") is False:
            print(f"[ERROR] Failed to send message: {result}")
            return False

        print("[SUCCESS] Mention message sent successfully")
        return True
            
    except Exception as e:
        import traceback
        print(f"[ERROR] Exception in send_mention_message: {e}")
        traceback.print_exc()
        return False


def mention_user(chat: ChatContext):
    """명령어를 입력한 사용자를 멘션합니다."""
    try:
        print(f"[DEBUG] mention_user called")
        
        user_id = chat.sender.id
        user_name = chat.sender.name
        
        print(f"[DEBUG] Sender - ID: {user_id}, Name: {user_name}")
        
        if not user_name:
            chat.reply("사용자 이름을 가져올 수 없습니다.")
            return
        
        # 메시지 내용 (명령어 제거)
        message_text = chat.message.msg[4:].strip()
        
        success = send_mention_message(chat, user_id, user_name, message_text)
        
        if not success:
            chat.reply("멘션 전송에 실패했습니다.")
            
    except Exception as e:
        import traceback
        print(f"[ERROR] Exception in mention_user: {e}")
        traceback.print_exc()
        chat.reply("멘션 중 오류가 발생했습니다.")


def mention_new_member(chat: ChatContext):
    """입장한 멤버를 멘션합니다 (기존 이벤트용)."""
    try:
        print(f"[DEBUG] mention_new_member called")
        print(f"[DEBUG] Sender ID: {chat.sender.id}")
        print(f"[DEBUG] Sender Name: {chat.sender.name}")
        print(f"[DEBUG] Room ID: {chat.room.id}")
        print(f"[DEBUG] Room Name: {chat.room.name}")
        
        # new_member 이벤트에서는 chat.sender가 입장한 사람
        user_id = chat.sender.id
        user_name = chat.sender.name
        
        if not user_id or not user_name:
            print("[ERROR] Could not get user info")
            return
        
        print(f"[DEBUG] Mentioning new member: {user_name} ({user_id})")
        send_mention_message(chat, user_id, user_name, f"Hello 🎉{ALLSEE}\n테스트 메세지 입니다")
            
    except Exception as e:
        import traceback
        print(f"[ERROR] Exception in mention_new_member: {e}")
        traceback.print_exc()


def handle_member_event(chat: ChatContext):
    """입장/퇴장/강퇴 이벤트를 파싱하여 처리합니다."""
    try:
        print(f"[DEBUG] handle_member_event called")
        print(f"[DEBUG] Message: {chat.message.msg}")
        
        # 메시지 파싱
        msg_data = json.loads(chat.message.msg)
        feed_type = msg_data.get("feedType")
        
        print(f"[DEBUG] feedType: {feed_type}")
        
        if feed_type == 4:  # 입장
            # members 배열에서 첫 번째 멤버 정보 추출
            members = msg_data.get("members", [])
            if members and len(members) > 0:
                member = members[0]
                user_id = member.get("userId")
                user_name = member.get("nickName")
                
                print(f"[DEBUG] 입장 - User ID: {user_id}, Name: {user_name}")
                
                if user_id and user_name:
                    message_text = f"안녕하세요! 🎉{ALLSEE}\n\n테스트 메세지 입니다!"
                    send_mention_message(chat, user_id, user_name, message_text, use_brackets=True)
        
        elif feed_type == 2:  # 퇴장
            member = msg_data.get("member", {})
            user_id = member.get("userId")
            user_name = member.get("nickName")
            
            print(f"[DEBUG] 퇴장 - User ID: {user_id}, Name: {user_name}")
            
            if user_id and user_name:
                message_text = f"안녕히 가세요!{ALLSEE}\n\n테스트 메세지 입니다!"
                send_mention_message(chat, user_id, user_name, message_text, use_brackets=True)
        
        elif feed_type == 6:  # 강퇴
            member = msg_data.get("member", {})
            user_id = member.get("userId")
            user_name = member.get("nickName")
            
            print(f"[DEBUG] 강퇴 - User ID: {user_id}, Name: {user_name}")
            print(f"[DEBUG] 강퇴한 사람 - Name: {chat.sender.name}")
            
            if user_id and user_name:
                # 강퇴는 특별한 형식: "강퇴한사람님이 [ @유저 ] 님을 강퇴했습니다!"
                message_text = f"{chat.sender.name}님이 "
                full_message = f"{message_text}[ @{user_name} ] 님을 강퇴했습니다! {ALLSEE}\n\n테스트 메세지 입니다!"
                
                # @ 위치 계산: message_text 길이 + "[ " 길이
                at_position = len(message_text) + 2
                
                attachment_obj = {
                    "mentions": [{
                        "user_id": user_id,
                        "at": [at_position],
                        "len": len(user_name)
                    }]
                }
                
                print(f"[DEBUG] Full message: {full_message}")
                print(f"[DEBUG] Attachment: {attachment_obj}")
                
                result = talk_write(
                    iris_endpoint=chat.api.iris_endpoint,
                    chat_id=chat.room.id,
                    msg=full_message,
                    attach=attachment_obj,
                    msg_type=1,
                )
                
                if result.get("result") is False:
                    print(f"[ERROR] Failed to send kick message: {result}")
        
        else:
            print(f"[DEBUG] Unknown feedType: {feed_type}")
            
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON parsing error: {e}")
        import traceback
        traceback.print_exc()
    except Exception as e:
        import traceback
        print(f"[ERROR] Exception in handle_member_event: {e}")
        traceback.print_exc()


def mention_room_master(chat: ChatContext):
    """현재 방의 방장을 멘션합니다."""
    try:
        print(f"[DEBUG] mention_room_master called")
        print(f"[DEBUG] Room ID: {chat.room.id}")
        
        # 먼저 DB에서 방장 정보 조회
        master_info = get_room_master_from_db(chat)
        
        # DB에서 못 찾으면 멤버 리스트에서 찾기
        if not master_info:
            print(f"[DEBUG] Trying to find master from members list")
            master_info = get_room_master_from_members(chat)
        
        if not master_info:
            chat.reply("방장 정보를 찾을 수 없습니다.")
            return
        
        master_id = master_info["id"]
        master_name = master_info["name"]
        
        if not master_name:
            chat.reply("방장의 이름을 가져올 수 없습니다.")
            return
        
        # 메시지 내용 (명령어 제거)
        message_text = chat.message.msg[4:].strip()  # !방장 제거
        
        if not message_text:
            message_text = "방장님 호출합니다!"
        
        print(f"[DEBUG] Mentioning room master: {master_name} ({master_id})")
        
        success = send_mention_message(chat, master_id, master_name, message_text)
        
        if not success:
            chat.reply("방장 멘션 전송에 실패했습니다.")
            
    except Exception as e:
        import traceback
        print(f"[ERROR] Exception in mention_room_master: {e}")
        traceback.print_exc()
        chat.reply("방장 호출 중 오류가 발생했습니다.")