import requests
from iris import ChatContext
from iris.decorators import *
from bots.talk_api import get_auth


def search_open_chat(keyword: str, count: int, access_token: str, device_uuid: str, os_str: str = "android", version: str = "9.8.0", language: str = "ko"):
    """오픈채팅방을 검색합니다."""
    try:
        url = f"https://open.kakao.com/c/search/unified?q={requests.utils.quote(keyword)}&c={count}&page=1"

        headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "A": f"{os_str}/{version}/{language}",
            "Authorization": f"{access_token}-{device_uuid}",
        }

        response = requests.post(url, headers=headers, timeout=10)

        if response.status_code == 200:
            result = response.json()
            import json
            print(f"[RoomInfo] ===== SEARCH RESPONSE =====")
            print(f"[RoomInfo] keyword: {keyword}, count: {count}")
            print(f"[RoomInfo] status_code: {response.status_code}")
            print(f"[RoomInfo] full response:")
            print(json.dumps(result, ensure_ascii=False, indent=2))
            print(f"[RoomInfo] ============================")
            return result, "성공"
        else:
            print(f"[RoomInfo] ===== SEARCH ERROR =====")
            print(f"[RoomInfo] keyword: {keyword}, count: {count}")
            print(f"[RoomInfo] status_code: {response.status_code}")
            print(f"[RoomInfo] response body: {response.text}")
            print(f"[RoomInfo] ==========================")
            return None, f"HTTP 오류: {response.status_code}"

    except Exception as e:
        print(f"[RoomInfo] Exception in search_open_chat: {e}")
        return None, str(e)


@has_param
def room_search_command(chat: ChatContext):
    """!방검색 명령어 - 오픈채팅방을 검색합니다."""
    try:
        param = chat.message.param.strip()

        # 파라미터 파싱: "키워드" 또는 "키워드 개수"
        parts = param.rsplit(" ", 1)
        count = 1  # 기본값
        if len(parts) == 2 and parts[1].isdigit():
            keyword = parts[0].strip()
            count = min(int(parts[1]), 100)  # 최대 100개
        else:
            keyword = param

        if not keyword:
            chat.reply("사용법: !방검색 [키워드] (개수)\n예시: !방검색 파이썬\n예시: !방검색 파이썬 30")
            return

        access_token, device_uuid = get_auth(chat.api.iris_endpoint)
        if not access_token or not device_uuid:
            chat.reply("인증 정보를 가져올 수 없습니다.")
            return

        data, message = search_open_chat(keyword, count, access_token, device_uuid)

        if data is None:
            chat.reply(f"방 검색에 실패했습니다.\n사유: {message}")
            return

        # 결과 파싱
        rooms = data.get("result", {}).get("openLink", {}).get("links", [])

        if not rooms:
            chat.reply(f"'{keyword}' 검색 결과가 없습니다.")
            return

        ALLSEE = "\u200b" * 500
        lines = [f"🔍 '{keyword}' 오픈채팅 검색 결과 ({len(rooms)}개){ALLSEE}"]

        for i, room in enumerate(rooms, 1):
            name = room.get("linkName", "(이름 없음)")
            description = room.get("description", "").strip()
            member_count = room.get("memberCount", 0)
            max_member = room.get("maxMemberCount", 0)
            link_id = room.get("linkId", "")
            open_link_token = room.get("openToken", "")

            room_url = f"https://open.kakao.com/o/{open_link_token}" if open_link_token else ""

            line = f"\n{i}. {name}"
            line += f"\n👥 {member_count}"
            if max_member:
                line += f"/{max_member}명"
            else:
                line += "명"
            if description:
                short_desc = description[:40] + "..." if len(description) > 40 else description
                line += f"\n📝 {short_desc}"
            if room_url:
                line += f"\n🔗 {room_url}"

            lines.append(line)

        chat.reply("\n".join(lines))

    except Exception as e:
        import traceback
        traceback.print_exc()
        chat.reply("방 검색 중 오류가 발생했습니다.")
