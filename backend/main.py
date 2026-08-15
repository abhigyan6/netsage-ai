from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.rule_checker import check_rules
from backend.ai_diagnoser import diagnose_case


app = FastAPI(
    title="NetSage AI",
    description="AI-powered Cisco network troubleshooting assistant",
    version="1.0"
)


# Allow React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "name": "NetSage AI",
        "status": "running"
    }


@app.post("/diagnose")
def diagnose(case: dict):

    show_output = case.get("show_ip_interface_brief", "")
    affected_network = case.get(
        "affected_network",
        "192.168.20."
    )

    # -----------------------------
    # STEP 1: Rule Checker
    # -----------------------------

    rule_result = check_rules(
        show_output,
        affected_network
    )

    case["rule_checker_result"] = rule_result

    # -----------------------------
    # STEP 2: AI Diagnosis
    # -----------------------------

    diagnosis = diagnose_case(case)

    if diagnosis is None:
        return {
            "success": False,
            "error": "AI diagnosis failed",
            "rule_checker_result": rule_result
        }

    # -----------------------------
    # RESPONSE
    # -----------------------------

    return {
        "success": True,
        "case_id": case.get("case_id"),
        "rule_checker_result": rule_result,
        "ai_diagnosis": diagnosis
    }