import json
import json
import logging
import re
import time
import uuid
from typing import Literal

from langchain_core.messages import ToolMessage, SystemMessage, HumanMessage, RemoveMessage, \
    messages_to_dict, AIMessage
from langgraph.constants import END
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph

from internal.core.agent.entities.agnet_entity import AgentState, AGENT_SYSTEM_PROMPT_TEMPLATE, MAX_ITERATION_RESPONSE, \
    DATASET_RETRIEVAL_TOOL_NAME
from internal.core.agent.entities.queue_entity import QueueEvent, AgentThought
from internal.exception import FailException
from internal.lib.helper import convert_model_to_dict
from .base_angent import BaseAgent
from ...language_model.entities.model_entity import ModelFeature
from ...workflow import Workflow


class FunctionCallAgent(BaseAgent):
    """基于函数/工具调用的智能体"""

    def _build_agent(self) -> CompiledStateGraph:
        """构建langGraph图结构编译程序"""
        graph = StateGraph(AgentState)

        graph.add_node("preset_operation", self._preset_operation_node)
        graph.add_node("long_term_memory_recall", self._long_term_memory_recall_node)
        graph.add_node("llm", self._llm_node)
        graph.add_node("tools", self._tools_node)

        # 3. 添加边
        graph.set_entry_point("preset_operation")
        graph.add_conditional_edges("preset_operation", self._preset_operation_condition)
        graph.add_edge("long_term_memory_recall", "llm")
        graph.add_conditional_edges("llm", self._tool_condition)
        graph.add_edge("tools", "llm")

        agent = graph.compile()

        return agent

    def _preset_operation_node(self, state: AgentState) -> AgentState:
        """预设操作，包含：输入审核，数据预处理，条件边等"""
        # 1. 获取审核配置
        review_config = self.agent_config.review_config
        query = state["messages"][-1].content

        # 2. 检测是否开启审核配置
        if review_config["enable"] and review_config["inputs_config"]["enable"]:
            contains_keyword = any(keyword in query for keyword in review_config["keywords"])
            # 3. 如果包含敏感词则执行后续步骤
            if contains_keyword:
                preset_response = review_config["inputs_config"]["preset_response"]
                self.agent_queue_manager.publish(state["task_id"], AgentThought(
                    id=uuid.uuid4(),
                    task_id=state["task_id"],
                    event=QueueEvent.AGENT_MESSAGE,
                    thought=preset_response,
                    message=messages_to_dict(state["messages"]),
                    answer=preset_response,
                    latency=0
                ))
                self.agent_queue_manager.publish(state["task_id"], AgentThought(
                    id=uuid.uuid4(),
                    task_id=state["task_id"],
                    event=QueueEvent.AGENT_END
                ))
            return {"messages": [AIMessage(preset_response)]}
        return {"messages": []}

    def _long_term_memory_recall_node(self, state: AgentState) -> AgentState:
        """长期记忆召回节点"""

        # 1. 判断智能体是否需要召回长期记忆
        long_term_memory = ""
        if self.agent_config.enable_long_term_memory:
            long_term_memory = state["long_term_memory"]
            self.agent_queue_manager.publish(state["task_id"], AgentThought(
                id=uuid.uuid4(),
                task_id=state["task_id"],
                event=QueueEvent.LONG_TERM_MEMORY_RECALL,
                observation=long_term_memory
            ))

        # 2. 构建预设消息列表，并针preset_prompt+long_term_memory填充到系统消息中
        preset_messages = [
            SystemMessage(AGENT_SYSTEM_PROMPT_TEMPLATE.format(
                preset_prompt=self.agent_config.preset_prompt,
                long_term_memory=long_term_memory
            ))
        ]
        # 3. 将短期历史消息添加到消息列表中
        history = state["history"]
        if isinstance(history, list) and len(history) > 0:
            # 4. 检验历史消息是不是复数，也就是[人类，AI，人类，AI.....]
            if len(history) % 2 != 0:
                self.agent_queue_manager.publish_error(state["task_id"], "智能体历史消息列表格式错误")
                logging.exception(
                    f"智能体历史消息列表格式错误，len(history)={len(history)}, history={json.dumps(messages_to_dict(history))}"
                )
                raise FailException("智能体历史消息列表格式错误")
            # 5. 拼接历史消息
            preset_messages.extend(history)
        # 6. 拼接当前用户的提问消息
        human_message = state["messages"][-1]
        preset_messages.append(HumanMessage(human_message.content))

        # 7. 处理预设消息，将预设消息添加到用户消息前面，先去删除用户的原始消息，然后补充一个新的代替
        return {
            "messages": [RemoveMessage(id=human_message.id), *preset_messages]
        }

    def _llm_node(self, state: AgentState) -> AgentState:
        """大语言模型节点"""
        # 1. 检测当前Agent迭代次数是否符合需求
        if state["iteration_count"] > self.agent_config.max_iteration_count:
            self.agent_queue_manager.publish(
                state["task_id"],
                AgentThought(
                    id=uuid.uuid4(),
                    task_id=state["task_id"],
                    event=QueueEvent.AGENT_MESSAGE,
                    thought=messages_to_dict(state["messages"]),
                    answer=MAX_ITERATION_RESPONSE,
                    latency=0
                ))
            self.agent_queue_manager.publish(
                state["task_id"],
                AgentThought(
                    id=uuid.uuid4(),
                    task_id=state["task_id"],
                    event=QueueEvent.AGENT_END
                )
            )
            return {"messages": [AIMessage(MAX_ITERATION_RESPONSE)]}

        llm = self.llm
        id = uuid.uuid4()
        start_at = time.perf_counter()

        # 2. 检测LLM实例是否有bind_tools方法，如果没有则不绑定，tools为空也不绑定
        if (ModelFeature.TOOL_CALL in llm.features
                and hasattr(llm, "bind_tools")
                and callable(getattr(llm, "bind_tools"))
                and len(self.agent_config.tools) > 0
        ):
            llm = llm.bind_tools(self.agent_config.tools)

        # 3. 流式调用LLM输出对应内容
        gathered = None
        is_first_chunk = True
        generation_type = ""
        try:
            for chunk in llm.stream(state["messages"]):
                if is_first_chunk:
                    gathered = chunk
                    is_first_chunk = False
                else:
                    gathered += chunk
                # 4. 检测生成类型是工具参数还是文本生成
                if not generation_type:
                    if chunk.tool_calls:
                        generation_type = "thought"
                    elif chunk.content:
                        generation_type = "message"
                    elif chunk.additional_kwargs and chunk.additional_kwargs['reasoning_content']:
                        # modify: 2025-04-29 sam 增加思考过程
                        generation_type = "think"
                elif generation_type == "think" and chunk.content:
                    # modify: 2025-04-29 sam 兼容带think过程的模型 think => message
                    generation_type = "message"
                    start_at = time.perf_counter()
                    id = uuid.uuid4()
                elif generation_type == "think" and chunk.tool_calls:
                    # modify: 2025-04-29 sam 兼容带think过程的模型 think => tool_calls
                    generation_type = "thought"
                    start_at = time.perf_counter()
                    id = uuid.uuid4()
                elif generation_type == "message" and chunk.tool_calls:
                    # modify: 2025-07-03 sam 兼容带message过程的模型 message => tool_calls
                    generation_type = "thought"
                    start_at = time.perf_counter()
                    id = uuid.uuid4()

                # 5. 如果生成的是消息则提交智能体消息事件
                if generation_type == "message" or generation_type == "think":
                    # 7. 提取片段内容并检测是否开启输出审核
                    review_config = self.agent_config.review_config
                    content = chunk.additional_kwargs[
                        'reasoning_content'] if generation_type == 'think' else chunk.content

                    if review_config["enable"] and review_config["outputs_config"]["enable"]:
                        for keyword in review_config["keywords"]:
                            content = re.sub(re.escape(keyword), "**", content, flags=re.IGNORECASE)

                    self.agent_queue_manager.publish(state["task_id"], AgentThought(
                        id=id,
                        task_id=state["task_id"],
                        # modify: 2025-04-29 sam 增加agent_think部分
                        event=QueueEvent.AGENT_THINK if generation_type == "think" else QueueEvent.AGENT_MESSAGE,
                        thought=content,
                        message=messages_to_dict(state["messages"]),
                        answer="" if generation_type == "think" else content,
                        latency=(time.perf_counter() - start_at)
                    ))
        except Exception as e:
            logging.exception(f"LLM节点发生错误，错误信息：{str(e)}")
            self.agent_queue_manager.publish_error(state["task_id"], f"LLM节点发生错误，错误信息：{str(e)}")
            raise e

        # 计算LLM的输入、输出的Token总数、价格和单位、总成本
        input_token_count = self.llm.get_num_tokens_from_messages(state["messages"])
        output_token_count = self.llm.get_num_tokens_from_messages([gathered])

        input_price, output_price, unit = self.llm.get_pricing()

        total_token_count = input_token_count + output_token_count
        total_price = (input_token_count * input_price + output_token_count * output_price) * unit
        # 6. 如果是推理则添加智能体推理事件
        if generation_type == "thought":
            self.agent_queue_manager.publish(state["task_id"], AgentThought(
                id=id,
                task_id=state["task_id"],
                event=QueueEvent.AGENT_THOUGHT,
                thought=json.dumps(gathered.tool_calls),
                # 消息相关
                message=messages_to_dict(state["messages"]),
                message_token_count=input_token_count,
                message_unit_price=input_price,
                message_price_unit=unit,
                # 答案相关
                answer="",
                answer_token_count=output_token_count,
                answer_unit_price=output_price,
                answer_price_unit=unit,
                # 推理相关
                total_token_count=total_token_count,
                total_price=total_price,
                latency=(time.perf_counter() - start_at),
            ))
        elif generation_type == "message":
            # 7.如果LLM直接生成answer则表示已经拿到了最终答案，推送一条空内容用于计算总token+总成本，并停止监听
            self.agent_queue_manager.publish(state["task_id"], AgentThought(
                id=id,
                task_id=state["task_id"],
                event=QueueEvent.AGENT_MESSAGE,
                thought="",
                # 消息相关字段
                message=messages_to_dict(state["messages"]),
                message_token_count=input_token_count,
                message_unit_price=input_price,
                message_price_unit=unit,
                # 答案相关字段
                answer="",
                answer_token_count=output_token_count,
                answer_unit_price=output_price,
                answer_price_unit=unit,
                # Agent推理统计相关
                total_token_count=total_token_count,
                total_price=total_price,
                latency=(time.perf_counter() - start_at),
            ))
            self.agent_queue_manager.publish(
                state["task_id"],
                AgentThought(
                    id=uuid.uuid4(),
                    task_id=state["task_id"],
                    event=QueueEvent.AGENT_END
                )
            )
        return {"messages": [gathered], "iteration_count": state["iteration_count"] + 1}

    async def _tools_node(self, state: AgentState) -> AgentState:
        """工具执行节点"""
        tools_by_name = {tool.name: tool for tool in self.agent_config.tools}

        # 2. 提取消息中的工具调用参数
        tool_calls = state["messages"][-1].tool_calls

        # 3. 循环执行工具组装工具消息
        messages = []
        for tool_call in tool_calls:
            id = uuid.uuid4()
            start_at = time.perf_counter()

            try:
                tool = tools_by_name[tool_call["name"]]
                # 2025-07-14 sam 特殊处理工作流工具节点
                if isinstance(tool, Workflow):
                    """workflow 采用流式请求，输出处理过程"""
                    last_chunk = ''
                    async for chunk in tool.astream(tool_call["args"]):
                        chunk_value = list(chunk.values())[0]
                        latency = chunk_value.get('node_results')[0].latency
                        chunk_dic = {
                            "value": convert_model_to_dict(chunk_value),
                            "wf_cn_name": tool.get_workflow_config().cn_name
                        }
                        self.agent_queue_manager.publish(state["task_id"], AgentThought(
                            id=uuid.uuid4(),
                            task_id=state["task_id"],
                            event=QueueEvent.WORKFLOW_NODE_MESSAGE,
                            observation=json.dumps(chunk_dic),
                            tool=tool_call["name"],
                            tool_input=tool_call["args"],
                            latency=latency
                        ))
                        last_chunk = chunk
                    last_chunk_value = list(last_chunk.values())[0]
                    tool_result = last_chunk_value.get("outputs", {})
                else:
                    # modify: 2025-04-27 sam 增加兼容异步invoke的能力
                    if hasattr(tool, "ainvoke"):
                        tool_result = await tool.ainvoke(tool_call["args"])
                    else:
                        tool_result = tool.invoke(tool_call["args"])
            except Exception as e:
                tool_result = f"工具执行出错：{str(e)}"

            messages.append(ToolMessage(
                tool_call_id=tool_call["id"],
                content=json.dumps(tool_result),
                name=tool_call["name"]
            ))

            event = (
                QueueEvent.AGENT_ACTION
                if tool_call["name"] != DATASET_RETRIEVAL_TOOL_NAME
                else QueueEvent.DATASET_RETRIEVAL
            )

            self.agent_queue_manager.publish(state["task_id"], AgentThought(
                id=id,
                task_id=state["task_id"],
                event=event,
                observation=json.dumps(tool_result),
                tool=tool_call["name"],
                tool_input=tool_call["args"],
                latency=(time.perf_counter() - start_at)
            ))

        return {"messages": messages}

    @classmethod
    def _tool_condition(cls, state: AgentState) -> Literal["tools", "__end__"]:
        """检测下一节点是执行tools节点，不审直接结束"""
        messages = state["messages"]
        ai_message = messages[-1]

        if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:
            return "tools"
        return END

    @classmethod
    def _preset_operation_condition(cls, state: AgentState) -> Literal["long_term_memory_recall", "__end__"]:
        """条件判断，是否触发预设响应"""
        message = state["messages"][-1]
        if message.type == "ai":
            return END
        return "long_term_memory_recall"
