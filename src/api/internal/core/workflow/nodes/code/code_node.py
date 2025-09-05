import ast
import time
from typing import Optional

from langchain_core.runnables import RunnableConfig

from internal.core.workflow.entities.node_entity import NodeResult, NodeStatus
from internal.core.workflow.entities.variable_entity import VARIABLE_TYPE_DEFAULT_VALUE_MAP
from internal.core.workflow.entities.workflow_entity import WorkflowState
from internal.core.workflow.nodes.base_node import BaseNode
from internal.core.workflow.utils.helper import extract_variables_from_state
from internal.exception import FailException
from .code_entity import CodeNodeData


class CodeNode(BaseNode):
    """py代码运行节点"""
    node_data: CodeNodeData

    def invoke_inner(self, state: WorkflowState, config: Optional[RunnableConfig] = None) -> WorkflowState:
        """执行py代码，执行的代码函数名必须为main，并且参数名为params，有且只有一个函数，不允许有额外的其他语句"""
        start_at = time.perf_counter()
        inputs_dict = extract_variables_from_state(self.node_data.inputs, state)

        # 2. todo: 执行py代码，后期需要单独迁移到水箱中或者指定的容器中运行，需与项目分离
        result = self._execute_function(self.node_data.code, params=inputs_dict)

        # 3.检测函数的返回值是否为字典
        if not isinstance(result, dict):
            raise FailException("main函数的返回值必须是一个字典")

        # 4.提取输出数据
        outputs_dict = {}
        outputs = self.node_data.outputs
        for output in outputs:
            # 5.提取输出数据(非严格校验)
            outputs_dict[output.name] = result.get(
                output.name,
                VARIABLE_TYPE_DEFAULT_VALUE_MAP.get(output.type),
            )

        # 6.构建状态数据并返回
        return {
            "node_results": [
                NodeResult(
                    node_data=self.node_data,
                    status=NodeStatus.SUCCEEDED,
                    inputs=inputs_dict,
                    outputs=outputs_dict,
                    latency=(time.perf_counter() - start_at),
                )
            ]
        }

    @classmethod
    def _execute_function(cls, code: str, *args, **kwargs):
        """执行py代码"""
        try:
            # 1. 解析代码
            tree = ast.parse(code)
            main_func = None
            for node in tree.body:
                if isinstance(node, ast.FunctionDef):
                    if node.name == "main":
                        if main_func:
                            raise FailException("代码中只能有一个main函数")
                        if len(node.args.args) != 1 or node.args.args[0].arg != "params":
                            raise FailException("main函数必须只有一个参数，且参数为params")
                        main_func = node
                    else:
                        raise FailException("代码中不能包含其他函数，只能有main函数")
                else:
                    raise FailException("代码中只能包含函数定义，不允许其他语句存在")

            if not main_func:
                raise FailException("代码中必须包含名为main的函数")

            local_vars = {}
            exec(code, {}, local_vars)

            if "main" in local_vars and callable(local_vars["main"]):
                return local_vars["main"](*args, **kwargs)
            else:
                raise FailException("main函数必须是一个可调用的函数")
        except:
            raise FailException("py代码执行出错")
