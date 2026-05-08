import streamlit as st
import pandas as pd
import json
import os
import requests
import base64
import openai
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# 환경변수 로드
from dotenv import load_dotenv
load_dotenv()

# Streamlit Secrets 우선, 없으면 환경변수 fallback
def get_secret(key, default=""):
    try:
        return st.secrets[key]
    except:
        return os.getenv(key, default)

# OpenAI API 키 설정
openai.api_key = get_secret("OPENAI_API_KEY")

# 기본 계정 정보
DEFAULT_EMAIL = get_secret("MYREALTRIP_EMAIL")
DEFAULT_PASSWORD = get_secret("MYREALTRIP_PASSWORD")

# 기본 프롬프트 템플릿 (전역 상수)
DEFAULT_PROMPT_TEMPLATE = """역할: 당신은 여행사 몽키트래블 직원입니다. 리뷰에 대한 답변을 작성하며, 리뷰어의 감정·표현·세부사항을 그대로 반영하여 정직하고 공감되는 어조로 짧고 간결하게 답변을 남깁니다.

[나열 금지 – 한두 문장으로 흐르게]
- 리뷰에 나온 내용을 "A하셨다니 ~, B도 ~, C도 ~" 식으로 하나하나 나열하지 말 것. 그렇게 쓰면 말을 나열하는 것 같아서 부자연스러움.
- 리뷰의 "전체 느낌"만 담아서, 한두 문장이 자연스럽게 이어지도록 쓸 것. 예: "가족과 함께 디너 크루즈에서 좋은 시간 보내셨다니 정말 기쁩니다! 소중한 후기 감사합니다 😊" 처럼 짧고 흐르게.
- "~하셨다니 ... ~도 ... ~도 ... ~도 ..." 처럼 "~하셨다니/다행이에요"를 여러 번 반복하지 말 것. 한 번만 쓰고 바로 감사/마무리로 넘어가도 됨.
- 꼭 강조할 한 가지만 있으면 그걸 한 문장으로, 없으면 전체 만족만 담아 짧게 답할 것.

[리뷰 인용 – 최소화]
- 고객 리뷰 문장을 그대로 옮기거나 많이 인용하지 말 것. 인용이 많으면 어색해짐.
- 리뷰는 "참고만" 하고, 그 내용을 우리 말로 짧게 풀어서 "~하셨다니 기쁩니다", "~되셨다니 다행이에요" 식으로 자연스럽게 답할 것.
- 꼭 언급할 것만 간단히 (예: 가이드 이름, 투어 종류, 만족한 점 한두 가지) 담고, 나머지는 문맥에 맞는 공감·감사 문장으로 마무리.
- 따옴표로 리뷰 문구를 인용하는 것은 특별한 경우가 아니면 쓰지 말 것.

[자연스러운 한국어 문체 – 필수]
- 반드시 구어체·말하듯이 자연스러운 한국어로 작성할 것. 번역체나 딱딱한 문장 금지.
- 자연스러운 연결: "~덕분에", "~해주셔서", "~느끼셨다니", "~되셨다니 정말 기쁩니다"처럼 문장이 흐르도록 쓸 것.
- 종결은 "-되셨다니 정말 기쁩니다", "-다행이에요", "-기쁩니다", "-감사합니다" 등 한 번에 자연스럽게 마무리.
- 다음처럼 어색한 표현은 사용하지 말 것: "-했답니다", "-하셨답니다", "-이었답니다", "-되셨답니다" 등.

[이모티콘 사용 – 문맥에 맞게 필수]
- 문장 끝이나 감정이 드러나는 부분에 이모티콘을 문맥에 맞게 넣을 것. 과하지 않게 1~3개 정도.
- 예: 가족/아이와 함께 → 👨‍👩‍👧‍👦😊, 만족/감사/소개해주심 → ✨, 따뜻한 마무리 → 😊, 사과·공감·양해 구할 때 → 🙏, 즐거움/기쁨 → 😊✨
- "소중한 후기 감사합니다" 뒤에 😊 를 붙여 따뜻하게 마무리하는 것을 권장.
[이모티콘·줄바꿈 예시 1] 가족·아이·만족 후기
→ 안녕하세요, 몽키트래블입니다 :)

한국인 사장님과 직원분들의 친절한 설명 덕분에 아이들과 즐거운 시간 보내셨다니 정말 다행이었네요 👨‍👩‍👧‍👦😊

시설과 운영도 만족스러우셨고 주변에까지 소개해주셨다니 더욱 감사한 마음입니다 ✨

소중한 후기 감사합니다 😊

[이모티콘·줄바꿈 예시 2] 일정 피로 + 일부 불편 공감 후기
→ 안녕하세요, 몽키트래블입니다 :)

이른 일정으로 피곤하셨을 텐데도 색다른 투어로 느껴지셨다니 다행이에요 😊

수상시장 배 이용 중 불편함을 느끼신 점은 공감되며, 더 나은 안내가 될 수 있도록 참고하겠습니다 🙏

소중한 후기 감사합니다 😊

[줄바꿈]
- "안녕하세요, 몽키트래블입니다 :)" 다음에 반드시 줄바꿈(한 줄 띄기) 후 본문 작성.
- 본문은 의미 단위로 끊어서 줄바꿈: 인사 한 줄 → 본문 1~2문장 → 다음 줄 → 이어지는 문장 또는 마무리 → "소중한 후기 감사합니다" 등은 새 줄에.
- 한 줄에 문장이 너무 길게 이어지지 않도록 적절히 줄바꿈하여 읽기 쉽게 작성할 것.

작성 원칙:  
- 답변은 반드시 "안녕하세요, 몽키트래블입니다 :)"로 시작  
- 4줄 이내로 작성 (너무 길지 않도록)  
- 리뷰에 없는 내용은 유추하지 말 것  
- 감정선 그대로 반영  
- 위 [이모티콘 사용]을 참고하여 문맥에 맞는 이모티콘을 넣을 것 (과하지 않게)  
- 가이드 이름/특징이 있다면 반드시 언급  
- 정보성 후기엔 "팁 공유 감사합니다" 등 감사 표현 포함  
- 마지막에 "감사합니다" 문장은 꼭 포함
- 예약변경, 예약취소 요청 등은 후기에서 안내가 어려우니 고객센터 등으로 별도요청 유도
- 리뷰 내용을 정확히 이해한 뒤, 위 [나열 금지], [리뷰 인용 – 최소화], [자연스러운 한국어 문체]를 지켜 답변할 것
- 리뷰에 나온 항목을 하나하나 나열하지 말고, 전체 느낌만 담아 한두 문장으로 흐르게 쓸 것. 리뷰 문장을 많이 반복하지 말 것
- 부정적인 부분이 있다면 공감과 함께 개선 의지 표현
- 가이드 이름을 모르는 경우 "해당 가이드님" 또는 "가이드님"으로 표현
- 실제로 알 수 없는 정보는 유추하지 말 것
- 한국어 가능한 가이드/기사: "한국어로 편리하게 안내해주셔서", "한국어 소통이 편리해서" 등 자연스러운 표현 사용
- 고객이 이미 긍정적으로 표현한 내용에 대해 불필요한 추가 추측은 하지 말 것
- "감사합니다" 표현은 한 번만 사용하고 중복하지 말 것
- "소중한 후기 감사합니다" 또는 "감사합니다" 중 하나만 선택하여 사용

[참고: 나열하지 말고 흐르게 – 디너 크루즈 예시]
리뷰에 "부모님·아이와 3층, 음식 만족, 연어·새우·스테이크, 직원 친절, 공연·한국 노래, 인형 뽑기" 등이 다 나와도, 전부 하나하나 말하지 말 것.
✗ 나쁜 예 (나열해서 부자연스러움): "기대하셨던 디너 크루즈에서 좋은 시간 보내셨다니 기쁩니다! 부모님과 아이와 함께 즐거운 추억을 만드셨고, 음식도 만족하셨다니 다행이에요. 특히 연어와 새우구이가 기억에 남으셨다니 좋네요! 직원들의 친절한 서비스와 한국 노래 공연으로 분위기를 즐기셨다니 감사합니다. 아이가 인형 뽑기를 해서 기뻐했다니 기분이 좋으셨겠어요."
○ 좋은 예 (한두 문장으로 흐르게): "안녕하세요, 몽키트래블입니다 :) 가족과 함께 사와디 차오프라야 디너 크루즈에서 좋은 시간 보내셨다니 정말 기쁩니다! 소중한 후기 감사합니다 😊" 또는, 한 가지만 더 넣고: "음식과 분위기까지 만족하셨다니 다행이에요. 소중한 후기 감사합니다 😊"

[참고: 자연스러운 문체 예시]
"안녕하세요, 몽키트래블입니다 :) 가이드님의 친절함과 편안한 이동수단 덕분에 즐거운 여행이 되셨다니 정말 기쁩니다! 방콕과 다른 매력을 느끼셨다니 추천해주셔서 감사합니다. 소중한 후기 감사합니다!"
→ 위처럼 "-덕분에", "-되셨다니 정말 기쁩니다", "-해주셔서 감사합니다"로 문장이 자연스럽게 이어지도록 작성할 것.

예시 1) 상품명: [디너는 예쁘게, 선셋은 감성 있게] 차오프라야 프린세스 크루즈
리뷰: 공연과 식사 모두 좋았고, 배에서 보는 짜오프라야강의 야경이 아름다웠습니다.
→ 안녕하세요, 몽키트래블입니다 :) 공연과 식사에 만족하셨다니 정말 기쁩니다! 특히 야경이 인상 깊으셨다니 멋진 추억 되셨을 것 같아요 ✨ 소중한 후기 감사합니다 😊

예시 2) 상품명: [단독투어] 담넌사두억 수상시장 + 위험한 기찻길
리뷰: 초등 아이와 함께 했는데, 가이드님의 설명도 좋았고 아이도 좋아했어요.
→ 안녕하세요, 몽키트래블입니다 :) 초등 아이와 함께 투어에 참여하셨군요! 가이드님과 함께 안전하고 편안하게 여행하셨다니 정말 다행입니다 👨‍👩‍👧‍👦😊 소중한 후기 감사합니다 😊

예시 3) 상품명: [프리미엄 스노클링] 라차섬 + 코랄섬
리뷰: 5명이서 비 오는 날에도 스노클링을 즐기고 회와 소주로 마무리했어요 ㅎㅎ
→ 안녕하세요, 몽키트래블입니다 :) 5분이서 즐거운 시간을 보내셨다니 정말 다행입니다! 비가 와도 스노클링을 잘 즐기셨고, 회와 소주 번개까지 ㅎㅎ 좋은 추억이 되셨길 바랍니다. ^^

예시 4) 상품명: 왕궁 & 새벽사원
리뷰: 설명은 조금 어려웠지만 가이드님이 정말 친절했어요.
→ 안녕하세요, 몽키트래블입니다 :) 한국어 소통이 조금 어려우셨다니 아쉬워요 ㅠㅠ 그래도 가이드님의 친절함을 느끼셨다니 다행입니다 😊 소중한 후기 감사드려요 😊

예시 5) 상품명: 무앙깨우 골프장
리뷰: 코스가 예뻤고 직원들도 친절했어요.
→ 안녕하세요, 몽키트래블입니다 :) 코스와 직원 모두 만족스러우셨다니 정말 기쁩니다! 편안한 라운딩 되셨길 바라요 ✨ 소중한 후기 감사합니다 😊

예시 6) 상품명: 요트 투어
리뷰: 아이들이 처음 배에 타는지라 걱정이 되었는데 잘 놀았습니다. 감사합니다
→ 안녕하세요, 몽키트래블입니다 :) 아이들과 함께 즐거운 시간 보내셨다니 다행이에요! 처음이라 걱정되셨을 텐데 잘 즐기셨다니 기쁩니다. 또 함께 여행할 수 있기를 기대합니다. 감사합니다!

예시 7) 상품명: 망고 쿠킹 스쿨
리뷰: 장소 찾는 것도 생각보다 어렵지 않았어요. 깨끗한 공간에서 친절한 씨 선생님과 직원분들이 수업도 재밌게 이끌어주셨어요. 다만 당시 어떤 한국인 어머니 세분이 아이들을 데리고 방문 하셨는데 예약이 잘 안 되었는지 계속 얘기를 나누시더라구요. 이유는 알겠으나 그분들 때문에 20분이나 수업이 늦어졌어요.
→ 안녕하세요, 몽키트래블입니다 :) 씨 선생님과 직원분들과 함께 즐거운 수업 시간 보내셨다니 기쁩니다 😊 장소 찾기도 수월하셨다니 다행이에요. 수업 지연으로 불편을 드린 점 사과드립니다 🙏 앞으로는 더욱 원활한 수업 진행을 위해 노력하겠습니다. 소중한 후기 감사합니다 😊

예시 8) 상품명: 팡아만 존그레이 씨카누 투어
리뷰: 여러번 푸켓을 경험했지만 이보다 좋을 순 없습니다. 최고의 투어이고 너무 멋진 경험이었습니다. 크루들의 친절함과 남다른 투어 서비스는 너무 좋았어요.
→ 안녕하세요, 몽키트래블입니다 :) 푸켓 여행 중 최고의 경험이 되셨다니 정말 기쁩니다! 크루들의 친절한 서비스에 만족하셨다니 다행이에요. 소중한 후기 감사합니다!

예시 9) 상품명: 치앙마이 야경 투어
리뷰: 가이드분께서 상세한 설명과 역사까지 곁들여 안내해주셔서 너무너무 즐거운 시간보내었습니다. 가이드님 이름 꼭좀 알려주시면 감사하겠습니다!
→ 안녕하세요, 몽키트래블입니다 :) 가이드분의 상세한 설명과 역사 안내로 즐거운 시간을 보내셨다니 기쁩니다! 해당 가이드님의 이름은 별도로 확인 후 안내드리겠습니다. 소중한 후기 감사합니다!

예시 10) 상품명: 발리 남부 단독 투어
리뷰: 매우 즐거운 여행을 만들어줘서 기분이 좋아요~ 특히 한국어가 가능했던 수이따 기사님이 있어서 얼마나 편했는지 몰라요! 그래서 이것저것 설명도 잘 듣고 물어봐도 다 알 수 있어서 완전 간편 그 자체였어요ㅠㅠ
→ 안녕하세요, 몽키트래블입니다 :) 즐거운 여행을 만들어드려 기분이 좋아요! 수이따 기사님이 한국어로 편리하게 안내해주셔서 정말 다행이었네요. 설명도 잘 듣고 편안한 여행이 되셨다니 기쁩니다! 소중한 후기 감사합니다!

예시 11) 상품명: 발리 투어
리뷰: 한국어 가능한 가이드님이 있어서 편리했어요. 설명도 잘 듣고 만족스러웠습니다.
→ 안녕하세요, 몽키트래블입니다 :) 한국어 가능한 가이드님과 함께 편리한 여행이 되셨다니 정말 기쁩니다! 설명도 잘 듣고 만족스러우셨다니 다행이에요. 소중한 후기 감사합니다!

다음 리뷰에 대한 답변을 작성해주세요:

상품명: {product_title}
리뷰: {review_content}

답변:"""


# ──────────────────────────────────────────
# 유틸 함수
# ──────────────────────────────────────────

def validate_api_key():
    try:
        client = openai.OpenAI(api_key=openai.api_key)
        client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "테스트"}],
            max_tokens=5
        )
        return True
    except:
        return False


def clean_text(text):
    if not text:
        return text
    text = text.strip()
    emoji_pattern = re.compile("["
        u"\U0001F600-\U0001F64F"
        u"\U0001F300-\U0001F5FF"
        u"\U0001F680-\U0001F6FF"
        u"\U0001F1E0-\U0001F1FF"
        "]+", flags=re.UNICODE)
    cleaned = emoji_pattern.sub(r'', text)
    if len(cleaned.strip()) < 10:
        return text
    return cleaned


# ──────────────────────────────────────────
# API 상수
# ──────────────────────────────────────────

LOGIN_URL = "https://partner.myrealtrip.com/signin"
BASE_URL = "https://api3-backoffice.myrealtrip.com"
AVAILABLE_PARTNERS_URL = f"{BASE_URL}/partner/v1/sign-in/available-partners"
REVIEWS_URL = f"{BASE_URL}/review/partner/reviews/search"


# ──────────────────────────────────────────
# 클래스
# ──────────────────────────────────────────

class TokenManager:
    def __init__(self):
        self.base_token = None

    def get_login_token(self, email, password):
        try:
            res = requests.post(
                f"{BASE_URL}/partner/v1/sign-in",
                json={"email": email, "password": password}
            )
            if res.status_code == 200:
                token = res.json().get("data", {}).get("accessToken")
                if token:
                    self.base_token = token
                    return token
        except:
            pass
        return None

    def get_available_partners(self, token):
        headers = {"partner-access-token": token}
        res = requests.get(AVAILABLE_PARTNERS_URL, headers=headers)
        if res.status_code == 200:
            return [
                {
                    "id": p["partnerId"],
                    "name": p["partnerNickname"],
                    "partnerAccountId": p.get("partnerAccountId")
                }
                for p in res.json().get("data", [])
            ]
        return []

    def switch_partner_token(self, base_token, partner_id, partner_account_id=None):
        headers = {"partner-access-token": base_token}
        payload = {"partnerId": partner_id}
        if partner_account_id:
            payload["partnerAccountId"] = partner_account_id
        res = requests.post(f"{BASE_URL}/partner/v1/sign-in/{partner_id}", headers=headers, json=payload)
        if res.status_code == 200:
            data = res.json().get("data", {}) or {}
            return data.get("accessToken") or data.get("token")
        return None


class ReviewsCollector:
    def get_all_reviews(self, token, partner_id, score, page_size=100):
        all_data = []
        page = 1
        while True:
            headers = {"partner-access-token": token}
            payload = {
                "page": page,
                "pageSize": page_size,
                "productType": "TOURACTIVITY",
                "sort": "-createdAt",
                "partnerCommented": False,
                "score": score
            }
            res = requests.post(REVIEWS_URL, headers=headers, json=payload)
            if res.status_code != 200:
                break
            data = res.json().get("data", [])
            if not data:
                break
            all_data.extend(data)
            if len(data) < page_size:
                break
            page += 1
        return all_data

    def get_reviews_parallel(self, token, partner_id, scores=[3, 4, 5]):
        with ThreadPoolExecutor(max_workers=len(scores)) as executor:
            futures = {
                executor.submit(self.get_all_reviews, token, partner_id, score): score
                for score in scores
            }
            all_reviews = []
            for future in as_completed(futures):
                try:
                    reviews = future.result()
                    if reviews:
                        all_reviews.extend(reviews)
                except:
                    pass
            return all_reviews


class GPTResponseGenerator:
    def __init__(self, prompt_template=None):
        self.prompt_template = prompt_template if prompt_template else DEFAULT_PROMPT_TEMPLATE

    def generate_response(self, product_title, review_content):
        try:
            clean_product_title = clean_text(product_title)
            clean_review_content = clean_text(review_content)
            if len(clean_product_title.strip()) < 5:
                clean_product_title = product_title
            if len(clean_review_content.strip()) < 10:
                clean_review_content = review_content

            prompt = self.prompt_template.format(
                product_title=clean_product_title,
                review_content=clean_review_content
            )
            client = openai.OpenAI(api_key=openai.api_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "당신은 여행사 몽키트래블의 고객 서비스 담당자입니다. 모든 답변은 구어체에 가깝고 자연스러운 한국어로 작성하며, '-했답니다' 같은 어색한 표현은 사용하지 않습니다. 고객 리뷰 문장을 그대로 인용하지 말고, 리뷰에 나온 내용을 하나하나 나열하지 말 것. 전체 느낌만 담아 한두 문장이 흐르도록 짧게 답하세요."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.7,
                timeout=30
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            if "가이드" in review_content or "선생님" in review_content:
                return "안녕하세요, 몽키트래블입니다 :) 가이드님과 함께 즐거운 시간 보내셨다니 정말 기쁩니다! 소중한 후기 감사합니다!"
            elif "좋" in review_content or "만족" in review_content:
                return "안녕하세요, 몽키트래블입니다 :) 만족스러운 여행이 되셨다니 정말 기쁩니다! 소중한 후기 감사합니다!"
            else:
                return "안녕하세요, 몽키트래블입니다 :) 소중한 후기 감사합니다!"


# ──────────────────────────────────────────
# 리뷰 수집 (GPT 없이 raw 데이터만)
# ──────────────────────────────────────────

def collect_raw_reviews(account_email, account_password):
    tm = TokenManager()
    rc = ReviewsCollector()

    token = tm.get_login_token(account_email, account_password)
    if not token:
        return []

    partners = tm.get_available_partners(token)
    if not partners:
        return []

    # 파트너 중복 제거
    unique_partners = []
    seen_names = set()
    for p in partners:
        if p['name'] not in seen_names:
            unique_partners.append(p)
            seen_names.add(p['name'])

    def collect_partner(p):
        partner_token = tm.switch_partner_token(token, p["id"], p.get("partnerAccountId")) or token
        reviews = rc.get_reviews_parallel(partner_token, p["id"])
        for r in reviews:
            r['partner'] = p['name']
        return reviews

    all_reviews = []
    with ThreadPoolExecutor(max_workers=len(unique_partners)) as executor:
        futures = [executor.submit(collect_partner, p) for p in unique_partners]
        for future in as_completed(futures):
            try:
                all_reviews.extend(future.result())
            except:
                pass

    # 중복 제거
    unique = {}
    for r in all_reviews:
        if r.get('id') and r['id'] not in unique:
            unique[r['id']] = r

    # 최신순 정렬
    result = list(unique.values())
    result.sort(key=lambda x: x.get('createdAt', ''), reverse=True)
    return result


# ──────────────────────────────────────────
# 페이지 설정
# ──────────────────────────────────────────

st.set_page_config(
    page_title="마리트 긍정 리뷰 답변 생성",
    page_icon="📋",
    layout="wide"
)

# session_state 초기화
if 'display_count' not in st.session_state:
    st.session_state.display_count = 10
if 'raw_reviews' not in st.session_state:
    st.session_state.raw_reviews = []
if 'processed_reviews' not in st.session_state:
    st.session_state.processed_reviews = {}  # {review_id: gpt_text}

st.title("📋 마리트 긍정 리뷰 답변 생성")
st.markdown("---")

# CSS
st.markdown("""
<style>
.review-card {
    border: 1px solid #ddd;
    border-radius: 8px;
    padding: 16px;
    margin: 8px 0;
}
.gpt-response {
    background-color: #e8f5e8;
    border-left: 4px solid #4CAF50;
    padding: 12px;
    margin: 8px 0;
    border-radius: 4px;
}
.gpt-answer-body { margin-top: 8px; }
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────
# 사이드바
# ──────────────────────────────────────────

st.sidebar.header("🔍 설정")

account_email = DEFAULT_EMAIL or ""
account_password = DEFAULT_PASSWORD or ""

# GPT 프롬프트 설정
st.sidebar.subheader("🤖 GPT 프롬프트 설정")
prompt_type = st.sidebar.radio(
    "프롬프트 유형 선택",
    ["기본 프롬프트 사용", "사용자 정의 프롬프트 사용"],
    index=0
)

if prompt_type == "사용자 정의 프롬프트 사용":
    custom_prompt = st.sidebar.text_area(
        "사용자 정의 프롬프트",
        value=DEFAULT_PROMPT_TEMPLATE,
        height=400,
        help="{product_title}과 {review_content}는 자동으로 치환됩니다."
    )
else:
    custom_prompt = None

st.sidebar.markdown("---")

# 데이터 가져오기 버튼
if st.sidebar.button("📊 데이터 가져오기", key="load_data", use_container_width=True, type="primary"):
    if not account_email or not account_password:
        st.error("❌ 이메일과 비밀번호를 환경변수 또는 Secrets에 설정해주세요.")
    elif not openai.api_key:
        st.error("❌ OpenAI API 키가 설정되지 않았습니다.")
    else:
        with st.spinner("🔍 리뷰 수집 중..."):
            raw = collect_raw_reviews(account_email, account_password)
            st.session_state.raw_reviews = raw
            st.session_state.processed_reviews = {}
            st.session_state.display_count = 10
        if raw:
            st.success(f"✅ 리뷰 수집 완료! 필터를 설정하고 아래에서 확인하세요.")
        else:
            st.error("❌ 데이터 수집에 실패했습니다. 계정 정보를 확인해주세요.")

st.sidebar.markdown("---")

# 파트너 선택
st.sidebar.subheader("🏢 파트너 선택")
selected_partners = st.sidebar.multiselect(
    "파트너 선택",
    options=["토토부킹", "몽키트래블", "몽키트래블 태국"],
    default=["몽키트래블 태국"]
)

# 점수 필터
st.sidebar.subheader("⭐ 점수 선택")
selected_scores = st.sidebar.multiselect(
    "점수 선택",
    options=[3, 4, 5],
    default=[5]
)

# API 키 상태
if openai.api_key:
    if not validate_api_key():
        st.sidebar.error("❌ OpenAI API 연결 실패")
else:
    st.sidebar.warning("⚠️ OpenAI API 키가 설정되지 않음")


# ──────────────────────────────────────────
# 메인 화면
# ──────────────────────────────────────────

if st.session_state.raw_reviews:
    raw = st.session_state.raw_reviews
    gpt_gen = GPTResponseGenerator(prompt_template=custom_prompt)

    # 필터 적용
    filtered = [
        r for r in raw
        if r.get('partner') in selected_partners
        and r.get('score') in selected_scores
    ]

    total = len(filtered)
    display_count = st.session_state.display_count
    to_show = filtered[:display_count]

    st.metric("📊 총 리뷰 수", total)

    if selected_partners or selected_scores:
        filter_info = []
        if selected_partners:
            filter_info.append(f"파트너: {', '.join(selected_partners)}")
        if selected_scores:
            filter_info.append(f"점수: {', '.join(map(str, selected_scores))}")
        st.info(" | ".join(filter_info))

    st.markdown("---")
    st.subheader("📝 GPT 답변 목록")

    for r in to_show:
        review_id = r.get('id')
        partner_name = r.get('partner', 'N/A')

        # GPT 답변 없으면 생성
        if review_id not in st.session_state.processed_reviews:
            with st.spinner(f"🤖 GPT 답변 생성 중..."):
                gpt_text = gpt_gen.generate_response(
                    r.get('productTitle', ''),
                    r.get('comment', '')
                )
                st.session_state.processed_reviews[review_id] = gpt_text

        gpt_text = st.session_state.processed_reviews.get(review_id, '')

        # 파트너 색상
        if '토토부킹' in partner_name:
            partner_color = '#FF6B6B'
            partner_bg_color = '#FFE6E6'
        elif '몽키트래블' in partner_name:
            partner_color = '#4ECDC4'
            partner_bg_color = '#E6F7F5'
        else:
            partner_color = '#95A5A6'
            partner_bg_color = '#F5F5F5'

        gpt_display = '<br>'.join(line.strip() for line in gpt_text.split('\n'))

        st.markdown(f"""
        <div class="review-card" style="border-left: 5px solid {partner_color}; background-color: {partner_bg_color};">
            <div style="background-color: {partner_color}; color: white; padding: 8px 12px; margin: -16px -16px 16px -16px; border-radius: 8px 8px 0 0;">
                <h4 style="margin: 0; color: white;">🏢 {partner_name} | 📋 리뷰 ID: {review_id}</h4>
            </div>
            <p><strong>점수:</strong> ⭐ {r.get('score', 'N/A')}점</p>
            <p><strong>상품명:</strong> {r.get('productTitle', 'N/A')}</p>
            <p><strong>작성자:</strong> {r.get('username', 'N/A')}</p>
            <p><strong>예약번호:</strong> {r.get('reservationNo', 'N/A')} | <strong>여행일:</strong> {r.get('travelStartDate', 'N/A')} | <strong>작성일:</strong> {r.get('createdAt', 'N/A')}</p>
            <p><strong>후기내용:</strong> {r.get('comment', 'N/A')}</p>
            <div class="gpt-response">
                <strong>🤖 GPT 답변:</strong>
                <div class="gpt-answer-body">{gpt_display}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # 복사 버튼
        if gpt_text:
            safe_text = gpt_text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '').replace('`', '\\`')
            copy_html = f"""
            <div style="margin: 10px 0 20px 0;">
                <button id="copyBtn_{review_id}" onclick="copyText_{review_id}()"
                        style="background: linear-gradient(45deg, {partner_color}, {partner_color}cc);
                               color: white; border: none; padding: 10px 22px;
                               border-radius: 8px; cursor: pointer; font-size: 14px;
                               font-weight: bold; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">
                    📋 답변 복사하기 (ID: {review_id})
                </button>
                <span id="result_{review_id}" style="margin-left: 12px; font-weight: bold;"></span>
            </div>
            <script>
                async function copyText_{review_id}() {{
                    const text = "{safe_text}";
                    const result = document.getElementById('result_{review_id}');
                    try {{
                        if (navigator.clipboard && window.isSecureContext) {{
                            await navigator.clipboard.writeText(text);
                        }} else {{
                            const ta = document.createElement('textarea');
                            ta.value = text;
                            ta.style.position = 'fixed';
                            ta.style.left = '-9999px';
                            document.body.appendChild(ta);
                            ta.select();
                            document.execCommand('copy');
                            document.body.removeChild(ta);
                        }}
                        result.innerHTML = '<span style="color:#4CAF50;">✅ 복사 완료!</span>';
                        setTimeout(() => result.innerHTML = '', 3000);
                    }} catch(e) {{
                        result.innerHTML = '<span style="color:red;">❌ 복사 실패</span>';
                    }}
                }}
            </script>
            """
            st.components.v1.html(copy_html, height=70)

        st.markdown("---")

    # 더 보기 버튼
    if display_count < total:
        remaining = total - display_count
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button(f"⬇️ 10개 더 보기 (남은 리뷰: {remaining}개)", use_container_width=True, type="primary"):
                st.session_state.display_count += 10
                st.rerun()
    else:
        st.success("✅ 모든 리뷰를 확인했습니다!")

else:
    st.info("👆 왼쪽 사이드바에서 '📊 데이터 가져오기' 버튼을 클릭하여 리뷰를 불러오세요.")
    st.markdown("---")
    st.subheader("📖 사용법")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        **1단계: 데이터 가져오기**
        - 사이드바에서 "📊 데이터 가져오기" 클릭
        - 리뷰 목록만 빠르게 수집

        **2단계: 필터 설정**
        - 파트너 선택 (토토부킹/몽키트래블)
        - 점수 선택 (3점/4점/5점)
        """)
    with col2:
        st.markdown("""
        **3단계: GPT 답변 확인**
        - 처음 10개만 GPT 답변 자동 생성
        - "10개 더 보기" 클릭 시 추가 생성

        **4단계: 답변 복사**
        - "📋 답변 복사하기" 버튼 클릭
        - Ctrl+V로 붙여넣기
        """)

st.markdown("---")
st.markdown("*GPT 답변 복사 대시보드 - " + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "*")
