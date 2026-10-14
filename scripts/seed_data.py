from pathlib import Path

from sqlalchemy import func, select

from app.db.database import SessionLocal, init_db
from app.db.models import Location, Post
from app.services.importer import import_festival_schedules, import_locations

BASE_DIR = Path(__file__).resolve().parents[1]


def find_data_dir() -> Path:
    """Find the directory containing the downloaded Seoul content datasets."""
    candidates = [
        BASE_DIR / "data",
        BASE_DIR.parents[1] / "data",
    ]
    for candidate in candidates:
        if any(candidate.glob("서울_*.json")):
            return candidate
    return candidates[0]


DATA_DIR = find_data_dir()

def seed_sample_posts(db):
    posts = [
        # =========================
        # 혼밥 추천 10개
        # =========================
        Post(
            type="FOOD",
            title="혼밥하기 편한 광장시장 메뉴 추천해요",
            content="바 좌석이나 서서 먹는 메뉴가 많아서 혼자 방문하기 부담이 적었어요.",
            nickname="서울산책러",
            edit_password="1234",
            tags_json='["혼밥", "광장시장", "추천"]',
        ),
        Post(
            type="FOOD",
            title="성수동 혼밥하기 좋은 덮밥집",
            content="바 좌석이 있어서 혼자 방문해도 부담 없고 음식도 빠르게 나왔어요.",
            nickname="성수산책러",
            edit_password="1234",
            tags_json='["혼밥", "성수", "덮밥"]',
        ),
        Post(
            type="FOOD",
            title="망원시장 혼자 먹거리 투어 후기",
            content="간단한 먹거리를 포장해서 망원한강공원에서 먹기 좋았습니다.",
            nickname="망원여행자",
            edit_password="1234",
            tags_json='["혼밥", "망원시장", "한강"]',
        ),
        Post(
            type="FOOD",
            title="을지로 혼자 먹기 좋은 국수집",
            content="회전이 빠르고 혼자 오는 손님이 많아서 편하게 식사할 수 있었어요.",
            nickname="을지로직장인",
            edit_password="1234",
            tags_json='["혼밥", "을지로", "국수"]',
        ),
        Post(
            type="FOOD",
            title="홍대 혼밥 가능한 라멘집 추천",
            content="1인 좌석이 따로 마련되어 있어서 혼자 방문하기 좋았습니다.",
            nickname="라멘좋아",
            edit_password="1234",
            tags_json='["혼밥", "홍대", "라멘"]',
        ),
        Post(
            type="FOOD",
            title="강남역 근처 혼밥 가능한 식당",
            content="키오스크 주문이라 부담이 적고 혼자 앉을 수 있는 좌석도 많았습니다.",
            nickname="강남초보",
            edit_password="1234",
            tags_json='["혼밥", "강남역", "식당"]',
        ),
        Post(
            type="FOOD",
            title="연남동 혼자 브런치 먹기 좋은 곳",
            content="창가 좌석이 많고 분위기가 조용해서 혼자 브런치를 즐기기 좋았어요.",
            nickname="연남산책",
            edit_password="1234",
            tags_json='["혼밥", "연남동", "브런치"]',
        ),
        Post(
            type="FOOD",
            title="서울역 근처 혼자 먹기 좋은 식당",
            content="기차를 기다리면서 빠르게 식사하기 좋고 혼자 방문한 손님도 많았습니다.",
            nickname="기차여행자",
            edit_password="1234",
            tags_json='["혼밥", "서울역", "여행"]',
        ),
        Post(
            type="FOOD",
            title="잠실에서 혼자 먹기 좋은 돈가스집",
            content="테이블 간격이 넓고 주문도 간단해서 혼자 식사하기 편했습니다.",
            nickname="잠실러",
            edit_password="1234",
            tags_json='["혼밥", "잠실", "돈가스"]',
        ),
        Post(
            type="FOOD",
            title="이태원 혼자 방문하기 좋은 카페",
            content="노트북을 사용하는 사람이 많고 혼자 앉을 수 있는 좌석이 충분했어요.",
            nickname="카페탐험가",
            edit_password="1234",
            tags_json='["혼자카페", "이태원", "카페"]',
        ),

        # =========================
        # 동행 구하기 10개
        # =========================
        Post(
            type="COMPANION",
            title="주말 전시 같이 보실 분 있나요?",
            content="토요일 오후에 종로구 문화시설을 둘러볼 예정입니다.",
            nickname="익명여행자",
            edit_password="1234",
            tags_json='["전시", "동행", "종로"]',
        ),
        Post(
            type="COMPANION",
            title="이번 주 토요일 한강 산책하실 분",
            content="오후 5시쯤 여의나루역에서 만나 한 시간 정도 걸으려고 합니다.",
            nickname="한강초보",
            edit_password="1234",
            tags_json='["동행", "한강", "산책"]',
        ),
        Post(
            type="COMPANION",
            title="경복궁 야간개장 같이 보실 분",
            content="사진을 찍으면서 천천히 관람하실 분을 찾습니다.",
            nickname="궁궐좋아",
            edit_password="1234",
            tags_json='["동행", "경복궁", "야간개장"]',
        ),
        Post(
            type="COMPANION",
            title="서울숲 피크닉 같이 하실 분",
            content="주말 오후에 서울숲에서 간단하게 간식을 먹으며 이야기하고 싶어요.",
            nickname="초록피크닉",
            edit_password="1234",
            tags_json='["동행", "서울숲", "피크닉"]',
        ),
        Post(
            type="COMPANION",
            title="북촌 한옥마을 사진 동행 구해요",
            content="오전 시간에 북촌을 걸으며 사진을 찍을 분을 찾습니다.",
            nickname="사진산책러",
            edit_password="1234",
            tags_json='["동행", "북촌", "사진"]',
        ),
        Post(
            type="COMPANION",
            title="남산 야경 같이 보러 가실 분",
            content="저녁에 케이블카를 타고 남산에 올라가 야경을 볼 예정입니다.",
            nickname="야경여행자",
            edit_password="1234",
            tags_json='["동행", "남산", "야경"]',
        ),
        Post(
            type="COMPANION",
            title="DDP 전시 같이 관람하실 분",
            content="동대문디자인플라자 전시를 보고 근처 카페도 방문하려고 합니다.",
            nickname="디자인좋아",
            edit_password="1234",
            tags_json='["동행", "DDP", "전시"]',
        ),
        Post(
            type="COMPANION",
            title="광화문에서 박물관 투어하실 분",
            content="대한민국역사박물관과 주변 문화시설을 함께 둘러보고 싶습니다.",
            nickname="역사탐험가",
            edit_password="1234",
            tags_json='["동행", "광화문", "박물관"]',
        ),
        Post(
            type="COMPANION",
            title="한강 자전거 같이 타실 분 구해요",
            content="반포한강공원에서 출발해서 천천히 자전거를 탈 예정입니다.",
            nickname="자전거초보",
            edit_password="1234",
            tags_json='["동행", "한강", "자전거"]',
        ),
        Post(
            type="COMPANION",
            title="홍대 버스킹 같이 보실 분",
            content="금요일 저녁에 홍대 주변 버스킹을 구경하실 분을 찾습니다.",
            nickname="음악산책",
            edit_password="1234",
            tags_json='["동행", "홍대", "버스킹"]',
        ),

        # =========================
        # 여행 후기 10개
        # =========================
        Post(
            type="REVIEW",
            title="서울숲 혼자 산책한 후기",
            content="산책로가 잘 정리되어 있고 혼자 쉬기 좋은 공간도 많았습니다.",
            nickname="초록산책",
            edit_password="1234",
            tags_json='["서울숲", "산책", "혼자여행"]',
        ),
        Post(
            type="REVIEW",
            title="국립중앙박물관 혼자 관람 추천",
            content="전시 공간이 넓어서 혼자 천천히 둘러보기 좋았습니다.",
            nickname="박물관러버",
            edit_password="1234",
            tags_json='["박물관", "용산", "전시"]',
        ),
        Post(
            type="REVIEW",
            title="북촌한옥마을 평일 방문 후기",
            content="평일 오전에 방문하니 비교적 조용해서 사진을 찍기 좋았습니다.",
            nickname="서울사진가",
            edit_password="1234",
            tags_json='["북촌", "한옥마을", "종로"]',
        ),
        Post(
            type="REVIEW",
            title="남산서울타워 혼자 다녀온 후기",
            content="저녁에 방문했는데 야경이 멋지고 혼자 여행하는 사람도 많았어요.",
            nickname="야경수집가",
            edit_password="1234",
            tags_json='["남산", "서울타워", "야경"]',
        ),
        Post(
            type="REVIEW",
            title="망원한강공원 노을 감상 후기",
            content="돗자리 없이 벤치에 앉아도 충분히 노을을 즐길 수 있었습니다.",
            nickname="노을좋아",
            edit_password="1234",
            tags_json='["망원한강공원", "노을", "산책"]',
        ),
        Post(
            type="REVIEW",
            title="창덕궁 후원 혼자 관람한 후기",
            content="해설을 들으며 천천히 걷기 좋아 혼자 여행 코스로 추천합니다.",
            nickname="궁궐산책",
            edit_password="1234",
            tags_json='["창덕궁", "후원", "궁궐"]',
        ),
        Post(
            type="REVIEW",
            title="서울시립미술관 전시 관람 후기",
            content="무료 전시가 많고 주변에 산책할 곳도 있어서 혼자 방문하기 좋았어요.",
            nickname="미술관여행",
            edit_password="1234",
            tags_json='["미술관", "전시", "덕수궁"]',
        ),
        Post(
            type="REVIEW",
            title="청계천 야간 산책 후기",
            content="조명이 잘 되어 있고 길이 평탄해서 저녁 산책 코스로 괜찮았습니다.",
            nickname="밤산책러",
            edit_password="1234",
            tags_json='["청계천", "야간산책", "종로"]',
        ),
        Post(
            type="REVIEW",
            title="익선동 혼자 여행한 후기",
            content="골목을 구경하고 카페에 들르기 좋아 반나절 코스로 충분했습니다.",
            nickname="골목여행자",
            edit_password="1234",
            tags_json='["익선동", "카페", "골목"]',
        ),
        Post(
            type="REVIEW",
            title="하늘공원 혼자 다녀온 후기",
            content="오르막길이 조금 힘들었지만 정상에서 보는 풍경이 좋았습니다.",
            nickname="공원탐험가",
            edit_password="1234",
            tags_json='["하늘공원", "산책", "풍경"]',
        ),

        # =========================
        # 일반 질문 및 정보 10개
        # =========================
        Post(
            type="GENERAL",
            title="비 오는 날 혼자 갈 만한 곳 추천해주세요",
            content="실내에서 오래 머무를 수 있는 전시관이나 문화시설을 찾고 있습니다.",
            nickname="비오는서울",
            edit_password="1234",
            tags_json='["실내", "비오는날", "추천"]',
        ),
        Post(
            type="GENERAL",
            title="서울 야경 보기 좋은 장소 어디인가요?",
            content="혼자 방문하기 부담 없고 대중교통으로 갈 수 있는 곳이면 좋겠습니다.",
            nickname="야경수집가",
            edit_password="1234",
            tags_json='["야경", "서울", "추천"]',
        ),
        Post(
            type="GENERAL",
            title="서울 혼자 여행할 때 교통카드 필요한가요?",
            content="서울에서 3일 정도 여행할 예정인데 교통카드를 미리 준비해야 할까요?",
            nickname="서울첫여행",
            edit_password="1234",
            tags_json='["서울여행", "교통", "질문"]',
        ),
        Post(
            type="GENERAL",
            title="서울에서 혼자 사진 찍기 좋은 곳 추천",
            content="삼각대 없이 휴대폰으로 풍경 사진을 찍기 좋은 장소를 찾고 있습니다.",
            nickname="사진초보",
            edit_password="1234",
            tags_json='["사진", "서울", "추천"]',
        ),
        Post(
            type="GENERAL",
            title="외국인이 가기 좋은 서울 관광지는 어디인가요?",
            content="한국을 처음 방문하는 친구에게 추천할 만한 서울 관광지를 찾고 있어요.",
            nickname="여행도우미",
            edit_password="1234",
            tags_json='["외국인", "관광지", "서울"]',
        ),
        Post(
            type="GENERAL",
            title="서울 혼자 여행 하루 코스 추천해주세요",
            content="오전부터 저녁까지 대중교통으로 이동할 수 있는 코스를 찾고 있습니다.",
            nickname="하루여행자",
            edit_password="1234",
            tags_json='["서울여행", "하루코스", "추천"]',
        ),
        Post(
            type="GENERAL",
            title="혼자 가도 어색하지 않은 축제 있을까요?",
            content="사람이 너무 붐비지 않고 혼자 구경하기 좋은 축제를 찾고 있습니다.",
            nickname="축제초보",
            edit_password="1234",
            tags_json='["축제", "혼자여행", "질문"]',
        ),
        Post(
            type="GENERAL",
            title="서울에서 무료로 즐길 수 있는 곳 알려주세요",
            content="입장료 없이 전시나 산책을 즐길 수 있는 장소를 추천받고 싶습니다.",
            nickname="알뜰여행자",
            edit_password="1234",
            tags_json='["무료", "서울여행", "추천"]',
        ),
        Post(
            type="GENERAL",
            title="서울 여행할 때 숙소 위치 어디가 좋을까요?",
            content="지하철로 관광지를 이동하기 편한 지역을 알아보고 있습니다.",
            nickname="숙소고민중",
            edit_password="1234",
            tags_json='["숙소", "서울", "교통"]',
        ),
        Post(
            type="GENERAL",
            title="혼자 서울 여행할 때 주의할 점 있나요?",
            content="늦은 시간 이동이나 짐 보관 등 혼자 여행할 때 알아두면 좋은 점이 궁금합니다.",
            nickname="혼행입문자",
            edit_password="1234",
            tags_json='["혼자여행", "안전", "여행팁"]',
        ),
    ]

    existing_titles = set(
        db.scalars(select(Post.title)).all()
    )

    new_posts = [
        post
        for post in posts
        if post.title not in existing_titles
    ]

    if not new_posts:
        print("추가할 새 게시글이 없습니다.")
        return

    db.add_all(new_posts)
    db.commit()

    print(f"게시글 {len(new_posts)}개 추가 완료")

def main():
    init_db()
    with SessionLocal() as db:
        location_result = import_locations(db, DATA_DIR)
        schedule_result = import_festival_schedules(db, DATA_DIR)
        seed_sample_posts(db)
        total = db.scalar(select(func.count()).select_from(Location)) or 0
        print({
            "locations": location_result,
            "festivalSchedules": schedule_result,
            "totalLocations": total,
        })


if __name__ == "__main__":
    main()
