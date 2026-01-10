"""
Research Team Scenario - Multi-disciplinary research collaboration.

This example demonstrates coordinating a research team with:
- Data Scientists: ML/AI analysis
- Domain Experts: Subject matter expertise
- Analysts: Statistical analysis
- Reviewers: Quality control and validation
"""

import asyncio
import random
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from agent_coordinator import (
    AgentCoordinator,
    AgentRole,
    Task,
    TaskPriority,
    create_task,
    AgentMessage,
    MessageType,
)


class ResearchStage(str, Enum):
    """Stages of a research study."""
    HYPOTHESIS = "hypothesis"
    DATA_COLLECTION = "data_collection"
    ANALYSIS = "analysis"
    REVIEW = "review"
    VALIDATION = "validation"
    COMPLETE = "complete"


@dataclass
class ResearchHypothesis:
    """A research hypothesis to be tested."""
    statement: str
    field: str
    methodology: str = "experimental"
    variables: List[str] = field(default_factory=list)
    expected_outcome: str = ""


@dataclass
class ResearchStudy:
    """A research study being conducted."""
    id: str
    name: str
    hypothesis: ResearchHypothesis
    stage: ResearchStage = ResearchStage.HYPOTHESIS
    data: Dict[str, Any] = field(default_factory=dict)
    findings: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    @property
    def duration_days(self) -> Optional[float]:
        if self.completed_at:
            return (self.completed_at - self.created_at).total_seconds() / 86400
        return (datetime.now() - self.created_at).total_seconds() / 86400


@dataclass
class ResearchResult:
    """Results from a research task."""
    task_id: str
    researcher: str
    stage: ResearchStage
    findings: str
    confidence: float
    data: Dict[str, Any] = field(default_factory=dict)


class ResearchTeam:
    """
    Research team coordination scenario.

    Coordinates multi-disciplinary research projects.
    """

    def __init__(self):
        self.coordinator = None
        self.researchers: Dict[str, dict] = {}
        self.studies: Dict[str, ResearchStudy] = {}
        self.study_counter = 0
        self.metrics = {
            "total_studies": 0,
            "completed_studies": 0,
            "total_findings": 0,
        }

    async def setup(self) -> AgentCoordinator:
        """Set up the research team."""
        from agent_coordinator import create_coordinator

        self.coordinator = create_coordinator(name="research-lab")
        await self.coordinator.start()

        # Define research roles
        roles = [
            AgentRole(
                name="data_scientist",
                capabilities=["ml", "statistics", "data_analysis", "modeling"],
                max_concurrent_tasks=2,
            ),
            AgentRole(
                name="domain_expert",
                capabilities=["subject_matter", "literature_review", "theory", "validation"],
                max_concurrent_tasks=3,
            ),
            AgentRole(
                name="analyst",
                capabilities=["statistics", "visualization", "reporting", "presentation"],
                max_concurrent_tasks=2,
            ),
            AgentRole(
                name="reviewer",
                capabilities=["peer_review", "quality_control", "validation", "ethics"],
                max_concurrent_tasks=2,
            ),
        ]

        for role in roles:
            await self.coordinator.register_role(role)

        # Create researchers
        researchers = [
            ("alice", "data_scientist", ["ml", "modeling"]),
            ("bob", "data_scientist", ["statistics", "data_analysis"]),
            ("carol", "domain_expert", ["biology", "subject_matter"]),
            ("david", "domain_expert", ["chemistry", "theory"]),
            ("eve", "analyst", ["visualization", "reporting"]),
            ("frank", "reviewer", ["peer_review", "quality_control"]),
        ]

        for name, role, specialties in researchers:
            await self._add_researcher(name, role, specialties)

        print("\n🔬 Research Team Assembled! 🔬")
        print(f"  Data Scientists: {len([r for r in self.researchers.values() if r['role'] == 'data_scientist'])}")
        print(f"  Domain Experts: {len([r for r in self.researchers.values() if r['role'] == 'domain_expert'])}")
        print(f"  Analysts: {len([r for r in self.researchers.values() if r['role'] == 'analyst'])}")
        print(f"  Reviewers: {len([r for r in self.researchers.values() if r['role'] == 'reviewer'])}")

        return self.coordinator

    async def _add_researcher(self, name: str, role: str, specialties: List[str]) -> str:
        """Add a researcher to the team."""
        agent_id = f"{role}-{name}"

        async def task_handler(task):
            return await self._handle_research_task(agent_id, task)

        await self.coordinator.spawn_agent(
            agent_id=agent_id,
            role=role,
            task_handler=task_handler,
        )

        self.researchers[agent_id] = {
            "name": name,
            "role": role,
            "specialties": specialties,
            "studies_contributed": 0,
        }

        return agent_id

    async def _handle_research_task(self, agent_id: str, task: Task) -> dict:
        """Handle a research task."""
        researcher = self.researchers[agent_id]
        stage = ResearchStage(task.payload.get("stage", "analysis"))

        researcher["studies_contributed"] += 1

        # Simulate research work
        await asyncio.sleep(random.uniform(1.0, 3.0))

        if stage == ResearchStage.DATA_COLLECTION:
            return await self._collect_data(researcher, task.payload)
        elif stage == ResearchStage.ANALYSIS:
            return await self._analyze_data(researcher, task.payload)
        elif stage == ResearchStage.REVIEW:
            return await self._review_research(researcher, task.payload)
        elif stage == ResearchStage.VALIDATION:
            return await self._validate_research(researcher, task.payload)

        return {"stage": stage, "status": "unknown"}

    async def _collect_data(self, researcher: dict, payload: dict) -> dict:
        """Collect research data."""
        study_id = payload.get("study_id")
        data_points = random.randint(50, 200)
        confidence = random.uniform(0.7, 0.95)

        return {
            "study_id": study_id,
            "researcher": researcher["name"],
            "stage": "data_collection",
            "findings": f"Collected {data_points} data points with {confidence:.1%} confidence",
            "confidence": confidence,
            "data": {"data_points": data_points, "source": "experimental"},
        }

    async def _analyze_data(self, researcher: dict, payload: dict) -> dict:
        """Analyze research data."""
        study_id = payload.get("study_id")
        findings = self._generate_findings(researcher, payload)

        return {
            "study_id": study_id,
            "researcher": researcher["name"],
            "stage": "analysis",
            "findings": findings,
            "confidence": random.uniform(0.75, 0.98),
            "data": {"analysis_type": researcher["specialties"][0] if researcher["specialties"] else "general"},
        }

    async def _review_research(self, researcher: dict, payload: dict) -> dict:
        """Review research findings."""
        study_id = payload.get("study_id")
        approved = random.random() > 0.2  # 80% approval rate

        return {
            "study_id": study_id,
            "researcher": researcher["name"],
            "stage": "review",
            "findings": "Research approved for publication" if approved else "Request revisions",
            "confidence": random.uniform(0.8, 0.99) if approved else random.uniform(0.4, 0.7),
            "data": {"approved": approved},
        }

    async def _validate_research(self, researcher: dict, payload: dict) -> dict:
        """Validate research methodology."""
        study_id = payload.get("study_id")
        valid = random.random() > 0.15

        return {
            "study_id": study_id,
            "researcher": researcher["name"],
            "stage": "validation",
            "findings": "Methodology validated" if valid else "Methodology concerns identified",
            "confidence": random.uniform(0.85, 0.95) if valid else random.uniform(0.5, 0.75),
            "data": {"valid": valid},
        }

    def _generate_findings(self, researcher: dict, payload: dict) -> str:
        """Generate research findings based on role."""
        role = researcher["role"]

        findings_templates = {
            "data_scientist": [
                "Analysis reveals significant correlation (p < 0.05)",
                "Model predictions show 95% accuracy on test set",
                "Statistical analysis confirms the hypothesis",
            ],
            "domain_expert": [
                "Findings align with established theoretical framework",
                "Results consistent with literature review",
                "Novel patterns detected requiring further investigation",
            ],
            "analyst": [
                "Trend analysis supports the research hypothesis",
                "Data visualization reveals clear patterns",
                "Statistical significance confirmed across multiple metrics",
            ],
        }

        templates = findings_templates.get(role, findings_templates["data_scientist"])
        return random.choice(templates)

    def create_study(self, name: str, hypothesis: ResearchHypothesis) -> ResearchStudy:
        """Create a new research study."""
        self.study_counter += 1
        study_id = f"STUDY-{self.study_counter:04d}"

        study = ResearchStudy(
            id=study_id,
            name=name,
            hypothesis=hypothesis,
        )

        self.studies[study_id] = study
        self.metrics["total_studies"] += 1

        return study

    async def run_study(self, study: ResearchStudy) -> dict:
        """Run a complete research study."""
        print(f"\n{'='*50}")
        print(f"Starting Study: {study.name}")
        print(f"Hypothesis: {study.hypothesis.statement}")
        print(f"Field: {study.hypothesis.field}")
        print(f"{'='*50}\n")

        results = []

        # Stage 1: Data Collection
        print("📊 Stage 1: Data Collection")
        data_task = create_task(
            description=f"Collect data for {study.id}",
            capabilities=["data_analysis"],
            payload={"study_id": study.id, "stage": "data_collection"},
        )

        data_result = await self.coordinator.submit_task(data_task, wait_for_completion=True)
        if data_result and data_result.success:
            print(f"  {data_result.result.get('researcher')}: {data_result.result.get('findings')}")
            study.data.update(data_result.result.get("data", {}))
            results.append(data_result.result)

        await asyncio.sleep(0.5)

        # Stage 2: Analysis
        print("\n🔬 Stage 2: Analysis")
        analysis_tasks = [
            create_task(
                description=f"Analyze data - {study.id}",
                capabilities=["ml", "statistics"],
                payload={"study_id": study.id, "stage": "analysis"},
            ),
            create_task(
                description=f"Domain analysis - {study.id}",
                capabilities=["subject_matter", "theory"],
                payload={"study_id": study.id, "stage": "analysis"},
            ),
        ]

        analysis_results = await self.coordinator.submit_tasks(analysis_tasks, wait_for_all=True)

        for result in analysis_results:
            if result and result.success:
                print(f"  {result.result.get('researcher')}: {result.result.get('findings')}")
                study.findings.append(result.result.get("findings", ""))
                results.append(result.result)

        await asyncio.sleep(0.5)

        # Stage 3: Review
        print("\n👁️ Stage 3: Peer Review")
        review_task = create_task(
            description=f"Review study {study.id}",
            capabilities=["peer_review", "quality_control"],
            payload={"study_id": study.id, "stage": "review"},
        )

        review_result = await self.coordinator.submit_task(review_task, wait_for_completion=True)
        if review_result and review_result.success:
            print(f"  {review_result.result.get('researcher')}: {review_result.result.get('findings')}")
            results.append(review_result.result)

            # Check if approved
            if not review_result.result.get("data", {}).get("approved", True):
                print("  ⚠️ Study requires revisions - restarting analysis")
                return await self.run_study(study)

        await asyncio.sleep(0.5)

        # Stage 4: Validation
        print("\n✅ Stage 4: Validation")
        validation_task = create_task(
            description=f"Validate study {study.id}",
            capabilities=["validation", "ethics"],
            payload={"study_id": study.id, "stage": "validation"},
        )

        validation_result = await self.coordinator.submit_task(validation_task, wait_for_completion=True)
        if validation_result and validation_result.success:
            print(f"  {validation_result.result.get('researcher')}: {validation_result.result.get('findings')}")
            results.append(validation_result.result)

        # Complete study
        study.stage = ResearchStage.COMPLETE
        study.completed_at = datetime.now()
        self.metrics["completed_studies"] += 1
        self.metrics["total_findings"] += len(study.findings)

        print(f"\n{'='*50}")
        print(f"Study Complete: {study.name}")
        print(f"Duration: {study.duration_days:.1f} days")
        print(f"Total Findings: {len(study.findings)}")
        print(f"{'='*50}")

        return {
            "study_id": study.id,
            "results": results,
            "findings": study.findings,
            "duration": study.duration_days,
        }

    async def simulate_research_program(self, num_studies: int = 3) -> dict:
        """Simulate a research program with multiple studies."""
        print(f"\n{'#'*50}")
        print(f"Starting Research Program: {num_studies} Studies")
        print(f"{'#'*50}")

        study_configs = [
            {
                "name": "Gene X Protein Interaction",
                "hypothesis": ResearchHypothesis(
                    statement="Gene X directly influences protein Y expression",
                    field="biology",
                    methodology="experimental",
                ),
            },
            {
                "name": "ML Model Interpretability",
                "hypothesis": ResearchHypothesis(
                    statement="Attention mechanisms improve model interpretability",
                    field="machine_learning",
                    methodology="experimental",
                ),
            },
            {
                "name": "Climate Change Impact",
                "hypothesis": ResearchHypothesis(
                    statement="Urban heat islands increase regional temperature variance",
                    field="climatology",
                    methodology="observational",
                ),
            },
        ]

        for i in range(min(num_studies, len(study_configs))):
            config = study_configs[i]
            study = self.create_study(config["name"], config["hypothesis"])
            await self.run_study(study)
            await asyncio.sleep(1)

        print(f"\n{'#'*50}")
        print("Research Program Complete!")
        print(f"  Studies Completed: {self.metrics['completed_studies']}/{self.metrics['total_studies']}")
        print(f"  Total Findings: {self.metrics['total_findings']}")
        print(f"{'#'*50}")

        return self.metrics

    async def cleanup(self) -> None:
        """Clean up after the scenario."""
        if self.coordinator:
            await self.coordinator.shutdown()


async def main():
    """Run the research team scenario."""
    team = ResearchTeam()

    try:
        await team.setup()
        await team.simulate_research_program(num_studies=3)

    finally:
        await team.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
