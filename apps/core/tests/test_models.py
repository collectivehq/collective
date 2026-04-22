from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel, CRUDModel, DeletableModel, ResolvableModel, UpdateableModel


class ExampleBase(BaseModel):
    class Meta:
        app_label = "core_tests"


class ExampleCrud(CRUDModel):
    class Meta:
        app_label = "core_tests"


class ExampleResolvable(BaseModel, ResolvableModel):
    class Meta:
        app_label = "core_tests"


def test_core_abstract_models_are_abstract() -> None:
    assert BaseModel._meta.abstract is True
    assert UpdateableModel._meta.abstract is True
    assert DeletableModel._meta.abstract is True
    assert ResolvableModel._meta.abstract is True
    assert CRUDModel._meta.abstract is True


def test_base_model_fields_are_available_on_subclasses() -> None:
    created_by = ExampleBase._meta.get_field("created_by")
    created_at = ExampleBase._meta.get_field("created_at")

    assert isinstance(created_by, models.ForeignKey)
    assert created_by.related_model._meta.label_lower == settings.AUTH_USER_MODEL.lower()
    assert isinstance(created_at, models.DateTimeField)


def test_crud_model_contributes_full_lifecycle_fields() -> None:
    assert isinstance(ExampleCrud._meta.get_field("created_at"), models.DateTimeField)
    assert isinstance(ExampleCrud._meta.get_field("updated_at"), models.DateTimeField)
    deleted_at = ExampleCrud._meta.get_field("deleted_at")

    assert isinstance(deleted_at, models.DateTimeField)
    assert deleted_at.null is True
    assert deleted_at.blank is True


def test_resolvable_model_fields_have_expected_options() -> None:
    resolution_type = ExampleResolvable._meta.get_field("resolution_type")
    resolved_by = ExampleResolvable._meta.get_field("resolved_by")

    assert isinstance(resolution_type, models.CharField)
    assert resolution_type.default == ""
    assert resolution_type.blank is True
    assert isinstance(resolved_by, models.ForeignKey)
    assert resolved_by.null is True
    assert resolved_by.blank is True
    assert resolved_by.related_model._meta.label_lower == settings.AUTH_USER_MODEL.lower()
