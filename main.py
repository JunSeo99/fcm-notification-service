from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict
from bson import ObjectId
import firebase_admin
from firebase_admin import messaging, credentials
from motor.motor_asyncio import AsyncIOMotorClient
import os
import uvicorn

app = FastAPI()

# MongoDB 연결 과정
MONGO_URI = os.getenv("MONGOURI")  # 환경변수로부터 MongoDB URI 가져오기
mongo_client = AsyncIOMotorClient(MONGO_URI)
db = mongo_client["WeAndNow"]
user_collection = db["users"]

# FCM 환경변수 설정

cred = credentials.Certificate("/home/ubuntu/firebase-service-account.json")  # 서비스 계정 키 파일 경로
firebase_admin.initialize_app(cred)


class Receive(BaseModel):
    userIds: List[str]
    data: Optional[Dict[str, str]] = None
    title: Optional[str] = None
    body: Optional[str] = None
    content: Optional[str] = None


class TokensReceive(BaseModel):
    tokens: List[str]
    data: Optional[Dict[str, str]] = None
    title: Optional[str] = None
    body: Optional[str] = None
    content: Optional[str] = None

@app.get("/test")
async def monitering():
    return "success"


@app.post("/notification/tokens")
async def send_tokens_notification(receive: TokensReceive):

    android_data = receive.data.copy() if receive.data else {}
    android_data["title"] = receive.title or ""
    android_data["body"] = receive.body or ""
    android_data["subText"] = receive.content or ""
    android_data["priority"] = "high"
    android_data["badge"] = "0"

    # APNS 설정 준비
    aps_alert = messaging.ApsAlert(
        title=receive.title or "",
        subtitle=receive.content or "",
        body=receive.body or ""
    )
    aps = messaging.Aps(
        alert=aps_alert,
        sound="default",
        thread_id=receive.data.get("roomId") if receive.data and "roomId" in receive.data else None
    )

    apns_config = messaging.APNSConfig(
        headers={"apns-collapse-id": receive.data.get(
            "messageId")} if receive.data and "messageId" in receive.data else None,
        payload=messaging.APNSPayload(aps=aps)
    )

    # Android 설정 준비
    android_config = messaging.AndroidConfig(
        data=android_data
    )

    # 메시지 생성
    message = messaging.MulticastMessage(
        data=receive.data,
        android=android_config,
        apns=apns_config,
        tokens=receive.tokens
    )

    # 메시지 전송
    try:
        response = messaging.send_each_for_multicast(message)
        print("메시지 전송 성공:", response.success_count)
        print("메시지 전송 실패:", response.failure_count)
        return {"success": True}
    except Exception as e:
        print("메시지 전송 에러:", e)
        raise HTTPException(status_code=500, detail="알림 전송 실패")


@app.post("/notification")
async def send_notification(receive: Receive):
    try:
        # userIds를 ObjectId로 변환
        user_ids = [ObjectId(id) for id in receive.userIds]
    except Exception as e:
        print("userIds 변환 에러:", e)
        raise HTTPException(status_code=400, detail="유효하지 않은 userIds입니다.")

    # MongoDB Aggregation 파이프라인 생성
    pipeline = [
        {"$match": {"_id": {"$in": user_ids}}},
        {"$unwind": "$fcmToken"},
        {"$match": {"fcmToken.fcmToken": {"$ne": ""}}},
        {"$replaceRoot": {"newRoot": "$fcmToken"}}
    ]

    # Aggregation 실행
    try:
        cursor = user_collection.aggregate(pipeline)
        results = await cursor.to_list(length=None)
    except Exception as e:
        print("MongoDB 조회 에러:", e)
        raise HTTPException(status_code=500, detail="데이터베이스 조회 실패")

    # FCM 토큰 추출
    tokens_set = set()
    for element in results:
        token = element.get("fcmToken")
        if token:
            tokens_set.add(token)
    tokens = list(tokens_set)
    print("토큰 목록:", tokens)

    if not tokens:
        return {"message": "토큰이 없습니다."}

    # Android 데이터 준비
    android_data = receive.data.copy() if receive.data else {}
    android_data["title"] = receive.title or ""
    android_data["body"] = receive.body or ""
    android_data["subText"] = receive.content or ""
    android_data["priority"] = "high"
    android_data["badge"] = "0"

    # APNS 설정 준비
    aps_alert = messaging.ApsAlert(
        title=receive.title or "",
        subtitle=receive.content or "",
        body=receive.body or ""
    )
    aps = messaging.Aps(
        alert=aps_alert,
        sound="default",
        thread_id=receive.data.get("roomId") if receive.data and "roomId" in receive.data else None
    )

    apns_config = messaging.APNSConfig(
        headers={"apns-collapse-id": receive.data.get(
            "messageId")} if receive.data and "messageId" in receive.data else None,
        payload=messaging.APNSPayload(aps=aps)
    )

    # Android 설정 준비
    android_config = messaging.AndroidConfig(
        data=android_data
    )

    # 메시지 생성
    message = messaging.MulticastMessage(
        data=receive.data,
        android=android_config,
        apns=apns_config,
        tokens=tokens
    )

    # 메시지 전송
    try:
        response = messaging.send_each_for_multicast(message)
        print("메시지 전송 성공:", response.success_count)
        print("메시지 전송 실패:", response.failure_count)
        return {"success": True}
    except Exception as e:
        print("메시지 전송 에러:", e)
        raise HTTPException(status_code=500, detail="알림 전송 실패")


@app.post("/notification/room")
async def send_room_notification(receive: Receive):
    try:
        # userIds를 ObjectId로 변환
        user_ids = [ObjectId(id) for id in receive.userIds]
    except Exception as e:
        print("userIds 변환 에러:", e)
        raise HTTPException(status_code=400, detail="유효하지 않은 userIds입니다.")

    # MongoDB Aggregation 파이프라인 생성
    pipeline = [
        {"$match": {"_id": {"$in": user_ids}}},
        {"$unwind": "$fcmToken"},
        {"$match": {"fcmToken.fcmToken": {"$ne": ""}}},
        {"$replaceRoot": {"newRoot": "$fcmToken"}}
    ]

    # Aggregation 실행
    try:
        cursor = user_collection.aggregate(pipeline)
        results = await cursor.to_list(length=None)
    except Exception as e:
        print("MongoDB 조회 에러:", e)
        raise HTTPException(status_code=500, detail="데이터베이스 조회 실패")

    # FCM 토큰 추출
    tokens_set = set()
    for element in results:
        token = element.get("fcmToken")
        if token:
            tokens_set.add(token)
    tokens = list(tokens_set)
    print("토큰 목록:", tokens)

    if not tokens:
        return {"message": "토큰이 없습니다."}

    # Android 데이터 준비
    android_data = receive.data.copy() if receive.data else {}
    android_data["title"] = receive.title or ""
    android_data["body"] = receive.body or ""
    android_data["subText"] = receive.content or ""
    android_data["priority"] = "high"
    android_data["badge"] = "0"

    # APNS 설정 준비
    aps_alert = messaging.ApsAlert(
        title=receive.title or "",
        subtitle=receive.content or "",
        body=receive.body or ""
    )
    aps = messaging.Aps(
        alert=aps_alert,
        sound="default",
        thread_id=receive.data.get("roomId") if receive.data and "roomId" in receive.data else None
    )

    apns_config = messaging.APNSConfig(
        headers={"apns-collapse-id": receive.data.get(
            "messageId")} if receive.data and "messageId" in receive.data else None,
        payload=messaging.APNSPayload(aps=aps)
    )

    # Android 설정 준비
    android_config = messaging.AndroidConfig(
        data=android_data
    )

    # 메시지 생성
    message = messaging.MulticastMessage(
        data=receive.data,
        android=android_config,
        apns=apns_config,
        tokens=tokens
    )

    # 메시지 전송
    try:
        response = messaging.send_each_for_multicast(message)
        print("메시지 전송 성공:", response.success_count)
        print("메시지 전송 실패:", response.failure_count)
        return {"success": True}
    except Exception as e:
        print("메시지 전송 에러:", e)
        raise HTTPException(status_code=500, detail="알림 전송 실패")


if __name__ == "__main__":
    # 서버 실행
    uvicorn.run(app, host="0.0.0.0", port=8080)