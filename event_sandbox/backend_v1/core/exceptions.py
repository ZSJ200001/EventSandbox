"""业务异常体系。

所有业务异常统一继承 EventSandboxError，携带可读的 code 与 message，
由 FastAPI 全局异常处理器转换为标准 HTTP 响应。
"""


class EventSandboxError(Exception):
    """业务异常基类"""

    def __init__(self, message: str = "业务错误", code: str = "BUSINESS_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class SimulationNotFoundError(EventSandboxError):
    """推演不存在"""

    def __init__(self, simulation_id: str):
        super().__init__(
            message=f"推演不存在: {simulation_id}",
            code="SIMULATION_NOT_FOUND",
        )


class AgentNotFoundError(EventSandboxError):
    """Agent 不存在"""

    def __init__(self, agent_id: str):
        super().__init__(
            message=f"Agent 不存在: {agent_id}",
            code="AGENT_NOT_FOUND",
        )


class StepLockedError(EventSandboxError):
    """推演正在进行中，无法并发执行 step"""

    def __init__(self, simulation_id: str):
        super().__init__(
            message=f"推演 {simulation_id} 正在进行中，请稍后再试",
            code="STEP_LOCKED",
        )


class SimulationPausedError(EventSandboxError):
    """推演已暂停"""

    def __init__(self, simulation_id: str):
        super().__init__(
            message=f"推演 {simulation_id} 已暂停，请先恢复后再执行",
            code="SIMULATION_PAUSED",
        )


class SimulationCompletedError(EventSandboxError):
    """推演已结束"""

    def __init__(self, simulation_id: str):
        super().__init__(
            message=f"推演 {simulation_id} 已结束",
            code="SIMULATION_COMPLETED",
        )


class LLMError(EventSandboxError):
    """LLM 调用失败（含重试耗尽）"""

    def __init__(self, message: str = "LLM 调用失败"):
        super().__init__(message=message, code="LLM_ERROR")


class ValidationError(EventSandboxError):
    """参数校验失败"""

    def __init__(self, message: str = "参数校验失败"):
        super().__init__(message=message, code="VALIDATION_ERROR")


class EventParseError(EventSandboxError):
    """事件解析失败"""

    def __init__(self, message: str = "事件解析失败"):
        super().__init__(message=message, code="EVENT_PARSE_ERROR")
