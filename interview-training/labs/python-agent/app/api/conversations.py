import logging

from fastapi import APIRouter, HTTPException
from openai import APITimeoutError, OpenAIError
from langchain_core.exceptions import OutputParserException
from sqlalchemy.exc import (
    OperationalError,
    SQLAlchemyError,
    TimeoutError as PoolTimeoutError,
)

from app.schemas.requirements import RequirementInput
from app.schemas.conversations import ConversationInput
from app.repositories import conversation_repository as repository
from app.services.conversation_service import chat_in_conversation

router = APIRouter(
    prefix="/conversations",
    tags=["conversations"],
)

DEMO_USER_ID = "user-001"  # 当前本地演练身份。
logger = logging.getLogger(__name__)


def http_error(error: Exception) -> HTTPException:
    if isinstance(error, repository.ConversationNotFound):
        return HTTPException(404, "会话不存在或无权访问")

    if isinstance(error, repository.ConversationBusy):
        return HTTPException(409, "该会话有任务正在执行，请稍后发送")

    if isinstance(error, APITimeoutError):
        return HTTPException(504, "模型请求超时")

    if isinstance(error, (OpenAIError, OutputParserException)):
        return HTTPException(502, "模型调用或结果解析失败")

    if isinstance(error, (OperationalError, PoolTimeoutError)):
        return HTTPException(503, "业务数据库暂时不可用")

    logger.exception("conversation operation failed")
    return HTTPException(500, "会话处理失败，请联系维护人员")


def db_call(function, *args):
    try:
        return function(*args)  # 调用对应数据库函数。
    except (
        repository.ConversationNotFound,
        repository.ConversationBusy,
        SQLAlchemyError,
    ) as error:
        raise http_error(error) from error


@router.post("", status_code=201)
def create(body: ConversationInput):
    return db_call(
        repository.create_conversation,
        DEMO_USER_ID,
        body.title,
    )


@router.get("")
def list_all():
    return db_call(
        repository.list_conversations,
        DEMO_USER_ID,
    )


@router.get("/{conversation_id}/messages")
def messages(conversation_id: str):
    return db_call(
        repository.read_conversation,
        DEMO_USER_ID,
        conversation_id,
    )


@router.get("/{conversation_id}/tasks")
def tasks(conversation_id: str):
    return db_call(
        repository.read_conversation,
        DEMO_USER_ID,
        conversation_id,
        True,  # 读取任务事件。
    )


@router.post("/{conversation_id}/chat")
async def chat(conversation_id: str, body: RequirementInput):
    try:
        return await chat_in_conversation(
            DEMO_USER_ID,
            conversation_id,
            body.input,
        )
    except Exception as error:
        raise http_error(error) from error


@router.delete("/{conversation_id}")
def delete(conversation_id: str):
    return db_call(
        repository.delete_conversation,
        DEMO_USER_ID,
        conversation_id,
    )