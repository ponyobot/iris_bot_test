import requests
import json
import uuid
import urllib.parse
from datetime import datetime, timedelta, timezone
from iris import ChatContext
from iris.decorators import *


def get_link_id(chat: ChatContext):
    """DB에서 현재 채팅방의 link_id를 가져옵니다."""
    try:
        result = chat.api.query(
            query="SELECT id, link_id, type FROM chat_rooms WHERE id = ?",
            bind=[str(chat.room.id)]
        )
        if result and len(result) > 0:
            return result[0].get("link_id")
        return None
    except Exception as e:
        print(f"[Vote] Failed to get link_id: {e}")
        return None


def create_poll(chat: ChatContext, subject: str, items: list, multi_select: bool = False, secret: bool = False, hours: int = 48):
    """투표를 생성합니다."""
    try:
        link_id = get_link_id(chat)
        print(f"[Vote] link_id: {link_id}")
        print(f"[Vote] room.id: {chat.room.id}")
        if not link_id:
            chat.reply("오픈채팅방의 link_id를 찾을 수 없습니다.\n오픈채팅방에서만 사용 가능합니다.")
            return

        # notification.py와 동일하게 매번 새로 fetch
        try:
            aot_resp = requests.get(f"{chat.api.iris_endpoint}/aot", timeout=3)
            aot_data = aot_resp.json()
            if not aot_data.get("success"):
                chat.reply("인증 정보를 가져올 수 없습니다.")
                return
            aot = aot_data.get("aot", {})
            access_token = aot.get("access_token")
            device_uuid = aot.get("d_id")
            if not access_token or not device_uuid:
                chat.reply("인증 정보를 가져올 수 없습니다.")
                return
        except Exception as e:
            print(f"[Vote] AOT fetch error: {e}")
            chat.reply("인증 정보를 가져올 수 없습니다.")
            return

        auth = f"{access_token}-{device_uuid}"
        print(f"[Vote] access_token: {access_token[:20]}...")
        print(f"[Vote] device_uuid: {device_uuid}")
        print(f"[Vote] auth: {auth[:30]}...{auth[-15:]}")

        closed_at = (datetime.now(timezone.utc) + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:00.000Z")

        poll_items = [{"title": item.strip()} for item in items]

        poll_content = json.dumps({
            "closed_at": closed_at,
            "alarm": 30,
            "poll_details": [{
                "subject": subject,
                "item_type": "text",
                "item_addable": False,
                "multi_select": multi_select,
                "secret": secret,
                "items": poll_items
            }]
        }, ensure_ascii=False, separators=(',', ':'))

        url = f"https://open.kakao.com/moim/chats/{chat.room.id}/posts?link_id={link_id}"
        body = (
            f"object_type=POLL"
            f"&poll_content={urllib.parse.quote(poll_content)}"
            f"&link_id={link_id}"
            f"&notice=false"
        )

        headers = {
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "A": "android/11.0.0/ko",
            "C": str(uuid.uuid4()),
            "User-Agent": "KT/11.0.0 An/9 ko",
            "Accept-Language": "ko",
            "Authorization": auth,
        }

        print(f"[Vote] ===== REQUEST =====")
        print(f"[Vote] URL: {url}")
        print(f"[Vote] Headers: A={headers['A']} | C={headers['C']}")
        print(f"[Vote] poll_content (decoded): {poll_content}")
        print(f"[Vote] Body (encoded): {body}")

        response = requests.post(url, data=body, headers=headers, timeout=5)

        print(f"[Vote] ===== RESPONSE =====")
        print(f"[Vote] Status: {response.status_code}")
        print(f"[Vote] Body: {response.text}")
        print(f"[Vote] ===================")

        # -4001 권한 오류 시 토큰 갱신 후 1회 재시도
        if response.status_code == 200 and response.json().get("status") == -4001:
            import time
            print(f"[Vote] -4001 발생, 토큰 갱신 후 재시도...")
            time.sleep(1)
            try:
                aot_resp2 = requests.get(f"{chat.api.iris_endpoint}/aot", timeout=3)
                aot2 = aot_resp2.json().get("aot", {})
                at2 = aot2.get("access_token")
                du2 = aot2.get("d_id")
                if at2 and du2:
                    headers["Authorization"] = f"{at2}-{du2}"
                    print(f"[Vote] 재시도 auth: {at2[:20]}...")
            except Exception as re:
                print(f"[Vote] 재시도 AOT fetch error: {re}")
            response = requests.post(url, data=body, headers=headers, timeout=5)
            print(f"[Vote] 재시도 Status: {response.status_code}")
            print(f"[Vote] 재시도 Body: {response.text}")
            

        if response.status_code == 200:
            data = response.json()
            status = data.get("status", 0)
            if status < 0:
                error_messages = {
                    -401: "인증 오류",
                    -403: "권한 없음",
                    -805: "방장이나 관리자만 사용 가능합니다",
                    -4001: "권한이 없습니다 (방장/관리자만 가능)",
                }
                error_msg = error_messages.get(status, f"API 오류 (status: {status})")
                chat.reply(f"❌ 투표 생성 실패\n사유: {error_msg}")
                return

            options = []
            if multi_select:
                options.append("복수선택 가능")
            if secret:
                options.append("익명투표")
            option_str = f" ({', '.join(options)})" if options else ""

            item_list = "\n".join([f"  {i+1}. {item}" for i, item in enumerate(items)])
            chat.reply(
                f"✅ 투표가 생성되었습니다{option_str}\n"
                f"📊 {subject}\n"
                f"{item_list}\n"
                f"⏰ {hours}시간 후 마감"
            )
        else:
            chat.reply(f"❌ 투표 생성 실패\nHTTP 오류: {response.status_code}\n{response.text}")

    except Exception as e:
        import traceback
        traceback.print_exc()
        chat.reply("투표 생성 중 오류가 발생했습니다.")


@has_param
def vote_command(chat: ChatContext):
    """
    !투표 명령어 - 투표를 생성합니다.

    사용법:
      !투표 제목##항목1##항목2##항목3
      !투표 제목##항목1##항목2 복수
      !투표 제목##항목1##항목2 비밀
      !투표 제목##항목1##항목2 복수 비밀
      !투표 제목##항목1##항목2 마감:72  (시간 단위, 기본 48시간)
    """
    try:
        raw = chat.message.param.strip()

        multi_select = False
        secret = False
        hours = 48

        parts = raw.split(" ")
        content_parts = []
        for part in parts:
            if part == "복수":
                multi_select = True
            elif part == "비밀":
                secret = True
            elif part.startswith("마감:"):
                try:
                    hours = int(part[3:])
                except ValueError:
                    pass
            else:
                content_parts.append(part)

        content = " ".join(content_parts)

        split = content.split("##")
        if len(split) < 3:
            chat.reply(
                "사용법: !투표 제목##항목1##항목2##...\n\n"
                "옵션 (공백으로 구분):\n"
                "  복수 - 복수선택 허용\n"
                "  비밀 - 익명투표\n"
                "  마감:시간 - 마감시간 설정 (기본 48시간)\n\n"
                "예시:\n"
                "  !투표 점심메뉴##짜장면##짬뽕##볶음밥\n"
                "  !투표 점심메뉴##짜장면##짬뽕 복수 비밀 마감:24"
            )
            return

        subject = split[0].strip()
        items = [item.strip() for item in split[1:] if item.strip()]

        if not subject:
            chat.reply("투표 제목을 입력해주세요.")
            return

        if len(items) < 2:
            chat.reply("항목은 최소 2개 이상 입력해주세요.")
            return

        if len(items) > 10:
            chat.reply("항목은 최대 10개까지 입력 가능합니다.")
            return

        create_poll(chat, subject, items, multi_select=multi_select, secret=secret, hours=hours)

    except Exception as e:
        import traceback
        traceback.print_exc()
        chat.reply("투표 명령어 처리 중 오류가 발생했습니다.")