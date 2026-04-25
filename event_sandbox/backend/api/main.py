import os
import sys

# Add parent directory to path for imports
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
    CompareReport,
)


# Global simulation engine
engine: SimulationEngine = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine
    # Initialize engine on startup
    engine = SimulationEngine()
    yield
    # Cleanup on shutdown
    engine = None


app = FastAPI(
    title="EventSandbox API",
    description="可干预的智能事件推演沙盘 API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    llm = get_llm_client()
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        llm_connected=llm.is_healthy(),
    )


@app.post("/api/simulations", response_model=CreateSimulationResponse)
async def create_simulation(request: CreateSimulationRequest):
    try:
        simulation = engine.create_simulation(
            name=request.name,
            description=request.description,
            event_text=request.event_text,
            config=request.config,
        )
        return CreateSimulationResponse(
            simulation=simulation,
            generated_agents=simulation.agents,
            topology=simulation.topology,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/simulations/{simulation_id}", response_model=SimulationStateResponse)
async def get_simulation(simulation_id: str):
    simulation = engine.get_simulation(simulation_id)
    if not simulation:
        raise HTTPException(status_code=404, detail="Simulation not found")

    # Get recent events
    recent_events = simulation.events[-10:] if len(simulation.events) > 10 else simulation.events

    # Get agent states
    agent_states = {}
    for agent in simulation.agents:
        agent_states[agent.id] = {
            "name": agent.name,
            "type": agent.type,
            "status": agent.status,
            "beliefs": [b.model_dump() for b in agent.beliefs],
            "position": {"x": agent.position_x, "y": agent.position_y} if agent.position_x else None,
        }

    return SimulationStateResponse(
        simulation=simulation,
        recent_events=recent_events,
        agent_states=agent_states,
    )


@app.post("/api/simulations/{simulation_id}/step", response_model=StepSimulationResponse)
async def step_simulation(simulation_id: str, request: StepSimulationRequest):
    try:
        simulation, new_events, updated_agents = engine.step(
            simulation_id=simulation_id,
            intervention=request.intervention,
        )
        return StepSimulationResponse(
            simulation=simulation,
            new_events=new_events,
            updated_agents=updated_agents,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/simulations/{simulation_id}/intervene", response_model=InterventionResponse)
async def intervene(simulation_id: str, request: InterventionRequest):
    try:
        intervention = request.intervention
        simulation, new_events, updated_agents = engine.step(
            simulation_id=simulation_id,
            intervention=intervention,
        )
        return InterventionResponse(
            success=True,
            message="Intervention applied successfully",
            updated_agents=updated_agents,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        return InterventionResponse(
            success=False,
            message=str(e),
            updated_agents=[],
        )


@app.get("/api/simulations/{simulation_id}/compare", response_model=CompareReport)
async def compare_scenarios(
    simulation_id: str,
    intervention_type: str,
    target: str = None,
    parameter: str = None,
    value: str = None,
):
    from models.entities import Intervention, InterventionType
    import ast

    # Parse value
    parsed_value = value
    if value:
        try:
            parsed_value = ast.literal_eval(value)
        except:
            parsed_value = value

    intervention = Intervention(
        id="temp",
        type=InterventionType(intervention_type),
        target=target,
        parameter=parameter,
        value=parsed_value,
        timestamp=0,
        round=0,
    )

    try:
        result = engine.compare_scenarios(simulation_id, intervention)
        return CompareReport(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/simulations/{simulation_id}")
async def delete_simulation(simulation_id: str):
    if simulation_id in engine.simulations:
        del engine.simulations[simulation_id]
        return {"message": "Simulation deleted"}
    raise HTTPException(status_code=404, detail="Simulation not found")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
