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
import os
from dotenv import load_dotenv

# .env 파일 로드 (로컬 개발용)
load_dotenv()

# OpenAI API 키 설정 (환경변수에서 가져오기)
openai.api_key = os.getenv("OPENAI_API_KEY")

# API 키 유효성 검증
def validate_api_key():
    """API 키 유효성 검증"""
    try:
        client = openai.OpenAI(api_key=openai.api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "테스트"}],
            max_tokens=5
        )
        return True
    except Exception as e:
        # API 키 검증 실패 - UI에서 처리됨
        return False

def clean_text(text):
    """이모지와 특수 문자 제거 (더 보수적으로)"""
    if not text:
        return text
    
    # 기본적인 공백 정리
    text = text.strip()
    
    # 이모지만 제거 (더 제한적으로)
    emoji_pattern = re.compile("["
        u"\U0001F600-\U0001F64F"  # emoticons
        u"\U0001F300-\U0001F5FF"  # symbols & pictographs
        u"\U0001F680-\U0001F6FF"  # transport & map symbols
        u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "]+", flags=re.UNICODE)
    
    cleaned = emoji_pattern.sub(r'', text)
    
    # 너무 짧아지면 원본 반환
    if len(cleaned.strip()) < 10:
        return text
    
    return cleaned

# 기본 계정 정보 (환경변수에서 가져오기)
DEFAULT_EMAIL = os.getenv("MYREALTRIP_EMAIL", "")
DEFAULT_PASSWORD = os.getenv("MYREALTRIP_PASSWORD", "")

LOGIN_URL = "https://partner.myrealtrip.com/signin"
BASE_URL = "https://api3-backoffice.myrealtrip.com"
AVAILABLE_PARTNERS_URL = f"{BASE_URL}/partner/v1/sign-in/available-partners"
REVIEWS_URL = f"{BASE_URL}/review/partner/reviews/search"

class TokenManager:
    def __init__(self):
        self.base_token = None  # 기본 토큰 저장
        self.partner_info = None  # 파트너 정보 저장
    
    def get_login_token(self, email, password):
        """직접 로그인 API 호출로 토큰 발급"""
        try:
            # 로그인 API 호출
            login_url = "https://api3-backoffice.myrealtrip.com/partner/v1/sign-in"
            login_data = {
                "email": email,
                "password": password
            }
            
            response = requests.post(login_url, json=login_data)
            
            if response.status_code == 200:
                data = response.json()
                token = data.get("data", {}).get("accessToken")
                if token:
                    self.base_token = token
                    return token
                else:
                    return None
            else:
                return None
                
        except Exception as e:
            return None

    def decode_token(self, token):
        """JWT 토큰에서 partnerId와 partnerAccountId 추출"""
        try:
            # JWT 토큰의 두 번째 부분(페이로드) 디코딩
            parts = token.split('.')
            if len(parts) >= 2:
                payload = parts[1]
                # 패딩 추가
                payload += '=' * (4 - len(payload) % 4)
                decoded = base64.b64decode(payload)
                data = json.loads(decoded)
                return {
                    'partnerId': data.get('partnerId'),
                    'partnerAccountId': data.get('partnerAccountId')
                }
        except Exception as e:
            pass
        return None

    def get_available_partners(self, token):
        """로그인 토큰으로 사용 가능한 파트너 목록 조회"""
        headers = {"partner-access-token": token}
        res = requests.get(AVAILABLE_PARTNERS_URL, headers=headers)
        if res.status_code == 200:
            partners = res.json().get("data", [])
            return [
                {
                    "id": p["partnerId"],
                    "name": p["partnerNickname"],
                    "partnerAccountId": p.get("partnerAccountId")
                }
                for p in partners
            ]
        else:
            return []

    def switch_partner_token(self, base_token, partner_id, partner_account_id=None):
        """기본 토큰으로 partnerId 전환 후 새 토큰 발급"""
        headers = {"partner-access-token": base_token}
        url = f"{BASE_URL}/partner/v1/sign-in/{partner_id}"

        payload = {"partnerId": partner_id}
        if partner_account_id:
            payload["partnerAccountId"] = partner_account_id

        res = requests.post(url, headers=headers, json=payload)

        if res.status_code == 200:
            try:
                response_data = res.json()
                data = response_data.get("data", {}) if response_data else {}
            except Exception as e:
                data = {}
            
            new_token = data.get("accessToken") or data.get("token")
            if new_token:
                return new_token
            else:
                return None
        else:
            return None

class ReviewsCollector:
    def get_reviews(self, token, partner_id, score):
        """특정 점수의 미답변 리뷰 조회"""
        headers = {"partner-access-token": token}
        
        payload = {
            "page": 1,
            "pageSize": 50,
            "productType": "TOURACTIVITY",
            "sort": "-createdAt",
            "partnerCommented": False,
            "score": score
        }
        
        res = requests.post(REVIEWS_URL, headers=headers, json=payload)
        if res.status_code == 200:
            data = res.json().get("data", [])
            return data
        else:
            return []
    
    def get_reviews_parallel(self, token, partner_id, scores=[4, 5]):
        """병렬로 여러 점수의 리뷰 조회"""
        with ThreadPoolExecutor(max_workers=len(scores)) as executor:
            futures = {
                executor.submit(self.get_reviews, token, partner_id, score): score 
                for score in scores
            }
            
            all_reviews = []
            for future in as_completed(futures):
                score = futures[future]
                try:
                    reviews = future.result()
                    if reviews:
                        all_reviews.extend(reviews)
                except Exception as e:
                    print(f"  ⚠️ {score}점 리뷰 조회 실패: {e}")
            
            return all_reviews

class GPTResponseGenerator:
    def __init__(self, prompt_template=None):
        # 기본 프롬프트 템플릿
        self.default_prompt_template = """역할: 당신은 여행사 몽키트래블 직원입니다. 리뷰에 대한 답변을 작성하며, 리뷰어의 감정·표현·세부사항을 그대로 반영하여 정직하고 공감되는 어조로 짧고 간결하게 답변을 남깁니다.

작성 원칙:  
- 답변은 반드시 "안녕하세요, 몽키트래블입니다 :)"로 시작  
- 4줄 이내로 작성 (너무 길지 않도록)  
- 리뷰에 없는 내용은 유추하지 말 것  
- 감정선 그대로 반영  
- 느낌표, ㅎㅎ, ^^, 이모지 등은 감정에 따라 적절히 사용  
- 가이드 이름/특징이 있다면 반드시 언급  
- 정보성 후기엔 "팁 공유 감사합니다" 등 감사 표현 포함  
- 마지막에 "감사합니다" 문장은 꼭 포함
- 예약변경, 예약취소 요청 등은 후기에서 안내가 어려우니 고객센터 등으로 별도요청 유도
- 리뷰 내용을 정확히 이해하고 자연스러운 한국어로 답변할 것
- 리뷰의 구체적인 내용을 반영하여 개인화된 답변 작성
- 부정적인 부분이 있다면 공감과 함께 개선 의지 표현
- 가이드 이름을 모르는 경우 "해당 가이드님" 또는 "가이드님"으로 표현
- 실제로 알 수 없는 정보는 유추하지 말 것
- 한국어 가능한 가이드/기사에 대해서는 "한국어로 편리하게 안내해주셔서" 또는 "한국어 소통이 편리해서" 등 자연스러운 표현 사용
- "-했답니다" 같은 어색한 표현 대신 "-해서 정말 다행이었네요", "-되셨다니 기쁩니다" 등 자연스러운 표현 사용
- 문맥에 맞게 자연스러운 한국어로 답변할 것
- 고객이 이미 긍정적으로 표현한 내용에 대해 불필요한 추가 추측은 하지 말 것
- "감사합니다" 표현은 한 번만 사용하고 중복하지 말 것
- "소중한 후기 감사합니다" 또는 "감사합니다" 중 하나만 선택하여 사용

예시 1) 상품명: [디너는 예쁘게, 선셋은 감성 있게] 차오프라야 프린세스 크루즈
리뷰: 공연과 식사 모두 좋았고, 배에서 보는 짜오프라야강의 야경이 아름다웠습니다.
→ 안녕하세요, 몽키트래블입니다 :) 공연과 식사에 만족하셨다니 정말 기쁩니다! 특히 야경이 인상 깊으셨다니 멋진 추억 되셨을 것 같아요. 소중한 후기 감사합니다!

예시 2) 상품명: [단독투어] 담넌사두억 수상시장 + 위험한 기찻길
리뷰: 초등 아이와 함께 했는데, 가이드님의 설명도 좋았고 아이도 좋아했어요.
→ 안녕하세요, 몽키트래블입니다 :) 초등 아이와 함께 투어에 참여하셨군요! 가이드님과 함께 안전하고 편안하게 여행하셨다니 정말 다행입니다. 소중한 후기 감사합니다!

예시 3) 상품명: [프리미엄 스노클링] 라차섬 + 코랄섬
리뷰: 5명이서 비 오는 날에도 스노클링을 즐기고 회와 소주로 마무리했어요 ㅎㅎ
→ 안녕하세요, 몽키트래블입니다 :) 5분이서 즐거운 시간을 보내셨다니 정말 다행입니다! 비가 와도 스노클링을 잘 즐기셨고, 회와 소주 번개까지 ㅎㅎ 좋은 추억이 되셨길 바랍니다. ^^

예시 4) 상품명: 왕궁 & 새벽사원
리뷰: 설명은 조금 어려웠지만 가이드님이 정말 친절했어요.
→ 안녕하세요, 몽키트래블입니다 :) 한국어 소통이 조금 어려우셨다니 아쉬워요 ㅠㅠ 그래도 가이드님의 친절함을 느끼셨다니 다행입니다. 소중한 후기 감사드려요!

예시 5) 상품명: 무앙깨우 골프장
리뷰: 코스가 예뻤고 직원들도 친절했어요.
→ 안녕하세요, 몽키트래블입니다 :) 코스와 직원 모두 만족스러우셨다니 정말 기쁩니다! 편안한 라운딩 되셨길 바라요. 소중한 후기 감사합니다!

예시 6) 상품명: 요트 투어
리뷰: 아이들이 처음 배에 타는지라 걱정이 되었는데 잘 놀았습니다. 감사합니다
→ 안녕하세요, 몽키트래블입니다 :) 아이들과 함께 즐거운 시간 보내셨다니 다행이에요! 처음이라 걱정되셨지만 잘 즐기셨다니 기쁩니다. 또 함께 여행할 수 있기를 기대합니다. 감사합니다!

예시 7) 상품명: 망고 쿠킹 스쿨
리뷰: 장소 찾는 것도 생각보다 어렵지 않았어요. 깨끗한 공간에서 친절한 씨 선생님과 직원분들이 수업도 재밌게 이끌어주셨어요. 다만 당시 어떤 한국인 어머니 세분이 아이들을 데리고 방문 하셨는데 예약이 잘 안 되었는지 계속 얘기를 나누시더라구요. 이유는 알겠으나 그분들 때문에 20분이나 수업이 늦어졌어요.
→ 안녕하세요, 몽키트래블입니다 :) 씨 선생님과 직원분들과 함께 즐거운 수업 시간 보내셨다니 기쁩니다! 장소 찾기도 수월하셨다니 다행이에요. 수업 지연으로 불편을 드린 점 사과드립니다. 앞으로는 더욱 원활한 수업 진행을 위해 노력하겠습니다. 소중한 후기 감사합니다!

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
        
        # 사용자 정의 프롬프트가 있으면 사용, 없으면 기본 프롬프트 사용
        self.prompt_template = prompt_template if prompt_template else self.default_prompt_template

    def generate_response(self, product_title, review_content):
        """GPT를 사용하여 리뷰 답변 생성"""
        try:
            # 텍스트 정리
            clean_product_title = clean_text(product_title)
            clean_review_content = clean_text(review_content)
            
            # 텍스트가 너무 짧으면 원본 사용
            if len(clean_product_title.strip()) < 5:
                clean_product_title = product_title
            if len(clean_review_content.strip()) < 10:
                clean_review_content = review_content
            
            prompt = self.prompt_template.format(
                product_title=clean_product_title,
                review_content=clean_review_content
            )
            
            # 성능 최적화: 더 빠른 모델 사용
            client = openai.OpenAI(api_key=openai.api_key)
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",  # gpt-4o-mini보다 빠름
                messages=[
                    {"role": "system", "content": "당신은 여행사 몽키트래블의 고객 서비스 담당자입니다."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,  # 토큰 수 줄여서 속도 향상
                temperature=0.7,
                timeout=30  # 타임아웃 설정
            )
            
            result = response.choices[0].message.content.strip()
            return result
            
        except Exception as e:
            print(f"GPT API 호출 실패: {str(e)}")
            # 더 구체적인 기본 답변 생성
            if "가이드" in review_content or "선생님" in review_content:
                return "안녕하세요, 몽키트래블입니다 :) 가이드님과 함께 즐거운 시간 보내셨다니 정말 기쁩니다! 소중한 후기 감사합니다!"
            elif "좋" in review_content or "만족" in review_content:
                return "안녕하세요, 몽키트래블입니다 :) 만족스러운 여행이 되셨다니 정말 기쁩니다! 소중한 후기 감사합니다!"
            else:
                return "안녕하세요, 몽키트래블입니다 :) 소중한 후기 감사합니다!"

def extract_review_data(review, gpt_generator):
    """리뷰 데이터에서 필요한 정보 추출 및 GPT 답변 생성"""
    # 기본 데이터 추출
    review_data = {
        "id": review.get("id"),
        "productTitle": review.get("productTitle", "상품명 없음"),
        "comment": review.get("comment", "후기 내용 없음"),
        "score": review.get("score", 0),
        "reservationNo": review.get("reservationNo", "예약번호 없음"),
        "username": review.get("username", "익명"),
        "travelStartDate": review.get("travelStartDate", "날짜 정보 없음"),
        "createdAt": review.get("createdAt", "작성일 없음")
    }
    
    # GPT 답변 생성
    gpt_response = gpt_generator.generate_response(
        review_data["productTitle"],
        review_data["comment"]
    )
    review_data["gptResponse"] = gpt_response
    
    return review_data

def process_reviews_parallel(reviews, gpt_generator, partner_name):
    """병렬로 리뷰 데이터 처리"""
    # 리뷰 ID 기준으로 중복 제거
    unique_reviews = {}
    for review in reviews:
        review_id = review.get('id')
        if review_id and review_id not in unique_reviews:
            unique_reviews[review_id] = review
    
    reviews = list(unique_reviews.values())
    print(f"  🔍 중복 제거: {len(reviews)}개 리뷰로 처리")
    
    with ThreadPoolExecutor(max_workers=min(10, len(reviews))) as executor:
        futures = [
            executor.submit(extract_review_data, review, gpt_generator) 
            for review in reviews
        ]
        
        processed_reviews = []
        for future in as_completed(futures):
            try:
                review_data = future.result()
                review_data['partner'] = partner_name
                processed_reviews.append(review_data)
            except Exception as e:
                print(f"  ⚠️ 리뷰 처리 실패: {e}")
        
        return processed_reviews

def collect_reviews_data(custom_prompt=None, account_email=None, account_password=None):
    """리뷰 데이터 수집 및 GPT 답변 생성"""
    tm = TokenManager()
    rc = ReviewsCollector()
    
    gpt_gen = GPTResponseGenerator(prompt_template=custom_prompt)

    # API 키 검증
    if not validate_api_key():
        pass  # 에러는 UI에서 처리됨
    
    # 계정 정보 확인
    if not account_email or not account_password:
        return []
    
    # 로그인 토큰 발급
    token = tm.get_login_token(account_email, account_password)
    if not token:
        return []

    # 사용 가능한 파트너 목록 조회
    partners = tm.get_available_partners(token)
    if not partners:
        return []

    # 중복 제거: 파트너 이름 기준으로 중복 제거 (한 번만 실행)
    unique_partners = []
    seen_names = set()
    
    for p in partners:
        partner_name = p['name']
        if partner_name not in seen_names:
            unique_partners.append(p)
            seen_names.add(partner_name)
        else:
            print(f"  ⚠️ 중복 파트너 제거: {partner_name} (ID: {p['id']})")
    
    # 파트너 정보 로그 (한 번만 출력)
    print(f"🔍 발견된 파트너 수: {len(partners)} (중복 제거 후: {len(unique_partners)})")
    for p in unique_partners:
        print(f"  - ID: {p['id']}, 이름: {p['name']}, 계정ID: {p.get('partnerAccountId', 'N/A')}")

    all_reviews = []

    # 병렬로 파트너별 리뷰 수집
    def collect_partner_reviews(p):
        print(f"📊 파트너 '{p['name']}' (ID: {p['id']}) 리뷰 수집 시작...")
        
        # 파트너별 토큰 발급
        partner_token = tm.switch_partner_token(token, p["id"], p.get("partnerAccountId"))
        if not partner_token:
            partner_token = token
            print(f"  ⚠️ 파트너별 토큰 발급 실패, 기본 토큰 사용")
        else:
            print(f"  ✅ 파트너별 토큰 발급 성공")
        
        # 병렬로 4,5점 리뷰 조회
        reviews = rc.get_reviews_parallel(partner_token, p["id"])
        
        if reviews:
            print(f"  📝 총 {len(reviews)}개 리뷰 발견")
            # 병렬로 GPT 답변 생성
            processed_reviews = process_reviews_parallel(reviews, gpt_gen, p['name'])
            print(f"  ✅ 파트너 '{p['name']}' 총 {len(processed_reviews)}개 리뷰 처리 완료")
            return processed_reviews
        else:
            print(f"  📝 리뷰 없음")
            return []
    
    # 병렬로 모든 파트너 처리
    with ThreadPoolExecutor(max_workers=len(unique_partners)) as executor:
        futures = [executor.submit(collect_partner_reviews, p) for p in unique_partners]
        
        for future in as_completed(futures):
            try:
                partner_reviews = future.result()
                all_reviews.extend(partner_reviews)
            except Exception as e:
                print(f"⚠️ 파트너 리뷰 수집 실패: {e}")

    # 최종 중복 제거 (리뷰 ID 기준)
    unique_all_reviews = {}
    for review in all_reviews:
        review_id = review.get('id')
        if review_id and review_id not in unique_all_reviews:
            unique_all_reviews[review_id] = review
    
    final_reviews = list(unique_all_reviews.values())
    print(f"🎯 최종 중복 제거 완료: 총 {len(final_reviews)}개 리뷰")
    
    return final_reviews

def create_dataframe(data):
    """데이터를 DataFrame으로 변환"""
    if not data:
        return pd.DataFrame()
    
    df = pd.DataFrame(data)
    
    # 필드명을 한글로 변경
    column_mapping = {
        'id': '리뷰ID',
        'productTitle': '상품명',
        'comment': '후기내용',
        'score': '점수',
        'reservationNo': '예약번호',
        'username': '작성자',
        'travelStartDate': '여행일',
        'createdAt': '작성일',
        'gptResponse': 'GPT답변',
        'partner': '파트너'
    }
    
    # 존재하는 컬럼만 변경
    existing_columns = {k: v for k, v in column_mapping.items() if k in df.columns}
    df = df.rename(columns=existing_columns)
    
    return df

# 페이지 설정
st.set_page_config(
    page_title="마리트 긍정 리뷰 답변 생성",
    page_icon="📋",
    layout="wide"
)

# 제목
st.title("📋 마리트 긍정 리뷰 답변 생성")
st.markdown("---")

# CSS 스타일 및 JavaScript 추가
st.markdown("""
<style>
.copy-button {
    background-color: #4CAF50;
    border: none;
    color: white;
    padding: 8px 16px;
    text-align: center;
    text-decoration: none;
    display: inline-block;
    font-size: 14px;
    margin: 4px 2px;
    cursor: pointer;
    border-radius: 4px;
}
.copy-button:hover {
    background-color: #45a049;
}
.review-card {
    border: 1px solid #ddd;
    border-radius: 8px;
    padding: 16px;
    margin: 8px 0;
    background-color: #f9f9f9;
}
.gpt-response {
    background-color: #e8f5e8;
    border-left: 4px solid #4CAF50;
    padding: 12px;
    margin: 8px 0;
    border-radius: 4px;
}

/* 파트너 선택 버튼 스타일 */
.stMultiSelect [data-baseweb="select"] {
    border-radius: 8px;
}

/* 파트너 선택 시 각각 다른 색상 강조 */
.stMultiSelect [data-baseweb="select"]:has(option[value="몽키트래블"]:checked) {
    border-color: #4ECDC4;
    box-shadow: 0 0 0 2px rgba(78, 205, 196, 0.2);
}

.stMultiSelect [data-baseweb="select"]:has(option[value="토토부킹"]:checked) {
    border-color: #FF6B6B;
    box-shadow: 0 0 0 2px rgba(255, 107, 107, 0.2);
}

/* 파트너 옵션 텍스트 색상 */
.stMultiSelect [data-baseweb="select"] option[value="몽키트래블"] {
    color: #4ECDC4 !important;
    font-weight: bold;
}

.stMultiSelect [data-baseweb="select"] option[value="토토부킹"] {
    color: #FF6B6B !important;
    font-weight: bold;
}

/* 선택된 파트너 옵션 배경색 */
.stMultiSelect [data-baseweb="select"] option[value="몽키트래블"]:checked {
    background-color: #4ECDC4 !important;
    color: white !important;
}

.stMultiSelect [data-baseweb="select"] option[value="토토부킹"]:checked {
    background-color: #FF6B6B !important;
    color: white !important;
}

/* Streamlit 멀티셀렉트 내부 스타일링 */
.stMultiSelect [data-baseweb="select"] div[role="option"] {
    border-radius: 4px;
}

/* 파트너 옵션 호버 효과 */
.stMultiSelect [data-baseweb="select"] div[role="option"]:hover {
    background-color: rgba(78, 205, 196, 0.1);
}
</style>

<script>
function copyToClipboard(textId, reviewId) {
    const textArea = document.getElementById(textId);
    const statusDiv = document.getElementById('status_' + textId);
    
    if (textArea) {
        // 임시로 textarea를 보이게 하고 선택
        textArea.style.display = 'block';
        textArea.select();
        textArea.setSelectionRange(0, 99999); // 모바일 지원
        
        try {
            const successful = document.execCommand('copy');
            if (successful) {
                statusDiv.innerHTML = '<span style="color: green;">✅ 복사 완료! (리뷰 ID: ' + reviewId + ')</span>';
                setTimeout(() => {
                    statusDiv.innerHTML = '';
                }, 3000);
            } else {
                statusDiv.innerHTML = '<span style="color: red;">❌ 복사 실패</span>';
            }
        } catch (err) {
            statusDiv.innerHTML = '<span style="color: red;">❌ 복사 실패: ' + err + '</span>';
        }
        
        // textarea 다시 숨기기
        textArea.style.display = 'none';
    }
}
</script>
""", unsafe_allow_html=True)

# 사이드바 - 설정
st.sidebar.header("🔍 설정")

# 계정 정보 설정 (환경변수에서 자동으로 가져오기)
if DEFAULT_EMAIL and DEFAULT_PASSWORD:
    # 환경변수에 계정 정보가 있으면 자동으로 사용
    account_email = DEFAULT_EMAIL
    account_password = DEFAULT_PASSWORD
else:
    # 환경변수에 없으면 기본값 설정
    account_email = ""
    account_password = ""



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
        value="""역할: 당신은 여행사 몽키트래블 직원입니다. 리뷰에 대한 답변을 작성하며, 리뷰어의 감정·표현·세부사항을 그대로 반영하여 정직하고 공감되는 어조로 짧고 간결하게 답변을 남깁니다.

작성 원칙:  
- 답변은 반드시 "안녕하세요, 몽키트래블입니다 :)"로 시작  
- 4줄 이내로 작성 (너무 길지 않도록)  
- 리뷰에 없는 내용은 유추하지 말 것  
- 감정선 그대로 반영  
- 느낌표, ㅎㅎ, ^^, 이모지 등은 감정에 따라 적절히 사용  
- 가이드 이름/특징이 있다면 반드시 언급  
- 정보성 후기엔 "팁 공유 감사합니다" 등 감사 표현 포함  
- 마지막에 "감사합니다" 문장은 꼭 포함
- 예약변경, 예약취소 요청 등은 후기에서 안내가 어려우니 고객센터 등으로 별도요청 유도
- 리뷰 내용을 정확히 이해하고 자연스러운 한국어로 답변할 것
- 리뷰의 구체적인 내용을 반영하여 개인화된 답변 작성
- 부정적인 부분이 있다면 공감과 함께 개선 의지 표현
- 가이드 이름을 모르는 경우 "해당 가이드님" 또는 "가이드님"으로 표현
- 실제로 알 수 없는 정보는 유추하지 말 것
- 한국어 가능한 가이드/기사에 대해서는 "한국어로 편리하게 안내해주셔서" 또는 "한국어 소통이 편리해서" 등 자연스러운 표현 사용
- "-했답니다" 같은 어색한 표현 대신 "-해서 정말 다행이었네요", "-되셨다니 기쁩니다" 등 자연스러운 표현 사용
- 문맥에 맞게 자연스러운 한국어로 답변할 것
- 고객이 이미 긍정적으로 표현한 내용에 대해 불필요한 추가 추측은 하지 말 것
- "감사합니다" 표현은 한 번만 사용하고 중복하지 말 것
- "소중한 후기 감사합니다" 또는 "감사합니다" 중 하나만 선택하여 사용

예시 1) 상품명: [디너는 예쁘게, 선셋은 감성 있게] 차오프라야 프린세스 크루즈
리뷰: 공연과 식사 모두 좋았고, 배에서 보는 짜오프라야강의 야경이 아름다웠습니다.
→ 안녕하세요, 몽키트래블입니다 :) 공연과 식사에 만족하셨다니 정말 기쁩니다! 특히 야경이 인상 깊으셨다니 멋진 추억 되셨을 것 같아요. 소중한 후기 감사합니다!

예시 2) 상품명: [단독투어] 담넌사두억 수상시장 + 위험한 기찻길
리뷰: 초등 아이와 함께 했는데, 가이드님의 설명도 좋았고 아이도 좋아했어요.
→ 안녕하세요, 몽키트래블입니다 :) 초등 아이와 함께 투어에 참여하셨군요! 가이드님과 함께 안전하고 편안하게 여행하셨다니 정말 다행입니다. 소중한 후기 감사합니다!

예시 3) 상품명: [프리미엄 스노클링] 라차섬 + 코랄섬
리뷰: 5명이서 비 오는 날에도 스노클링을 즐기고 회와 소주로 마무리했어요 ㅎㅎ
→ 안녕하세요, 몽키트래블입니다 :) 5분이서 즐거운 시간을 보내셨다니 정말 다행입니다! 비가 와도 스노클링을 잘 즐기셨고, 회와 소주 번개까지 ㅎㅎ 좋은 추억이 되셨길 바랍니다. ^^

예시 4) 상품명: 왕궁 & 새벽사원
리뷰: 설명은 조금 어려웠지만 가이드님이 정말 친절했어요.
→ 안녕하세요, 몽키트래블입니다 :) 한국어 소통이 조금 어려우셨다니 아쉬워요 ㅠㅠ 그래도 가이드님의 친절함을 느끼셨다니 다행입니다. 소중한 후기 감사드려요!

예시 5) 상품명: 무앙깨우 골프장
리뷰: 코스가 예뻤고 직원들도 친절했어요.
→ 안녕하세요, 몽키트래블입니다 :) 코스와 직원 모두 만족스러우셨다니 정말 기쁩니다! 편안한 라운딩 되셨길 바라요. 소중한 후기 감사합니다!

예시 6) 상품명: 요트 투어
리뷰: 아이들이 처음 배에 타는지라 걱정이 되었는데 잘 놀았습니다. 감사합니다
→ 안녕하세요, 몽키트래블입니다 :) 아이들과 함께 즐거운 시간 보내셨다니 다행이에요! 처음이라 걱정되셨지만 잘 즐기셨다니 기쁩니다. 또 함께 여행할 수 있기를 기대합니다. 감사합니다!

예시 7) 상품명: 망고 쿠킹 스쿨
리뷰: 장소 찾는 것도 생각보다 어렵지 않았어요. 깨끗한 공간에서 친절한 씨 선생님과 직원분들이 수업도 재밌게 이끌어주셨어요. 다만 당시 어떤 한국인 어머니 세분이 아이들을 데리고 방문 하셨는데 예약이 잘 안 되었는지 계속 얘기를 나누시더라구요. 이유는 알겠으나 그분들 때문에 20분이나 수업이 늦어졌어요.
→ 안녕하세요, 몽키트래블입니다 :) 씨 선생님과 직원분들과 함께 즐거운 수업 시간 보내셨다니 기쁩니다! 장소 찾기도 수월하셨다니 다행이에요. 수업 지연으로 불편을 드린 점 사과드립니다. 앞으로는 더욱 원활한 수업 진행을 위해 노력하겠습니다. 소중한 후기 감사합니다!

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

답변:""",
        height=400,
        help="GPT가 리뷰에 답변할 때 사용할 프롬프트를 입력하세요. {product_title}과 {review_content}는 자동으로 치환됩니다."
    )
else:
    custom_prompt = None

# 데이터 가져오기 버튼을 최상단에 배치
st.sidebar.markdown("---")

# 캐시 키 생성 (프롬프트와 계정 정보 기반)
cache_key = f"reviews_{hash(str(custom_prompt))}_{hash(account_email)}_{hash(account_password)}"

if st.sidebar.button("📊 데이터 가져오기", key="load_data", use_container_width=True, type="primary"):
    # 필수 정보 확인
    if not account_email or not account_password:
        st.error("❌ 이메일과 비밀번호를 입력해주세요.")
    elif not openai.api_key:
        st.error("❌ OpenAI API 키가 설정되지 않았습니다. 환경변수를 확인해주세요.")
    else:
        # 캐시된 데이터가 있는지 확인
        if 'review_cache' in st.session_state and cache_key in st.session_state.review_cache:
            st.success("✅ 캐시된 데이터를 사용합니다.")
            st.session_state.review_df = st.session_state.review_cache[cache_key]
        else:
            # 데이터 수집 및 GPT 답변 생성
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            try:
                status_text.text("🔍 파트너 정보 조회 중...")
                progress_bar.progress(10)
                
                review_data = collect_reviews_data(
                    custom_prompt=custom_prompt,
                    account_email=account_email,
                    account_password=account_password
                )
                
                progress_bar.progress(100)
                status_text.text("✅ 데이터 수집 완료!")
                
                if review_data:
                    # DataFrame 생성
                    df = create_dataframe(review_data)
                    st.session_state.review_df = df
                    
                    # 캐시에 저장
                    if 'review_cache' not in st.session_state:
                        st.session_state.review_cache = {}
                    st.session_state.review_cache[cache_key] = df
                else:
                    st.error("데이터 수집에 실패했습니다. 계정 정보를 확인해주세요.")
            except Exception as e:
                st.error(f"데이터 수집 중 오류 발생: {e}")

st.sidebar.markdown("---")

# 파트너 선택
st.sidebar.subheader("🏢 파트너 선택")
selected_partners = st.sidebar.multiselect(
    "파트너 선택",
    options=["토토부킹", "몽키트래블"],
    default=["몽키트래블"]
)

# 점수 필터
st.sidebar.subheader("⭐ 점수 선택")
selected_scores = st.sidebar.multiselect(
    "점수 선택",
    options=[4, 5],
    default=[5]
)

# API 키 상태 확인 (오류만 표시)
if openai.api_key:
    api_status = validate_api_key()
    if not api_status:
        st.sidebar.error("❌ OpenAI API 연결 실패")
else:
    st.sidebar.warning("⚠️ OpenAI API 키가 설정되지 않음")



# 저장된 데이터가 있으면 표시
if 'review_df' in st.session_state and not st.session_state.review_df.empty:
    df = st.session_state.review_df
    
    # 필터 적용
    filtered_df = df.copy()
    
    if selected_partners:
        filtered_df = filtered_df[filtered_df['파트너'].isin(selected_partners)]
    
    if selected_scores:
        filtered_df = filtered_df[filtered_df['점수'].isin(selected_scores)]
    
    # 작성일시 최신 순으로 정렬
    if '작성일' in filtered_df.columns:
        # 작성일 컬럼을 datetime으로 변환하여 정렬
        filtered_df['작성일_정렬용'] = pd.to_datetime(filtered_df['작성일'], errors='coerce')
        filtered_df = filtered_df.sort_values('작성일_정렬용', ascending=False)
        filtered_df = filtered_df.drop('작성일_정렬용', axis=1)
    
    # 리뷰 수 표시
    st.metric("📊 총 리뷰 수", len(filtered_df))
    
    # 현재 필터 표시
    if selected_partners or selected_scores:
        filter_info = []
        if selected_partners:
            filter_info.append(f"파트너: {', '.join(selected_partners)}")
        if selected_scores:
            filter_info.append(f"점수: {', '.join(map(str, selected_scores))}")
        
        st.info(" | ".join(filter_info))
    
    st.markdown("---")
    
    # GPT 답변 카드 형태로 표시
    st.subheader("📝 GPT 답변 목록")
    
    if not filtered_df.empty:
        for idx, row in filtered_df.iterrows():
            with st.container():
                # 파트너별 색상 설정
                partner_name = row.get('파트너', 'N/A')
                if '토토부킹' in partner_name:
                    partner_color = '#FF6B6B'  # 빨간색
                    partner_bg_color = '#FFE6E6'
                elif '몽키트래블' in partner_name:
                    partner_color = '#4ECDC4'  # 청록색
                    partner_bg_color = '#E6F7F5'
                else:
                    partner_color = '#95A5A6'  # 회색
                    partner_bg_color = '#F5F5F5'
                
                st.markdown(f"""
                <div class="review-card" style="border-left: 5px solid {partner_color}; background-color: {partner_bg_color};">
                    <div style="background-color: {partner_color}; color: white; padding: 8px 12px; margin: -16px -16px 16px -16px; border-radius: 8px 8px 0 0;">
                        <h4 style="margin: 0; color: white;">🏢 {partner_name} | 📋 리뷰 ID: {row.get('리뷰ID', 'N/A')}</h4>
                    </div>
                    <p><strong>점수:</strong> ⭐ {row.get('점수', 'N/A')}점</p>
                    <p><strong>상품명:</strong> {row.get('상품명', 'N/A')}</p>
                    <p><strong>작성자:</strong> {row.get('작성자', 'N/A')}</p>
                    <p><strong>예약번호:</strong> {row.get('예약번호', 'N/A')} | <strong>여행일:</strong> {row.get('여행일', 'N/A')} | <strong>작성일:</strong> {row.get('작성일', 'N/A')}</p>
                    <p><strong>후기내용:</strong> {row.get('후기내용', 'N/A')}</p>
                    <div class="gpt-response">
                        <strong>🤖 GPT 답변:</strong><br>
                        {row.get('GPT답변', 'N/A')}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # 진짜 원클릭 복사 버튼
                gpt_text = row.get('GPT답변', '')
                if gpt_text and gpt_text != 'N/A':
                    # 안전하게 텍스트 이스케이프 처리
                    safe_text = gpt_text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '').replace('`', '\\`')
                    
                    # HTML과 JavaScript로 원클릭 복사 구현
                    copy_html = f"""
                    <div style="margin: 15px 0;">
                        <button id="copyBtn_{idx}" onclick="copyText_{idx}()" 
                                style="background: linear-gradient(45deg, {partner_color}, {partner_color}dd); 
                                       color: white; border: none; padding: 12px 24px; 
                                       border-radius: 8px; cursor: pointer; font-size: 14px; 
                                       font-weight: bold; box-shadow: 0 2px 4px rgba(0,0,0,0.2);
                                       transition: all 0.3s ease;">
                            📋 {partner_name} 답변 복사하기 (ID: {row.get('리뷰ID', 'N/A')})
                        </button>
                        <div id="result_{idx}" style="margin-top: 10px; font-weight: bold;"></div>
                    </div>
                    
                    <script>
                        async function copyText_{idx}() {{
                            const text = "{safe_text}";
                            const btn = document.getElementById('copyBtn_{idx}');
                            const result = document.getElementById('result_{idx}');
                            
                            try {{
                                // 최신 브라우저 Clipboard API 시도
                                if (navigator.clipboard && window.isSecureContext) {{
                                    await navigator.clipboard.writeText(text);
                                    result.innerHTML = '<span style="color: #4CAF50;">✅ 복사 완료! 붙여넣기(Ctrl+V)하세요</span>';
                                    btn.style.background = 'linear-gradient(45deg, #2196F3, #1976D2)';
                                    btn.innerHTML = '✅ 복사 완료!';
                                }} else {{
                                    // 폴백: 임시 텍스트 영역 생성
                                    const textArea = document.createElement('textarea');
                                    textArea.value = text;
                                    textArea.style.position = 'fixed';
                                    textArea.style.left = '-9999px';
                                    textArea.style.top = '-9999px';
                                    document.body.appendChild(textArea);
                                    textArea.focus();
                                    textArea.select();
                                    
                                    const successful = document.execCommand('copy');
                                    document.body.removeChild(textArea);
                                    
                                    if (successful) {{
                                        result.innerHTML = '<span style="color: #4CAF50;">✅ 복사 완료! 붙여넣기(Ctrl+V)하세요</span>';
                                        btn.style.background = 'linear-gradient(45deg, #2196F3, #1976D2)';
                                        btn.innerHTML = '✅ 복사 완료!';
                                    }} else {{
                                        throw new Error('복사 실패');
                                    }}
                                }}
                                
                                // 3초 후 원래 상태로 복원
                                setTimeout(() => {{
                                    result.innerHTML = '';
                                    btn.style.background = 'linear-gradient(45deg, {partner_color}, {partner_color}dd)';
                                    btn.innerHTML = '📋 {partner_name} 답변 복사하기 (ID: {row.get("리뷰ID", "N/A")})';
                                }}, 3000);
                                
                            }} catch (err) {{
                                result.innerHTML = '<span style="color: #f44336;">❌ 복사 실패. 브라우저가 지원하지 않습니다.</span>';
                                console.error('복사 실패:', err);
                                
                                // 실패 시 텍스트 영역 표시
                                setTimeout(() => {{
                                    result.innerHTML = `
                                        <div style="margin-top: 10px; padding: 10px; background: #f5f5f5; border-radius: 5px;">
                                            <p style="margin: 0 0 5px 0; font-size: 12px;">수동 복사용:</p>
                                            <textarea style="width: 100%; height: 80px; font-family: inherit;" readonly onclick="this.select()">${{text}}</textarea>
                                        </div>
                                    `;
                                }}, 1000);
                            }}
                        }}
                        
                        // 버튼 호버 효과
                        document.getElementById('copyBtn_{idx}').addEventListener('mouseover', function() {{
                            this.style.transform = 'translateY(-2px)';
                            this.style.boxShadow = '0 4px 8px rgba(0,0,0,0.3)';
                        }});
                        
                        document.getElementById('copyBtn_{idx}').addEventListener('mouseout', function() {{
                            this.style.transform = 'translateY(0)';
                            this.style.boxShadow = '0 2px 4px rgba(0,0,0,0.2)';
                        }});
                    </script>
                    """
                    
                    # HTML 렌더링
                    st.components.v1.html(copy_html, height=120)
                
                st.markdown("---")
    
    else:
        st.warning("선택된 필터에 해당하는 데이터가 없습니다.")

else:
    # 초기 화면
    st.info("👆 왼쪽 사이드바에서 '📊 데이터 가져오기' 버튼을 클릭하여 리뷰 데이터를 생성하고 가져오세요.")
    
    # 사용법 안내
    st.markdown("---")
    st.subheader("📖 사용법")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        **1단계: 데이터 가져오기**
        - 사이드바에서 "📊 데이터 가져오기" 클릭
        - 자동으로 데이터 생성 및 로드
        """)
        
        st.markdown("""
        **2단계: 필터 설정**
        - 파트너 선택 (토토부킹/몽키트래블)
        - 점수 선택 (4점/5점)
        """)
    
    with col2:
        st.markdown("""
        **3단계: GPT 답변 확인**
        - 생성된 GPT 답변 확인
        - 리뷰 내용과 함께 표시
        """)
        
        st.markdown("""
        **4단계: 답변 복사**
        - 원하는 GPT 답변의 "📋 답변 복사하기" 버튼 클릭
        - 자동으로 클립보드에 복사됨
        - "✅ 복사 완료!" 확인 후 Ctrl+V로 붙여넣기
        """)

# 푸터
st.markdown("---")
st.markdown("*GPT 답변 복사 대시보드 - 통합 버전 - " + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "*")
