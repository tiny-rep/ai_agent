export const apiPrefix:string = import.meta.env.VITE_API_PREFIX

//业务状态码
export const httpCode = {
  success: 'success',
  fail: 'fail',
  notFound: 'notFound',
  unauthorized: 'unauthorized',
  forbidden: 'forbidden',
  validateError: 'validate_error'
}

//类型与字符串的映射
export const typeMap: {[key:string]:string} = {
  str: "字符串",
  int: "整型",
  float: "浮点型",
  bool: "布尔型"
}

// 智能体事件类型
export const QueueEvent = {
  longTermMemoryRecall: 'long_term_memory_recall',
  agentThought: 'agent_thought',
  agentMessage: 'agent_message',
  agentAction: 'agent_action',
  datasetRetrieval: 'dataset_retrieval',
  agentEnd: 'agent_ent',
  stop: 'stop',
  error: 'error',
  timeout: 'timeout',
  ping: 'ping',
  agentThink: 'agent_think',
  workflowNodeMessage: 'workflow_node_message'
}