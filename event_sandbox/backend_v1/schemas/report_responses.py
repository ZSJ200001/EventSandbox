"""报告生成响应模型"""

from pydantic import BaseModel, Field


class AgentSummary(BaseModel):
    """逐 Agent 行为小结"""

    agent_name: str
    summary: str


class GenerateReportResponse(BaseModel):
    """推演报告生成响应"""

    simulation_id: str
    title: str = "推演分析报告"
    agent_summaries: list[AgentSummary] = Field(default_factory=list)
    overall_summary: str = ""
    conclusion: str = ""
    full_report: str = ""


class ReportBundleResponse(BaseModel):
    """报告组合响应（推演报告 + 基线报告）"""

    report: GenerateReportResponse | None = None
    baseline_report: GenerateReportResponse | None = None
