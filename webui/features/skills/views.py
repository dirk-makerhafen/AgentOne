"""Skills: overview, detail, rename and delete."""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from server.models.skills.skill import SkillModel
from webui.core.assistants import assistant_panel_context
from webui.core.layout import render_page


def _read_skill_manifest(skill: SkillModel) -> tuple[Path, dict, str]:
    from runtime.paths import model_manifest_dir

    directory = model_manifest_dir(skill, "skill", skill.name, skill.parent_project)
    md = directory / "skill.md"
    if not md.is_file():
        return directory, {}, ""
    try:
        import frontmatter as frontmatter_lib

        post = frontmatter_lib.load(md)
        return directory, dict(post.metadata or {}), post.content or ""
    except Exception:  # pylint: disable=broad-exception-caught
        return directory, {}, ""


def _reload_skill_scope(skill: SkillModel) -> None:
    try:
        from django.conf import settings

        if skill.parent_project is not None:
            from registry.loader.load_project_folder import load_scope_dir

            load_scope_dir(skill.parent_project.get_agentone_dir(), skill.parent_project)
        else:
            from registry.management.commands.reload_all import run_reload_all

            run_reload_all(str(settings.BASE_DIR))
    except Exception:  # pylint: disable=broad-exception-caught
        pass


def skills(request):
    show_archived = request.GET.get("archived") == "1"
    rows = list(
        SkillModel.objects.select_related(
            "parent_agent", "parent_project", "parent_skill", "latest_skill_version"
        ).filter(is_archived=show_archived).order_by("name")
    )
    return render_page(request, "skills", "skills/list.html", {"skills": rows, "show_archived": show_archived})


def skill_detail(request, skill_id: int):
    skill = get_object_or_404(
        SkillModel.objects.select_related(
            "parent_agent", "parent_project", "parent_skill", "latest_skill_version"
        ),
        pk=skill_id,
    )
    _directory, manifest, body = _read_skill_manifest(skill)
    context = {
        "skill": skill,
        "versions": list(skill.versions.order_by("-version_number", "-pk")[:40]),
        "child_skills": list(skill.related_skills.order_by("name")),
        "child_agents": list(skill.child_agents.select_related("latest_agent_version")),
        "manifest": manifest,
        "manifest_body": body,
        "error": request.GET.get("error", ""),
    }
    context.update(assistant_panel_context("skill", skill, request.GET.get("assistant_session")))
    return render_page(request, "skills", "skills/detail.html", context,
                       active_id=skill.pk)


@require_POST
def skill_edit(request, skill_id: int):
    skill = get_object_or_404(SkillModel, pk=skill_id)
    old_name = skill.name
    new_name = (request.POST.get("name") or "").strip() or old_name
    directory, manifest, body = _read_skill_manifest(skill)
    description = (request.POST.get("description") or "").strip()

    target_dir = directory
    try:
        if new_name != old_name and directory.name == old_name:
            target_dir = directory.parent / new_name
            if target_dir.exists():
                return redirect(f"/app/skills/{skill.pk}?error=exists")
            directory.rename(target_dir)
        if target_dir.is_dir() and (target_dir / "skill.md").is_file():
            manifest = dict(manifest or {})
            manifest["name"] = new_name
            if description:
                manifest["description"] = description
            lines = [
                "---",
                yaml.dump(manifest, default_flow_style=False, sort_keys=False).strip(),
                "---",
            ]
            if body:
                lines.extend(["", body])
            (target_dir / "skill.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        return redirect(f"/app/skills/{skill.pk}?error=write")

    skill.name = new_name
    skill.save(update_fields=["name"])
    _reload_skill_scope(skill)
    refreshed = SkillModel.objects.filter(name=new_name).first()
    if refreshed is not None:
        return redirect("webui:skill", skill_id=refreshed.pk)
    return redirect("webui:skills")


@require_POST
def skill_delete(request, skill_id: int):
    skill = get_object_or_404(SkillModel, pk=skill_id)
    directory, _manifest, _body = _read_skill_manifest(skill)
    delete_files = request.POST.get("delete_files") == "on"
    parent_project = skill.parent_project
    skill.delete()
    if delete_files and directory.is_dir():
        try:
            shutil.rmtree(directory)
        except OSError:
            pass
        try:
            from django.conf import settings

            if parent_project is not None:
                from registry.loader.load_project_folder import load_scope_dir

                load_scope_dir(parent_project.get_agentone_dir(), parent_project)
            else:
                from registry.management.commands.reload_all import run_reload_all

                run_reload_all(str(settings.BASE_DIR))
        except Exception:  # pylint: disable=broad-exception-caught
            pass
    return redirect("webui:skills")
