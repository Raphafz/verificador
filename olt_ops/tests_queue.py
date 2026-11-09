"""Testes — fila de jobs OLT."""
from unittest.mock import patch

from django.test import TestCase

from core.models import Company
from olt_ops.models import OltEquipment, OnuCleanupJob
from olt_ops.queue import enqueue_job, process_olt_queue
from olt_ops.vpn_slot import OltSlotBusyError


class OltQueueTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name="ISP Fila",
            slug="isp-fila",
            cnpj="11.222.333/0001-81",
            email="fila@isp.local",
            module_olt=True,
        )
        self.olt = OltEquipment.objects.create(
            company=self.company,
            name="OLT-Fila",
            host="10.0.0.1",
            username="admin",
            password="secret",
        )

    def test_enqueue_sets_status_and_operation(self):
        job = OnuCleanupJob.objects.create(
            company=self.company,
            olt=self.olt,
            gpon_port="0/1/1",
            status="draft",
        )
        enqueue_job(job.pk, "list")
        job.refresh_from_db()
        self.assertEqual(job.status, "queued")
        self.assertEqual(job.pending_operation, "list")
        self.assertIn("Na fila", job.log_output)

    @patch("olt_ops.dispatcher.dispatch_job")
    def test_process_queue_dispatches_oldest(self, mock_dispatch):
        job1 = OnuCleanupJob.objects.create(
            company=self.company,
            olt=self.olt,
            gpon_port="0/1/1",
            status="queued",
            pending_operation="list",
        )
        job2 = OnuCleanupJob.objects.create(
            company=self.company,
            olt=self.olt,
            gpon_port="0/1/2",
            status="queued",
            pending_operation="delete",
        )
        process_olt_queue(self.company.pk)
        mock_dispatch.assert_called_once_with(job1.pk, "list")
        job1.refresh_from_db()
        self.assertEqual(job1.status, "draft")
        job2.refresh_from_db()
        self.assertEqual(job2.status, "queued")

    @patch("olt_ops.dispatcher.enqueue_job")
    @patch("olt_ops.dispatcher.acquire_container_slot", side_effect=OltSlotBusyError("busy"))
    @patch("olt_ops.dispatcher.docker_available", return_value=True)
    @patch("olt_ops.dispatcher.effective_execution_mode", return_value="container")
    def test_dispatch_container_enqueues_on_busy(self, _mode, _docker, _slot, mock_enqueue):
        from olt_ops.dispatcher import dispatch_job

        job = OnuCleanupJob.objects.create(
            company=self.company,
            olt=self.olt,
            gpon_port="0/1/1",
        )
        dispatch_job(job.pk, "list")
        mock_enqueue.assert_called_once_with(job.pk, "list")
