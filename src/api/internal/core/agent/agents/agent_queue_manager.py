import queue
import time
import uuid
from queue import Queue
from typing import Generator
from uuid import UUID

from redis import Redis

from internal.core.agent.entities.queue_entity import QueueEvent, AgentThought
from internal.entity.conversation_entity import InvokeFrom


class AgentQueueManager:
    """智能体队列管理器"""
    _queues: dict[str, Queue]
    user_id: UUID
    invoke_from: InvokeFrom
    redis_client: Redis

    def __init__(self,
                 user_id: UUID,
                 invoke_form: InvokeFrom
                 ):
        self._queues = {}
        self.user_id = user_id
        self.invoke_from = invoke_form
        from app.http.module import injector
        self.redis_client = injector.get(Redis)

    def listen(self, task_id: UUID) -> Generator:
        """监听队列返回的生成式数据"""
        # 1. 定义基础数据记录超时时间、开始时间、最后一次ping通时间
        listen_timeout = 600
        start_time = time.time()
        last_ping_time = 0

        # 2. 创建循环读取数据，直到超时或者数据读取完毕
        while True:
            try:
                # 3. 从队列中提取数据并检测数据是否存在，如果存在使用yield关键字返回
                item = self.queue(task_id).get(timeout=1)
                if item is None:
                    break
                yield item
            except queue.Empty:
                continue
            finally:
                # 4. 计算获取数据的总耗时
                elapsed_time = time.time() - start_time
                # 5. 每10秒发起一个ping请求
                if elapsed_time // 10 > last_ping_time:
                    self.publish(task_id, AgentThought(
                        id=uuid.uuid4(),
                        task_id=task_id,
                        event=QueueEvent.PING
                    ))
                    last_ping_time = elapsed_time // 10
                # 6. 判断总耗时是否超时，如果超时则往队列中添加超时事件
                if elapsed_time >= listen_timeout:
                    self.publish(task_id, AgentThought(
                        id=uuid.uuid4(),
                        task_id=task_id,
                        event=QueueEvent.TIMEOUT
                    ))

                # 7. 检测是否停止，如果已经停止则添加停止事件
                if self._is_stooped(task_id):
                    self.publish(task_id, AgentThought(
                        id=uuid.uuid4(),
                        task_id=task_id,
                        event=QueueEvent.STOP
                    ))

    def stop_listen(self, task_id: UUID) -> None:
        """停止监听队列信息"""
        self.queue(task_id).put(None)

    def publish(self, task_id: UUID, agent_queue_event: AgentThought) -> None:
        """发布事件信息到队列"""
        self.queue(task_id).put(agent_queue_event)

        if agent_queue_event.event in [QueueEvent.STOP, QueueEvent.ERROR, QueueEvent.TIMEOUT, QueueEvent.AGENT_END]:
            self.stop_listen(task_id)

    def publish_error(self, task_id: UUID, error) -> None:
        """发布错误信息到队列"""
        self.publish(task_id, AgentThought(
            id=uuid.uuid4(),
            task_id=task_id,
            event=QueueEvent.ERROR,
            observation=error
        ))

    def _is_stooped(self, task_id: UUID) -> bool:
        """检测任务是否停止"""
        task_stopped_cache_key = self.generate_task_stopped_cache_key(task_id)
        result = self.redis_client.get(task_stopped_cache_key)

        if result is not None:
            return True
        return False

    def queue(self, task_id: UUID) -> Queue:
        """根据任务Id，获取对应的任务队列信息"""
        q = self._queues.get(str(task_id))

        if not q:
            # 3.添加缓存键标识
            user_prefix = "account" if (self.invoke_from in
                                        [InvokeFrom.WEB_APP, InvokeFrom.DEBUGGER,
                                         InvokeFrom.ASSISTANT_AGENT]) else "end-user"

            # 4.设置任务对应的缓存键，代表这次任务已经开始了
            self.redis_client.setex(
                self.generate_task_belong_cache_key(task_id),
                1800,
                f"{user_prefix}-{str(self.user_id)}",
            )
            q = Queue()
            self._queues[str(task_id)] = q
        return q

    @classmethod
    def set_stop_flag(cls, task_id: UUID, invoke_from: InvokeFrom, user_id: UUID) -> None:
        """根据任务Id+调用来源停止某次会话"""
        from app.http.module import injector
        redis_client = injector.get(Redis)

        result = redis_client.get(cls.generate_task_belong_cache_key(task_id))
        if not result:
            return
        user_prefix = "account" if invoke_from in [InvokeFrom.WEB_APP, InvokeFrom.DEBUGGER] else "end-user"
        if result.decode("utf-8") != f"{user_prefix}-{str(user_id)}":
            return
        stopped_cache_key = cls.generate_task_stopped_cache_key(task_id)
        redis_client.setex(stopped_cache_key, 600, 1)

    @classmethod
    def generate_task_belong_cache_key(cls, task_id: UUID) -> str:
        """生成任务专属的缓存键"""
        return f"generate_task_belong:{str(task_id)}"

    @classmethod
    def generate_task_stopped_cache_key(cls, task_id: UUID) -> str:
        """生成任务已停止的缓存键"""
        return f"generate_task_stopped:{str(task_id)}"
