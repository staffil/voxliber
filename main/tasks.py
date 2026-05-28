from celery import shared_task
from notion_client import Client
import os


@shared_task
def sync_notion_task():
    from main.management.commands.sync_notion import get_notion_client, sync_books
    notion = get_notion_client()
    sync_books(notion)
