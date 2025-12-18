from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from main.models import SnapBtn, Advertisment,Notice, FAQ, Contact, Terms, Policy

from book.models import Books, Genres, Content, Poem_list

User = get_user_model()


# 사용자
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("번호", "아이디", "이메일", "닉네임", )
    list_filter = ("username", "nickname", "created_at")

    # 커스텀 Users 모델에 맞게 fieldsets 재정의
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('개인정보', {'fields': ('username', 'nickname', 'gender', 'age', 'birthdate', 'user_img', 'cover_img')}),
        ('OAuth', {'fields': ('oauth_provider', 'oauth_uid')}),
        ('권한', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('상태', {'fields': ('status', 'is_profile_completed', 'follow_count')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'nickname'),
        }),
    )

    ordering = ('email',)
    search_fields = ('email', 'nickname', 'username')

    @admin.display(description='번호')
    def 번호(self, obj):
        return obj.username
    
    @admin.display(description='아이디')
    def 아이디(self, obj):
        return obj.username
    
    @admin.display(description="이메일")
    def 이메일(self, obj):
        return obj.email
    
    @admin.display(description="닉네임")
    def 닉네임(self, obj):
        return obj.nickname
    
# 뉴스 관리자
@admin.register(SnapBtn)
class SnapBtnAdmin(admin.ModelAdmin):
    list_display = ("제목", "설명", "이미지", "링크")
    search_fields = ("title", "news_link")

    @admin.display(description="제목")
    def 제목(self, obj):
        return obj.title
    
    @admin.display(description="설명")
    def 설명(self, obj):
        return obj.news_description
    
    @admin.display(description="이미지")
    def 이미지(self, obj):
        return obj.news_img
    
    @admin.display(description="링크")
    def 링크(self, obj):
        return obj.news_link
    



    
# 광고 관리자
@admin.register(Advertisment)
class AdvertismentAdmin(admin.ModelAdmin):
    list_display = ("제목", "이미지", "링크")
    search_fields = ("title", "link")

    @admin.display(description="제목")
    def 제목(self, obj):
        return obj.title

    
    @admin.display(description="이미지")
    def 이미지(self, obj):
        return obj.advertisment_img
    
    @admin.display(description="링크")
    def 링크(self, obj):
        return obj.link
    


# 시 관리자
@admin.register(Poem_list)
class Poem_listAdmin(admin.ModelAdmin):
    list_display = ("제목",  )
    search_fields = ("title", )

    @admin.display(description="제목")
    def 제목(self, obj):
        return obj.title


    

# 1️⃣ 공지사항
@admin.register(Notice)
class NoticeAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('title', 'content')
    ordering = ('-created_at',)
    list_editable = ('is_active',)
    date_hierarchy = 'created_at'


# 2️⃣ FAQ
@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ('id', 'question', 'category', 'is_active', 'created_at')
    list_filter = ('category', 'is_active')
    search_fields = ('question', 'answer')
    ordering = ('category', 'id')
    list_editable = ('category', 'is_active')


# 3️⃣ 문의(Contact)
@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('id', 'subject', 'email', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('subject', 'email', 'message')
    ordering = ('-created_at',)
    list_editable = ('status',)
    readonly_fields = ('user', 'email', 'subject', 'message', 'created_at', 'updated_at')

    fieldsets = (
        ('문의 정보', {
            'fields': ('user', 'email', 'subject', 'message')
        }),
        ('답변', {
            'fields': ('answer', 'status')
        }),
        ('메타 정보', {
            'fields': ('created_at', 'updated_at')
        }),
    )


# 4️⃣ 이용약관
@admin.register(Terms)
class TermsAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'created_at')
    search_fields = ('title', 'content')
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'


# 5️⃣ 정책(Policy)
@admin.register(Policy)
class PolicyAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'policy_type', 'created_at')
    list_filter = ('policy_type',)
    search_fields = ('title', 'content')
    ordering = ('policy_type', 'id')
    

