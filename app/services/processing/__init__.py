"""
Processing Services Package

Contains post-processing and task management services.
"""

__all__ = [
    "PostProcessingTasks",
    "PostProcessingTaskHandlers",
    "RecordingTaskFactory",
    "TaskDependencyManager",
]


def __getattr__(name):
    """Lazy import of processing services to avoid side effects at import time"""
    if name == "PostProcessingTasks":
        from .post_processing_tasks import PostProcessingTasks

        return PostProcessingTasks
    elif name == "PostProcessingTaskHandlers":
        from .post_processing_task_handlers import PostProcessingTaskHandlers

        return PostProcessingTaskHandlers
    elif name == "RecordingTaskFactory":
        from .recording_task_factory import RecordingTaskFactory

        return RecordingTaskFactory
    elif name == "TaskDependencyManager":
        from .task_dependency_manager import TaskDependencyManager

        return TaskDependencyManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
