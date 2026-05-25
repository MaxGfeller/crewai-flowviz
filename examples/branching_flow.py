"""Small CrewAI Flow used to exercise crewai-flowviz layouts."""

from __future__ import annotations

from crewai.flow.flow import Flow, and_, listen, or_, router, start


class BranchingSupportFlow(Flow[dict]):
    @start()
    def intake(self) -> None:
        self.state["kind"] = "billing"

    @listen(intake)
    def enrich_customer(self) -> None:
        self.state["customer"] = "Acme"

    @listen(intake)
    def fetch_history(self) -> None:
        self.state["history"] = []

    @listen(and_(enrich_customer, fetch_history))
    def classify(self) -> str:
        return self.state["kind"]

    @router(classify)
    def route_ticket(self) -> str:
        if self.state["kind"] == "billing":
            return "billing"
        if self.state["kind"] == "technical":
            return "technical"
        return "human"

    @listen("billing")
    def draft_billing_reply(self) -> None:
        self.state["drafted"] = True

    @listen("technical")
    def draft_technical_reply(self) -> None:
        self.state["drafted"] = True

    @listen(or_(draft_billing_reply, draft_technical_reply))
    def quality_gate(self) -> None:
        self.state["needs_retry"] = False

    @router(quality_gate)
    def route_quality(self) -> str:
        if self.state["needs_retry"]:
            return "technical"
        return "done"

    @listen("human")
    def escalate(self) -> None:
        self.state["escalated"] = True

    @listen("done")
    def finalize(self) -> dict:
        return dict(self.state)
