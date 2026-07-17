import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from app.projects.models import Project
from app.research_objects.models import ResearchObject, Tag


class Command(BaseCommand):
    help = "Create an idempotent ordinary demo user and private sample content."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="demo")
        parser.add_argument("--email", default="demo@example.com")
        parser.add_argument("--password", default=os.environ.get("DEMO_USER_PASSWORD"))

    @transaction.atomic
    def handle(self, *args, **options):
        username = options["username"].strip()
        password = options["password"]
        if not username:
            raise CommandError("Demo username cannot be empty.")
        if not password:
            raise CommandError("Provide --password or set DEMO_USER_PASSWORD.")

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": options["email"].strip()},
        )
        if user.is_staff or user.is_superuser:
            raise CommandError("Refusing to use a staff or administrator account for demo data.")
        user.email = options["email"].strip()
        user.is_active = True
        user.set_password(password)
        user.save(update_fields=("email", "is_active", "password"))

        profile = user.profile
        if not profile.display_name:
            profile.display_name = "演示研究员"
            profile.affiliation = "Research Workspace Demo Lab"
            profile.research_interests = "可复现计算、科研知识管理"
            profile.save()

        project, _ = Project.objects.get_or_create(
            owner=user,
            name="可复现研究演示",
            defaults={"description": "用于熟悉私人记录、关联和发布流程的本地演示项目。"},
        )
        tag, _ = Tag.objects.get_or_create(
            owner=user,
            normalized_name="demo",
            defaults={"name": "demo"},
        )
        samples = (
            (
                ResearchObject.ObjectType.NOTE,
                "欢迎使用私人科研工作台",
                "## 开始\n\n这是一条仅演示用户可见的私人记录。",
            ),
            (
                ResearchObject.ObjectType.IDEA,
                "一个待验证的研究想法",
                "## 想法描述\n\n建立轻量、可复现的验证流程。\n\n## 下一步验证\n\n设计最小实验。",
            ),
            (
                ResearchObject.ObjectType.EXPERIMENT,
                "最小可复现实验",
                "## 实验目的\n\n验证基线配置。\n\n## 结论\n\n等待运行。",
            ),
        )
        for object_type, title, content in samples:
            obj, _ = ResearchObject.objects.get_or_create(
                owner=user,
                title=title,
                defaults={
                    "object_type": object_type,
                    "content_markdown": content,
                    "project": project,
                },
            )
            obj.tags.add(tag)

        action = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{action} private demo workspace for '{username}'."))
