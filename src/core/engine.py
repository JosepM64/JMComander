import logging

from PySide6.QtCore import QObject, QThreadPool

from src.core.jobs import CopyJob, DeleteJob, MoveJob, SecureDeleteJob

logger = logging.getLogger(__name__)


class OperationEngine(QObject):
    _instance = None

    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(2)
        self.active_jobs = []

    @classmethod
    def instance(cls, parent=None):
        if cls._instance is None:
            cls._instance = cls(parent)
        return cls._instance

    def queue_copy(self, src_list, dst_folder):
        job = CopyJob(src_list, dst_folder)
        self._prepare_job(job)
        return job

    def queue_move(self, src_list, dst_folder):
        job = MoveJob(src_list, dst_folder)
        self._prepare_job(job)
        return job

    def queue_delete(self, src_list, permanent=False):
        job = DeleteJob(src_list, permanent)
        self._prepare_job(job)
        return job

    def queue_secure_delete(self, src_list, secure_params):
        job = SecureDeleteJob(src_list, secure_params)
        self._prepare_job(job)
        return job

    def _prepare_job(self, job):
        self.active_jobs.append(job)
        if hasattr(job.signals, "conflict"):
            job.signals.conflict.connect(self._on_job_conflict)
        # cancelled també: molts jobs emeten només cancelled en sortir d'hora
        # (sense això queden com a zombis a active_jobs per sempre)
        job.signals.finished.connect(lambda: self._on_job_finished(job))
        job.signals.cancelled.connect(lambda: self._on_job_finished(job))

    def start_job(self, job):
        logger.info(
            f"[Engine] start_job called, active threads: {self.thread_pool.activeThreadCount()}"  # noqa: G004
        )
        self.thread_pool.start(job)

    def _on_job_conflict(self, job, src, dst, index, total):
        if self.parent and hasattr(self.parent, "_handle_copy_conflict"):
            self.parent._handle_copy_conflict(job, src, dst, index, total)  # noqa: SLF001

    def _on_job_finished(self, job):
        if job in self.active_jobs:
            self.active_jobs.remove(job)

    def cancel_all(self):
        for job in self.active_jobs:
            job.cancel()
        self.thread_pool.clear()
        self.thread_pool.waitForDone(2000)
