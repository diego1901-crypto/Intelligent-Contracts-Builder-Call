# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
import json


class DeliverableEscrow(gl.Contract):
    """
    A reusable Intelligent Contract primitive for verifying that a submitted
    deliverable satisfies an agreed-upon specification, using GenLayer's
    Equivalence Principle to reach validator consensus on a non-deterministic
    (LLM-based) judgment.

    Use cases beyond this demo:
      - Freelance / gig-work escrow (client vs. contributor)
      - DAO grant milestone verification
      - Bounty platforms (submission vs. bounty spec)
      - Content moderation appeals with a bounded dispute window
    """

    client: str
    freelancer: str
    spec: str
    status: str  # "pending" | "approved" | "rejected" | "disputed"
    deliverable_url: str
    review_reasoning: str
    dispute_count: u256

    def __init__(self, client: str, freelancer: str, spec: str):
        """
        Args:
            client: Address (as string) of the party paying for the work.
            freelancer: Address (as string) of the party delivering the work.
            spec: Plain-language description of what counts as acceptable work.
        """
        self.client = client
        self.freelancer = freelancer
        self.spec = spec
        self.status = "pending"
        self.deliverable_url = ""
        self.review_reasoning = ""
        self.dispute_count = u256(0)

    @gl.public.write
    def submit_deliverable(self, deliverable_url: str) -> None:
        """
        Freelancer submits a deliverable (a URL or plain-text description).
        Validators independently run the same review prompt and must reach
        strict equivalence on the resulting JSON verdict before it is
        accepted into contract state. This is what gives the "approved" /
        "rejected" outcome real consensus weight, rather than trusting a
        single node's LLM call.
        """
        assert self.status in ("pending", "disputed"), "Contract is not accepting submissions in its current state"
        self.deliverable_url = deliverable_url

        spec = self.spec
        prompt = f"""
        You are an impartial reviewer for an escrow contract between a client and a freelancer.

        Agreed specification:
        {spec}

        Submitted deliverable (URL or description provided by the freelancer):
        {deliverable_url}

        Assess strictly whether the deliverable satisfies the specification above.
        Be conservative: if the deliverable is ambiguous, incomplete, or does not
        clearly match the spec, mark it as not meeting spec.

        Respond using ONLY the following JSON format:
        {{
            "reasoning": str,
            "meets_spec": bool
        }}
        It is mandatory that you respond only using the JSON format above, nothing else.
        Do not include any other words, characters, or markdown formatting.
        """

        def nondet():
            res = gl.nondet.exec_prompt(prompt)
            res = res.replace("```json", "").replace("```", "").strip()
            data = json.loads(res)
            # Normalize to a canonical JSON string so strict_eq can compare
            # validator outputs byte-for-byte.
            return json.dumps(
                {"reasoning": data["reasoning"], "meets_spec": bool(data["meets_spec"])},
                sort_keys=True,
            )

        raw_result = gl.eq_principle.strict_eq(nondet)
        result = json.loads(raw_result)

        self.review_reasoning = result["reasoning"]
        self.status = "approved" if result["meets_spec"] else "rejected"

    @gl.public.write
    def raise_dispute(self, reason: str) -> None:
        """
        Freelancer can contest a rejection once the contract has already
        rejected a submission. Bounded to 2 disputes total to prevent
        indefinite re-litigation of the same deliverable.
        """
        assert self.status == "rejected", "Disputes can only be raised after a rejection"
        assert self.dispute_count < u256(2), "Maximum number of disputes reached"

        self.dispute_count = self.dispute_count + u256(1)
        self.status = "disputed"
        self.review_reasoning = f"Dispute raised: {reason}"

    @gl.public.view
    def get_status(self) -> str:
        return self.status

    @gl.public.view
    def get_review_reasoning(self) -> str:
        return self.review_reasoning

    @gl.public.view
    def get_dispute_count(self) -> int:
        return int(self.dispute_count)

    @gl.public.view
    def get_spec(self) -> str:
        return self.spec
