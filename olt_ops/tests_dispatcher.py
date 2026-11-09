"""Testes — despacho OLT host vs container."""
from unittest.mock import patch

from django.test import TestCase, override_settings

from core.models import Company
from olt_ops.dispatcher import dispatch_job
from olt_ops.models import OltEquipment, OnuCleanupJob


class DispatcherHostTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name="ISP Dispatch",
            slug="isp-dispatch",
            cnpj="11.222.333/0001-81",
            email="dispatch@isp.local",
            module_olt=True,
        )
        self.olt = OltEquipment.objects.create(
            company=self.company,
            name="OLT-1",
            host="10.0.0.1",
            username="admin",
            password="secret",
        )

    @override_settings(OLT_EXECUTION_MODE="host")
    @patch("olt_ops.dispatcher._dispatch_host")
    def test_dispatch_host_mode(self, mock_host):
        job = OnuCleanupJob.objects.create(
            company=self.company,
            olt=self.olt,
            gpon_port="0/1/1",
        )
        dispatch_job(job.pk, "list")
        mock_host.assert_called_once_with(job.pk, "list")

    @patch("olt_ops.dispatcher.docker_available", return_value=True)
    @patch("olt_ops.dispatcher._dispatch_container")
    @patch("olt_ops.dispatcher.effective_execution_mode", return_value="container")
    def test_dispatch_container_mode(self, _mode, mock_container, _docker):
        job = OnuCleanupJob.objects.create(
            company=self.company,
            olt=self.olt,
            gpon_port="0/1/1",
        )
        dispatch_job(job.pk, "list")
        mock_container.assert_called_once()

    @patch("olt_ops.dispatcher._dispatch_host")
    @patch("olt_ops.dispatcher.append_job_line")
    @patch("olt_ops.dispatcher.docker_available", return_value=False)
    @patch("olt_ops.dispatcher.effective_execution_mode", return_value="container")
    def test_dispatch_falls_back_without_docker(self, _mode, _docker, mock_line, mock_host):
        job = OnuCleanupJob.objects.create(
            company=self.company,
            olt=self.olt,
            gpon_port="0/1/1",
        )
        dispatch_job(job.pk, "list")
        mock_line.assert_called()
        mock_host.assert_called_once()
