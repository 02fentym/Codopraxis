from django.contrib import admin
from .models import Language, Course, Unit, Topic


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name", "slug")


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("title",)
    search_fields = ("title",)


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ("course", "order", "title")
    list_filter = ("course",)
    ordering = ("course", "order")


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ("unit", "order", "title")
    list_filter = ("unit__course",)
    ordering = ("unit", "order")
