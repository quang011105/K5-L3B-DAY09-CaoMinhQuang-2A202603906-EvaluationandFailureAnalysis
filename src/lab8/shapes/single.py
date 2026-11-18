"""Shape B — one ReAct agent. Student work.

Use `lab8.runtime.run_react` with max_steps=8. `decide` may pick a read tool.
It must not call `issue_refund`. After the loop, the host validates the quote
and is the only writer.

A decide() that trusts ticket text over the order row will fail hidden claims
where the customer overstates the delay or cites a superseded clause.

Per-order cap: an order may already have been refunded by an earlier claim.
The read tool `lookup_refund_history` shows how much. The host still enforces
the cap, so pass the full quote to `durability.issue_refund`, not a net amount.

Caps: stop at 8 steps. Count model calls in the Budget so cost stays comparable.

Trace contract v1 (docs/contracts.md): return a trace_path to a JSON file written in this run,
{"run_id": <same run_id>, "events": [...]}, on every return path including early
ones. `lab8.trace.Trace` does this; your own tracer is fine if it matches.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from lab8.db import connect
from lab8.durability import InjectedCrash, issue_refund
from lab8.mock_llm import complete
from lab8.runtime import run_react
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish, safe_dump
from lab8.tools import get_claim_view, tool_cost
from lab8.trace import Trace


def run_claim(
    claim_id: str,
    *,
    seed: int,
    store_path: str,
    crash_at: str | None = None,
) -> RunResult:
    conn = connect(store_path)
    try:
        return _run(conn, claim_id, seed=seed, crash_at=crash_at)
    finally:
        conn.close()


def _run(
    conn: sqlite3.Connection,
    claim_id: str,
    *,
    seed: int,
    crash_at: str | None,
) -> RunResult:
    budget = Budget()
    run_id = make_run_id("single", claim_id, seed)
    trace = Trace(run_id)

    # 1. Đọc claim qua view an toàn (allowlist), không đọc trực tiếp SELECT *
    budget.add_tool(tool_cost())
    claim_view = get_claim_view(conn, claim_id)
    if not claim_view.get("found"):
        trace.add("error", {"reason": "unknown_claim"})
        return finish(
            conn,
            shape="single",
            claim_id=claim_id,
            seed=seed,
            status="failed",
            proposal_amount=0,
            budget=budget,
            trace=trace,
            error_reason="unknown_claim",
        )

    order_holder: dict[str, Any] = {}

    def decide(obs: dict[str, Any]) -> dict[str, Any]:
        claim = obs.get("claim") or {}
        if "last_tool" not in obs:
            if not claim.get("order_id"):
                complete(budget, seed=seed, purpose="draft", prompt="needs_info")
                return {"final": {"status": "needs_info", "error_reason": "missing_order_id"}}
            complete(budget, seed=seed, purpose="thought", prompt=f"lookup_order:{claim['order_id']}")
            return {
                "tool": "lookup_order",
                "args": {"order_id": claim["order_id"], "principal_id": claim["principal_id"]},
            }

        last_tool = obs.get("last_tool")
        last_result = obs.get("last_result") or {}

        if last_tool == "lookup_order":
            if not last_result.get("visible"):
                complete(budget, seed=seed, purpose="draft", prompt="escalated")
                return {"final": {"status": "escalated", "error_reason": last_result.get("reason")}}
            order_holder["order"] = last_result["order"]
            complete(budget, seed=seed, purpose="thought", prompt=f"lookup_refund_history:{claim['order_id']}")
            return {
                "tool": "lookup_refund_history",
                "args": {"order_id": claim["order_id"], "principal_id": claim["principal_id"]},
            }

        if last_tool == "lookup_refund_history":
            order = order_holder["order"]
            complete(budget, seed=seed, purpose="thought", prompt=f"compute_compensation:{order['order_id']}")
            return {
                "tool": "compute_compensation",
                "args": {"order": order},
            }

        if last_tool == "compute_compensation":
            return {"final": {"status": "ready", "quote": last_result}}

        return {"final": {"status": "failed", "error_reason": "unexpected_step"}}

    # Vòng lặp ReAct có chặn max_steps=8 và worker=True để ngăn model gọi tool ghi tiền
    react_outcome = run_react(
        conn,
        budget,
        observation={"claim": claim_view},
        decide=decide,
        max_steps=8,
        worker=True,
    )

    trace.add("react_summary", {"stopped": react_outcome.get("stopped")})

    if react_outcome.get("stopped") == "step_cap":
        trace.add("error", {"reason": "step_cap"})
        return finish(
            conn,
            shape="single",
            claim_id=claim_id,
            seed=seed,
            status="failed",
            proposal_amount=0,
            budget=budget,
            trace=trace,
            error_reason="step_cap",
        )

    final = react_outcome.get("final") or {}
    status = final.get("status")

    if status in ("needs_info", "escalated"):
        trace.add("decision", {"status": status, "reason": final.get("error_reason")})
        return finish(
            conn,
            shape="single",
            claim_id=claim_id,
            seed=seed,
            status=status,
            proposal_amount=0,
            budget=budget,
            trace=trace,
            error_reason=final.get("error_reason"),
        )

    if status != "ready":
        return finish(
            conn,
            shape="single",
            claim_id=claim_id,
            seed=seed,
            status="failed",
            proposal_amount=0,
            budget=budget,
            trace=trace,
            error_reason=final.get("error_reason", "unknown_react_status"),
        )

    quote_payload = final["quote"]
    proposal = int(quote_payload["amount_vnd"])
    trace.add("quote", safe_dump(quote_payload))
    complete(budget, seed=seed, purpose="draft", prompt=f"proposal={proposal}")

    if proposal <= 0:
        return finish(
            conn,
            shape="single",
            claim_id=claim_id,
            seed=seed,
            status="denied",
            proposal_amount=0,
            budget=budget,
            trace=trace,
            error_reason=quote_payload.get("reason"),
        )

    # Truyền quote đầy đủ vào durability.issue_refund; host kiểm approval, idempotency và trừ tiền đã nhận
    try:
        outcome = issue_refund(conn, claim_id, proposal, crash_at=crash_at)
    except InjectedCrash:
        trace.add("crash", {"at": crash_at})
        trace.write()
        raise

    if not outcome["ok"]:
        final_status = "failed" if outcome["conflict"] else "denied"
        return finish(
            conn,
            shape="single",
            claim_id=claim_id,
            seed=seed,
            status=final_status,
            proposal_amount=proposal,
            budget=budget,
            trace=trace,
            error_reason=outcome["reason"],
        )

    return finish(
        conn,
        shape="single",
        claim_id=claim_id,
        seed=seed,
        status="resolved",
        proposal_amount=proposal,
        budget=budget,
        trace=trace,
        error_reason=None,
    )
