from datetime import timedelta

from django.apps.registry import Apps
from django.db import IntegrityError, connection, models, transaction
from django.db.models import Q
from django.test import TestCase
from django.utils import timezone

from core.models import SoftDeleteModel, TimestampedModel

# A registry of their own keeps these models out of the project: no app, no migration.
test_apps = Apps()


class Note(TimestampedModel, SoftDeleteModel):
    slug = models.CharField(max_length=50)

    class Meta:
        app_label = "core"
        apps = test_apps
        constraints = [
            models.UniqueConstraint(
                fields=["slug"],
                condition=Q(deleted_at__isnull=True),
                name="unique_alive_note_slug",
            )
        ]


class Comment(SoftDeleteModel):
    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name="comments")

    class Meta:
        app_label = "core"
        apps = test_apps


class ModelTableTestCase(TestCase):
    # TestCase wraps the class in a transaction, and PostgreSQL rolls the DDL back with it.
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with connection.schema_editor() as editor:
            editor.create_model(Note)
            editor.create_model(Comment)


class TimestampedModelTests(ModelTableTestCase):
    def test_create_sets_both_timestamps(self):
        before = timezone.now()
        note = Note.objects.create(slug="first")
        self.assertGreaterEqual(note.created_at, before)
        self.assertGreaterEqual(note.updated_at, note.created_at)

    def test_save_moves_updated_at_and_keeps_created_at(self):
        note = Note.objects.create(slug="first")
        created_at = note.created_at
        Note.all_objects.filter(pk=note.pk).update(
            updated_at=note.updated_at - timedelta(hours=1)
        )
        note.refresh_from_db()
        note.slug = "renamed"
        note.save()
        note.refresh_from_db()
        self.assertEqual(note.created_at, created_at)
        self.assertGreater(note.updated_at, created_at)


class SoftDeleteInstanceTests(ModelTableTestCase):
    def test_delete_keeps_the_row_and_hides_it(self):
        note = Note.objects.create(slug="first")
        deleted = note.delete()
        self.assertEqual(deleted, (1, {"core.Note": 1}))
        self.assertTrue(note.is_deleted)
        self.assertFalse(Note.objects.filter(pk=note.pk).exists())
        self.assertTrue(Note.all_objects.filter(pk=note.pk).exists())

    def test_restore_brings_the_row_back(self):
        note = Note.objects.create(slug="first")
        note.delete()
        note.restore()
        self.assertFalse(note.is_deleted)
        self.assertTrue(Note.objects.filter(pk=note.pk).exists())

    def test_hard_delete_removes_the_row(self):
        note = Note.objects.create(slug="first")
        note.hard_delete()
        self.assertFalse(Note.all_objects.filter(pk=note.pk).exists())


class SoftDeleteQuerySetTests(ModelTableTestCase):
    def setUp(self):
        Note.objects.bulk_create([Note(slug="a"), Note(slug="b"), Note(slug="c")])

    def test_delete_marks_every_row(self):
        deleted = Note.objects.filter(slug__in=["a", "b"]).delete()
        self.assertEqual(deleted, (2, {"core.Note": 2}))
        self.assertEqual(list(Note.objects.values_list("slug", flat=True)), ["c"])
        self.assertEqual(Note.all_objects.count(), 3)

    def test_alive_and_deleted_split_the_rows(self):
        Note.objects.filter(slug="a").delete()
        self.assertEqual(Note.all_objects.alive().count(), 2)
        self.assertEqual(
            list(Note.all_objects.deleted().values_list("slug", flat=True)), ["a"]
        )

    def test_restore_brings_every_row_back(self):
        Note.objects.all().delete()
        restored = Note.all_objects.deleted().restore()
        self.assertEqual(restored, 3)
        self.assertEqual(Note.objects.count(), 3)

    def test_hard_delete_removes_the_rows(self):
        Note.all_objects.filter(slug="a").hard_delete()
        self.assertEqual(Note.all_objects.count(), 2)


class ConditionalUniqueConstraintTests(ModelTableTestCase):
    def test_a_deleted_row_frees_its_value(self):
        Note.objects.create(slug="taken").delete()
        Note.objects.create(slug="taken")
        self.assertEqual(Note.all_objects.filter(slug="taken").count(), 2)

    def test_two_alive_rows_still_clash(self):
        Note.objects.create(slug="taken")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Note.objects.create(slug="taken")


class SoftDeleteRelationTests(ModelTableTestCase):
    def setUp(self):
        self.note = Note.objects.create(slug="first")
        self.comment = Comment.objects.create(note=self.note)
        self.note.delete()

    def test_the_delete_does_not_cascade(self):
        self.assertTrue(Comment.objects.filter(pk=self.comment.pk).exists())

    def test_the_forward_side_still_reaches_the_deleted_row(self):
        comment = Comment.objects.get(pk=self.comment.pk)
        self.assertEqual(comment.note, self.note)

    def test_the_reverse_side_hides_the_deleted_rows(self):
        note = Note.all_objects.get(pk=self.note.pk)
        Comment.objects.create(note=note).delete()
        self.assertEqual(list(note.comments.all()), [self.comment])
