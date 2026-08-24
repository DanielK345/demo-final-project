import pytest

from eval_cases.run_agent_workflow_evals import CASE_DEFINITIONS, execute_case


@pytest.mark.asyncio
@pytest.mark.parametrize("definition", CASE_DEFINITIONS, ids=lambda item: item.case_id)
async def test_agent_workflow_case(definition):
    result = await execute_case(definition)

    assert result["status"] == "passed", result
