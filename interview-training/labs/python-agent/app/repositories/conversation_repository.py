from uuid import uuid4  # 生成会话编号和任务编号。
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import engine  # 复用现有连接池。
from app.db.models import Conversation, Message, TaskEvent


class ConversationNotFound(Exception):
    pass  # HTTP层转换为404。


class ConversationBusy(Exception):
    pass  # HTTP层转换为409。


def owned(session, user_id, conversation_id, lock=False):
    query = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.user_id == user_id,  # 同时检查会话归属。
    )

    if lock:
        query = query.with_for_update()  # 短事务内锁住当前会话行。

    conversation = session.scalar(query)

    if conversation is None:
        raise ConversationNotFound()

    return conversation


def create_conversation(user_id: str, title: str) -> dict:
    conversation_id = str(uuid4())  # 后端生成会话编号。

    with Session(engine) as session, session.begin():
        session.add(
            Conversation(
                id=conversation_id,
                user_id=user_id,
                title=title,
            )
        )

    return {"conversation_id": conversation_id, "title": title}


def list_conversations(user_id: str) -> list[dict]:
    with Session(engine) as session:
        rows = session.scalars(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.created_at.desc(), Conversation.id)
            .limit(100)
        )

        return [
            {
                "conversation_id": row.id,
                "title": row.title,
                "active_task_id": row.active_task_id,
            }
            for row in rows
        ]


def read_conversation(
    user_id: str,
    conversation_id: str,
    events=False,
) -> list[dict]:
    with Session(engine) as session:
        owned(session, user_id, conversation_id)  # 先验证归属。

        table = TaskEvent if events else Message  # 选择读取事件或消息。

        rows = list(
            session.scalars(
                select(table)
                .where(table.conversation_id == conversation_id)
                .order_by(table.id.desc())
                .limit(100)  # 界面返回最近100条。
            )
        )

        return [
            {
                "id": row.id,
                "task_id": row.task_id,
                "created_at": row.created_at.isoformat(),
                **(
                    {"status": row.status, "details": row.details}
                    if events
                    else {"role": row.role, "content": row.content}
                ),
            }
            for row in reversed(rows)  # 显示时按旧→新排列。
        ]


def start_turn(
    user_id: str,
    conversation_id: str,
    input_text: str,
) -> tuple[str, list]:
    task_id = str(uuid4())  # 本轮执行编号。

    with Session(engine) as session, session.begin():
        conversation = owned(
            session, user_id, conversation_id, lock=True
        )

        if conversation.active_task_id:
            raise ConversationBusy()  # 这段会话已有任务正在执行。

        completed = select(TaskEvent.task_id).where(
            TaskEvent.conversation_id == conversation_id,
            TaskEvent.status == "completed",
        )  # 找到已经完成的历史轮次。

        rows = list(
            session.scalars(
                select(Message)
                .where(
                    Message.conversation_id == conversation_id,
                    Message.task_id.in_(completed),
                )
                .order_by(Message.id.desc())
                .limit(20)  # 最近20条已完成消息，通常对应10轮。
            )
        )

        history = [
            {"role": row.role, "content": row.content}
            for row in reversed(rows)
        ]  # 转为模型可以接收的消息列表。

        conversation.active_task_id = task_id

        session.add(
            Message(
                conversation_id=conversation_id,
                task_id=task_id,
                role="user",
                content=input_text,
            )
        )  # 保存本次用户输入。

        session.add(
            TaskEvent(
                conversation_id=conversation_id,
                task_id=task_id,
                status="started",
                details={},
            )
        )  # 记录开始执行。

    return task_id, history  # 此时事务已提交，连接已归还。


def finish_turn(
    user_id: str,
    conversation_id: str,
    task_id: str,
    result: dict | None,
    error_code: str = "execution_failed",
) -> None:
    with Session(engine) as session, session.begin():
        conversation = owned(
            session, user_id, conversation_id, lock=True
        )

        if conversation.active_task_id != task_id:
            raise ConversationBusy()  # 防止旧任务修改其他任务的状态。

        status = result["status"] if result else "failed"

        if result:
            session.add(
                Message(
                    conversation_id=conversation_id,
                    task_id=task_id,
                    role="assistant",
                    content=result["answer"],
                )
            )  # 保存助手回答。

        session.add(
            TaskEvent(
                conversation_id=conversation_id,
                task_id=task_id,
                status=status,
                details=(
                    {"tool_results": result["tool_results"]}
                    if result
                    else {"error_code": error_code}
                ),
            )
        )  # 保存工具记录，或者安全错误码。

        conversation.active_task_id = None  # 这段会话恢复空闲。


def delete_conversation(user_id: str, conversation_id: str) -> dict:
    with Session(engine) as session, session.begin():
        conversation = owned(
            session, user_id, conversation_id, lock=True
        )

        if conversation.active_task_id:
            raise ConversationBusy()

        session.delete(conversation)  # 外键级联删除关联消息与事件。

    return {"deleted": True}