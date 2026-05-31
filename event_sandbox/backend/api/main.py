import os
import sys
import time
import ast

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from core import SimulationEngine, get_llm_client
from models import (
    CreateSimulationRequest,
    CreateSimulationResponse,
    StepSimulationRequest,
    StepSimulationResponse,
    InterventionRequest,
    InterventionResponse,
    SimulationStateResponse,
    HealthResponse,
    CompareScenariosRequest,
    CompareScenariosResponse,
    SimulationStateRequest,
    AgentDetailRequest,
    AgentDetailResponse,
    ModifyAgentRequest,
    ModifyAgentResponse,
    BatchStepRequest,
    BatchStepResponse,
    ListSimulationsRequest,
    ListSimulationsResponse,
    SimulationSummary,
    DeleteSimulationResponse,
    PauseSimulationRequest,
    PauseSimulationResponse,
    QuickInterventionRequest,
    QuickInterventionResponse,
    QuickInterventionOption,
    ErrorResponse,
)


# 全局仿真引擎
engine: SimulationEngine = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine
    engine = SimulationEngine()
    yield
    engine = None


app = FastAPI(
    title="EventSandbox API",
    description="可干预的智能事件推演沙盘 API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== 健康检查 ==============
@app.get("/health", response_model=HealthResponse)
async def health_check():
    llm = get_llm_client()
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        llm_connected=llm.is_healthy(),
        llm_model=llm.get_model_name(),
        simulation_count=len(engine.simulations) if engine else 0,
        timestamp=int(time.time() * 1000)
    )


# ============== 创建推演 ==============
@app.post("/api/simulations", response_model=CreateSimulationResponse)
async def create_simulation(request: CreateSimulationRequest):
    try:
        simulation = engine.create_simulation(
            name=request.name,
            description=request.description,
            event_text=request.event_text,
            config=request.config,
            rounds=request.rounds
        )
        return CreateSimulationResponse(
            simulation=simulation,
            generated_agents=simulation.agents,
            topology=simulation.topology,
            message="推演场景创建成功"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== 批量创建（快速模板） ==============
@app.get("/api/templates")
async def list_templates():
    """列出预设的推演模板"""
    return {
        "templates": [
            {
                "key": "milk_tea_price_increase",
                "name": "奶茶涨价事件",
                "description": "分析奶茶品牌涨价后的市场连锁反应",
                "default_event": "XX奶茶招牌产品涨价3元，引发市场连锁反应"
            },
            {
                "key": "tech_company_layoff",
                "name": "科技公司裁员",
                "description": "大型互联网公司宣布裁员的影响",
                "default_event": "某大型互联网公司宣布裁员10%，引发股价下跌和员工不满"
            },
            {
                "key": "competitor_product_launch",
                "name": "竞品发布新品",
                "description": "竞争对手推出革命性产品的应对策略",
                "default_event": "华为发布新款MatePhone，苹果公司紧急召开会议讨论应对策略"
            },
            {
                "key": "government_regulation",
                "name": "政府监管介入",
                "description": "监管部门出台新政策对行业的影响",
                "default_event": "监管部门宣布将加强对互联网平台的监管，多家科技公司股价承压"
            }
        ]
    }


# ============== 获取推演详情 ==============
@app.get("/api/simulations/{simulation_id}", response_model=SimulationStateResponse)
async def get_simulation(simulation_id: str):
    simulation = engine.get_simulation(simulation_id)
    if not simulation:
        raise HTTPException(status_code=404, detail="推演不存在")

    # 获取最近事件
    recent_events = simulation.events[-20:] if len(simulation.events) > 20 else simulation.events

    # 获取 Agent 摘要
    agent_summaries = []
    for agent in simulation.agents:
        sentiment = 0
        sentiment_belief = agent.get_belief("sentiment")
        if sentiment_belief:
            sentiment = float(sentiment_belief.value)

        agent_summaries.append({
            "id": agent.id,
            "name": agent.name,
            "type": agent.type,
            "status": agent.status,
            "sentiment": sentiment,
            "goals_count": len(agent.goals),
            "relationship_count": len(agent.relationships)
        })

    return SimulationStateResponse(
        simulation=simulation,
        active_agent_count=len(simulation.get_active_agents()),
        event_count=len(simulation.events),
        recent_events=recent_events,
        agent_summaries=agent_summaries
    )


# ============== 获取 Agent 详情 ==============
@app.get("/api/simulations/{simulation_id}/agents/{agent_id}", response_model=AgentDetailResponse)
async def get_agent_detail(simulation_id: str, agent_id: str):
    result = engine.get_agent_detail(simulation_id, agent_id)
    if not result:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    return AgentDetailResponse(**result)


# ============== 修改 Agent 状态 ==============
@app.post("/api/simulations/{simulation_id}/agents/{agent_id}/modify", response_model=ModifyAgentResponse)
async def modify_agent(simulation_id: str, agent_id: str, request: ModifyAgentRequest):
    simulation = engine.get_simulation(simulation_id)
    if not simulation:
        raise HTTPException(status_code=404, detail="推演不存在")

    agent = simulation.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 不存在")

    try:
        # 根据字段修改
        if request.field == "status":
            from models.entities import AgentStatus
            agent.status = AgentStatus(request.value)
        elif request.field == "sentiment":
            agent.update_belief("sentiment", float(request.value), confidence=1.0, source="api_modify")
        elif request.field == "goal":
            agent.goals.append(str(request.value))
        elif request.field == "belief":
            if isinstance(request.value, dict):
                agent.update_belief(
                    request.value.get("key", "custom"),
                    request.value.get("value", ""),
                    confidence=0.9,
                    source="api_modify"
                )
        else:
            # 通用属性设置
            setattr(agent, request.field, request.value)

        return ModifyAgentResponse(
            success=True,
            agent=agent,
            message=f"成功修改 {request.field}"
        )
    except Exception as e:
        return ModifyAgentResponse(
            success=False,
            agent=agent,
            message=str(e)
        )


# ============== 执行推进一步 ==============
@app.post("/api/simulations/{simulation_id}/step", response_model=StepSimulationResponse)
async def step_simulation(simulation_id: str, request: StepSimulationRequest):
    try:
        simulation, new_events, updated_agents, action_results = engine.step(
            simulation_id=simulation_id,
            intervention=request.intervention,
        )

        # 生成回合摘要
        round_summary = f"第 {simulation.current_round} 回合完成"
        if new_events:
            round_summary += f"，产生 {len(new_events)} 个事件"

        return StepSimulationResponse(
            simulation=simulation,
            new_events=new_events,
            updated_agents=updated_agents,
            action_results=action_results,
            round_summary=round_summary
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== 批量执行 ==============
@app.post("/api/simulations/{simulation_id}/batch-step", response_model=BatchStepResponse)
async def batch_step(simulation_id: str, request: BatchStepRequest):
    try:
        simulation, steps_executed, events, stop_reason = engine.batch_step(
            simulation_id=simulation_id,
            steps=request.steps,
            stop_on_condition=request.stop_on_condition,
            sentiment_threshold=request.sentiment_threshold,
            conflict_threshold=request.conflict_threshold
        )

        return BatchStepResponse(
            simulation=simulation,
            steps_executed=steps_executed,
            events_generated=events,
            final_metrics=simulation.metrics,
            stop_reason=stop_reason
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== 干预推演 ==============
@app.post("/api/simulations/{simulation_id}/intervene", response_model=InterventionResponse)
async def intervene(simulation_id: str, request: InterventionRequest):
    try:
        intervention = request.intervention
        simulation, new_events, updated_agents, _ = engine.step(
            simulation_id=simulation_id,
            intervention=intervention,
        )

        return InterventionResponse(
            success=True,
            message="干预已成功应用",
            intervention_id=intervention.id,
            affected_agents=[a.id for a in updated_agents],
            predicted_effects={}
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        return InterventionResponse(
            success=False,
            message=str(e),
            intervention_id=request.intervention.id,
            affected_agents=[],
            predicted_effects={}
        )


# ============== 快速干预 ==============
@app.get("/api/interventions/options")
async def get_intervention_options():
    """获取快速干预选项"""
    return {
        "event_options": [
            QuickInterventionOption(key="regulatory_warning", label="监管约谈", description="监管部门约谈企业负责人", icon="👮"),
            QuickInterventionOption(key="competitor_price_cut", label="竞品降价", description="主要竞争对手宣布大幅降价", icon="💰"),
            QuickInterventionOption(key="negative_news", label="负面新闻", description="媒体曝光企业负面信息", icon="📰"),
            QuickInterventionOption(key="promotion", label="促销活动", description="启动大规模促销活动", icon="🎁"),
            QuickInterventionOption(key="policy_change", label="政策变化", description="政府出台新的政策法规", icon="📜"),
            QuickInterventionOption(key="market_boom", label="市场繁荣", description="整体市场环境变好", icon="📈"),
        ],
        "agent_options": [
            QuickInterventionOption(key="positive_mood", label="积极情绪", description="调整 Agent 情绪为积极状态", icon="😊"),
            QuickInterventionOption(key="negative_mood", label="消极情绪", description="调整 Agent 情绪为消极状态", icon="😞"),
            QuickInterventionOption(key="inject_info", label="注入信息", description="向 Agent 注入新信息或情报", icon="💬"),
            QuickInterventionOption(key="add_goal", label="添加目标", description="为 Agent 添加新目标", icon="🎯"),
        ],
        "env_options": [
            QuickInterventionOption(key="market_bad", label="市场情绪差", description="整体市场情绪变差", icon="📉"),
            QuickInterventionOption(key="economy_down", label="经济恶化", description="宏观经济环境变差", icon="🏭"),
            QuickInterventionOption(key="confidence_low", label="信心下降", description="消费者信心下降", icon="💸"),
            QuickInterventionOption(key="regulation_tight", label="政策收紧", description="行业监管政策收紧", icon="🔒"),
        ]
    }


@app.post("/api/interventions/quick", response_model=InterventionResponse)
async def quick_intervene(request: QuickInterventionRequest):
    """快速干预接口"""
    from models.entities import Intervention, InterventionType

    # 构建干预
    intervention_type_map = {
        "event": InterventionType.EXTERNAL_EVENT,
        "agent": InterventionType.AGENT_STATE,
        "env": InterventionType.GLOBAL_PARAM,
    }

    intervention_type = intervention_type_map.get(request.intervention_type, InterventionType.EXTERNAL_EVENT)

    # 值映射
    event_values = {
        "regulatory_warning": "【突发事件】监管部门约谈企业负责人，要求解释近期市场行为",
        "competitor_price_cut": "【突发事件】竞争对手宣布降价15%，市场格局生变",
        "negative_news": "【突发事件】媒体曝光企业产品存在质量问题，舆论哗然",
        "promotion": "【突发事件】企业启动全品促销，活动力度空前",
        "policy_change": "【政策变化】政府出台新法规，对行业产生重大影响",
        "market_boom": "【市场变化】整体市场繁荣期到来，消费者购买力增强",
    }

    value = request.custom_value or event_values.get(request.quick_option, "干预事件")

    intervention = Intervention(
        id=f"quick_{int(time.time() * 1000)}",
        type=intervention_type,
        target=request.target_agent_id,
        parameter="belief",
        value=value,
        timestamp=int(time.time() * 1000),
        round=0
    )

    try:
        simulation, new_events, updated_agents, _ = engine.step(
            simulation_id=request.simulation_id,
            intervention=intervention
        )

        return InterventionResponse(
            success=True,
            message=f"快速{request.intervention_type}干预已应用",
            intervention_id=intervention.id,
            affected_agents=[a.id for a in updated_agents],
            predicted_effects={}
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        return InterventionResponse(
            success=False,
            message=str(e),
            intervention_id=intervention.id,
            affected_agents=[],
            predicted_effects={}
        )


# ============== 场景对比 ==============
@app.post("/api/simulations/{simulation_id}/compare", response_model=CompareScenariosResponse)
async def compare_scenarios(simulation_id: str, request: CompareScenariosRequest):
    try:
        result = engine.compare_scenarios(
            simulation_id=simulation_id,
            intervention=request.intervention,
            steps=request.steps
        )

        return CompareScenariosResponse(
            simulation_id=result["simulation_id"],
            baseline_metrics=result["baseline_metrics"],
            with_intervention_metrics=result["with_intervention_metrics"],
            metric_deltas=result["metric_deltas"],
            metric_percentage_changes=result["metric_percentage_changes"],
            timeline_comparison=result["timeline_comparison"],
            key_insights=result["key_insights"],
            conclusion=result["conclusion"]
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== 场景对比（旧接口，保持兼容）==============
@app.get("/api/simulations/{simulation_id}/compare", response_model=CompareScenariosResponse)
async def compare_scenarios_simple(
    simulation_id: str,
    intervention_type: str,
    target: str = None,
    parameter: str = None,
    value: str = None,
):
    from models.entities import Intervention, InterventionType

    parsed_value = value
    if value:
        try:
            parsed_value = ast.literal_eval(value)
        except:
            parsed_value = value

    intervention = Intervention(
        id="compare_temp",
        type=InterventionType(intervention_type),
        target=target,
        parameter=parameter,
        value=parsed_value,
        timestamp=0,
        round=0
    )

    try:
        result = engine.compare_scenarios(simulation_id, intervention, steps=3)
        return CompareScenariosResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============== 暂停/恢复 ==============
@app.post("/api/simulations/{simulation_id}/pause", response_model=PauseSimulationResponse)
async def pause_simulation(simulation_id: str):
    try:
        simulation = engine.pause_simulation(simulation_id)
        return PauseSimulationResponse(
            success=True,
            simulation=simulation,
            message="推演已暂停"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/simulations/{simulation_id}/resume", response_model=PauseSimulationResponse)
async def resume_simulation(simulation_id: str):
    try:
        simulation = engine.resume_simulation(simulation_id)
        return PauseSimulationResponse(
            success=True,
            simulation=simulation,
            message="推演已恢复"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============== 删除推演 ==============
@app.delete("/api/simulations/{simulation_id}", response_model=DeleteSimulationResponse)
async def delete_simulation(simulation_id: str):
    if engine.delete_simulation(simulation_id):
        return DeleteSimulationResponse(
            success=True,
            message="推演已删除"
        )
    raise HTTPException(status_code=404, detail="推演不存在")


# ============== 列出推演 ==============
@app.get("/api/simulations", response_model=ListSimulationsResponse)
async def list_simulations(
    status: str = None,
    limit: int = 20,
    offset: int = 0
):
    from models.entities import SimulationStatus

    filter_status = SimulationStatus(status) if status else None
    simulations = engine.list_simulations(status=filter_status)

    summaries = [
        SimulationSummary(
            id=s.id,
            name=s.name,
            description=s.description,
            status=s.status,
            current_round=s.current_round,
            rounds=s.rounds,
            agent_count=len(s.agents),
            event_count=len(s.events)
        )
        for s in simulations
    ]

    return ListSimulationsResponse(
        simulations=summaries[offset:offset+limit],
        total=len(summaries),
        limit=limit,
        offset=offset
    )


# ============== 获取指标历史 ==============
@app.get("/api/simulations/{simulation_id}/metrics-history")
async def get_metrics_history(simulation_id: str):
    """获取指标历史数据"""
    simulation = engine.get_simulation(simulation_id)
    if not simulation:
        raise HTTPException(status_code=404, detail="推演不存在")

    # 从事件中提取历史指标
    history = []
    for event in simulation.events:
        if event.round > 0:
            # 这里应该存储历史指标，但目前是动态计算的
            pass

    return {
        "simulation_id": simulation_id,
        "current_metrics": simulation.metrics.model_dump(),
        "current_round": simulation.current_round,
        "total_events": len(simulation.events)
    }


# ============== 获取事件详情 ==============
@app.get("/api/simulations/{simulation_id}/events/{event_id}")
async def get_event_detail(simulation_id: str, event_id: str):
    """获取事件详情"""
    simulation = engine.get_simulation(simulation_id)
    if not simulation:
        raise HTTPException(status_code=404, detail="推演不存在")

    event = next((e for e in simulation.events if e.id == event_id), None)
    if not event:
        raise HTTPException(status_code=404, detail="事件不存在")

    # 获取涉及的 Agent 详情
    involved_agents = []
    for agent_id in event.involved_agents:
        agent = simulation.get_agent(agent_id)
        if agent:
            involved_agents.append(agent)

    return {
        "event": event,
        "involved_agents": involved_agents,
        "impact_analysis": {
            "affected_count": len(event.impact.affected_agents),
            "sentiment_changes": event.impact.sentiment_change,
            "cascade_effects": event.impact.cascade_effects
        }
    }


# ============== 获取行动历史 ==============
@app.get("/api/simulations/{simulation_id}/agents/{agent_id}/actions")
async def get_agent_actions(simulation_id: str, agent_id: str):
    """获取 Agent 的行动历史"""
    simulation = engine.get_simulation(simulation_id)
    if not simulation:
        raise HTTPException(status_code=404, detail="推演不存在")

    agent = simulation.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 不存在")

    actions = []
    for event in simulation.events:
        if agent.id in event.involved_agents and event.type in ["action", "reaction"]:
            actions.append({
                "round": event.round,
                "type": event.type,
                "action": event.action_taken,
                "description": event.description,
                "result": event.action_result,
                "impact": event.impact.model_dump() if event.impact else {}
            })

    return {
        "agent_id": agent_id,
        "agent_name": agent.name,
        "total_actions": len(actions),
        "actions": actions[-20:]  # 最近20条
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
