"""Testes — execução OLT (host vs container)."""
from django.test import TestCase, override_settings

from core.models import Company
from olt_ops.execution import effective_execution_mode, get_execution_mode
from olt_ops.models import CompanyOltExecutionConfig


class OltExecutionModeTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name="ISP Teste",
            slug="isp-teste",
            cnpj="12.345.678/0001-90",
            email="teste@isp.local",
            module_olt=True,
        )

    @override_settings(OLT_EXECUTION_MODE="container")
    def test_global_container_mode(self):
        self.assertEqual(get_execution_mode(self.company), "container")

    @override_settings(OLT_EXECUTION_MODE="host")
    def test_company_override_container(self):
        CompanyOltExecutionConfig.objects.create(
            company=self.company,
            worker_mode="container",
        )
        self.assertEqual(get_execution_mode(self.company), "container")

    @override_settings(OLT_EXECUTION_MODE="container")
    def test_effective_falls_back_without_docker(self):
        with override_settings(OLT_DOCKER_BINARY="docker-nao-existe-xyz"):
            self.assertEqual(effective_execution_mode(self.company), "host")
