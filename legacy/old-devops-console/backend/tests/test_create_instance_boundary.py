from __future__ import annotations

import asyncio
from pathlib import Path
import unittest

from fastapi import BackgroundTasks, HTTPException

from app.domains.deploy.router import DeployRequest, deploy
from app.domains.llm.commands.infra_action import InfraAction, InfraActionService
from app.domains.llm.llm_core import LLMService
from app.shared.gitlab_settings import STAGING_ENV_DEDICATED_VM, get_staging_environment_catalog


REPO_ROOT = Path(__file__).resolve().parents[2]


def read_repo_text(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text()


class CreateInstanceBoundaryTest(unittest.TestCase):
    def test_public_deploy_endpoint_is_gone(self):
        request = DeployRequest(
            server_id="node-a",
            template_id="node-a/9000",
            storage_id="local-lvm",
            network_ids=["vmbr0"],
            server_name="should-not-create",
        )

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(deploy(request, BackgroundTasks()))

        self.assertEqual(ctx.exception.status_code, 410)
        self.assertIn("Gjallar", ctx.exception.detail)

    def test_llm_create_vm_action_is_disabled(self):
        result = InfraActionService().execute_action(
            InfraAction(
                type="create_vm",
                params={
                    "server_name": "should-not-create",
                    "template_id": "node-a/9000",
                },
            )
        )

        self.assertTrue(result.raw_result["disabled"])
        self.assertEqual(result.raw_result["owner"], "Gjallar")
        self.assertIn("Heimdall", result.result_message)

    def test_staging_environment_catalog_does_not_offer_dedicated_vm(self):
        catalog = get_staging_environment_catalog()

        self.assertNotIn(STAGING_ENV_DEDICATED_VM, {item["key"] for item in catalog})

    def test_frontend_active_surface_has_no_create_instance_route_or_helper(self):
        app_source = read_repo_text("frontend/src/App.jsx")
        api_source = read_repo_text("frontend/src/services/api.js")
        overview_source = read_repo_text("frontend/src/components/OverviewDashboard.jsx")
        gitlab_source = read_repo_text("frontend/src/components/GitLabWorkspace.jsx")
        llm_chat_source = read_repo_text("frontend/src/components/LlmInfraChat.jsx")

        self.assertNotIn("CreateInstanceWizard", app_source)
        self.assertNotIn('path="/create"', app_source)
        self.assertNotIn("path='/create'", app_source)
        self.assertNotIn("navigate('/create')", app_source)
        self.assertNotIn('navigate("/create")', app_source)

        self.assertNotIn("deployInfrastructure", api_source)
        self.assertNotIn("post('/deploy", api_source)
        self.assertNotIn('post("/deploy', api_source)

        self.assertNotIn("Create Instance", overview_source)
        self.assertNotIn("navigate('/create')", overview_source)
        self.assertNotIn("deployInfrastructure", overview_source)

        self.assertNotIn("Create Instance", gitlab_source)
        self.assertNotIn("dedicated_vm", gitlab_source)
        self.assertNotIn("deployInfrastructure", gitlab_source)

        self.assertNotIn("create_vm", llm_chat_source)

    def test_llm_system_prompt_excludes_create_vm_from_allowed_action_types(self):
        prompt = LLMService()._build_system_prompt()
        action_type_line = next(
            line for line in prompt.splitlines() if '"type":' in line
        )

        self.assertNotIn("create_vm", action_type_line)
        self.assertIn("actions 배열에는 create_vm 액션을 넣지 않습니다", prompt)

    def test_llm_response_normalization_drops_create_vm_actions(self):
        raw_response = """{
          "assistant_message": "VM 생성은 Gjallar가 담당합니다.",
          "actions": [
            {"type": "create_vm", "description": "legacy create", "params": {"server_name": "bad"}},
            {"type": "list_vms", "description": "inventory", "params": {}}
          ]
        }"""

        result = LLMService()._parse_llm_text(raw_response)

        self.assertEqual([action.type for action in result.actions], ["list_vms"])
        self.assertIn("Gjallar", result.assistant_message)


if __name__ == "__main__":
    unittest.main()
