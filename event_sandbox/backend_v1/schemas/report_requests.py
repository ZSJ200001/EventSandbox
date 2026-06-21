"""报告生成请求模型"""

from pydantic import BaseModel


class GenerateReportRequest(BaseModel):
    """生成推演报告请求

    目前无需额外参数，报告内容完全从推演状态自动生成。
    未来可扩展：指定报告风格、聚焦特定 Agent、限定回合范围等。
    """

    pass
