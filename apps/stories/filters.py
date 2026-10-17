"""Faceted filter for Stories and News. Every filter lives in the URL so views are linkable.

Parameter names: type, program, location, emergency, topic (slugs, repeatable).
"""
import django_filters
from django import forms

from apps.countries.models import CountryPage
from apps.emergencies.models import EmergencyPage
from apps.programs.models import ProgramPage
from apps.taxonomy.models import Topic

from .models import STORY_TYPES, StoryPage


class StoryFilter(django_filters.FilterSet):
    type = django_filters.MultipleChoiceFilter(
        field_name="story_type", choices=STORY_TYPES, label="Content Type", widget=forms.CheckboxSelectMultiple
    )
    program = django_filters.ModelMultipleChoiceFilter(
        field_name="programs__slug",
        to_field_name="slug",
        queryset=ProgramPage.objects.live().order_by("title"),
        label="Program",
        widget=forms.CheckboxSelectMultiple,
    )
    location = django_filters.ModelMultipleChoiceFilter(
        field_name="countries__slug",
        to_field_name="slug",
        queryset=CountryPage.objects.live().filter(has_detail_page=True).order_by("title"),
        label="Location",
        widget=forms.CheckboxSelectMultiple,
    )
    emergency = django_filters.ModelMultipleChoiceFilter(
        field_name="emergencies__slug",
        to_field_name="slug",
        queryset=EmergencyPage.objects.live().order_by("title"),
        label="Emergency",
        widget=forms.CheckboxSelectMultiple,
    )
    topic = django_filters.ModelMultipleChoiceFilter(
        field_name="topics__slug",
        to_field_name="slug",
        queryset=Topic.objects.all(),
        label="General",
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = StoryPage
        fields = []
