from django.contrib import admin

# Register your models here.
from character.models import LLM, LLMPrompt, Prompt, LLMSubImage, Conversation, ConversationState, CharacterMemory, LoreEntry ,HPImageMapping, Story, ConversationMessage, Comment, LLMLike, StoryComment, StoryLike, StoryBookmark, LastWard, UserLastWard, ArchivedConversation
from django.utils.html import format_html

# -----------------------------
# Story
# -----------------------------
@admin.register(Story)
class StoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'user', 'is_public', 'created_at')
    list_filter = ('is_public', 'adult_choice', 'created_at')
    search_fields = ('title', 'description', 'user__email')
    filter_horizontal = ('genres', 'tags')


# -----------------------------
# LLM
# -----------------------------
class LLMSubImageInline(admin.TabularInline):
    model = LLMSubImage
    extra = 0


class HPImageMappingInline(admin.TabularInline):
    model = HPImageMapping
    extra = 0


@admin.register(LLM)
class LLMAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'user', 'model', 'is_public', 'created_at')
    list_filter = ('model', 'is_public', 'language')
    search_fields = ('name', 'user__email')
    inlines = [LLMSubImageInline, HPImageMappingInline]


# -----------------------------
# LastWard
# -----------------------------
@admin.register(LastWard)
class LastWardAdmin(admin.ModelAdmin):
    list_display = ('id', 'llm', 'order', 'is_public', 'created_at')
    list_filter = ('is_public', 'llm')
    search_fields = ('ward', 'description')


@admin.register(UserLastWard)
class UserLastWardAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'last_ward', 'is_public', 'viewed')
    list_filter = ('is_public', 'viewed')
    search_fields = ('user__email',)


# -----------------------------
# Conversation
# -----------------------------
class ConversationMessageInline(admin.TabularInline):
    model = ConversationMessage
    extra = 0
    readonly_fields = ('created_at',)


class ConversationStateInline(admin.StackedInline):
    model = ConversationState
    extra = 0


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'llm', 'created_at', 'is_public', 'is_deleted_by_user')
    list_filter = ('is_public', 'is_deleted_by_user', 'created_at')
    search_fields = ('user__email', 'llm__name')
    inlines = [ConversationMessageInline, ConversationStateInline]


@admin.register(ConversationMessage)
class ConversationMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'role', 'created_at', 'hp_after_message', 'is_deleted')
    list_filter = ('role', 'is_deleted')
    search_fields = ('content',)


@admin.register(ConversationState)
class ConversationStateAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'updated_at')


# -----------------------------
# ArchivedConversation
# -----------------------------
@admin.register(ArchivedConversation)
class ArchivedConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'original_conversation_id', 'user', 'llm', 'archived_at')
    list_filter = ('archived_at',)
    search_fields = ('user__email',)


# -----------------------------
# CharacterMemory
# -----------------------------
@admin.register(CharacterMemory)
class CharacterMemoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'llm', 'type', 'relevance_score', 'created_at')
    list_filter = ('type',)
    search_fields = ('summary',)


# -----------------------------
# LoreEntry
# -----------------------------
@admin.register(LoreEntry)
class LoreEntryAdmin(admin.ModelAdmin):
    list_display = ('id', 'llm', 'category', 'priority', 'always_active')
    list_filter = ('category', 'always_active')


# -----------------------------
# Likes / Bookmark / Comments
# -----------------------------
@admin.register(LLMLike)
class LLMLikeAdmin(admin.ModelAdmin):
    list_display = ('user', 'llm', 'created_at')


@admin.register(StoryLike)
class StoryLikeAdmin(admin.ModelAdmin):
    list_display = ('user', 'story', 'created_at')


@admin.register(StoryBookmark)
class StoryBookmarkAdmin(admin.ModelAdmin):
    list_display = ('user', 'story', 'created_at')


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'llm', 'created_at')
    search_fields = ('content',)


@admin.register(StoryComment)
class StoryCommentAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'story', 'created_at')
    search_fields = ('content',)


# -----------------------------
# Prompt
# -----------------------------
@admin.register(Prompt)
class PromptAdmin(admin.ModelAdmin):
    list_display = ('id', 'prompt_title', 'user', 'prompt_type', 'created_at')
    list_filter = ('prompt_type',)
    search_fields = ('prompt_title',)


@admin.register(LLMPrompt)
class LLMPromptAdmin(admin.ModelAdmin):
    list_display = ('llm', 'prompt', 'order')


# -----------------------------
# HP Mapping
# -----------------------------
@admin.register(HPImageMapping)
class HPImageMappingAdmin(admin.ModelAdmin):
    list_display = ('llm', 'min_hp', 'max_hp', 'priority', 'sub_image')
    list_filter = ('llm',)