from uuid import UUID

from celery import shared_task


@shared_task
def delete_dataset(dataset_id: UUID):
    """删除特定知识库的异步任务"""
    from app.http.module import injector
    from internal.service.indexing_service import IndexingService

    indexing_service = injector.get(IndexingService)
    indexing_service.delete_dataset(dataset_id)
