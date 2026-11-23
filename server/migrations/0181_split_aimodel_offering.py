# Generated manually for the AiModel (raw) / AiModelOffering (join) split.
from django.db import migrations, models
import django.db.models.deletion


def forwards(apps, schema_editor):
    AiModelOffering = apps.get_model("server", "AiModelOffering")
    AiModel = apps.get_model("server", "AiModel")

    import re

    def slugify(value):
        base = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-") or "model"
        return base

    seen = {}
    for off in AiModelOffering.objects.all():
        key = (off.canonical_id or off.name or "").strip() or off.name
        if key not in seen:
            slug = slugify(off.canonical_id or off.name)
            # de-dupe slug
            n = 2
            base = slug
            while AiModel.objects.filter(slug=slug).exists():
                slug = f"{base}-{n}"
                n += 1
            raw = AiModel.objects.create(
                slug=slug,
                name=off.name,
                developer=off.developer,
                canonical_id=off.canonical_id,
                family=off.family,
                description=off.description,
                leaderboard_id=off.leaderboard_id,
                leaderboard_rank=off.leaderboard_rank,
                leaderboard_rank_is_estimate=off.leaderboard_rank_is_estimate,
                context_length=off.context_length,
                max_output_tokens=(off.max_response_tokens or off.context_length or 1000000),
                open_weights=off.open_weights,
                supports_reasoning=off.supports_reasoning,
                requires_reasoning_echo=off.requires_reasoning_echo,
                supports_tool_call=off.supports_tool_call,
                vision=off.vision,
                audio=off.audio,
                video=off.video,
                filesize=off.filesize,
                total_parameters=off.total_parameters,
                active_parameters=off.active_parameters,
                quantization=off.quantization,
            )
            seen[key] = raw
        off.model = seen[key]
        off.save(update_fields=["model"])


class Migration(migrations.Migration):

    dependencies = [
        ("server", "0180_alter_settingsmodel_precision"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="AiModel",
            new_name="AiModelOffering",
        ),
        migrations.CreateModel(
            name="AiModel",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("slug", models.CharField(blank=True, max_length=256, null=True, unique=True)),
                ("name", models.CharField(max_length=512)),
                ("developer", models.CharField(blank=True, default="", max_length=512)),
                ("canonical_id", models.CharField(blank=True, db_index=True, default="", max_length=512)),
                ("family", models.CharField(blank=True, default="", max_length=512)),
                ("description", models.TextField(blank=True, default="", max_length=65000)),
                ("leaderboard_id", models.CharField(blank=True, default="", max_length=512)),
                ("leaderboard_rank", models.IntegerField(blank=True, null=True)),
                ("leaderboard_rank_is_estimate", models.BooleanField(default=False)),
                ("context_length", models.IntegerField(default=1000000)),
                ("max_output_tokens", models.IntegerField(default=1000000)),
                ("open_weights", models.BooleanField(default=False)),
                ("supports_reasoning", models.BooleanField(default=False)),
                ("requires_reasoning_echo", models.BooleanField(default=False)),
                ("supports_tool_call", models.BooleanField(default=False)),
                ("structured_output", models.BooleanField(default=False)),
                ("temperature", models.BooleanField(default=False)),
                ("vision", models.BooleanField(default=False)),
                ("audio", models.BooleanField(default=False)),
                ("video", models.BooleanField(default=False)),
                ("knowledge_cutoff", models.CharField(blank=True, default="", max_length=64)),
                ("filesize", models.IntegerField(default=-1)),
                ("total_parameters", models.FloatField(default=0)),
                ("active_parameters", models.FloatField(default=0)),
                ("quantization", models.CharField(blank=True, default="", max_length=64)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.AddField(
            model_name="aimodeloffering",
            name="model",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="offerings",
                to="server.aimodel",
            ),
        ),
        migrations.AddField(
            model_name="aimodeloffering",
            name="is_free",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="aimodeloffering",
            name="free_verified",
            field=models.CharField(default="", max_length=32, blank=True),
        ),
        migrations.AddField(
            model_name="aimodeloffering",
            name="context_window_override",
            field=models.IntegerField(blank=True, null=True, default=None),
        ),
        migrations.AddField(
            model_name="aimodeloffering",
            name="max_output_tokens_override",
            field=models.IntegerField(blank=True, null=True, default=None),
        ),
        migrations.RunPython(forwards, migrations.RunPython.noop),
        # Remove now-raw model facts from the offering table.
        # (api_provider stays on offering)
        migrations.RemoveField(model_name="aimodeloffering", name="name"),
        migrations.RemoveField(model_name="aimodeloffering", name="family"),
        migrations.RemoveField(model_name="aimodeloffering", name="description"),
        migrations.RemoveField(model_name="aimodeloffering", name="developer"),
        migrations.RemoveField(model_name="aimodeloffering", name="canonical_id"),
        migrations.RemoveField(model_name="aimodeloffering", name="leaderboard_id"),
        migrations.RemoveField(model_name="aimodeloffering", name="leaderboard_rank"),
        migrations.RemoveField(model_name="aimodeloffering", name="leaderboard_rank_is_estimate"),
        migrations.RemoveField(model_name="aimodeloffering", name="open_weights"),
        migrations.RemoveField(model_name="aimodeloffering", name="supports_reasoning"),
        migrations.RemoveField(model_name="aimodeloffering", name="requires_reasoning_echo"),
        migrations.RemoveField(model_name="aimodeloffering", name="supports_tool_call"),
        migrations.RemoveField(model_name="aimodeloffering", name="vision"),
        migrations.RemoveField(model_name="aimodeloffering", name="audio"),
        migrations.RemoveField(model_name="aimodeloffering", name="video"),
        migrations.RemoveField(model_name="aimodeloffering", name="filesize"),
        migrations.RemoveField(model_name="aimodeloffering", name="total_parameters"),
        migrations.RemoveField(model_name="aimodeloffering", name="active_parameters"),
        migrations.RemoveField(model_name="aimodeloffering", name="quantization"),
        migrations.RemoveField(model_name="aimodeloffering", name="context_length"),
        migrations.RemoveField(model_name="aimodeloffering", name="max_prompt_tokens"),
        migrations.RemoveField(model_name="aimodeloffering", name="max_response_tokens"),
        migrations.AddField(
            model_name="apiprovider",
            name="free_setup_instructions",
            field=models.TextField(blank=True, default="", max_length=65000),
        ),
        migrations.AddField(
            model_name="apiprovider",
            name="free_verified",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
        # Unique constraint intentionally omitted: production data contains
        # duplicate (api_provider, provider_model_id) rows.  Identity is handled
        # in the loader instead.
    ]
